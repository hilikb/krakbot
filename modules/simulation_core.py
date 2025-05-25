import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import SMAIndicator, EMAIndicator, MACD
from ta.volatility import BollingerBands

class SimulationEngine:
    def __init__(self, initial_balance=1000, take_profit=0.1, stop_loss=0.05):
        self.initial_balance = initial_balance
        self.take_profit = take_profit
        self.stop_loss = stop_loss
        self.reset()

    def reset(self):
        self.balance = self.initial_balance
        self.holdings = 0
        self.entry_price = 0
        self.trade_log = []

    def apply_indicators(self, df):
        df = df.copy()
        df['rsi'] = RSIIndicator(close=df['price'], window=14).rsi()
        df['sma_short'] = SMAIndicator(close=df['price'], window=20).sma_indicator()
        df['sma_long'] = SMAIndicator(close=df['price'], window=50).sma_indicator()
        df['ema_fast'] = EMAIndicator(close=df['price'], window=12).ema_indicator()
        df['ema_slow'] = EMAIndicator(close=df['price'], window=26).ema_indicator()
        # MACD
        macd = MACD(close=df['price'], window_slow=26, window_fast=12, window_sign=9)
        df['macd'] = macd.macd()
        df['macd_signal'] = macd.macd_signal()
        # Bollinger Bands
        bb = BollingerBands(close=df['price'], window=20, window_dev=2)
        df['bb_high'] = bb.bollinger_hband()
        df['bb_low'] = bb.bollinger_lband()
        return df

    def determine_action(self, row, strategy='combined'):
        # ---- אסטרטגיית RSI ----
        def rsi_strat(row):
            if pd.isna(row['rsi']):
                return 'hold'
            if row['rsi'] < 30:
                return 'long'
            elif row['rsi'] > 70:
                return 'short'
            return 'hold'

        # ---- אסטרטגיית EMA (ממוצעים נעים מהירים/איטיים) ----
        def ema_strat(row):
            if pd.isna(row.get('ema_fast', None)) or pd.isna(row.get('ema_slow', None)):
                return 'hold'
            if row['ema_fast'] > row['ema_slow']:
                return 'long'
            elif row['ema_fast'] < row['ema_slow']:
                return 'short'
            return 'hold'

        # ---- אסטרטגיית MACD ----
        def macd_strat(row):
            if pd.isna(row.get('macd', None)) or pd.isna(row.get('macd_signal', None)):
                return 'hold'
            if row['macd'] > row['macd_signal']:
                return 'long'
            elif row['macd'] < row['macd_signal']:
                return 'short'
            return 'hold'

        # ---- אסטרטגיית Bollinger Bands ----
        def bollinger_strat(row):
            if pd.isna(row.get('bb_high', None)) or pd.isna(row.get('bb_low', None)):
                return 'hold'
            if row['price'] < row['bb_low']:
                return 'long'
            elif row['price'] > row['bb_high']:
                return 'short'
            return 'hold'

        # ---- אסטרטגיית SMA (בין SMA קצר לארוך) ----
        def sma_strat(row):
            if pd.isna(row['sma_short']) or pd.isna(row['sma_long']):
                return 'hold'
            if row['sma_short'] > row['sma_long']:
                return 'long'
            elif row['sma_short'] < row['sma_long']:
                return 'short'
            return 'hold'

        # בחירת אסטרטגיה
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
            # רוב קולות מתוך 5 אסטרטגיות
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

    def execute_trade(self, action, price, time):
        if action == 'long' and self.balance > 0:
            self.holdings = self.balance / price
            self.entry_price = price
            self.trade_log.append({
                'time': time, 'action': 'long_entry', 'price': price,
                'amount': self.holdings, 'profit_pct': None
            })
            self.balance = 0

        elif action == 'short' and self.holdings > 0:
            self.balance = self.holdings * price
            profit_pct = (self.balance - self.initial_balance) / self.initial_balance
            self.trade_log.append({
                'time': time, 'action': 'short_exit', 'price': price,
                'amount': self.balance, 'profit_pct': profit_pct
            })
            self.holdings = 0
            self.entry_price = 0

    def check_risk_management(self, current_price, time):
        if self.holdings > 0:
            current_value = self.holdings * current_price
            entry_value = self.holdings * self.entry_price
            profit_loss_pct = (current_value - entry_value) / entry_value

            if profit_loss_pct >= self.take_profit or profit_loss_pct <= -self.stop_loss:
                self.balance = current_value
                profit_pct = (self.balance - self.initial_balance) / self.initial_balance
                self.trade_log.append({
                    'time': time, 'action': 'risk_exit', 'price': current_price,
                    'amount': self.balance, 'profit_pct': profit_pct
                })
                self.holdings = 0
                self.entry_price = 0

    def run_simulation(self, df, strategy='combined'):
        self.reset()
        df = self.apply_indicators(df)

        for i, row in df.iterrows():
            action = self.determine_action(row, strategy=strategy)
            price = row['price']
            time = row['time']

            self.execute_trade(action, price, time)
            self.check_risk_management(price, time)

        final_value = self.balance + (self.holdings * df.iloc[-1]['price'] if self.holdings else 0)
        total_profit_pct = (final_value - self.initial_balance) / self.initial_balance

        if len(self.trade_log) > 0:
            trade_log_df = pd.DataFrame(self.trade_log, columns=['time', 'action', 'price', 'amount', 'profit_pct'])
        else:
            trade_log_df = pd.DataFrame(columns=['time', 'action', 'price', 'amount', 'profit_pct'])

        return {
            'final_balance': final_value,
            'total_profit_pct': total_profit_pct,
            'trade_log': trade_log_df
        }
