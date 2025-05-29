
import os
import sys
import pandas as pd
import time
from datetime import datetime, timedelta
import krakenex
from typing import Dict, List, Optional, Tuple
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import asyncio
import aiohttp
import json
from dataclasses import dataclass
import sqlite3
from functools import lru_cache

# הוספת נתיב למודולים
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config

logger = Config.setup_logging('market_collector')

@dataclass
class MarketDataPoint:
    """נקודת נתונים בודדת"""
    timestamp: datetime
    symbol: str
    price: float
    volume: float
    high_24h: float
    low_24h: float
    change_24h: float
    change_pct_24h: float
    bid: float
    ask: float
    spread: float
    source: str
    quality_score: float = 1.0

class DataQualityManager:
    """מנהל איכות נתונים"""
    
    def __init__(self):
        self.quality_thresholds = {
            'price_change_limit': 0.5,  # 50% max change per update
            'spread_limit': 0.05,       # 5% max spread
            'volume_anomaly_factor': 10, # 10x volume spike threshold
            'data_age_limit': 3600      # 1 hour max age (was 5 minutes - too strict)
        }
        
        self.symbol_baselines = {}
    
    def validate_data_point(self, data_point: MarketDataPoint, 
                           previous_data: Optional[MarketDataPoint] = None) -> Tuple[bool, float, List[str]]:
        """בדיקת איכות נקודת נתונים - גרסה מעודכנת"""
        issues = []
        quality_score = 1.0
        
        # Basic validations
        if data_point.price <= 0:
            issues.append("Invalid price: <= 0")
            quality_score = 0
            return False, quality_score, issues
        
        if data_point.volume < 0:
            issues.append("Invalid volume: < 0")
            quality_score *= 0.9  # Less harsh penalty
        
        # Spread validation (more lenient)
        if data_point.spread > 0 and data_point.price > 0:
            spread_pct = data_point.spread / data_point.price
            if spread_pct > self.quality_thresholds['spread_limit']:
                issues.append(f"High spread: {spread_pct*100:.2f}%")
                quality_score *= 0.8  # Less harsh penalty
        
        # Price change validation (if we have previous data)
        if previous_data:
            # Skip validation if previous data is very old (more than 1 day)
            data_age_hours = (data_point.timestamp - previous_data.timestamp).total_seconds() / 3600
            
            if data_age_hours < 24:  # Only validate if data is less than 24 hours old
                price_change = abs(data_point.price - previous_data.price) / previous_data.price
                if price_change > self.quality_thresholds['price_change_limit']:
                    issues.append(f"Extreme price change: {price_change*100:.2f}%")
                    quality_score *= 0.6  # Less harsh penalty
                
                # Volume anomaly check (more lenient)
                if (data_point.volume > 0 and previous_data.volume > 0 and 
                    data_point.volume > previous_data.volume * self.quality_thresholds['volume_anomaly_factor']):
                    issues.append(f"Volume spike detected: {data_point.volume/previous_data.volume:.1f}x")
                    quality_score *= 0.95  # Very small penalty
        
        # Data freshness (more lenient)
        data_age = (datetime.now() - data_point.timestamp).total_seconds()
        if data_age > self.quality_thresholds['data_age_limit']:
            issues.append(f"Stale data: {data_age:.0f}s old")
            quality_score *= 0.8  # Less harsh penalty
        
        data_point.quality_score = quality_score
        is_valid = quality_score > 0.1  # Much more lenient threshold (was 0.3)
        
        return is_valid, quality_score, issues

