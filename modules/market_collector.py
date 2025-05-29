import os
import sys
import pandas as pd
import time
from datetime import datetime, timedelta
import krakenex
from typing import Dict, List, Optional, Tuple
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

# הוספת נתיב למודולים
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config

logger = Config.setup_logging('market_collector')

class MarketCollector:
    """איסוף נתוני שוק משופר עם תמיכה ב-Kraken ו-fallback"""
    
    def __init__(self, use_kraken: bool = True, use_binance: bool = True):
        self.use_kraken = use_kraken and Config.KRAKEN_API_KEY
        self.use_binance = use_binance
        
        # אתחול APIs
        self.kraken_api = None
        if self.use_kraken:
            self.kraken_api = krakenex.API(Config.KRAKEN_API_KEY, Config.KRAKEN_API_SECRET)
            
        self.binance_client = None
        if self.use_binance:
            try:
                from binance.client import Client
                self.binance_client = Client()
            except ImportError:
                logger.warning("Binance client not installed, using Kraken only")
                self.use_binance = False
        
        # קבצי נתונים
        self.live_file = Config.MARKET_LIVE_FILE
        self.history_file = Config.MARKET_HISTORY_FILE
        
        # cache לאופטימיזציה
        self.last_prices = {}
        self.error_count = {}
        
    def get_kraken_prices(self, symbols: Optional[List[str]] = None) -> Dict[str, Dict]:
        """שליפת מחירים מ-Kraken"""
        if not self.kraken_api:
            return {}
            
        try:
            # שליפת כל המחירים בקריאה אחת
            ticker_resp = self.kraken_api.query_public('Ticker')
            
            if ticker_resp.get('error'):
                logger.error(f"Kraken API error: {ticker_resp['error']}")
                return {}
                
            results = {}
            ticker_data = ticker_resp.get('result', {})
            
            for pair, data in ticker_data.items():
                # המרת שם הזוג לפורמט סטנדרטי
                if 'USD' in pair:
                    symbol = self._normalize_kraken_symbol(pair)
                    
                    if symbols and symbol not in symbols:
                        continue
                        
                    try:
                        # בדיקה שכל הערכים קיימים
                        current_price = float(data.get('c', [0])[0])
                        open_price = float(data.get('o', current_price))
                        
                        # הגנה מפני חלוקה באפס
                        if open_price != 0:
                            change_pct = ((current_price - open_price) / open_price) * 100
                        else:
                            change_pct = 0
                            
                        results[symbol] = {
                            'price': current_price,
                            'volume': float(data.get('v', [0, 0])[1]),
                            'high_24h': float(data.get('h', [0, current_price])[1]),
                            'low_24h': float(data.get('l', [0, current_price])[1]),
                            'change_24h': current_price - open_price,
                            'change_pct_24h': change_pct,
                            'bid': float(data.get('b', [current_price])[0]),
                            'ask': float(data.get('a', [current_price])[0]),
                            'spread': float(data.get('a', [0])[0]) - float(data.get('b', [0])[0]),
                            'trades_24h': int(data.get('t', [0, 0])[1]),
                            'source': 'kraken'
                        }
                    except (KeyError, ValueError, IndexError) as e:
                        logger.warning(f"Error parsing Kraken data for {pair}: {e}")
                        
            return results
            
        except Exception as e:
            logger.error(f"Kraken prices fetch error: {e}")
            return {}
    
    def get_binance_prices(self, symbols: Optional[List[str]] = None) -> Dict[str, Dict]:
        """שליפת מחירים מ-Binance כ-fallback"""
        if not self.binance_client:
            return {}
            
        try:
            # שליפת ticker 24h
            ticker_24h = self.binance_client.get_ticker()
            
            results = {}
            for ticker in ticker_24h:
                symbol_pair = ticker['symbol']
                
                if symbol_pair.endswith('USDT'):
                    symbol = symbol_pair.replace('USDT', '')
                    
                    if symbols and symbol not in symbols:
                        continue
                        
                    try:
                        results[symbol] = {
                            'price': float(ticker['lastPrice']),
                            'volume': float(ticker['volume']),
                            'high_24h': float(ticker['highPrice']),
                            'low_24h': float(ticker['lowPrice']),
                            'change_24h': float(ticker['priceChange']),
                            'change_pct_24h': float(ticker['priceChangePercent']),
                            'bid': float(ticker['bidPrice']),
                            'ask': float(ticker['askPrice']),
                            'spread': float(ticker['askPrice']) - float(ticker['bidPrice']),
                            'trades_24h': int(ticker['count']),
                            'source': 'binance'
                        }
                    except (KeyError, ValueError) as e:
                        logger.warning(f"Error parsing Binance data for {symbol_pair}: {e}")
                        
            return results
            
        except Exception as e:
            logger.error(f"Binance prices fetch error: {e}")
            return {}
    
    def get_combined_prices(self, symbols: Optional[List[str]] = None) -> Dict[str, Dict]:
        """שליפת מחירים משולבת עם עדיפות ל-Kraken"""
        all_prices = {}
        
        # נסה קודם Kraken
        if self.use_kraken:
            kraken_prices = self.get_kraken_prices(symbols)
            all_prices.update(kraken_prices)
            logger.info(f"Got {len(kraken_prices)} prices from Kraken")
        
        # השלם עם Binance למטבעות חסרים
        if self.use_binance:
            missing_symbols = None
            if symbols:
                missing_symbols = [s for s in symbols if s not in all_prices]
                
            if not symbols or missing_symbols:
                binance_prices = self.get_binance_prices(missing_symbols)
                
                # הוסף רק מטבעות שלא קיימים
                for symbol, data in binance_prices.items():
                    if symbol not in all_prices:
                        all_prices[symbol] = data
                        
                logger.info(f"Added {len(binance_prices)} prices from Binance")
        
        return all_prices
    
    def get_all_available_symbols(self) -> List[str]:
        """קבלת כל המטבעות הזמינים ב-Kraken"""
        if not self.kraken_api:
            return Config.DEFAULT_COINS
    
        try:
            # שליפת כל הזוגות
            resp = self.kraken_api.query_public('AssetPairs')
            if resp.get('error'):
                logger.error(f"Error getting pairs: {resp['error']}")
                return Config.DEFAULT_COINS
        
            symbols = set()
            for pair, info in resp.get('result', {}).items():
                # רק זוגות עם USD שפעילים
                if 'USD' in pair and info.get('status') == 'online':
                    # נקה את הסמל
                    symbol = self._normalize_kraken_symbol(pair)
                    if symbol not in ['USD', 'EUR', 'GBP']:  # לא מטבעות פיאט
                        symbols.add(symbol)
        
            # החזר רשימה ממוינת
            return sorted(list(symbols))
    
        except Exception as e:
            logger.error(f"Error getting symbols: {e}")
            return Config.DEFAULT_COINS
            
    def collect_market_data(self, symbols: Optional[List[str]] = None) -> pd.DataFrame:
        """איסוף נתוני שוק מלאים"""
        if symbols is None:
            symbols = Config.DEFAULT_COINS
            
        # שליפת מחירים
        prices_data = self.get_combined_prices(symbols)
        
        if not prices_data:
            logger.error("No price data collected")
            return pd.DataFrame()
        
        # המרה ל-DataFrame
        timestamp = datetime.utcnow()
        data_rows = []
        
        for symbol, data in prices_data.items():
            row = {
                'timestamp': timestamp,
                'pair': f"{symbol}USD",
                'symbol': symbol,
                'price': data['price'],
                'volume': data['volume'],
                'high_24h': data['high_24h'],
                'low_24h': data['low_24h'],
                'change_24h': data.get('change_24h', 0),
                'change_pct_24h': data.get('change_pct_24h', 0),
                'bid': data.get('bid', data['price']),
                'ask': data.get('ask', data['price']),
                'spread': data.get('spread', 0),
                'trades_24h': data.get('trades_24h', 0),
                'source': data['source']
            }
            
            # בדיקת שינוי ממשי מהמחיר האחרון
            last_price = self.last_prices.get(symbol, 0)
            if last_price > 0:
                row['price_change'] = data['price'] - last_price
                row['price_change_pct'] = ((data['price'] - last_price) / last_price) * 100
            else:
                row['price_change'] = 0
                row['price_change_pct'] = 0
                
            self.last_prices[symbol] = data['price']
            data_rows.append(row)
        
        df = pd.DataFrame(data_rows)
        
        # הוספת מידע נוסף
        df['collection_time'] = datetime.utcnow()
        df['day_of_week'] = df['timestamp'].dt.day_name()
        df['hour'] = df['timestamp'].dt.hour
        
        return df
    
    def save_data(self, df: pd.DataFrame):
        """שמירת נתונים לקבצים"""
        if df.empty:
            return
            
        # שמירה לקובץ live (דריסה)
        df.to_csv(self.live_file, index=False, encoding='utf-8')
        logger.info(f"Saved {len(df)} records to live file")
        
        # הוספה להיסטוריה
        if os.path.exists(self.history_file):
            # בדיקה שאין כפילויות
            try:
                history_df = pd.read_csv(self.history_file, parse_dates=['timestamp'])
                
                # סינון רק שורות חדשות
                last_timestamp = history_df['timestamp'].max()
                new_rows = df[df['timestamp'] > last_timestamp]
                
                if not new_rows.empty:
                    new_rows.to_csv(self.history_file, mode='a', header=False, index=False, encoding='utf-8')
                    logger.info(f"Added {len(new_rows)} new records to history")
                    
            except Exception as e:
                logger.error(f"Error updating history: {e}")
        else:
            # יצירת קובץ היסטוריה חדש
            df.to_csv(self.history_file, index=False, encoding='utf-8')
            logger.info("Created new history file")
    
    def clean_history(self, days_to_keep: int = 90):
        """ניקוי נתונים ישנים מההיסטוריה"""
        if not os.path.exists(self.history_file):
            return
            
        try:
            df = pd.read_csv(self.history_file, parse_dates=['timestamp'])
            cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
            
            # סינון נתונים חדשים
            df_clean = df[df['timestamp'] > cutoff_date]
            
            # שמירה מחדש
            if len(df_clean) < len(df):
                df_clean.to_csv(self.history_file, index=False, encoding='utf-8')
                logger.info(f"Cleaned history: removed {len(df) - len(df_clean)} old records")
                
        except Exception as e:
            logger.error(f"Error cleaning history: {e}")
    
    def get_market_summary(self) -> Dict:
        """יצירת סיכום שוק"""
        prices = self.get_combined_prices()
        
        if not prices:
            return {}
            
        # חישוב סטטיסטיקות
        total_volume = sum(p['volume'] for p in prices.values())
        avg_change = sum(p['change_pct_24h'] for p in prices.values()) / len(prices)
        
        gainers = sorted(
            [(s, p['change_pct_24h']) for s, p in prices.items() if p['change_pct_24h'] > 0],
            key=lambda x: x[1],
            reverse=True
        )[:5]
        
        losers = sorted(
            [(s, p['change_pct_24h']) for s, p in prices.items() if p['change_pct_24h'] < 0],
            key=lambda x: x[1]
        )[:5]
        
        return {
            'timestamp': datetime.utcnow(),
            'total_symbols': len(prices),
            'total_volume_24h': total_volume,
            'avg_change_24h': avg_change,
            'top_gainers': gainers,
            'top_losers': losers,
            'market_sentiment': 'bullish' if avg_change > 0 else 'bearish'
        }
    
    def _normalize_kraken_symbol(self, pair: str) -> str:
        """נרמול סמלי Kraken לפורמט סטנדרטי"""
        # הסרת USD/ZUSD מהסוף
        cleaned = pair.replace('USD', '').replace('ZUSD', '')
        
        # הסרת סיומות (.S = Staked, .F = Futures, .B = Bond, .M = Multi-collateral)
        if '.' in cleaned:
            cleaned = cleaned.split('.')[0]
        
        # הסרת תווים מיוחדים של Kraken
        cleaned = cleaned.replace('X', '').replace('Z', '')
        
        # המרות ספציפיות
        replacements = {
            'XBT': 'BTC',
            'XETH': 'ETH',
            'XXRP': 'XRP',
            'XLTC': 'LTC',
            'XXLM': 'XLM',
            'XDOGE': 'DOGE',
            'XETC': 'ETC',
            'XMLN': 'MLN',
            'XREP': 'REP',
            'XXMR': 'XMR',
            'XXTZ': 'XTZ',
            'XZEC': 'ZEC',
            'XICN': 'ICN',
            'XLTC': 'LTC',
            'XNMC': 'NMC',
            'XXDG': 'XDG',
            'XXLM': 'XLM',
            'XXRP': 'XRP',
            'XXVN': 'XVN',
            # Staking variants
            'ADAXS': 'ADA',
            'ATOMXS': 'ATOM',
            'DOTXS': 'DOT',
            'FLOWHS': 'FLOW',
            'KSMXS': 'KSM',
            'SCRTBS': 'SCRT',
            'SOLXS': 'SOL',
            'MATICXS': 'MATIC',
            'USDCM': 'USDC',
            'USDTM': 'USDT',
            'ETHW': 'ETH',
            'LUNA2': 'LUNA',
            'LUNA': 'LUNC',
        }
        
        # החלפה לפי המילון
        for old, new in replacements.items():
            if cleaned == old or cleaned.startswith(old):
                return new
        
        return cleaned


