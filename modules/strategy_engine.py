import pandas as pd
import numpy as np
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.trend import EMAIndicator, SMAIndicator, MACD
from ta.volatility import BollingerBands

class StrategyEngine:
    def __init__(self, df):
        self.df = df.copy()

    def add_indicators(self):
        close = self.df['price']

        # הוספה זהירה: לא מוסיף פעמיים
        if 'rsi' not in self.df:
            self.df['rsi'] = RSIIndicator(close=close, window=14).rsi()
        if 'ema_fast' not in self.df:
            self.df['ema_fast'] = EMAIndicator(close=close, window=12).ema_indicator()
            self.df['ema_slow'] = EMAIndicator(close=close, window=26).ema_indicator()
        if 'sma_fast' not in self.df:
            self.df['sma_fast'] = SMAIndicator(close=close, window=10).sma_indicator()
            self.df['sma_slow'] = SMAIndicator(close=close, window=30).sma_indicator()
        if 'bb_high' not in self.df:
            bb = BollingerBands(close=close, window=20, window_dev=2)
            self.df['bb_high'] = bb.bollinger_hband()
            self.df['bb_low'] = bb.bollinger_lband()
        if 'macd' not in self.df:
            macd = MACD(close=close, window_slow=26, window_fast=12, window_sign=9)
            self.df['macd'] = macd.macd()
            self.df['macd_signal'] = macd.macd_signal()
        if 'stoch_k' not in self.df:
            stoch = StochasticOscillator(high=close, low=close, close=close, window=14, smooth_window=3)
            self.df['stoch_k'] = stoch.stoch()
            self.df['stoch_d'] = stoch.stoch_signal()

    def ema_crossover(self, row):
        try:
            if np.isnan(row.get('ema_fast')) or np.isnan(row.get('ema_slow')):
                return 'hold'
            return 'long' if row['ema_fast'] > row['ema_slow'] else 'short'
        except:
            return 'hold'

    def sma_crossover(self, row):
        try:
            if np.isnan(row.get('sma_fast')) or np.isnan(row.get('sma_slow')):
                return 'hold'
            return 'long' if row['sma_fast'] > row['sma_slow'] else 'short'
        except:
            return 'hold'

    def rsi_strategy(self, row):
        try:
            if np.isnan(row.get('rsi')):
                return 'hold'
            if row['rsi'] < 30:
                return 'long'
            elif row['rsi'] > 70:
                return 'short'
            return 'hold'
        except:
            return 'hold'

    def bollinger_strategy(self, row):
        try:
            if np.isnan(row.get('bb_high')) or np.isnan(row.get('bb_low')):
                return 'hold'
            if row['price'] < row['bb_low']:
                return 'long'
            elif row['price'] > row['bb_high']:
                return 'short'
            return 'hold'
        except:
            return 'hold'

    def macd_strategy(self, row):
        try:
            if np.isnan(row.get('macd')) or np.isnan(row.get('macd_signal')):
                return 'hold'
            return 'long' if row['macd'] > row['macd_signal'] else 'short'
        except:
            return 'hold'

    def stochastic_strategy(self, row):
        try:
            if np.isnan(row.get('stoch_k')) or np.isnan(row.get('stoch_d')):
                return 'hold'
            if row['stoch_k'] < 20 and row['stoch_k'] > row['stoch_d']:
                return 'long'
            elif row['stoch_k'] > 80 and row['stoch_k'] < row['stoch_d']:
                return 'short'
            return 'hold'
        except:
            return 'hold'

    def combined_strategy(self, row):
        signals = [
            self.ema_crossover(row),
            self.sma_crossover(row),
            self.rsi_strategy(row),
            self.bollinger_strategy(row),
            self.macd_strategy(row),
            self.stochastic_strategy(row)
        ]
        if signals.count('long') >= 3:
            return 'long'
        elif signals.count('short') >= 3:
            return 'short'
        return 'hold'

    def generate_signals(self, strategy='combined', return_full=False):
        self.add_indicators()
        if strategy == 'ema':
            self.df['signal'] = self.df.apply(self.ema_crossover, axis=1)
        elif strategy == 'sma':
            self.df['signal'] = self.df.apply(self.sma_crossover, axis=1)
        elif strategy == 'rsi':
            self.df['signal'] = self.df.apply(self.rsi_strategy, axis=1)
        elif strategy == 'bollinger':
            self.df['signal'] = self.df.apply(self.bollinger_strategy, axis=1)
        elif strategy == 'macd':
            self.df['signal'] = self.df.apply(self.macd_strategy, axis=1)
        elif strategy == 'stochastic':
            self.df['signal'] = self.df.apply(self.stochastic_strategy, axis=1)
        else:
            self.df['signal'] = self.df.apply(self.combined_strategy, axis=1)
        if return_full:
            return self.df  # מחזיר את כל הטבלה כולל האינדיקטורים
        else:
            return self.df[['time', 'price', 'signal']]
