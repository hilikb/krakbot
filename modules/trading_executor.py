import krakenex
import time
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import logging
import json
import os
import sys

# הוספת נתיב למודולים
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config

logger = Config.setup_logging('trading_executor')

class TradingExecutor:
    """מנהל ביצוע פקודות מסחר עם אמצעי בטיחות משופרים"""
    
    def __init__(self, mode: str = 'demo', safety_checks: bool = True):
        """
        mode: 'demo' / 'real' / 'test'
        safety_checks: האם לבצע בדיקות בטיחות לפני ביצוע
        """
        self.mode = mode.lower()
        self.safety_checks = safety_checks
        self.log_file = Config.TRADING_LOG_FILE
        
        # אתחול API רק במצב real
        self.api = None
        if self.mode == 'real' and Config.KRAKEN_API_KEY:
            self.api = krakenex.API(Config.KRAKEN_API_KEY, Config.KRAKEN_API_SECRET)
            logger.info("Trading executor initialized in REAL mode - be careful!")
        else:
            logger.info(f"Trading executor initialized in {self.mode.upper()} mode")
        
        # הגדרות בטיחות
        self.min_order_size = Config.DEFAULT_TRADING_PARAMS.get('min_trade_amount', 10)
        self.max_trade_percent = Config.DEFAULT_TRADING_PARAMS.get('max_trade_percent', 0.25)
        self.daily_loss_limit = 0.1  # 10% הפסד יומי מקסימלי
        
        # מעקב אחר ביצועים
        self.daily_trades = []
        self.daily_pnl = 0
        
    def get_balance(self, asset='ZUSD') -> Dict[str, float]:
        """קבלת יתרות החשבון"""
        if self.mode == 'demo':
            return {
                'USD': 10000.0,
                'BTC': 0.5,
                'ETH': 10.0,
                'SOL': 100.0
            }
        
        if not self.api:
            logger.error("No API connection")
            return {}
        
        try:
            resp = self.api.query_private('Balance')
            
            if resp.get('error'):
                logger.error(f"Balance query error: {resp['error']}")
                return {}
                
            balances = {}
            for asset, amount in resp.get('result', {}).items():
                amount_float = float(amount)
                if amount_float > 0:
                    # נרמול שמות נכסים
                    clean_asset = self._normalize_asset_name(asset)
                    balances[clean_asset] = amount_float
                    
            return balances
            
        except Exception as e:
            logger.error(f"Failed to get balance: {e}")
            return {}
    
    def get_account_balance(self) -> Dict[str, float]:
        """תאימות אחורה - קריאה ל-get_balance"""
        return self.get_balance()
    
    def get_tradable_pairs(self) -> List[str]:
        """קבלת רשימת זוגות מסחר זמינים"""
        if self.mode == 'demo':
            return ['BTCUSD', 'ETHUSD', 'SOLUSD', 'ADAUSD', 'DOTUSD']
        
        if not self.api:
            return []
        
        try:
            resp = self.api.query_public('AssetPairs')
            
            if resp.get('error'):
                logger.error(f"AssetPairs query error: {resp['error']}")
                return []
                
            pairs = []
            for pair, info in resp.get('result', {}).items():
                if info.get('status') == 'online' and 'USD' in pair:
                    pairs.append(pair)
                    
            return sorted(pairs)
            
        except Exception as e:
            logger.error(f"Failed to get tradable pairs: {e}")
            return []
    
    def get_ticker_info(self, pair: str) -> Dict[str, float]:
        """קבלת מידע על זוג מסחר"""
        if self.mode == 'demo':
            # מחירי דמו
            demo_prices = {
                'BTCUSD': {'price': 45000, 'bid': 44990, 'ask': 45010, 'spread': 20},
                'ETHUSD': {'price': 2500, 'bid': 2498, 'ask': 2502, 'spread': 4},
                'SOLUSD': {'price': 100, 'bid': 99.9, 'ask': 100.1, 'spread': 0.2}
            }
            return demo_prices.get(pair, {'price': 100, 'bid': 99, 'ask': 101, 'spread': 2})
        
        if not self.api:
            return {}
        
        try:
            resp = self.api.query_public('Ticker', {'pair': pair})
            
            if resp.get('error'):
                logger.error(f"Ticker query error: {resp['error']}")
                return {}
                
            ticker_data = list(resp.get('result', {}).values())[0]
            
            return {
                'price': float(ticker_data['c'][0]),
                'bid': float(ticker_data['b'][0]),
                'ask': float(ticker_data['a'][0]),
                'spread': float(ticker_data['a'][0]) - float(ticker_data['b'][0]),
                'volume': float(ticker_data['v'][1]),
                'high': float(ticker_data['h'][1]),
                'low': float(ticker_data['l'][1])
            }
            
        except Exception as e:
            logger.error(f"Failed to get ticker info: {e}")
            return {}
    
    def validate_order(self, pair: str, side: str, amount_usd: float) -> Tuple[bool, str]:
        """בדיקת תקינות פקודה לפני ביצוע"""
        
        # בדיקת סכום מינימלי
        if amount_usd < self.min_order_size:
            return False, f"Order size ${amount_usd} below minimum ${self.min_order_size}"
        
        # בדיקת יתרה
        balances = self.get_account_balance()
        usd_balance = balances.get('USD', 0)
        
        if side == 'buy' and amount_usd > usd_balance:
            return False, f"Insufficient USD balance: ${usd_balance:.2f}"
        
        # בדיקת אחוז מקסימלי מהיתרה
        if usd_balance > 0:
            trade_percent = amount_usd / usd_balance
            if trade_percent > self.max_trade_percent:
                return False, f"Trade size {trade_percent*100:.1f}% exceeds max {self.max_trade_percent*100}%"
        
        # בדיקת הגבלת הפסד יומי
        if self.safety_checks and self.daily_pnl < -self.daily_loss_limit * usd_balance:
            return False, f"Daily loss limit reached: ${self.daily_pnl:.2f}"
        
        # בדיקת זוג מסחר תקין
        valid_pairs = self.get_tradable_pairs()
        if valid_pairs and pair not in valid_pairs:
            return False, f"Invalid trading pair: {pair}"
        
        return True, "Order validated"
    
    def execute_market_order(self, 
                           pair: str, 
                           side: str, 
                           amount_usd: float,
                           slippage_tolerance: float = 0.01) -> Dict:
        """ביצוע פקודת שוק"""
        
        # בדיקת תקינות
        if self.safety_checks:
            is_valid, message = self.validate_order(pair, side, amount_usd)
            if not is_valid:
                logger.warning(f"Order validation failed: {message}")
                return {
                    'status': 'rejected',
                    'error': message,
                    'pair': pair,
                    'side': side,
                    'amount_usd': amount_usd
                }
        
        # קבלת מחיר נוכחי
        ticker = self.get_ticker_info(pair)
        if not ticker:
            return {'status': 'failed', 'error': 'Cannot get ticker info'}
        
        # חישוב כמות
        price = ticker['ask'] if side == 'buy' else ticker['bid']
        volume = amount_usd / price
        
        # מצב דמו
        if self.mode == 'demo':
            result = {
                'status': 'success',
                'mode': 'demo',
                'order_id': f"DEMO_{int(time.time())}",
                'pair': pair,
                'side': side,
                'price': price,
                'volume': volume,
                'amount_usd': amount_usd,
                'fee': amount_usd * 0.0026,  # 0.26% Kraken maker fee
                'timestamp': datetime.utcnow()
            }
            
            logger.info(f"[DEMO] Executed {side} {volume:.8f} {pair} @ ${price:.2f}")
            self._log_trade(result)
            return result
        
        # מצב בדיקה
        if self.mode == 'test':
            result = {
                'status': 'test',
                'message': 'Order validated but not executed (test mode)',
                'pair': pair,
                'side': side,
                'price': price,
                'volume': volume,
                'amount_usd': amount_usd
            }
            return result
        
        # מצב אמיתי
        if self.mode == 'real' and self.api:
            try:
                # הכנת פרמטרי פקודה
                order_params = {
                    'pair': pair,
                    'type': side,
                    'ordertype': 'market',
                    'volume': str(volume),
                    'validate': False  # ביצוע אמיתי
                }
                
                # ביצוע
                resp = self.api.query_private('AddOrder', order_params)
                
                if resp.get('error'):
                    error_msg = ', '.join(resp['error'])
                    logger.error(f"Order execution error: {error_msg}")
                    return {
                        'status': 'failed',
                        'error': error_msg,
                        'pair': pair,
                        'side': side,
                        'amount_usd': amount_usd
                    }
                
                # פקודה הצליחה
                result_data = resp.get('result', {})
                order_id = result_data.get('txid', [None])[0]
                
                result = {
                    'status': 'success',
                    'mode': 'real',
                    'order_id': order_id,
                    'pair': pair,
                    'side': side,
                    'price': price,
                    'volume': volume,
                    'amount_usd': amount_usd,
                    'timestamp': datetime.utcnow(),
                    'description': result_data.get('descr', {})
                }
                
                logger.info(f"[REAL] Order executed: {order_id}")
                self._log_trade(result)
                
                # עדכון PnL יומי (משוער)
                if side == 'sell':
                    self.daily_pnl += amount_usd * 0.01  # הערכה גסה
                
                return result
                
            except Exception as e:
                logger.error(f"Order execution exception: {e}", exc_info=True)
                return {
                    'status': 'failed',
                    'error': str(e),
                    'pair': pair,
                    'side': side,
                    'amount_usd': amount_usd
                }
        
        return {'status': 'failed', 'error': 'Invalid mode or no API connection'}
    
    def execute_limit_order(self,
                          pair: str,
                          side: str,
                          price: float,
                          amount_usd: float,
                          time_in_force: str = 'GTC') -> Dict:
        """ביצוע פקודת limit"""
        
        # חישוב כמות
        volume = amount_usd / price
        
        # מצב דמו
        if self.mode == 'demo':
            result = {
                'status': 'success',
                'mode': 'demo',
                'order_id': f"DEMO_LIMIT_{int(time.time())}",
                'order_type': 'limit',
                'pair': pair,
                'side': side,
                'price': price,
                'volume': volume,
                'amount_usd': amount_usd,
                'time_in_force': time_in_force,
                'timestamp': datetime.utcnow()
            }
            
            logger.info(f"[DEMO] Placed limit {side} {volume:.8f} {pair} @ ${price:.2f}")
            self._log_trade(result)
            return result
        
        # TODO: מימוש למצב real
        return {'status': 'not_implemented', 'error': 'Limit orders not yet implemented for real mode'}
    
    def cancel_order(self, order_id: str) -> Dict:
        """ביטול פקודה פתוחה"""
        if self.mode == 'demo':
            logger.info(f"[DEMO] Cancelled order {order_id}")
            return {'status': 'success', 'cancelled': order_id}
        
        if self.mode == 'real' and self.api:
            try:
                resp = self.api.query_private('CancelOrder', {'txid': order_id})
                
                if resp.get('error'):
                    return {'status': 'failed', 'error': resp['error']}
                    
                return {'status': 'success', 'cancelled': order_id}
                
            except Exception as e:
                logger.error(f"Cancel order error: {e}")
                return {'status': 'failed', 'error': str(e)}
        
        return {'status': 'failed', 'error': 'Invalid mode'}
    
    def get_open_orders(self) -> List[Dict]:
        """קבלת פקודות פתוחות"""
        if self.mode == 'demo':
            return []  # אין פקודות פתוחות בדמו
        
        if self.mode == 'real' and self.api:
            try:
                resp = self.api.query_private('OpenOrders')
                
                if resp.get('error'):
                    logger.error(f"Open orders query error: {resp['error']}")
                    return []
                
                orders = []
                for order_id, order_data in resp.get('result', {}).get('open', {}).items():
                    orders.append({
                        'order_id': order_id,
                        'pair': order_data.get('descr', {}).get('pair'),
                        'side': order_data.get('descr', {}).get('type'),
                        'price': float(order_data.get('descr', {}).get('price', 0)),
                        'volume': float(order_data.get('vol', 0)),
                        'executed': float(order_data.get('vol_exec', 0)),
                        'status': order_data.get('status'),
                        'timestamp': order_data.get('opentm')
                    })
                
                return orders
                
            except Exception as e:
                logger.error(f"Failed to get open orders: {e}")
                return []
        
        return []
    
    def get_trade_history(self, hours: int = 24) -> pd.DataFrame:
        """קבלת היסטוריית מסחר"""
        try:
            if os.path.exists(self.log_file):
                df = pd.read_csv(self.log_file)
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                
                # סינון לפי זמן
                cutoff = datetime.utcnow() - pd.Timedelta(hours=hours)
                df = df[df['timestamp'] > cutoff]
                
                return df
            else:
                return pd.DataFrame()
                
        except Exception as e:
            logger.error(f"Failed to load trade history: {e}")
            return pd.DataFrame()
    
    def _log_trade(self, trade_data: Dict):
        """רישום עסקה ללוג"""
        try:
            # הכנת נתונים לשמירה
            log_entry = {
                'timestamp': trade_data.get('timestamp', datetime.utcnow()),
                'mode': trade_data.get('mode', self.mode),
                'order_id': trade_data.get('order_id'),
                'pair': trade_data.get('pair'),
                'side': trade_data.get('side'),
                'price': trade_data.get('price'),
                'volume': trade_data.get('volume'),
                'amount_usd': trade_data.get('amount_usd'),
                'fee': trade_data.get('fee', 0),
                'status': trade_data.get('status')
            }
            
            # שמירה ל-CSV
            df = pd.DataFrame([log_entry])
            header = not os.path.exists(self.log_file)
            df.to_csv(self.log_file, mode='a', header=header, index=False)
            
            # עדכון רשימת עסקאות יומיות
            self.daily_trades.append(log_entry)
            
        except Exception as e:
            logger.error(f"Failed to log trade: {e}")
    
    def _normalize_asset_name(self, asset: str) -> str:
        """נרמול שמות נכסים של Kraken"""
        replacements = {
            'XXBT': 'BTC',
            'XBT': 'BTC',
            'XETH': 'ETH',
            'XXRP': 'XRP',
            'ZUSD': 'USD',
            'ZEUR': 'EUR'
        }
        
        cleaned = asset.upper()
        for old, new in replacements.items():
            if cleaned.startswith(old):
                cleaned = cleaned.replace(old, new, 1)
                
        return cleaned
    
    def get_performance_summary(self) -> Dict:
        """סיכום ביצועים"""
        history = self.get_trade_history(hours=24*7)  # שבוע אחרון
        
        if history.empty:
            return {
                'total_trades': 0,
                'success_rate': 0,
                'total_volume': 0,
                'total_fees': 0
            }
        
        return {
            'total_trades': len(history),
            'success_rate': (history['status'] == 'success').mean() * 100,
            'total_volume': history['amount_usd'].sum(),
            'total_fees': history['fee'].sum(),
            'avg_trade_size': history['amount_usd'].mean(),
            'most_traded': history['pair'].mode().iloc[0] if not history.empty else 'N/A'
        }