def run_collector(interval: int = 30):
    """הפעלת לולאת איסוף נתונים"""
    collector = MarketCollector()
    
    logger.info(f"Market collector started - interval: {interval}s")
    logger.info(f"Using: Kraken={collector.use_kraken}, Binance={collector.use_binance}")
    
    # ניקוי היסטוריה בהפעלה
    collector.clean_history()
    
    error_count = 0
    max_errors = 10
    
    while True:
        try:
            start_time = time.time()
            
            # איסוף נתונים
            df = collector.collect_market_data()
            
            if not df.empty:
                # שמירה
                collector.save_data(df)
                
                # הצגת סיכום
                summary = collector.get_market_summary()
                logger.info(
                    f"Collected {summary['total_symbols']} symbols | "
                    f"Market: {summary['market_sentiment']} ({summary['avg_change_24h']:.2f}%)"
                )
                
                # איפוס מונה שגיאות
                error_count = 0
            else:
                logger.warning("No data collected in this cycle")
                
            # חישוב זמן המתנה
            elapsed = time.time() - start_time
            sleep_time = max(0, interval - elapsed)
            
            if sleep_time > 0:
                logger.debug(f"Sleeping for {sleep_time:.1f}s")
                time.sleep(sleep_time)
                
        except KeyboardInterrupt:
            logger.info("Market collector stopped by user")
            break
            
        except Exception as e:
            error_count += 1
            logger.error(f"Collection error ({error_count}/{max_errors}): {e}", exc_info=True)
            
            if error_count >= max_errors:
                logger.critical("Too many errors, stopping collector")
                break
                
            # המתנה מוגברת לאחר שגיאה
            time.sleep(min(interval * 2, 300))
    
    logger.info("Market collector shutdown complete")


