import krakenex
import time
from config import KRAKEN_API_KEY, KRAKEN_API_SECRET

class TradingExecutor:
    def __init__(self, mode='real', log_file='data/trading_log.csv'):
        self.api = krakenex.API(KRAKEN_API_KEY, KRAKEN_API_SECRET)
        self.mode = mode  # 'real' or 'demo'
        self.log_file = log_file

    def get_balance(self, asset='ZUSD'):
        try:
            resp = self.api.query_private('Balance')
            return float(resp['result'].get(asset, 0))
        except Exception as e:
            print(f"[שגיאת יתרה] {e}")
            return 0

    def get_price(self, pair):
        try:
            ticker = self.api.query_public('Ticker', {'pair': pair})
            price = float(list(ticker['result'].values())[0]['c'][0])
            return price
        except Exception as e:
            print(f"[שגיאת מחיר] {e}")
            return None

    def convert_usd_to_asset(self, pair, usd_amount):
        price = self.get_price(pair)
        if price is None or price == 0:
            return 0
        return round(usd_amount / price, 8)

    def execute_order(self, pair, action, usd_amount, max_retries=3, ordertype='market'):
        # במצב דמו, רק הדפסה ולוג
        if self.mode == 'demo':
            print(f"[דמו] מבצע {action.upper()} של {usd_amount}$ על {pair}")
            self.log_trade(pair, action, usd_amount, 0, 'demo')
            return {"status": "demo", "pair": pair, "action": action, "usd_amount": usd_amount}

        # חישוב כמות למטבע
        volume = self.convert_usd_to_asset(pair, usd_amount)
        if volume <= 0:
            print(f"[כישלון] לא חושבה כמות חוקית. בדוק את המחיר לזוג {pair}.")
            return {"status": "failed", "reason": "invalid_volume"}

        print(f"🔁 מבצע {action.upper()} {volume} ({usd_amount}$) ב־{pair}")

        for attempt in range(max_retries):
            try:
                order = {
                    'pair': pair,
                    'type': action,
                    'ordertype': ordertype,
                    'volume': str(volume)
                }
                result = self.api.query_private('AddOrder', order)
                if 'error' in result and result['error']:
                    print(f"[נסיון {attempt+1}] שגיאת API: {result['error']}")
                    time.sleep(2)
                    continue
                self.log_trade(pair, action, usd_amount, volume, 'real')
                return result
            except Exception as e:
                print(f"[נסיון {attempt+1}] שגיאה בביצוע הזמנה: {e}")
                time.sleep(2)
        print("[כישלון] כל הנסיונות לבצע את הפעולה נכשלו.")
        return {"status": "failed", "error": "max retries exceeded"}

    def log_trade(self, pair, action, usd_amount, volume, mode):
        import pandas as pd
        from datetime import datetime

        log = {
            'timestamp': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
            'pair': pair,
            'action': action,
            'usd_amount': usd_amount,
            'volume': volume,
            'mode': mode
        }
        try:
            df = pd.DataFrame([log])
            header = not self._log_file_exists()
            df.to_csv(self.log_file, mode='a', index=False, header=header)
        except Exception as e:
            print(f"[שגיאת לוג] {e}")

    def _log_file_exists(self):
        import os
        return os.path.isfile(self.log_file)
