"""
Mean Reversion Strategy
=======================
אסטרטגיית חזרה לממוצע - מנצלת סטיות קיצוניות מהממוצע
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

class MeanReversionStrategy:
    """אסטרטגיית מסחר מבוססת חזרה לממוצע"""
    
    def __init__(self, params: Dict = None):
        self.params = params or {
            'bb_period': 20,          # Bollinger Bands period
            'bb_std': 2.0,           # Bollinger Bands standard deviations
            'rsi_period': 14,        # RSI period
            'rsi_oversold': 30,      # RSI oversold threshold
            'rsi_overbought': 70,    # RSI overbought threshold
            'zscore_threshold': 2.0,  # Z-score threshold for entry
            'mean_period': 20,       # Period for mean calculation
            'exit_zscore': 0.5       # Z-score for exit
        }
        
        self.positions = {}
        self.trades = []
        
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """חישוב אינדיקטורים לזיהוי חזרה לממוצע"""
        
        # Bollinger Bands
        df['bb_middle'] = df['close'].rolling(self.params['bb_period']).mean()
        bb_std = df['close'].rolling(self.params['bb_period']).std()
        df['bb_upper'] = df['bb_middle'] + (bb_std * self.params['bb_std'])
        df['bb_lower'] = df['bb_middle'] - (bb_std * self.params['bb_std'])
        df['bb_width'] = df['bb_upper'] - df['bb_lower']
        df['bb_position'] = (df['close'] - df['bb_lower']) / df['bb_width']
        
        # RSI
        df['rsi'] = self.calculate_rsi(df['close'], self.params['rsi_period'])
        
        # Z-Score
        df['zscore'] = self.calculate_zscore(df['close'], self.params['mean_period'])
        
        # Mean reversion indicators
        df['distance_from_mean'] = (df['close'] - df['bb_middle']) / df['bb_middle'] * 100
        
        # Volatility
        df['volatility'] = df['close'].pct_change().rolling(20).std() * np.sqrt(252)
        
        # Volume indicators
        df['volume_sma'] = df['volume'].rolling(20).mean()
        df['volume_ratio'] = df['volume'] / df['volume_sma']
        
        # Price momentum
        df['momentum'] = df['close'].pct_change(10)
        
        return df
    
    def calculate_rsi(self, prices: pd.Series, period: int) -> pd.Series:
        """חישוב RSI"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def calculate_zscore(self, prices: pd.Series, period: int) -> pd.Series:
        """חישוב Z-Score"""
        mean = prices.rolling(period).mean()
        std = prices.rolling(period).std()
        zscore = (prices - mean) / std
        
        return zscore
    
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """יצירת אותות מסחר"""
        df = self.calculate_indicators(df)
        
        # Initialize signals
        df['signal'] = 0
        df['position'] = 0
        
        # Long entry conditions (oversold)
        long_condition = (
            (df['close'] < df['bb_lower']) |  # Price below lower band
            (df['rsi'] < self.params['rsi_oversold']) |  # RSI oversold
            (df['zscore'] < -self.params['zscore_threshold'])  # Z-score extreme
        ) & (
            df['volume_ratio'] > 1.2  # Volume confirmation
        )
        
        # Short entry conditions (overbought)
        short_condition = (
            (df['close'] > df['bb_upper']) |  # Price above upper band
            (df['rsi'] > self.params['rsi_overbought']) |  # RSI overbought
            (df['zscore'] > self.params['zscore_threshold'])  # Z-score extreme
        ) & (
            df['volume_ratio'] > 1.2  # Volume confirmation
        )
        
        # Exit conditions - return to mean
        exit_long = (
            (df['close'] > df['bb_middle']) |  # Price crosses middle band
            (df['zscore'] > -self.params['exit_zscore']) |  # Z-score normalizes
            (df['rsi'] > 50)  # RSI returns to neutral
        )
        
        exit_short = (
            (df['close'] < df['bb_middle']) |  # Price crosses middle band
            (df['zscore'] < self.params['exit_zscore']) |  # Z-score normalizes
            (df['rsi'] < 50)  # RSI returns to neutral
        )
        
        # Generate signals with position tracking
        positions = 0
        for i in range(len(df)):
            if positions == 0:  # No position
                if long_condition.iloc[i]:
                    df.loc[df.index[i], 'signal'] = 1
                    positions = 1
                elif short_condition.iloc[i]:
                    df.loc[df.index[i], 'signal'] = -1
                    positions = -1
            elif positions == 1:  # Long position
                if exit_long.iloc[i]:
                    df.loc[df.index[i], 'signal'] = 0
                    positions = 0
            elif positions == -1:  # Short position
                if exit_short.iloc[i]:
                    df.loc[df.index[i], 'signal'] = 0
                    positions = 0
            
            df.loc[df.index[i], 'position'] = positions
        
        # Apply filters
        df = self.apply_filters(df)
        
        return df
    
    def apply_filters(self, df: pd.DataFrame) -> pd.DataFrame:
        """החלת פילטרים נוספים על האותות"""
        # Don't trade in low volatility
        df.loc[df['volatility'] < 0.1, 'signal'] = 0
        
        # Don't trade against strong trends
        strong_trend_up = df['close'].rolling(50).mean() > df['close'].rolling(200).mean() * 1.1
        strong_trend_down = df['close'].rolling(50).mean() < df['close'].rolling(200).mean() * 0.9
        
        # Remove short signals in strong uptrend
        df.loc[strong_trend_up & (df['signal'] == -1), 'signal'] = 0
        
        # Remove long signals in strong downtrend
        df.loc[strong_trend_down & (df['signal'] == 1), 'signal'] = 0
        
        return df
    
    def calculate_position_size(self, df: pd.DataFrame, 
                              capital: float, 
                              row_idx: int) -> float:
        """חישוב גודל פוזיציה בהתאם לרמת הביטחון"""
        base_position = capital * 0.1  # 10% base position
        
        # Adjust based on signal strength
        row = df.iloc[row_idx]
        
        # Z-score based sizing
        zscore_mult = min(abs(row['zscore']) / self.params['zscore_threshold'], 2.0)
        
        # RSI based sizing
        if row['signal'] == 1:  # Long
            rsi_mult = (self.params['rsi_oversold'] - row['rsi']) / self.params['rsi_oversold']
        elif row['signal'] == -1:  # Short
            rsi_mult = (row['rsi'] - self.params['rsi_overbought']) / (100 - self.params['rsi_overbought'])
        else:
            rsi_mult = 0
        
        # Volatility adjustment
        vol_mult = 1 / (1 + row['volatility'])
        
        # Final position size
        position_size = base_position * zscore_mult * (1 + rsi_mult) * vol_mult
        
        return min(position_size, capital * 0.25)  # Max 25% of capital
    
    def backtest(self, df: pd.DataFrame, initial_capital: float = 10000) -> Dict:
        """ביצוע backtest מפורט"""
        df = self.generate_signals(df)
        
        # Initialize portfolio
        capital = initial_capital
        positions = 0
        entry_price = 0
        trades = []
        portfolio_value = []
        
        for i in range(len(df)):
            row = df.iloc[i]
            
            # Entry
            if row['signal'] != 0 and positions == 0:
                position_size = self.calculate_position_size(df, capital, i)
                positions = position_size / row['close']
                entry_price = row['close']
                capital -= position_size
                
                trades.append({
                    'entry_date': df.index[i],
                    'entry_price': entry_price,
                    'position_size': position_size,
                    'direction': 'long' if row['signal'] == 1 else 'short'
                })
            
            # Exit
            elif row['signal'] == 0 and positions != 0:
                exit_value = positions * row['close']
                capital += exit_value
                
                # Calculate trade return
                if trades:
                    trade = trades[-1]
                    trade['exit_date'] = df.index[i]
                    trade['exit_price'] = row['close']
                    
                    if trade['direction'] == 'long':
                        trade['return'] = (row['close'] - trade['entry_price']) / trade['entry_price']
                    else:
                        trade['return'] = (trade['entry_price'] - row['close']) / trade['entry_price']
                    
                    trade['pnl'] = trade['return'] * trade['position_size']
                
                positions = 0
            
            # Calculate portfolio value
            current_value = capital + (positions * row['close'] if positions != 0 else 0)
            portfolio_value.append(current_value)
        
        # Convert to DataFrame
        df['portfolio_value'] = portfolio_value
        
        # Calculate metrics
        total_return = (portfolio_value[-1] / initial_capital - 1) * 100
        
        # Completed trades only
        completed_trades = [t for t in trades if 'return' in t]
        
        if completed_trades:
            returns = [t['return'] for t in completed_trades]
            win_rate = sum(1 for r in returns if r > 0) / len(returns) * 100
            avg_win = np.mean([r for r in returns if r > 0]) * 100 if any(r > 0 for r in returns) else 0
            avg_loss = np.mean([r for r in returns if r < 0]) * 100 if any(r < 0 for r in returns) else 0
            
            # Sharpe ratio
            daily_returns = pd.Series(portfolio_value).pct_change().dropna()
            sharpe_ratio = daily_returns.mean() / daily_returns.std() * np.sqrt(252) if daily_returns.std() > 0 else 0
            
            # Max drawdown
            rolling_max = pd.Series(portfolio_value).expanding().max()
            drawdown = (pd.Series(portfolio_value) - rolling_max) / rolling_max
            max_drawdown = drawdown.min() * 100
        else:
            win_rate = avg_win = avg_loss = sharpe_ratio = max_drawdown = 0
        
        return {
            'total_return': total_return,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown,
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'num_trades': len(completed_trades),
            'final_portfolio_value': portfolio_value[-1],
            'trades': completed_trades,
            'df': df
        }