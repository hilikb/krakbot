import os
import sys
import pandas as pd
import time
import asyncio
import websockets
import json
import threading
import logging
from datetime import datetime, timedelta
import krakenex
from typing import Dict, List, Optional, Tuple, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from dataclasses import dataclass, asdict
import sqlite3
from functools import lru_cache
import queue

# הוספת נתיב למודולים
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config

logger = Config.setup_logging('hybrid_market_collector')

@dataclass
class RealTimePriceUpdate:
    """עדכון מחיר בזמן אמת"""
    symbol: str
    price: float
    timestamp: datetime
    volume: float
    bid: float
    ask: float
    high_24h: float
    low_24h: float
    change_24h_pct: float
    source: str = 'websocket'
    quality_score: float = 1.0

class WebSocketClient:
    """לקוח WebSocket לKraken"""
    
    def __init__(self, symbols: List[str]):
        self.symbols = symbols
        self.ws_url = "wss://ws.kraken.com"
        self.websocket = None
        self.is_connected = False
        self.should_run = False
        
        # Callbacks
        self.price_callbacks = []
        self.connection_callbacks = []
        
        # Data storage
        self.latest_prices = {}
        self.connection_status = "disconnected"
        
        # Reconnection settings
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        self.reconnect_delay = 5
        
    async def connect(self):
        """התחברות ל-WebSocket"""
        try:
            logger.info("🔗 Connecting to Kraken WebSocket...")
            self.websocket = await websockets.connect(
                self.ws_url,
                ping_interval=20,
                ping_timeout=10,
                close_timeout=10
            )
            
            self.is_connected = True
            self.connection_status = "connected"
            self.reconnect_attempts = 0
            
            logger.info("✅ WebSocket connected successfully")
            
            # הודעה לcallbacks
            for callback in self.connection_callbacks:
                try:
                    callback("connected")
                except Exception as e:
                    logger.error(f"Error in connection callback: {e}")
            
            # התחלת האזנה
            await self._subscribe_to_symbols()
            await self._listen_loop()
            
        except Exception as e:
            logger.error(f"❌ Failed to connect to WebSocket: {e}")
            self.is_connected = False
            self.connection_status = "error"
            await self._handle_reconnection()
    
    async def _subscribe_to_symbols(self):
        """הרשמה לסמלים"""
        try:
            # המרת סמלים לפורמט Kraken
            kraken_pairs = [self._convert_symbol_to_kraken(symbol) for symbol in self.symbols]
            
            subscription_msg = {
                "event": "subscribe",
                "pair": kraken_pairs,
                "subscription": {
                    "name": "ticker"
                }
            }
            
            logger.info(f"📡 Subscribing to {len(kraken_pairs)} pairs: {kraken_pairs[:5]}...")
            await self.websocket.send(json.dumps(subscription_msg))
            
        except Exception as e:
            logger.error(f"❌ Error subscribing to symbols: {e}")
    
    def _convert_symbol_to_kraken(self, symbol: str) -> str:
        """המרת סמל לפורמט Kraken"""
        # מיפויים מיוחדים בלבד - רק למטבעות עם שמות שונים ב-Kraken
        special_mappings = {
            'BTC': 'XBT/USD',  # Bitcoin נקרא XBT ב-Kraken
        }
        
        # בדיקה אם יש מיפוי מיוחד
        if symbol in special_mappings:
            return special_mappings[symbol]
        
        # לכל השאר - פשוט הוסף /USD
        # זה יעבוד עבור: ETH, SOL, ADA, DOT, MATIC, LINK וכו'
        return f"{symbol}/USD"
    
    async def _listen_loop(self):
        """לולאת האזנה"""
        try:
            while self.should_run and self.is_connected:
                try:
                    message = await asyncio.wait_for(
                        self.websocket.recv(), 
                        timeout=30
                    )
                    await self._handle_message(message)
                    
                except asyncio.TimeoutError:
                    logger.debug("WebSocket timeout - sending ping")
                    if self.websocket:
                        await self.websocket.ping()
                    
                except websockets.exceptions.ConnectionClosed:
                    logger.warning("🔌 WebSocket connection closed")
                    self.is_connected = False
                    break
                    
        except Exception as e:
            logger.error(f"❌ Error in WebSocket listen loop: {e}")
            self.is_connected = False
        
        # ניסיון התחברות מחדש
        if self.should_run:
            await self._handle_reconnection()
    
    async def _handle_message(self, message: str):
        """טיפול בהודעות WebSocket"""
        try:
            data = json.loads(message)
            
            # הודעות מערכת
            if isinstance(data, dict):
                event = data.get('event')
                if event == 'heartbeat':
                    logger.debug("💓 Heartbeat received")
                    return
                elif event == 'systemStatus':
                    status = data.get('status', 'unknown')
                    logger.info(f"🔧 System status: {status}")
                    return
                elif event == 'subscriptionStatus':
                    if data.get('status') == 'subscribed':
                        pair = data.get('pair', 'unknown')
                        logger.info(f"✅ Subscribed to {pair}")
                    return
            
            # נתוני ticker
            if isinstance(data, list) and len(data) >= 4:
                await self._process_ticker_data(data)
            
        except json.JSONDecodeError:
            logger.warning(f"⚠️ Failed to parse WebSocket message: {message[:100]}...")
        except Exception as e:
            logger.error(f"❌ Error handling WebSocket message: {e}")
    
    async def _process_ticker_data(self, data: list):
        """עיבוד נתוני ticker"""
        try:
            if len(data) < 4:
                return
            
            channel_id = data[0]
            ticker_data = data[1]
            channel_name = data[2]
            pair = data[3]
            
            if channel_name != "ticker":
                return
            
            # המרת pair לסמל פשוט
            symbol = self._convert_pair_to_symbol(pair)
            
            # חילוץ נתונים
            if isinstance(ticker_data, dict):
                current_price = float(ticker_data.get('c', [0, 0])[0])
                if current_price <= 0:
                    return
                
                # חישוב שינוי 24 שעות
                open_price = float(ticker_data.get('o', [current_price, current_price])[0])
                change_24h_pct = 0
                if open_price > 0:
                    change_24h_pct = ((current_price - open_price) / open_price) * 100
                
                price_update = RealTimePriceUpdate(
                    symbol=symbol,
                    price=current_price,
                    timestamp=datetime.now(),
                    volume=float(ticker_data.get('v', [0, 0])[1]),
                    bid=float(ticker_data.get('b', [current_price, 0])[0]),
                    ask=float(ticker_data.get('a', [current_price, 0])[0]),
                    high_24h=float(ticker_data.get('h', [current_price, current_price])[1]),
                    low_24h=float(ticker_data.get('l', [current_price, current_price])[1]),
                    change_24h_pct=change_24h_pct,
                    source='websocket',
                    quality_score=1.0
                )
                
                # שמירה
                self.latest_prices[symbol] = price_update
                
                # הודעה לcallbacks
                for callback in self.price_callbacks:
                    try:
                        callback(price_update)
                    except Exception as e:
                        logger.error(f"Error in price callback: {e}")
                
                logger.debug(f"💰 {symbol}: ${current_price:,.2f} ({change_24h_pct:+.2f}%)")
            
        except Exception as e:
            logger.error(f"❌ Error processing ticker data: {e}")
    
    def _convert_pair_to_symbol(self, pair: str) -> str:
        """המרת pair לסמל"""
        # Remove /USD and clean up
        symbol = pair.replace('/USD', '').replace('XBT', 'BTC')
        return symbol
    
    async def _handle_reconnection(self):
        """טיפול בהתחברות מחדש"""
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            logger.error(f"❌ Max reconnection attempts ({self.max_reconnect_attempts}) reached")
            self.connection_status = "failed"
            return
        
        self.reconnect_attempts += 1
        wait_time = self.reconnect_delay * (2 ** (self.reconnect_attempts - 1))  # Exponential backoff
        
        logger.info(f"🔄 Reconnection attempt {self.reconnect_attempts}/{self.max_reconnect_attempts} in {wait_time}s...")
        
        await asyncio.sleep(wait_time)
        
        if self.should_run:
            await self.connect()
    
    async def start(self):
        """התחלת הלקוח"""
        self.should_run = True
        await self.connect()
    
    async def stop(self):
        """עצירת הלקוח"""
        logger.info("🛑 Stopping WebSocket client...")
        self.should_run = False
        self.is_connected = False
        
        if self.websocket:
            await self.websocket.close()
        
        self.connection_status = "stopped"
    
    def add_price_callback(self, callback: Callable[[RealTimePriceUpdate], None]):
        """הוספת callback לעדכוני מחירים"""
        self.price_callbacks.append(callback)
    
    def add_connection_callback(self, callback: Callable[[str], None]):
        """הוספת callback לשינויי חיבור"""
        self.connection_callbacks.append(callback)
    
    def get_latest_prices(self) -> Dict[str, RealTimePriceUpdate]:
        """קבלת מחירים אחרונים"""
        return self.latest_prices.copy()

