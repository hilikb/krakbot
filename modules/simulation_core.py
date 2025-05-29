import pandas as pd
import numpy as np
from itertools import product
import os
from ta.momentum import RSIIndicator
from ta.trend import SMAIndicator, EMAIndicator, MACD
from ta.volatility import BollingerBands

# ---- הגדרות נתיבים ----
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')
HISTORY_FILE = os.path.join(DATA_DIR, 'market_history.csv')
LIVE_FILE = os.path.join(DATA_DIR, 'market_live.csv')

class SimulationEngine:
    def __init__(self, initial_balance=1000, take_profit=0.1, stop_loss=0.05, max_positions=2):
        self.initial_balance = initial_balance
        self.take_profit = take_profit
        self.stop_loss = stop_loss
        self.max_positions = max_positions
        self.reset()

    def reset(self):
        self.balance = self.initial_balance
        self.positions = []  # פוזיציות פתוחות: כל אחת dict עם price, amount, entry_time
        self.trade_log = []

    def apply_indicators(self, df):
        df = df.copy()
        try:
            df['rsi'] = RSIIndicator(close=df['price'], window=14).rsi()
        except Exception:
            df['rsi'] = np.nan
        try:
            df['sma_short'] = SMAIndicator(close=df['price'], window=20).sma_indicator()
            df['sma_long'] = SMAIndicator(close=df['price'], window=50).sma_indicator()
        except Exception:
            df['sma_short'] = np.nan
            df['sma_long'] = np.nan
        try:
            df['ema_fast'] = EMAIndicator(close=df['price'], window=12).ema_indicator()
            df['ema_slow'] = EMAIndicator(close=df['price'], window=26).ema_indicator()
        except Exception:
            df['ema_fast'] = np.nan
            df['ema_slow'] = np.nan
        try:
            macd = MACD(close=df['price'], window_slow=26, window_fast=12, window_sign=9)
            df['macd'] = macd.macd()
            df['macd_signal'] = macd.macd_signal()
        except Exception:
            df['macd'] = np.nan
            df['macd_signal'] = np.nan
        try:
            bb = BollingerBands(close=df['price'], window=20, window_dev=2)
            df['bb_high'] = bb.bollinger_hband()
            df['bb_low'] = bb.bollinger_lband()
        except Exception:
            df['bb_high'] = np.nan
            df['bb_low'] = np.nan
        return df

    def determine_action(self, row, strategy='combined'):
        def rsi_strat(row):
            if pd.isna(row['rsi']):
                return 'hold'
            if row['rsi'] < 30:
                return 'long'
            elif row['rsi'] > 70:
                return 'short'
            return 'hold'

        def ema_strat(row):
            if pd.isna(row.get('ema_fast')) or pd.isna(row.get('ema_slow')):
                return 'hold'
            if row['ema_fast'] > row['ema_slow']:
                return 'long'
            elif row['ema_fast'] < row['ema_slow']:
                return 'short'
            return 'hold'

        def macd_strat(row):
            if pd.isna(row.get('macd')) or pd.isna(row.get('macd_signal')):
                return 'hold'
            if row['macd'] > row['macd_signal']:
                return 'long'
            elif row['macd'] < row['macd_signal']:
                return 'short'
            return 'hold'

        def bollinger_strat(row):
            if pd.isna(row.get('bb_high')) or pd.isna(row.get('bb_low')):
                return 'hold'
            if row['price'] < row['bb_low']:
                return 'long'
            elif row['price'] > row['bb_high']:
                return 'short'
            return 'hold'

        def sma_strat(row):
            if pd.isna(row['sma_short']) or pd.isna(row['sma_long']):
                return 'hold'
            if row['sma_short'] > row['sma_long']:
                return 'long'
            elif row['sma_short'] < row['sma_long']:
                return 'short'
            return 'hold'

        if strategy == 'rsi':
            return rsi_strat(row)
        elif strategy == 'ema':
            return ema_strat(row)
        elif strategy == 'macd':
            return macd_strat(row)
        elif strategy == 'bollinger':
            return bollinger_strat(row)
        elif strategy == 'sma':
            return sma_strat(row)
        elif strategy == 'combined':
            results = [
                rsi_strat(row),
                ema_strat(row),
                macd_strat(row),
                bollinger_strat(row),
                sma_strat(row)
            ]
            long_votes = results.count('long')
            short_votes = results.count('short')
            if long_votes >= 3:
                return 'long'
            elif short_votes >= 3:
                return 'short'
            else:
                return 'hold'
        else:
            return 'hold'

    def execute_trade(self, action, price, timestamp):
        # פתיחת פוזיציה חדשה אם יש מקום
        if action == 'long' and self.balance > 0 and len(self.positions) < self.max_positions:
            portion = self.balance / (self.max_positions - len(self.positions))
            self.positions.append({'price': price, 'amount': portion / price, 'entry_time': timestamp})
            self.trade_log.append({
                'timestamp': timestamp, 'action': 'long_entry', 'price': price,
                'amount': portion / price, 'profit_pct': None
            })
            self.balance -= portion

        # סגירת פוזיציות פעילות
        elif action == 'short' and len(self.positions) > 0:
            for pos in self.positions[:]:
                profit = (price - pos['price']) * pos['amount']
                profit_pct = (price - pos['price']) / pos['price']
                self.trade_log.append({
                    'timestamp': timestamp, 'action': 'short_exit', 'price': price,
                    'amount': pos['amount'], 'profit_pct': profit_pct
                })
                self.balance += pos['amount'] * price
                self.positions.remove(pos)

    def check_risk_management(self, price, timestamp):
        for pos in self.positions[:]:
            profit_loss_pct = (price - pos['price']) / pos['price']
            if profit_loss_pct >= self.take_profit or profit_loss_pct <= -self.stop_loss:
                profit_pct = profit_loss_pct
                self.trade_log.append({
                    'timestamp': timestamp, 'action': 'risk_exit', 'price': price,
                    'amount': pos['amount'], 'profit_pct': profit_pct
                })
                self.balance += pos['amount'] * price
                self.positions.remove(pos)

    def run_simulation(self, df, strategy='combined'):
        self.reset()
        df = self.apply_indicators(df)
        for _, row in df.iterrows():
            timestamp = row['timestamp'] if 'timestamp' in row else row['time']
            action = self.determine_action(row, strategy=strategy)
            price = row['price']
            self.execute_trade(action, price, timestamp)
            self.check_risk_management(price, timestamp)
        # סגירה של כל הפוזיציות הפתוחות
        for pos in self.positions:
            self.balance += pos['amount'] * df.iloc[-1]['price']
            self.trade_log.append({
                'timestamp': df.iloc[-1]['timestamp'], 'action': 'final_exit', 'price': df.iloc[-1]['price'],
                'amount': pos['amount'], 'profit_pct': (df.iloc[-1]['price'] - pos['price']) / pos['price']
            })
        final_value = self.balance
        total_profit_pct = (final_value - self.initial_balance) / self.initial_balance
        trade_log_df = pd.DataFrame(self.trade_log)
        return {
            'final_balance': final_value,
            'total_profit_pct': total_profit_pct,
            'trade_log': trade_log_df
        }

