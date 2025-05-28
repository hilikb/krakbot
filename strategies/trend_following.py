"""
Trend Following Strategy
========================
אסטרטגיית עקיבה אחר מגמות
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
import logging

logger = logging.getLogger(__name__)

class TrendFollowingStrategy:
    """אסטרטגיית מסחר מבוססת מגמה"""
    
    def __init__(self, params: Dict = None):
        self.params = params or {
            'fast_ema': 12,
            'slow_ema': 26,
            'signal_ema': 9,
            'atr_multiplier': 2.0,
            'trend_strength_threshold': 0.02
        }
        
        self.positions = {}
        self.signals_history = []
        
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """חישוב אינדיקטורים טכניים"""
        # EMA
        df['ema_fast'] = df['close'].ewm(span=self.params['fast_ema']).mean()
        df['ema_slow'] = df['close'].ewm(span=self.params['slow_ema']).mean()
        df['ema_signal'] = df['ema_fast'].ewm(span=self.params['signal_ema']).mean()
        
        # MACD
        df['macd'] = df['ema_fast'] - df['ema_slow']
        df['macd_signal'] = df['macd'].ewm(span=self.params['signal_ema']).mean()
        df['macd_histogram'] = df['macd'] - df['macd_signal']
        
        # ATR (Average True Range)
        high_low = df['high'] - df['low']
        high_close = abs(df['high'] - df['close'].shift())
        low_close = abs(df['low'] - df['close'].shift())
        
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df['atr'] = true_range.rolling(window=14).mean()
        
        # Trend Strength
        df['trend_strength'] = (df['ema_fast'] - df['ema_slow']) / df['ema_slow']
        
        # ADX (Average Directional Index)
        df['adx'] = self.calculate_adx(df)
        
        return df
    
    def calculate_adx(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """חישוב ADX"""
        # +DM and -DM
        df['high_diff'] = df['high'].diff()
        df['low_diff'] = df['low'].diff()
        
        df['+dm'] = np.where(
            (df['high_diff'] > df['low_diff']) & (df['high_diff'] > 0),
            df['high_diff'], 0
        )
        df['-dm'] = np.where(
            (df['low_diff'] > df['high_diff']) & (df['low_diff'] > 0),
            df['low_diff'], 0
        )
        
        # +DI and -DI
        df['+di'] = 100 * (df['+dm'].rolling(period).mean() / df['atr'])
        df['-di'] = 100 * (df['-dm'].rolling(period).mean() / df['atr'])
        
        # DX and ADX
        df['dx'] = 100 * abs(df['+di'] - df['-di']) / (df['+di'] + df['-di'])
        adx = df['dx'].rolling(period).mean()
        
        # Cleanup
        df.drop(['+dm', '-dm', '+di', '-di', 'dx', 'high_diff', 'low_diff'], 
                axis=1, inplace=True)
        
        return adx
    
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """יצירת אותות מסחר"""
        df = self.calculate_indicators(df)
        
        # Initialize signals
        df['signal'] = 0
        df['position'] = 0
        
        # Entry conditions
        long_condition = (
            (df['ema_fast'] > df['ema_slow']) &  # EMA crossover
            (df['macd'] > df['macd_signal']) &   # MACD confirmation
            (df['adx'] > 25) &                   # Strong trend
            (df['trend_strength'] > self.params['trend_strength_threshold'])
        )
        
        short_condition = (
            (df['ema_fast'] < df['ema_slow']) &
            (df['macd'] < df['macd_signal']) &
            (df['adx'] > 25) &
            (df['trend_strength'] < -self.params['trend_strength_threshold'])
        )
        
        # Exit conditions
        exit_long = (
            (df['ema_fast'] < df['ema_signal']) |  # Fast EMA crosses below signal
            (df['macd'] < df['macd_signal'])       # MACD crosses below signal
        )
        
        exit_short = (
            (df['ema_fast'] > df['ema_signal']) |
            (df['macd'] > df['macd_signal'])
        )
        
        # Generate signals
        df.loc[long_condition, 'signal'] = 1
        df.loc[short_condition, 'signal'] = -1
        df.loc[exit_long & (df['position'].shift() > 0), 'signal'] = 0
        df.loc[exit_short & (df['position'].shift() < 0), 'signal'] = 0
        
        # Calculate positions
        df['position'] = df['signal'].replace(to_replace=0, method='ffill').fillna(0)
        
        # Stop loss and take profit
        df = self.apply_risk_management(df)
        
        return df
    
    def apply_risk_management(self, df: pd.DataFrame) -> pd.DataFrame:
        """ניהול סיכונים - Stop Loss / Take Profit"""
        # Calculate entry prices
        df['entry_price'] = np.where(
            df['signal'] != 0, 
            df['close'], 
            np.nan
        )
        df['entry_price'].fillna(method='ffill', inplace=True)
        
        # ATR-based stops
        df['stop_loss'] = np.where(
            df['position'] > 0,
            df['entry_price'] - self.params['atr_multiplier'] * df['atr'],
            np.where(
                df['position'] < 0,
                df['entry_price'] + self.params['atr_multiplier'] * df['atr'],
                np.nan
            )
        )
        
        df['take_profit'] = np.where(
            df['position'] > 0,
            df['entry_price'] + 3 * self.params['atr_multiplier'] * df['atr'],
            np.where(
                df['position'] < 0,
                df['entry_price'] - 3 * self.params['atr_multiplier'] * df['atr'],
                np.nan
            )
        )
        
        # Check stops
        stop_loss_hit = (
            ((df['position'] > 0) & (df['low'] <= df['stop_loss'])) |
            ((df['position'] < 0) & (df['high'] >= df['stop_loss']))
        )
        
        take_profit_hit = (
            ((df['position'] > 0) & (df['high'] >= df['take_profit'])) |
            ((df['position'] < 0) & (df['low'] <= df['take_profit']))
        )
        
        # Exit on stop
        df.loc[stop_loss_hit | take_profit_hit, 'signal'] = 0
        df.loc[stop_loss_hit | take_profit_hit, 'position'] = 0
        
        return df
    
    def backtest(self, df: pd.DataFrame, initial_capital: float = 10000) -> Dict:
        """ביצוע backtest"""
        df = self.generate_signals(df)
        
        # Calculate returns
        df['returns'] = df['close'].pct_change()
        df['strategy_returns'] = df['position'].shift() * df['returns']
        
        # Calculate cumulative returns
        df['cumulative_returns'] = (1 + df['returns']).cumprod()
        df['cumulative_strategy_returns'] = (1 + df['strategy_returns']).cumprod()
        
        # Portfolio value
        df['portfolio_value'] = initial_capital * df['cumulative_strategy_returns']
        
        # Calculate metrics
        total_return = (df['portfolio_value'].iloc[-1] / initial_capital - 1) * 100
        
        # Sharpe ratio (annualized)
        sharpe_ratio = (
            df['strategy_returns'].mean() / df['strategy_returns'].std() * np.sqrt(252)
            if df['strategy_returns'].std() > 0 else 0
        )
        
        # Maximum drawdown
        rolling_max = df['portfolio_value'].expanding().max()
        drawdown = (df['portfolio_value'] - rolling_max) / rolling_max
        max_drawdown = drawdown.min() * 100
        
        # Win rate
        trades = df[df['signal'] != 0].copy()
        if len(trades) > 1:
            trade_returns = []
            for i in range(1, len(trades)):
                if trades.iloc[i]['signal'] == 0:  # Exit
                    entry_price = trades.iloc[i-1]['close']
                    exit_price = trades.iloc[i]['close']
                    if trades.iloc[i-1]['signal'] == 1:  # Long
                        ret = (exit_price - entry_price) / entry_price
                    else:  # Short
                        ret = (entry_price - exit_price) / entry_price
                    trade_returns.append(ret)
            
            if trade_returns:
                win_rate = sum(1 for r in trade_returns if r > 0) / len(trade_returns) * 100
                avg_win = np.mean([r for r in trade_returns if r > 0]) * 100 if any(r > 0 for r in trade_returns) else 0
                avg_loss = np.mean([r for r in trade_returns if r < 0]) * 100 if any(r < 0 for r in trade_returns) else 0
            else:
                win_rate = avg_win = avg_loss = 0
        else:
            win_rate = avg_win = avg_loss = 0
        
        return {
            'total_return': total_return,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown,
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'num_trades': len(trades),
            'final_portfolio_value': df['portfolio_value'].iloc[-1],
            'df': df  # Return full dataframe for analysis
        }
    
    def optimize_parameters(self, df: pd.DataFrame, 
                          param_ranges: Dict[str, List],
                          metric: str = 'sharpe_ratio') -> Dict:
        """אופטימיזציה של פרמטרים"""
        best_params = None
        best_score = -np.inf
        results = []
        
        # Grid search
        from itertools import product
        
        param_names = list(param_ranges.keys())
        param_values = [param_ranges[name] for name in param_names]
        
        for values in product(*param_values):
            # Update parameters
            test_params = self.params.copy()
            for name, value in zip(param_names, values):
                test_params[name] = value
            
            # Run backtest
            self.params = test_params
            result = self.backtest(df.copy())
            
            # Track results
            result['params'] = test_params.copy()
            results.append(result)
            
            # Check if best
            if result[metric] > best_score:
                best_score = result[metric]
                best_params = test_params.copy()
        
        # Restore best parameters
        self.params = best_params
        
        return {
            'best_params': best_params,
            'best_score': best_score,
            'all_results': results
        }