class OptimizedHTTPClient:
    """לקוח HTTP מואץ עם connection pooling"""
    
    def __init__(self, api_key=None, api_secret=None):
        self.api_key = api_key
        self.api_secret = api_secret
        
        # יצירת session עם אופטימיזציות
        self.session = requests.Session()
        
        # Retry strategy
        retry_strategy = Retry(
            total=3,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "POST"],
            backoff_factor=1
        )
        
        # Connection pooling
        adapter = HTTPAdapter(
            pool_connections=10,
            pool_maxsize=20,
            max_retries=retry_strategy
        )
        
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # Headers
        self.session.headers.update({
            'User-Agent': 'Kraken Hybrid Bot v2.0',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json'
        })
        
        # Cache
        self.cache = {}
        self.cache_timeouts = {}
        
        # Rate limiting
        self.last_call_times = {}
        self.call_intervals = {
            'public': 1.0,
            'private': 2.0
        }
        
        # Kraken API for private calls
        if self.api_key and self.api_secret:
            self.kraken_api = krakenex.API(self.api_key, self.api_secret)
        else:
            self.kraken_api = None
    
    def _respect_rate_limits(self, call_type: str = 'public'):
        """כיבוד מגבלות קצב"""
        current_time = time.time()
        last_call = self.last_call_times.get(call_type, 0)
        interval = self.call_intervals.get(call_type, 1.0)
        
        time_since_last = current_time - last_call
        if time_since_last < interval:
            sleep_time = interval - time_since_last
            time.sleep(sleep_time)
        
        self.last_call_times[call_type] = time.time()
    
    def _get_cached_data(self, cache_key: str, ttl_seconds: int = 60):
        """קבלת נתונים מcache"""
        if cache_key in self.cache:
            cached_time = self.cache_timeouts.get(cache_key, 0)
            if time.time() - cached_time < ttl_seconds:
                return self.cache[cache_key]
        return None
    
    def _cache_data(self, cache_key: str, data):
        """שמירת נתונים בcache"""
        self.cache[cache_key] = data
        self.cache_timeouts[cache_key] = time.time()
    
    def get_account_balance(self) -> Dict:
        """קבלת יתרות חשבון"""
        if not self.kraken_api:
            logger.warning("No API credentials for balance query")
            return {}
        
        try:
            self._respect_rate_limits('private')
            
            response = self.kraken_api.query_private('Balance')
            
            if response.get('error'):
                logger.error(f"Balance query error: {response['error']}")
                return {}
            
            return response.get('result', {})
            
        except Exception as e:
            logger.error(f"Error getting balance: {e}")
            return {}
    
    def get_trading_history(self, count: int = 50) -> List:
        """קבלת היסטוריית מסחר"""
        if not self.kraken_api:
            return []
        
        try:
            self._respect_rate_limits('private')
            
            response = self.kraken_api.query_private('TradesHistory', {
                'ofs': 0,
                'count': count
            })
            
            if response.get('error'):
                logger.error(f"Trading history error: {response['error']}")
                return []
            
            trades = response.get('result', {}).get('trades', {})
            return list(trades.values())
            
        except Exception as e:
            logger.error(f"Error getting trading history: {e}")
            return []
    
    def get_asset_pairs(self, use_cache: bool = True) -> Dict:
        """קבלת זוגות מסחר"""
        cache_key = "asset_pairs"
        
        if use_cache:
            cached_data = self._get_cached_data(cache_key, ttl_seconds=3600)  # 1 hour cache
            if cached_data:
                return cached_data
        
        try:
            self._respect_rate_limits('public')
            
            url = "https://api.kraken.com/0/public/AssetPairs"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get('error'):
                logger.error(f"Asset pairs error: {data['error']}")
                return {}
            
            result = data.get('result', {})
            
            if use_cache:
                self._cache_data(cache_key, result)
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting asset pairs: {e}")
            return {}
    
    def get_historical_ohlc(self, pair: str, interval: int = 1440, since: int = None) -> List:
        """קבלת נתוני OHLC היסטוריים"""
        try:
            self._respect_rate_limits('public')
            
            url = "https://api.kraken.com/0/public/OHLC"
            params = {
                'pair': pair,
                'interval': interval
            }
            
            if since:
                params['since'] = since
            
            response = self.session.get(url, params=params, timeout=15)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get('error'):
                logger.error(f"OHLC error for {pair}: {data['error']}")
                return []
            
            # הנתונים מגיעים בתוך key שהוא שם הpair
            result = data.get('result', {})
            for key, value in result.items():
                if key != 'last' and isinstance(value, list):
                    return value
            
            return []
            
        except Exception as e:
            logger.error(f"Error getting OHLC for {pair}: {e}")
            return []
    
    def cleanup(self):
        """ניקוי משאבים"""
        self.session.close()