def optimize_simulation_params(
    strategies = ['combined', 'ema', 'rsi'],
    initial_balances = [1000],
    take_profits = [0.05, 0.1, 0.15],
    stop_losses = [0.02, 0.04, 0.06],
    max_positions_list = [1, 2]
):
    # בדיקת קיום קבצי נתונים
    if not os.path.exists(HISTORY_FILE) and not os.path.exists(LIVE_FILE):
        print("❌ לא נמצאו קבצי נתונים!")
        print(f"נדרש: {HISTORY_FILE} או {LIVE_FILE}")
        return pd.DataFrame()
    
    # טעינת נתונים
    df_all = pd.DataFrame()
    
    if os.path.exists(HISTORY_FILE):
        try:
            hist = pd.read_csv(HISTORY_FILE, parse_dates=['timestamp'])
            df_all = pd.concat([df_all, hist], ignore_index=True)
            print(f"✅ נטען קובץ היסטוריה: {len(hist)} שורות")
        except Exception as e:
            print(f"⚠️ שגיאה בטעינת היסטוריה: {e}")
    
    if os.path.exists(LIVE_FILE):
        try:
            live = pd.read_csv(LIVE_FILE, parse_dates=['timestamp'])
            df_all = pd.concat([df_all, live], ignore_index=True)
            print(f"✅ נטען קובץ לייב: {len(live)} שורות")
        except Exception as e:
            print(f"⚠️ שגיאה בטעינת נתונים חיים: {e}")
    
    if df_all.empty:
        print("❌ לא נטענו נתונים!")
        return pd.DataFrame()
    
    # ניקוי כפילויות
    df_all.drop_duplicates(subset=['timestamp', 'pair'], inplace=True)
    print(f"📊 סה״כ נתונים לאחר ניקוי: {len(df_all)} שורות")

    param_grid = list(product(strategies, initial_balances, take_profits, stop_losses, max_positions_list))
    results = []
    best_overall = None
    best_profit = -np.inf

    print(f"🧪 מריץ {len(param_grid)} סימולציות...")

    for i, params in enumerate(param_grid):
        strategy, initial_balance, take_profit, stop_loss, max_positions = params
        print(f"\n[{i+1}/{len(param_grid)}] בדיקה: {strategy} | balance={initial_balance} | tp={take_profit} | sl={stop_loss} | pos={max_positions}")
        
        all_profits = []
        pairs_tested = 0
        
        for pair in sorted(df_all['pair'].unique()):
            df = df_all[df_all['pair'] == pair].sort_values('timestamp').reset_index(drop=True)
            if len(df) < 50:
                continue
            
            try:
                engine = SimulationEngine(
                    initial_balance=initial_balance,
                    take_profit=take_profit,
                    stop_loss=stop_loss,
                    max_positions=max_positions
                )
                result = engine.run_simulation(df, strategy=strategy)
                all_profits.append(result['total_profit_pct'])
                pairs_tested += 1
            except Exception as e:
                print(f"    ⚠️ שגיאה ב-{pair}: {e}")
                continue
        
        if not all_profits:
            print("    ❌ לא הושלמו סימולציות")
            continue
            
        avg_profit = np.mean(all_profits)
        max_profit = np.max(all_profits)
        min_profit = np.min(all_profits)
        
        result_dict = {
            'strategy': strategy,
            'initial_balance': initial_balance,
            'take_profit': take_profit,
            'stop_loss': stop_loss,
            'max_positions': max_positions,
            'avg_profit_pct': avg_profit,  # הוסף את העמודה החסרה!
            'max_profit_pct': max_profit,
            'min_profit_pct': min_profit,
            'pairs_tested': pairs_tested
        }
        
        print(f"    ✅ תוצאה: {avg_profit*100:.2f}% (על {pairs_tested} זוגות)")
        results.append(result_dict)
        
        if avg_profit > best_profit:
            best_profit = avg_profit
            best_overall = result_dict

    if not results:
        print("❌ לא התקבלו תוצאות!")
        return pd.DataFrame()

    summary_df = pd.DataFrame(results)
    
    # מיון בטוח - בדיקה שהעמודה קיימת
    if 'avg_profit_pct' in summary_df.columns:
        summary_df.sort_values('avg_profit_pct', ascending=False, inplace=True)
    else:
        print("⚠️ Warning: avg_profit_pct column not found")
    
    # שמירת תוצאות
    outpath = os.path.join(DATA_DIR, 'param_optimization_summary.csv')
    try:
        summary_df.to_csv(outpath, index=False)
        print(f"\n💾 נשמרה טבלת אופטימיזציה: {outpath}")
    except Exception as e:
        print(f"⚠️ שגיאה בשמירה: {e}")
    
    # הצגת תוצאות
    print(f"\n🏆 סיכום: הפרמטרים הכי טובים:")
    if best_overall:
        print(f"📊 אסטרטגיה: {best_overall['strategy']}")
        print(f"💰 הון: ${best_overall['initial_balance']}")
        print(f"📈 Take Profit: {best_overall['take_profit']*100}%")
        print(f"📉 Stop Loss: {best_overall['stop_loss']*100}%")
        print(f"🎯 פוזיציות מקס: {best_overall['max_positions']}")
        print(f"💹 רווח ממוצע: {best_overall['avg_profit_pct']*100:.2f}%")
    
    print(f"\n📋 Top 10 תוצאות:")
    print(summary_df.head(10).to_string(index=False))
    
    return summary_df

if __name__ == "__main__":
    optimize_simulation_params(
        strategies = ['combined', 'ema', 'rsi'],
        initial_balances = [1000],
        take_profits = [0.05, 0.10, 0.15],
        stop_losses = [0.02, 0.04, 0.06],
        max_positions_list = [1, 2]
    )