class MarketCollector:
    """מאסף נתוני שוק פשוט - תואם לבקרה"""
    
    def __init__(self, use_kraken: bool = True, use_binance: bool = True):
        self.use_kraken = use_kraken
        self.use_binance = use_binance
        
        # Initialize APIs
        self.kraken_api = None
        if self.use_kraken:
            kraken_key = Config.get_api_key('KRAKEN_API_KEY') if hasattr(Config, 'get_api_key') else getattr(Config, 'KRAKEN_API_KEY', '')
            kraken_secret = Config.get_api_key('KRAKEN_API_SECRET') if hasattr(Config, 'get_api_key') else getattr(Config, 'KRAKEN_API_SECRET', '')
            
            if kraken_key and kraken_secret:
                try:
                    self.kraken_api = krakenex.API(kraken_key, kraken_secret)
                    logger.info("Kraken API initialized successfully")
                except Exception as e:
                    logger.error(f"Failed to initialize Kraken API: {e}")
            else:
                logger.warning("No Kraken API credentials available")
        
        # Data quality manager
        self.quality_manager = DataQualityManager()
        
        # Enhanced caching
        self.price_cache = {}
        self.cache_timestamps = {}
        self.cache_duration = 10  # seconds
        
        # Database connection for historical data
        self.db_path = os.path.join(Config.DATA_DIR, 'market_data.db')
        self._init_database()
        
        # Performance metrics
        self.collection_stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'data_quality_score': 0,
            'last_update': None
        }
        
        # Rate limiting
        self.last_api_call = {}
        self.min_interval_seconds = {
            'kraken': 1,    # 1 second between calls
            'binance': 0.5  # 0.5 seconds between calls
        }
        
        # Symbol mapping for Kraken
        self.symbol_mapping = {
            'XXBTZUSD': 'BTC', 'XBTUSD': 'BTC', 'BTCUSD': 'BTC',
            'XETHZUSD': 'ETH', 'ETHUSD': 'ETH',
            'SOLUSD': 'SOL', 'ADAUSD': 'ADA', 'DOTUSD': 'DOT',
            'MATICUSD': 'MATIC', 'LINKUSD': 'LINK', 'AVAXUSD': 'AVAX',
            'XRPUSD': 'XRP', 'ATOMUSD': 'ATOM'
        }
    
    def _init_database(self):
        """אתחול בסיס נתונים לאחסון היסטורי"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS market_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME,
                    symbol TEXT,
                    price REAL,
                    volume REAL,
                    high_24h REAL,
                    low_24h REAL,
                    change_24h REAL,
                    change_pct_24h REAL,
                    bid REAL,
                    ask REAL,
                    spread REAL,
                    source TEXT,
                    quality_score REAL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(timestamp, symbol, source)
                )
            ''')
            
            # Create indexes for better performance
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_symbol_timestamp ON market_data(symbol, timestamp)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON market_data(timestamp)')
            
            conn.commit()
            conn.close()
            
            logger.info("Database initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
    
    def _respect_rate_limit(self, source: str):
        """כיבוד מגבלות קצב קריאות API"""
        if source in self.last_api_call:
            time_since_last = time.time() - self.last_api_call[source]
            min_interval = self.min_interval_seconds.get(source, 1)
            
            if time_since_last < min_interval:
                sleep_time = min_interval - time_since_last
                time.sleep(sleep_time)
        
        self.last_api_call[source] = time.time()
    
    def get_combined_prices(self, symbols: List[str]) -> Dict[str, Dict]:
        """קבלת מחירים מכל המקורות - פונקציה נדרשת לmain.py"""
        try:
            if not self.kraken_api:
                logger.warning("No Kraken API available")
                return {}
            
            self._respect_rate_limit('kraken')
            
            # Get ticker data from Kraken
            ticker_resp = self.kraken_api.query_public('Ticker')
            
            if ticker_resp.get('error'):
                logger.error(f"Kraken API error: {ticker_resp['error']}")
                return {}
            
            results = {}
            ticker_data = ticker_resp.get('result', {})
            
            for pair, data in ticker_data.items():
                if 'USD' not in pair:
                    continue
                
                symbol = self._normalize_kraken_symbol(pair)
                
                if symbol not in symbols:
                    continue
                
                try:
                    current_price = self._safe_float(data.get('c', [0])[0])
                    if current_price <= 0:
                        continue
                    
                    open_price = self._safe_float(data.get('o', current_price))
                    
                    # Calculate change
                    if open_price > 0:
                        change_pct = ((current_price - open_price) / open_price) * 100
                    else:
                        change_pct = 0
                    
                    results[symbol] = {
                        'price': current_price,
                        'change_pct_24h': change_pct,
                        'volume': self._safe_float(data.get('v', [0, 0])[1]),
                        'high_24h': self._safe_float(data.get('h', [0, current_price])[1]),
                        'low_24h': self._safe_float(data.get('l', [0, current_price])[1]),
                        'bid': self._safe_float(data.get('b', [current_price])[0]),
                        'ask': self._safe_float(data.get('a', [current_price])[0])
                    }
                    
                except Exception as e:
                    logger.warning(f"Error parsing data for {pair}: {e}")
                    continue
            
            return results
            
        except Exception as e:
            logger.error(f"Error getting combined prices: {e}")
            return {}
    
    def get_all_available_symbols(self) -> List[str]:
        """קבלת כל הסמלים הזמינים - פונקציה נדרשת לmain.py"""
        try:
            if not self.kraken_api:
                return Config.DEFAULT_COINS if hasattr(Config, 'DEFAULT_COINS') else []
            
            # Get asset pairs from Kraken
            pairs_resp = self.kraken_api.query_public('AssetPairs')
            
            if pairs_resp.get('error'):
                logger.error(f"Kraken API error: {pairs_resp['error']}")
                return Config.DEFAULT_COINS if hasattr(Config, 'DEFAULT_COINS') else []
            
            symbols = []
            pairs_data = pairs_resp.get('result', {})
            
            for pair, info in pairs_data.items():
                if 'USD' in pair and info.get('status') == 'online':
                    symbol = self._normalize_kraken_symbol(pair)
                    if symbol not in symbols:
                        symbols.append(symbol)
            
            return sorted(symbols)
            
        except Exception as e:
            logger.error(f"Error getting available symbols: {e}")
            return Config.DEFAULT_COINS if hasattr(Config, 'DEFAULT_COINS') else []
    
    @lru_cache(maxsize=100)
    def _get_symbol_mapping(self, symbol: str) -> str:
        """מיפוי סמלים עם cache"""
        return self._normalize_kraken_symbol(symbol)
    
    def get_kraken_prices_enhanced(self, symbols: Optional[List[str]] = None) -> Dict[str, MarketDataPoint]:
        """שליפת מחירים משופרת מ-Kraken"""
        if not self.kraken_api:
            return {}
        
        self._respect_rate_limit('kraken')
        
        try:
            self.collection_stats['total_requests'] += 1
            
            # Use cached data if available and fresh
            cache_key = f"kraken_{'_'.join(symbols) if symbols else 'all'}"
            if (cache_key in self.price_cache and 
                cache_key in self.cache_timestamps and
                (time.time() - self.cache_timestamps[cache_key]) < self.cache_duration):
                return self.price_cache[cache_key]
            
            # Fetch from API
            ticker_resp = self.kraken_api.query_public('Ticker')
            
            if ticker_resp.get('error'):
                logger.error(f"Kraken API error: {ticker_resp['error']}")
                self.collection_stats['failed_requests'] += 1
                return {}
            
            results = {}
            ticker_data = ticker_resp.get('result', {})
            timestamp = datetime.utcnow()
            
            quality_scores = []
            
            for pair, data in ticker_data.items():
                if 'USD' not in pair:
                    continue
                
                symbol = self._get_symbol_mapping(pair)
                
                if symbols and symbol not in symbols:
                    continue
                
                try:
                    # Parse data more carefully with better validation
                    current_price = self._safe_float(data.get('c', [0])[0])
                    if current_price <= 0:
                        continue
                    
                    # Sanity check for price - typical crypto prices
                    if current_price > 1000000 or current_price < 0.0001:
                        logger.warning(f"Suspicious price for {symbol}: ${current_price}")
                        continue
                    
                    # Get open price with better handling
                    open_price = self._safe_float(data.get('o', current_price))
                    
                    # Calculate change with better validation
                    change_pct = 0
                    change_24h = 0
                    
                    if open_price > 0 and abs(open_price - current_price) / open_price < 0.5:  # Max 50% change
                        change_pct = ((current_price - open_price) / open_price) * 100
                        change_24h = current_price - open_price
                    else:
                        # If change is too extreme, don't calculate change
                        logger.debug(f"Skipping change calculation for {symbol} - extreme values")
                    
                    # Validate other price data
                    high_24h = self._safe_float(data.get('h', [0, current_price])[1])
                    low_24h = self._safe_float(data.get('l', [0, current_price])[1]) 
                    
                    # Sanity check high/low vs current price
                    if high_24h > 0 and high_24h < current_price * 0.5:
                        high_24h = current_price
                    if low_24h > 0 and low_24h > current_price * 2:
                        low_24h = current_price
                    
                    # Get bid/ask with validation
                    bid = self._safe_float(data.get('b', [current_price])[0])
                    ask = self._safe_float(data.get('a', [current_price])[0])
                    
                    # Validate bid/ask makes sense
                    if bid <= 0:
                        bid = current_price
                    if ask <= 0:
                        ask = current_price
                    if bid > ask:  # Bid should be lower than ask
                        bid, ask = ask, bid
                    
                    spread = max(0, ask - bid)
                    
                    # Create data point
                    data_point = MarketDataPoint(
                        timestamp=timestamp,
                        symbol=symbol,
                        price=current_price,
                        volume=self._safe_float(data.get('v', [0, 0])[1]),
                        high_24h=high_24h if high_24h > 0 else current_price,
                        low_24h=low_24h if low_24h > 0 else current_price,
                        change_24h=change_24h,
                        change_pct_24h=change_pct,
                        bid=bid,
                        ask=ask,
                        spread=spread,
                        source='kraken'
                    )
                    
                    # Skip quality validation for first data point to avoid stale data issues
                    previous_data = self._get_last_data_point(symbol, 'kraken')
                    if previous_data:
                        is_valid, quality_score, issues = self.quality_manager.validate_data_point(
                            data_point, previous_data
                        )
                        
                        if is_valid:
                            results[symbol] = data_point
                            quality_scores.append(quality_score)
                        else:
                            # For debug purposes, log but still use data if it's not too bad
                            if quality_score > 0.1:  # Very lenient threshold
                                logger.debug(f"Low quality data for {symbol}: {issues}")
                                results[symbol] = data_point
                                quality_scores.append(quality_score)
                            else:
                                logger.warning(f"Rejected data for {symbol}: {issues}")
                    else:
                        # First time collecting this symbol - accept it
                        results[symbol] = data_point
                        quality_scores.append(1.0)
                        
                except (KeyError, ValueError, IndexError, TypeError) as e:
                    logger.warning(f"Error parsing Kraken data for {pair}: {e}")
                    continue
            
            # Update statistics
            if quality_scores:
                avg_quality = sum(quality_scores) / len(quality_scores)
                self.collection_stats['data_quality_score'] = avg_quality
                self.collection_stats['successful_requests'] += 1
            
            # Cache results
            self.price_cache[cache_key] = results
            self.cache_timestamps[cache_key] = time.time()
            
            return results
            
        except Exception as e:
            logger.error(f"Kraken enhanced collection error: {e}")
            self.collection_stats['failed_requests'] += 1
            return {}
    
    def _safe_float(self, value, default: float = 0.0) -> float:
        """המרה בטוחה לfloat"""
        try:
            if isinstance(value, (list, tuple)) and len(value) > 0:
                return float(value[0])
            return float(value) if value is not None else default
        except (ValueError, TypeError):
            return default
    
    def _get_last_data_point(self, symbol: str, source: str) -> Optional[MarketDataPoint]:
        """קבלת נקודת נתונים אחרונה מהDB"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM market_data 
                WHERE symbol = ? AND source = ? 
                ORDER BY timestamp DESC 
                LIMIT 1
            ''', (symbol, source))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return MarketDataPoint(
                    timestamp=datetime.fromisoformat(row[1]),
                    symbol=row[2],
                    price=row[3],
                    volume=row[4],
                    high_24h=row[5],
                    low_24h=row[6],
                    change_24h=row[7],
                    change_pct_24h=row[8],
                    bid=row[9],
                    ask=row[10],
                    spread=row[11],
                    source=row[12],
                    quality_score=row[13]
                )
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting last data point: {e}")
            return None
    
    def collect_and_store_enhanced(self, symbols: Optional[List[str]] = None) -> pd.DataFrame:
        """איסוף ושמירה משופרים"""
        logger.info("Starting enhanced data collection")
        
        # Collect from all sources
        all_data_points = []
        
        # Kraken data
        if self.use_kraken:
            kraken_data = self.get_kraken_prices_enhanced(symbols)
            all_data_points.extend(kraken_data.values())
        
        # Binance data (if available)
        if self.use_binance:
            try:
                binance_data = self._get_binance_data_enhanced(symbols)
                all_data_points.extend(binance_data.values())
            except Exception as e:
                logger.warning(f"Binance collection failed: {e}")
        
        if not all_data_points:
            logger.warning("No data collected")
            return pd.DataFrame()
        
        # Convert to DataFrame
        df_data = []
        valid_points = 0
        
        for data_point in all_data_points:
            # Much more lenient validation - accept any data with minimal quality
            if data_point.quality_score > 0.1:  # Very low threshold
                df_data.append({
                    'timestamp': data_point.timestamp,
                    'pair': f"{data_point.symbol}USD",
                    'symbol': data_point.symbol,
                    'price': data_point.price,
                    'volume': data_point.volume,
                    'high_24h': data_point.high_24h,
                    'low_24h': data_point.low_24h,
                    'change_24h': data_point.change_24h,
                    'change_pct_24h': data_point.change_pct_24h,
                    'bid': data_point.bid,
                    'ask': data_point.ask,
                    'spread': data_point.spread,
                    'source': data_point.source,
                    'quality_score': data_point.quality_score
                })
                valid_points += 1
        
        if not df_data:
            logger.warning("No valid data points after filtering")
            return pd.DataFrame()
        
        df = pd.DataFrame(df_data)
        
        # Store in database
        self._store_in_database(all_data_points)
        
        # Save to CSV files (backward compatibility)
        self._save_to_csv_files(df)
        
        # Update collection statistics
        self.collection_stats['last_update'] = datetime.now()
        
        logger.info(f"Enhanced collection completed: {valid_points} valid data points")
        
        return df
    
    def _get_binance_data_enhanced(self, symbols: Optional[List[str]] = None) -> Dict[str, MarketDataPoint]:
        """Placeholder for Binance data - can be implemented later"""
        return {}
    
    def _store_in_database(self, data_points: List[MarketDataPoint]):
        """שמירה בבסיס נתונים"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            for point in data_points:
                cursor.execute('''
                    INSERT OR REPLACE INTO market_data 
                    (timestamp, symbol, price, volume, high_24h, low_24h, 
                     change_24h, change_pct_24h, bid, ask, spread, source, quality_score)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    point.timestamp.isoformat(),
                    point.symbol,
                    point.price,
                    point.volume,
                    point.high_24h,
                    point.low_24h,
                    point.change_24h,
                    point.change_pct_24h,
                    point.bid,
                    point.ask,
                    point.spread,
                    point.source,
                    point.quality_score
                ))
            
            conn.commit()
            conn.close()
            
            logger.debug(f"Stored {len(data_points)} data points in database")
            
        except Exception as e:
            logger.error(f"Database storage error: {e}")
    
    def _save_to_csv_files(self, df: pd.DataFrame):
        """שמירה לקבצי CSV (תאימות אחורה)"""
        try:
            # Save to live file
            df.to_csv(Config.MARKET_LIVE_FILE, index=False, encoding='utf-8')
            
            # Append to history file
            if os.path.exists(Config.MARKET_HISTORY_FILE):
                # Load existing and merge
                existing_df = pd.read_csv(Config.MARKET_HISTORY_FILE)
                combined_df = pd.concat([existing_df, df], ignore_index=True)
                
                # Remove duplicates and keep recent data
                combined_df = combined_df.drop_duplicates(subset=['timestamp', 'symbol', 'source'], keep='last')
                
                # Keep only last 30 days
                combined_df['timestamp'] = pd.to_datetime(combined_df['timestamp'], format='%Y-%m-%d %H:%M:%S', errors='coerce')
                cutoff_date = datetime.now() - timedelta(days=1800)
                combined_df = combined_df[combined_df['timestamp'] > cutoff_date]
                
                combined_df.to_csv(Config.MARKET_HISTORY_FILE, index=False, encoding='utf-8')
            else:
                df.to_csv(Config.MARKET_HISTORY_FILE, index=False, encoding='utf-8')
                
        except Exception as e:
            logger.error(f"CSV save error: {e}")
    
    def get_historical_data(self, symbol: str, 
                          start_date: Optional[datetime] = None,
                          end_date: Optional[datetime] = None,
                          source: Optional[str] = None) -> pd.DataFrame:
        """קבלת נתונים היסטוריים מהDB"""
        try:
            conn = sqlite3.connect(self.db_path)
            
            query = "SELECT * FROM market_data WHERE symbol = ?"
            params = [symbol]
            
            if start_date:
                query += " AND timestamp >= ?"
                params.append(start_date.isoformat())
            
            if end_date:
                query += " AND timestamp <= ?"
                params.append(end_date.isoformat())
            
            if source:
                query += " AND source = ?"
                params.append(source)
            
            query += " ORDER BY timestamp ASC"
            
            df = pd.read_sql_query(query, conn, params=params)
            conn.close()
            
            if not df.empty:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            return df
            
        except Exception as e:
            logger.error(f"Error getting historical data: {e}")
            return pd.DataFrame()
    
    def get_data_quality_report(self) -> Dict:
        """דוח איכות נתונים"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Overall statistics
            cursor.execute('''
                SELECT 
                    COUNT(*) as total_records,
                    AVG(quality_score) as avg_quality,
                    MIN(quality_score) as min_quality,
                    MAX(quality_score) as max_quality,
                    COUNT(DISTINCT symbol) as unique_symbols,
                    COUNT(DISTINCT source) as unique_sources
                FROM market_data 
                WHERE timestamp > datetime('now', '-1 day')
            ''')
            
            stats = cursor.fetchone()
            
            # Quality by source
            cursor.execute('''
                SELECT source, AVG(quality_score) as avg_quality, COUNT(*) as count
                FROM market_data 
                WHERE timestamp > datetime('now', '-1 day')
                GROUP BY source
            ''')
            
            source_stats = cursor.fetchall()
            
            conn.close()
            
            return {
                'timestamp': datetime.now(),
                'collection_stats': self.collection_stats,
                'data_quality': {
                    'total_records': stats[0],
                    'average_quality_score': stats[1],
                    'min_quality_score': stats[2],
                    'max_quality_score': stats[3],
                    'unique_symbols': stats[4],
                    'unique_sources': stats[5]
                },
                'quality_by_source': [
                    {'source': row[0], 'avg_quality': row[1], 'count': row[2]}
                    for row in source_stats
                ]
            }
            
        except Exception as e:
            logger.error(f"Error generating quality report: {e}")
            return {'error': str(e)}
    
    def cleanup_old_data(self, days_to_keep: int = 30):
        """ניקוי נתונים ישנים"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                DELETE FROM market_data 
                WHERE timestamp < datetime('now', '-{} days')
            '''.format(days_to_keep))
            
            deleted_rows = cursor.rowcount
            conn.commit()
            conn.close()
            
            logger.info(f"Cleaned up {deleted_rows} old records")
            
        except Exception as e:
            logger.error(f"Cleanup error: {e}")
    
    def _normalize_kraken_symbol(self, pair: str) -> str:
        """נרמול סמלי Kraken - משופר"""
        # Remove USD/ZUSD from the end
        cleaned = pair.replace('USD', '').replace('ZUSD', '')
        
        # Remove suffixes (.S = Staked, .F = Futures, etc.)
        if '.' in cleaned:
            cleaned = cleaned.split('.')[0]
        
        # Remove Kraken prefixes
        cleaned = cleaned.replace('X', '').replace('Z', '')
        
        # Enhanced replacements
        replacements = {
            'XBT': 'BTC', 'XETH': 'ETH', 'XXRP': 'XRP', 'XLTC': 'LTC',
            'XXLM': 'XLM', 'XDOGE': 'DOGE', 'XETC': 'ETC', 'XMLN': 'MLN',
            'XREP': 'REP', 'XXMR': 'XMR', 'XXTZ': 'XTZ', 'XZEC': 'ZEC',
            'ADAXS': 'ADA', 'ATOMXS': 'ATOM', 'DOTXS': 'DOT', 'FLOWHS': 'FLOW',
            'KSMXS': 'KSM', 'SCRTBS': 'SCRT', 'SOLXS': 'SOL', 'MATICXS': 'MATIC',
            'USDCM': 'USDC', 'USDTM': 'USDT', 'ETHW': 'ETH', 'LUNA2': 'LUNA'
        }
        
        return replacements.get(cleaned, cleaned)


# Enhanced version as alias for backward compatibility
EnhancedMarketCollector = MarketCollector

# פונקציות נדרשות ל-main.py
def run_collector(interval: int = 30):
    """פונקציה פשוטה להפעלת איסוף נתונים"""
    collector = MarketCollector()
    
    logger.info(f"Market collector started - interval: {interval}s")
    
    error_count = 0
    max_errors = 5
    
    while True:
        try:
            start_time = time.time()
            
            # Get symbols to collect
            symbols = Config.DEFAULT_COINS[:20] if hasattr(Config, 'DEFAULT_COINS') else ['BTC', 'ETH', 'SOL']
            # קבל את כל המטבעות הזמינים אם מוגדר כך
            max_symbols = getattr(Config, 'SYMBOL_CONFIG', {}).get('max_symbols', 600)
            all_available = collector.get_all_available_symbols()
            symbols = all_available[:max_symbols] if len(all_available) > max_symbols else all_available
            logger.info(f"📊 Collecting data for {len(symbols)} symbols")
            
            # Collect data
            df = collector.collect_and_store_enhanced(symbols)