class HybridMarketCollector:
    """איוסף שוק היברידי - WebSocket + HTTP מואץ"""
    
    def __init__(self, symbols: List[str] = None, api_key: str = None, api_secret: str = None):
        # עדכון לתמיכה בהגדרות החדשות
        websocket_limit = Config.WEBSOCKET_MAX_SYMBOLS
        all_symbols = symbols or Config.DEFAULT_COINS[:Config.SYMBOL_CONFIG.get('max_symbols', 600)]
        
        # הפרדה בין סמלים ל-WebSocket ו-HTTP
        self.websocket_symbols = all_symbols[:websocket_limit]
        self.http_only_symbols = all_symbols[websocket_limit:]
        
        # שמירת כל הסמלים - חשוב!
        self.symbols = all_symbols
        self.all_symbols = all_symbols  # הוסף את השורה הזו!
        
        logger.info(f"🚀 Hybrid Setup: {len(self.websocket_symbols)} WebSocket + {len(self.http_only_symbols)} HTTP-only symbols")
        
        # Clients
        self.ws_client = WebSocketClient(self.websocket_symbols)
        self.http_client = OptimizedHTTPClient(api_key, api_secret)
        
        # State
        self.is_running = False
        self.data_queue = queue.Queue()
        self.latest_data = {}
        
        # Threading
        self.ws_thread = None
        self.http_thread = None
        self.http_all_symbols_thread = None
        self.processing_thread = None
        
        # Database
        self.db_path = os.path.join(Config.DATA_DIR, 'hybrid_market_data.db')
        self._init_database()
        
        # Callbacks
        self.data_callbacks = []
        
        # Statistics
        self.stats = {
            'websocket_updates': 0,
            'http_updates': 0,
            'http_only_updates': 0,
            'total_updates': 0,
            'websocket_symbols_count': len(self.websocket_symbols),
            'http_only_symbols_count': len(self.http_only_symbols),
            'total_symbols_count': len(all_symbols),  # הוסף גם את זה
            'start_time': None,
            'last_update': None
        }
        
        # Setup WebSocket callbacks
        self.ws_client.add_price_callback(self._on_websocket_update)
        self.ws_client.add_connection_callback(self._on_connection_change)

    def _fetch_all_available_symbols(self) -> List[str]:
        """שליפת כל הסמלים הזמינים מ-Kraken"""
        try:
            if not hasattr(self, 'http_client'):
                self.http_client = OptimizedHTTPClient()
            
            pairs = self.http_client.get_asset_pairs()
            
            symbols = []
            for pair, info in pairs.items():
                if 'USD' in pair and info.get('status') == 'online':
                    symbol = pair.replace('USD', '').replace('ZUSD', '')
                    # ניקוי סמלים של Kraken
                    symbol = symbol.replace('XXBT', 'BTC').replace('XETH', 'ETH')
                    if symbol not in symbols:
                        symbols.append(symbol)
            
            logger.info(f"📊 Found {len(symbols)} available symbols on Kraken")
            return sorted(symbols)
            
        except Exception as e:
            logger.error(f"Error fetching available symbols: {e}")
            return []
    
    def _http_all_symbols_worker(self):
        """Thread worker לעדכון כל הסמלים שלא בWebSocket"""
        http_interval = Config.HTTP_UPDATE_INTERVAL  # משתמש בהגדרה מ-Config
        
        while self.is_running:
            try:
                start_time = time.time()
                
                if self.http_only_symbols:
                    logger.info(f"📊 Updating {len(self.http_only_symbols)} HTTP-only symbols...")
                    
                    # חלוקה לbatches כדי לא להעמיס
                    batch_size = 20
                    for i in range(0, len(self.http_only_symbols), batch_size):
                        if not self.is_running:
                            break
                            
                        batch = self.http_only_symbols[i:i+batch_size]
                        
                        # קריאת Ticker עבור ה-batch
                        try:
                            self._fetch_http_batch_prices(batch)
                            time.sleep(2)  # המתנה בין batches
                        except Exception as e:
                            logger.error(f"Error fetching batch {i//batch_size}: {e}")
                
                # המתנה לפני הסיבוב הבא
                elapsed = time.time() - start_time
                sleep_time = max(0, http_interval - elapsed)
                
                logger.info(f"✅ HTTP update completed in {elapsed:.1f}s, next in {sleep_time:.0f}s")
                
                for _ in range(int(sleep_time)):
                    if not self.is_running:
                        break
                    time.sleep(1)
                    
            except Exception as e:
                logger.error(f"HTTP all symbols worker error: {e}")
                time.sleep(60)

    def _fetch_http_batch_prices(self, symbols: List[str]):
        """שליפת מחירים עבור batch של סמלים"""
        try:
            # בניית pairs string לKraken
            pairs = ','.join([f"{symbol}USD" for symbol in symbols])
            
            # קריאה לAPI
            self.http_client._respect_rate_limits('public')
            url = "https://api.kraken.com/0/public/Ticker"
            response = self.http_client.session.get(url, params={'pair': pairs}, timeout=15)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get('error'):
                logger.error(f"Ticker error: {data['error']}")
                return
            
            # עיבוד תוצאות
            for pair, ticker_data in data.get('result', {}).items():
                symbol = self._normalize_pair_to_symbol(pair)
                
                if symbol in self.http_only_symbols:
                    try:
                        current_price = float(ticker_data.get('c', [0])[0])
                        if current_price <= 0:
                            continue
                        
                        # חישוב שינוי
                        open_price = float(ticker_data.get('o', current_price))
                        change_24h_pct = ((current_price - open_price) / open_price * 100) if open_price > 0 else 0
                        
                        price_update = RealTimePriceUpdate(
                            symbol=symbol,
                            price=current_price,
                            timestamp=datetime.now(),
                            volume=float(ticker_data.get('v', [0, 0])[1]),
                            bid=float(ticker_data.get('b', [current_price])[0]),
                            ask=float(ticker_data.get('a', [current_price])[0]),
                            high_24h=float(ticker_data.get('h', [current_price, current_price])[1]),
                            low_24h=float(ticker_data.get('l', [current_price, current_price])[1]),
                            change_24h_pct=change_24h_pct,
                            source='http',
                            quality_score=0.9  # מעט נמוך יותר מWebSocket
                        )
                        
                        # הוספה לqueue
                        self.data_queue.put(('http', price_update))
                        self.stats['http_only_updates'] += 1
                        
                    except Exception as e:
                        logger.error(f"Error processing {pair}: {e}")
                        
        except Exception as e:
            logger.error(f"Batch fetch error: {e}")

    def _normalize_pair_to_symbol(self, pair: str) -> str:
        """נרמול pair לסמל"""
        # הסרת USD וניקוי
        symbol = pair.replace('USD', '').replace('ZUSD', '')
        
        # מיפויים מיוחדים של Kraken
        mappings = {
            'XXBT': 'BTC', 'XBT': 'BTC',
            'XETH': 'ETH', 'XXRP': 'XRP',
            'XLTC': 'LTC', 'XXLM': 'XLM',
            'XZEC': 'ZEC', 'XXMR': 'XMR'
        }
        
        for old, new in mappings.items():
            if symbol.startswith(old):
                return new
        
        # הסרת X/Z prefix
        if symbol.startswith('X') and len(symbol) > 3:
            symbol = symbol[1:]
        
        return symbol
    
    def _init_database(self):
        """אתחול בסיס נתונים"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS hybrid_market_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    price REAL NOT NULL,
                    timestamp DATETIME NOT NULL,
                    volume REAL,
                    bid REAL,
                    ask REAL,
                    high_24h REAL,
                    low_24h REAL,
                    change_24h_pct REAL,
                    source TEXT NOT NULL,
                    quality_score REAL DEFAULT 1.0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(symbol, timestamp, source)
                )
            ''')
            
            # יצירת אינדקסים
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_symbol_timestamp ON hybrid_market_data(symbol, timestamp)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON hybrid_market_data(timestamp)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_source ON hybrid_market_data(source)')
            
            conn.commit()
            conn.close()
            
            logger.info("✅ Hybrid database initialized")
            
        except Exception as e:
            logger.error(f"❌ Database initialization error: {e}")
    
    def _on_websocket_update(self, price_update: RealTimePriceUpdate):
        """טיפול בעדכון WebSocket"""
        try:
            # הוספה לqueue לעיבוד
            self.data_queue.put(('websocket', price_update))
            self.stats['websocket_updates'] += 1
            
        except Exception as e:
            logger.error(f"Error handling WebSocket update: {e}")
    
    def _on_connection_change(self, status: str):
        """טיפול בשינוי סטטוס חיבור"""
        logger.info(f"🔗 WebSocket status: {status}")
        
        if status in ['error', 'failed', 'disconnected'] and self.is_running:
            # אם WebSocket נפל, נגביר את תדירות HTTP
            logger.warning("⚠️ WebSocket issues detected, increasing HTTP polling frequency")
    
    def _websocket_worker(self):
        """Thread worker ל-WebSocket"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            loop.run_until_complete(self.ws_client.start())
        except Exception as e:
            logger.error(f"WebSocket worker error: {e}")
        finally:
            loop.close()
    
    def _http_worker(self):
        """Thread worker ל-HTTP - מילוי פערים ועדכון סמלים נוספים"""
        http_interval = Config.HYBRID_CONFIG.get('http_update_interval', 120)  # 2 דקות
        
        while self.is_running:
            try:
                start_time = time.time()
                
                # עדכון סמלים שלא ב-WebSocket
                if self.http_only_symbols:
                    logger.info(f"📊 HTTP update for {len(self.http_only_symbols)} additional symbols")
                    self._update_http_only_symbols()
                
                # בדיקת סמלים ישנים מ-WebSocket
                stale_symbols = self._find_stale_symbols()
                if stale_symbols:
                    logger.info(f"🔄 HTTP fallback for {len(stale_symbols)} stale symbols")
                    self._update_stale_symbols(stale_symbols)
                
                # המתנה לסיבוב הבא
                elapsed = time.time() - start_time
                sleep_time = max(0, http_interval - elapsed)
                
                for _ in range(int(sleep_time)):
                    if not self.is_running:
                        break
                    time.sleep(1)
                    
            except Exception as e:
                logger.error(f"HTTP worker error: {e}")
                time.sleep(30)

    def _update_http_only_symbols(self):
        """עדכון סמלים שרק ב-HTTP"""
        batch_size = 10  # מספר סמלים לכל קריאת API
        
        for i in range(0, len(self.http_only_symbols), batch_size):
            batch = self.http_only_symbols[i:i+batch_size]
            
            try:
                # קריאת Ticker API עבור הבאץ'
                pairs = [f"{symbol}USD" for symbol in batch]
                ticker_resp = self.http_client.kraken_api.query_public('Ticker', {'pair': ','.join(pairs)})
                
                if ticker_resp.get('result'):
                    self._process_http_ticker_data(ticker_resp['result'])
                
                # השהייה קטנה בין באצ'ים
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Error updating HTTP symbols batch: {e}")
    
    def _update_stale_symbols(self, symbols: List[str]):
        """עדכון סמלים ישנים"""
        # Similar implementation to _update_http_only_symbols
        pass
    
    def _find_stale_symbols(self, max_age_seconds: int = 120) -> List[str]:
        """מציאת סמלים שלא התעדכנו מזמן"""
        stale_symbols = []
        current_time = datetime.now()
        
        ws_prices = self.ws_client.get_latest_prices()
        
        for symbol in self.websocket_symbols:
            if symbol not in ws_prices:
                stale_symbols.append(symbol)
            else:
                last_update = ws_prices[symbol].timestamp
                age = (current_time - last_update).total_seconds()
                if age > max_age_seconds:
                    stale_symbols.append(symbol)
        
        return stale_symbols
    
    def _data_processor(self):
        """Thread לעיבוד נתונים"""
        while self.is_running:
            try:
                # קבלת נתונים מהqueue
                try:
                    source, data = self.data_queue.get(timeout=1)
                except queue.Empty:
                    continue
                
                # עיבוד נתונים
                if isinstance(data, RealTimePriceUpdate):
                    self._process_price_update(data)
                
                # סימון שהמשימה הושלמה
                self.data_queue.task_done()
                
            except Exception as e:
                logger.error(f"Data processor error: {e}")
    
    def _process_price_update(self, price_update: RealTimePriceUpdate):
        """עיבוד עדכון מחיר"""
        try:
            # שמירה בזיכרון
            self.latest_data[price_update.symbol] = price_update
            
            # שמירה בדאטבאס
            self._save_to_database(price_update)
            
            # שמירה לקבצים (תאימות אחורה)
            self._save_to_csv_files(price_update)
            
            # הודעה לcallbacks
            for callback in self.data_callbacks:
                try:
                    callback(price_update)
                except Exception as e:
                    logger.error(f"Error in data callback: {e}")
            
            # עדכון סטטיסטיקות
            self.stats['total_updates'] += 1
            self.stats['last_update'] = datetime.now()
            
        except Exception as e:
            logger.error(f"Error processing price update: {e}")
    
    def _save_to_database(self, price_update: RealTimePriceUpdate):
        """שמירה בדאטבאס"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO hybrid_market_data 
                (symbol, price, timestamp, volume, bid, ask, high_24h, low_24h, 
                 change_24h_pct, source, quality_score)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                price_update.symbol,
                price_update.price,
                price_update.timestamp,
                price_update.volume,
                price_update.bid,
                price_update.ask,
                price_update.high_24h,
                price_update.low_24h,
                price_update.change_24h_pct,
                price_update.source,
                price_update.quality_score
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Database save error: {e}")
    
    def _save_to_csv_files(self, price_update: RealTimePriceUpdate):
        """שמירה לקבצי CSV (תאימות אחורה)"""
        try:
            # המרה לפורמט CSV
            row_data = {
                'timestamp': price_update.timestamp,
                'pair': f"{price_update.symbol}USD",
                'price': price_update.price,
                'volume': price_update.volume,
                'high_24h': price_update.high_24h,
                'low_24h': price_update.low_24h,
                'change_24h': price_update.change_24h_pct * price_update.price / 100,
                'change_pct_24h': price_update.change_24h_pct,
                'bid': price_update.bid,
                'ask': price_update.ask,
                'spread': price_update.ask - price_update.bid,
                'trades_24h': 0,  # לא זמין דרך WebSocket
                'source': price_update.source
            }
            
            df = pd.DataFrame([row_data])
            
            # שמירה לlive file
            df.to_csv(Config.MARKET_LIVE_FILE, mode='a', header=False, index=False)
            
        except Exception as e:
            logger.error(f"CSV save error: {e}")
    
    def start(self):
        """התחלת האיסוף ההיברידי"""
        if self.is_running:
            logger.warning("Hybrid collector already running")
            return
            
        logger.info("🚀 Starting Enhanced Hybrid Market Collector...")
        logger.info(f"📊 WebSocket: {len(self.websocket_symbols)} symbols")
        logger.info(f"🌐 HTTP-only: {len(self.http_only_symbols)} symbols")
        logger.info(f"💎 Total: {len(self.all_symbols)} symbols")  # כאן משתמש ב-all_symbols
        
        self.is_running = True
        self.stats['start_time'] = datetime.now()
        
        # התחלת threads
        self.ws_thread = threading.Thread(target=self._websocket_worker, daemon=True, name="WebSocket-Worker")
        self.http_thread = threading.Thread(target=self._http_worker, daemon=True, name="HTTP-Fallback")
        self.http_all_symbols_thread = threading.Thread(target=self._http_all_symbols_worker, daemon=True, name="HTTP-AllSymbols")
        self.processing_thread = threading.Thread(target=self._data_processor, daemon=True, name="Data-Processor")
        
        self.ws_thread.start()
        self.http_thread.start()
        self.http_all_symbols_thread.start()  # התחלת ה-thread החדש
        self.processing_thread.start()
        
        logger.info("✅ Enhanced Hybrid collector started successfully")
    
    def stop(self):
        """עצירת האיסוף"""
        if not self.is_running:
            return
        
        logger.info("🛑 Stopping Hybrid Market Collector...")
        
        self.is_running = False
        
        # עצירת WebSocket
        if self.ws_client:
            # נריץ את העצירה בloop חדש
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.ws_client.stop())
            loop.close()
        
        # המתנה לסיום threads
        threads_to_stop = [
            (self.ws_thread, "WebSocket"),
            (self.http_thread, "HTTP Fallback"),
            (self.http_all_symbols_thread, "HTTP All Symbols"),
            (self.processing_thread, "Processing")
        ]
        
        for thread, name in threads_to_stop:
            if thread and thread.is_alive():
                logger.info(f"Stopping {name} thread...")
                thread.join(timeout=5)
        
        # ניקוי HTTP client
        self.http_client.cleanup()
        
        logger.info("✅ Hybrid collector stopped")
    
    def get_latest_prices(self) -> Dict[str, RealTimePriceUpdate]:
        """קבלת מחירים אחרונים"""
        return self.latest_data.copy()
    
    def get_statistics(self) -> Dict:
        """קבלת סטטיסטיקות מורחבות"""
        stats = self.stats.copy()
        
        if stats['start_time']:
            runtime = datetime.now() - stats['start_time']
            stats['runtime_seconds'] = runtime.total_seconds()
            stats['updates_per_minute'] = stats['total_updates'] / (runtime.total_seconds() / 60) if runtime.total_seconds() > 0 else 0
        
        stats['websocket_status'] = self.ws_client.connection_status
        stats['active_websocket_symbols'] = len([s for s in self.websocket_symbols if s in self.latest_data])
        stats['active_http_symbols'] = len([s for s in self.http_only_symbols if s in self.latest_data])
        stats['total_active_symbols'] = len(self.latest_data)
        stats['active_symbols'] = stats['total_active_symbols']  # תאימות אחורה
        
        # חישוב אחוז כיסוי
        stats['coverage_percentage'] = (len(self.latest_data) / len(self.all_symbols) * 100) if self.all_symbols else 0
        
        return stats
    
    def add_data_callback(self, callback: Callable[[RealTimePriceUpdate], None]):
        """הוספת callback לעדכוני נתונים"""
        self.data_callbacks.append(callback)
    
    # Methods for backward compatibility
    def get_combined_prices(self, symbols: List[str]) -> Dict[str, Dict]:
        """תאימות אחורה - פורמט כמו הקוד הישן"""
        latest_prices = self.get_latest_prices()
        result = {}
        
        for symbol in symbols:
            if symbol in latest_prices:
                price_update = latest_prices[symbol]
                result[symbol] = {
                    'price': price_update.price,
                    'change_pct_24h': price_update.change_24h_pct,
                    'volume': price_update.volume,
                    'high_24h': price_update.high_24h,
                    'low_24h': price_update.low_24h,
                    'bid': price_update.bid,
                    'ask': price_update.ask
                }
        
        return result
    
    def get_all_available_symbols(self) -> List[str]:
        """תאימות אחורה"""
        return self.all_symbols.copy()

# Enhanced run function for the new collector
def run_hybrid_collector(symbols: List[str] = None, api_key: str = None, api_secret: str = None):
    """הפעלת איסוף היברידי עם תמיכה בהגדרות החדשות"""
    
    # קבלת כל הסמלים לפי ההגדרות
    max_symbols = Config.SYMBOL_CONFIG.get('max_symbols', 600)
    all_symbols = symbols or Config.DEFAULT_COINS[:max_symbols]
    
    # Initialize collector
    collector = HybridMarketCollector(
        symbols=all_symbols,  # עכשיו יכול לקבל עד 600 סמלים
        api_key=api_key or Config.get_api_key('KRAKEN_API_KEY'),
        api_secret=api_secret or Config.get_api_key('KRAKEN_API_SECRET')
    )
    
    # Add callback for monitoring
    def on_price_update(price_update: RealTimePriceUpdate):
        # Log every 100th update to avoid spam
        if collector.stats['total_updates'] % 100 == 0:
            logger.info(f"💰 [{collector.stats['total_updates']}] {price_update.symbol}: "
                       f"${price_update.price:,.2f} ({price_update.change_24h_pct:+.2f}%)")
    
    collector.add_data_callback(on_price_update)
    
    try:
        # Start collector
        collector.start()
        
        # Print stats every minute
        while True:
            time.sleep(60)
            stats = collector.get_statistics()
            logger.info(f"📊 Stats: {stats['total_updates']} updates, "
                       f"{stats['updates_per_minute']:.1f}/min, "
                       f"WebSocket: {stats['websocket_status']}, "
                       f"Active: {stats['active_symbols']} symbols")
    
    except KeyboardInterrupt:
        logger.info("⚠️ Stopping collector...")
    
    finally:
        collector.stop()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_hybrid_collector()