def test_collector():
    """בדיקת איסוף נתונים"""
    print("\n🧪 בודק איסוף נתוני שוק...")
    print("="*50)
    
    collector = MarketCollector()
    
    # בדיקת זמינות APIs
    print("\n📡 בדיקת חיבורים:")
    print(f"  • Kraken API: {'✅ זמין' if collector.use_kraken else '❌ לא זמין'}")
    print(f"  • Binance API: {'✅ זמין' if collector.use_binance else '❌ לא זמין'}")
    
    # בדיקת איסוף
    print("\n📊 בודק איסוף נתונים...")
    test_symbols = ['BTC', 'ETH', 'SOL']
    
    # Kraken
    if collector.use_kraken:
        kraken_prices = collector.get_kraken_prices(test_symbols)
        print(f"\nKraken - נמצאו {len(kraken_prices)} מחירים:")
        for symbol, data in kraken_prices.items():
            print(f"  • {symbol}: ${data['price']:,.2f} ({data['change_pct_24h']:+.2f}%)")
    
    # Binance
    if collector.use_binance:
        binance_prices = collector.get_binance_prices(test_symbols)
        print(f"\nBinance - נמצאו {len(binance_prices)} מחירים:")
        for symbol, data in binance_prices.items():
            print(f"  • {symbol}: ${data['price']:,.2f} ({data['change_pct_24h']:+.2f}%)")
    
    # איסוף משולב
    print("\n🔄 בודק איסוף משולב...")
    df = collector.collect_market_data(test_symbols)
    
    if not df.empty:
        print(f"\n✅ נאספו {len(df)} רשומות:")
        print(df[['symbol', 'price', 'change_pct_24h', 'volume', 'source']].to_string(index=False))
        
        # סיכום שוק
        summary = collector.get_market_summary()
        print(f"\n📈 סיכום שוק:")
        print(f"  • סנטימנט: {summary['market_sentiment']}")
        print(f"  • שינוי ממוצע: {summary['avg_change_24h']:.2f}%")
        
        if summary['top_gainers']:
            print(f"\n🚀 עליות חדות:")
            for symbol, change in summary['top_gainers'][:3]:
                print(f"  • {symbol}: +{change:.2f}%")
    else:
        print("\n❌ לא נאספו נתונים")
    
    print("\n✅ הבדיקה הושלמה")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Market Data Collector')
    parser.add_argument('--test', action='store_true', help='Run test mode')
    parser.add_argument('--interval', type=int, default=30, help='Collection interval in seconds')
    parser.add_argument('--symbols', nargs='+', help='Specific symbols to collect')
    
    args = parser.parse_args()
    
    if args.test:
        test_collector()
    else:
        # הפעלת איסוף רגיל
        print(f"Starting market collector (interval: {args.interval}s)")
        print("Press Ctrl+C to stop")
        
        try:
            run_collector(interval=args.interval)
        except KeyboardInterrupt:
            print("\n👋 Market collector stopped")