def interactive_trading_demo():
    """הדגמה אינטראקטיבית של מערכת המסחר"""
    print("\n💹 Trading Executor Demo")
    print("="*40)
    
    # בחירת מצב
    print("\nבחר מצב הפעלה:")
    print("1. Demo - סימולציה בלבד")
    print("2. Test - בדיקות ללא ביצוע")
    print("3. Real - מסחר אמיתי (זהירות!)")
    
    mode_choice = input("\nבחירה (1-3): ")
    mode_map = {'1': 'demo', '2': 'test', '3': 'real'}
    mode = mode_map.get(mode_choice, 'demo')
    
    if mode == 'real':
        confirm = input("\n⚠️  אזהרה: מצב REAL יבצע עסקאות אמיתיות! להמשיך? (yes/no): ")
        if confirm.lower() != 'yes':
            print("ביטול - חוזר למצב demo")
            mode = 'demo'
    
    # יצירת executor
    executor = TradingExecutor(mode=mode)
    
    while True:
        print(f"\n📊 Trading Menu (Mode: {mode.upper()})")
        print("="*40)
        print("1. הצג יתרות")
        print("2. הצג זוגות מסחר")
        print("3. הצג מחיר נוכחי")
        print("4. בצע פקודת שוק")
        print("5. הצג פקודות פתוחות")
        print("6. הצג היסטוריה")
        print("7. סיכום ביצועים")
        print("q. יציאה")
        
        choice = input("\nבחירה: ").lower()
        
        if choice == '1':
            # יתרות
            balances = executor.get_account_balance()
            print("\n💰 יתרות:")
            for asset, amount in balances.items():
                print(f"  {asset}: {amount:.8f}")
                
        elif choice == '2':
            # זוגות מסחר
            pairs = executor.get_tradable_pairs()
            print(f"\n🔄 זוגות מסחר ({len(pairs)}):")
            for i, pair in enumerate(pairs[:10], 1):
                print(f"  {i}. {pair}")
            if len(pairs) > 10:
                print(f"  ... ועוד {len(pairs)-10}")
                
        elif choice == '3':
            # מחיר נוכחי
            pair = input("\nזוג מסחר (לדוגמה BTCUSD): ").upper()
            ticker = executor.get_ticker_info(pair)
            
            if ticker:
                print(f"\n📈 {pair}:")
                print(f"  מחיר: ${ticker['price']:,.2f}")
                print(f"  Bid: ${ticker['bid']:,.2f}")
                print(f"  Ask: ${ticker['ask']:,.2f}")
                print(f"  Spread: ${ticker['spread']:.2f}")
            else:
                print("❌ לא נמצא מידע")
                
        elif choice == '4':
            # ביצוע פקודה
            pair = input("\nזוג מסחר: ").upper()
            side = input("כיוון (buy/sell): ").lower()
            amount = float(input("סכום בדולרים: "))
            
            print(f"\n⏳ מבצע פקודת {side} ${amount} {pair}...")
            result = executor.execute_market_order(pair, side, amount)
            
            print(f"\nתוצאה: {result['status']}")
            if result['status'] == 'success':
                print(f"  Order ID: {result['order_id']}")
                print(f"  מחיר: ${result['price']:,.2f}")
                print(f"  כמות: {result['volume']:.8f}")
            else:
                print(f"  שגיאה: {result.get('error', 'Unknown')}")
                
        elif choice == '5':
            # פקודות פתוחות
            orders = executor.get_open_orders()
            print(f"\n📋 פקודות פתוחות ({len(orders)}):")
            for order in orders:
                print(f"  {order['order_id']}: {order['side']} {order['volume']} {order['pair']} @ ${order['price']}")
                
        elif choice == '6':
            # היסטוריה
            history = executor.get_trade_history(hours=24)
            if not history.empty:
                print(f"\n📜 היסטוריה (24 שעות אחרונות):")
                print(history[['timestamp', 'pair', 'side', 'amount_usd', 'status']].to_string(index=False))
            else:
                print("\n📜 אין היסטוריית מסחר")
                
        elif choice == '7':
            # סיכום ביצועים
            summary = executor.get_performance_summary()
            print("\n📊 סיכום ביצועים:")
            print(f"  סה״כ עסקאות: {summary['total_trades']}")
            print(f"  אחוז הצלחה: {summary['success_rate']:.1f}%")
            print(f"  נפח כולל: ${summary['total_volume']:,.2f}")
            print(f"  עמלות: ${summary['total_fees']:.2f}")
            print(f"  גודל עסקה ממוצע: ${summary.get('avg_trade_size', 0):,.2f}")
            print(f"  הזוג הנסחר ביותר: {summary.get('most_traded', 'N/A')}")
                
        elif choice == 'q':
            print("\n👋 להתראות!")
            break
        else:
            print("❌ בחירה לא תקינה")


if __name__ == "__main__":
    interactive_trading_demo()