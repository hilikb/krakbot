#!/usr/bin/env python3
"""
Backtest Strategy Script
========================
סקריפט להרצת backtesting על אסטרטגיות מסחר
"""

import os
import sys
import pandas as pd
import numpy as np
import argparse
import json
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import seaborn as sns

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from strategies.trend_following import TrendFollowingStrategy
from strategies.mean_reversion import MeanReversionStrategy

class BacktestRunner:
    """מנהל הרצת Backtests"""
    
    def __init__(self):
        self.results = {}
        self.strategies = {
            'trend_following': TrendFollowingStrategy,
            'mean_reversion': MeanReversionStrategy
        }
        
    def load_data(self, symbol: str, start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """טעינת נתונים היסטוריים"""
        # Try to load from saved data
        data_file = f'data/market_history.csv'
        
        if os.path.exists(data_file):
            df = pd.read_csv(data_file, parse_dates=['timestamp'])
            
            # Filter by symbol
            df = df[df['pair'] == f'{symbol}USD']
            
            # Filter by dates
            if start_date:
                df = df[df['timestamp'] >= pd.to_datetime(start_date)]
            if end_date:
                df = df[df['timestamp'] <= pd.to_datetime(end_date)]
            
            # Prepare columns
            df = df.rename(columns={
                'price': 'close',
                'high_24h': 'high',
                'low_24h': 'low'
            })
            
            # Set timestamp as index
            df.set_index('timestamp', inplace=True)
            
            return df
        else:
            # Generate sample data for testing
            print("⚠️  No historical data found. Generating sample data...")
            return self.generate_sample_data(symbol)
    
    def generate_sample_data(self, symbol: str, days: int = 365) -> pd.DataFrame:
        """יצירת נתונים לדוגמה"""
        dates = pd.date_range(end=datetime.now(), periods=days*24, freq='H')
        
        # Generate realistic price data
        np.random.seed(42)
        price = 100
        prices = []
        volumes = []
        
        for _ in range(len(dates)):
            # Random walk with trend
            change = np.random.normal(0.0002, 0.01)
            price *= (1 + change)
            prices.append(price)
            
            # Volume
            volume = np.random.lognormal(10, 1)
            volumes.append(volume)
        
        # Create DataFrame
        df = pd.DataFrame({
            'close': prices,
            'high': [p * np.random.uniform(1.001, 1.01) for p in prices],
            'low': [p * np.random.uniform(0.99, 0.999) for p in prices],
            'volume': volumes
        }, index=dates)
        
        # Add open prices
        df['open'] = df['close'].shift(1)
        df.fillna(method='bfill', inplace=True)
        
        return df
    
    def run_backtest(self, strategy_name: str, symbol: str, 
                     params: dict = None, start_date: str = None, 
                     end_date: str = None, initial_capital: float = 10000) -> dict:
        """הרצת backtest על אסטרטגיה"""
        
        # Load data
        df = self.load_data(symbol, start_date, end_date)
        
        if df.empty:
            print(f"❌ No data available for {symbol}")
            return {}
        
        print(f"\n📊 Running backtest for {strategy_name} on {symbol}")
        print(f"   Period: {df.index[0]} to {df.index[-1]}")
        print(f"   Data points: {len(df)}")
        
        # Initialize strategy
        strategy_class = self.strategies.get(strategy_name)
        if not strategy_class:
            print(f"❌ Unknown strategy: {strategy_name}")
            return {}
        
        strategy = strategy_class(params)
        
        # Run backtest
        results = strategy.backtest(df.copy(), initial_capital)
        
        # Store results
        self.results[f"{strategy_name}_{symbol}"] = results
        
        return results
    
    def compare_strategies(self, symbol: str, strategies: list = None, 
                          start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """השוואת אסטרטגיות"""
        
        if strategies is None:
            strategies = list(self.strategies.keys())
        
        comparison_results = []
        
        for strategy_name in strategies:
            results = self.run_backtest(strategy_name, symbol, start_date=start_date, end_date=end_date)
            
            if results:
                comparison_results.append({
                    'Strategy': strategy_name,
                    'Total Return (%)': results['total_return'],
                    'Sharpe Ratio': results['sharpe_ratio'],
                    'Max Drawdown (%)': results['max_drawdown'],
                    'Win Rate (%)': results['win_rate'],
                    'Num Trades': results['num_trades']
                })
        
        return pd.DataFrame(comparison_results)
    
    def plot_results(self, results: dict, title: str = "Backtest Results"):
        """ציור תוצאות"""
        if 'df' not in results:
            print("❌ No data to plot")
            return
        
        df = results['df']
        
        # Create subplots
        fig, axes = plt.subplots(3, 1, figsize=(12, 10), sharex=True)
        
        # Price and signals
        ax1 = axes[0]
        ax1.plot(df.index, df['close'], 'b-', label='Price', alpha=0.7)
        
        # Mark entry/exit points
        long_entries = df[df['signal'] == 1]
        short_entries = df[df['signal'] == -1]
        exits = df[df['signal'] == 0]
        
        ax1.scatter(long_entries.index, long_entries['close'], 
                   color='green', marker='^', s=100, label='Long Entry')
        ax1.scatter(short_entries.index, short_entries['close'], 
                   color='red', marker='v', s=100, label='Short Entry')
        ax1.scatter(exits.index, exits['close'], 
                   color='black', marker='x', s=100, label='Exit')
        
        ax1.set_ylabel('Price')
        ax1.legend()
        ax1.set_title(f'{title} - Price & Signals')
        
        # Portfolio value
        ax2 = axes[1]
        if 'portfolio_value' in df.columns:
            ax2.plot(df.index, df['portfolio_value'], 'g-', label='Portfolio Value')
            ax2.set_ylabel('Portfolio Value ($)')
            ax2.legend()
            ax2.set_title('Portfolio Performance')
        
        # Drawdown
        ax3 = axes[2]
        if 'portfolio_value' in df.columns:
            rolling_max = df['portfolio_value'].expanding().max()
            drawdown = (df['portfolio_value'] - rolling_max) / rolling_max * 100
            ax3.fill_between(df.index, drawdown, 0, color='red', alpha=0.3)
            ax3.plot(df.index, drawdown, 'r-', label='Drawdown')
            ax3.set_ylabel('Drawdown (%)')
            ax3.set_xlabel('Date')
            ax3.legend()
            ax3.set_title('Drawdown')
        
        plt.tight_layout()
        
        # Save plot
        plot_dir = 'data/backtest_results'
        os.makedirs(plot_dir, exist_ok=True)
        plot_file = os.path.join(plot_dir, f"{title.replace(' ', '_')}.png")
        plt.savefig(plot_file)
        print(f"📊 Plot saved to: {plot_file}")
        
        plt.show()
    
    def save_results(self, results: dict, filename: str = None):
        """שמירת תוצאות"""
        if filename is None:
            filename = f"backtest_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        output_dir = 'data/backtest_results'
        os.makedirs(output_dir, exist_ok=True)
        
        # Remove DataFrame from results for JSON serialization
        save_results = {}
        for key, value in results.items():
            if isinstance(value, dict):
                save_results[key] = {k: v for k, v in value.items() if k != 'df'}
            else:
                save_results[key] = value
        
        output_file = os.path.join(output_dir, filename)
        with open(output_file, 'w') as f:
            json.dump(save_results, f, indent=2, default=str)
        
        print(f"📁 Results saved to: {output_file}")
    
    def optimize_parameters(self, strategy_name: str, symbol: str, 
                          param_grid: dict, metric: str = 'sharpe_ratio'):
        """אופטימיזציה של פרמטרים"""
        
        print(f"\n🔧 Optimizing {strategy_name} parameters for {symbol}")
        print(f"   Optimization metric: {metric}")
        
        # Load data once
        df = self.load_data(symbol)
        
        if df.empty:
            print("❌ No data available")
            return
        
        # Initialize strategy
        strategy_class = self.strategies.get(strategy_name)
        if not strategy_class:
            print(f"❌ Unknown strategy: {strategy_name}")
            return
        
        strategy = strategy_class()
        
        # Run optimization
        results = strategy.optimize_parameters(df, param_grid, metric)
        
        # Display results
        print(f"\n✅ Optimization complete!")
        print(f"   Best {metric}: {results['best_score']:.4f}")
        print(f"   Best parameters:")
        for param, value in results['best_params'].items():
            print(f"      {param}: {value}")
        
        # Save results
        self.save_results(results, f"optimization_{strategy_name}_{symbol}.json")
        
        return results

def main():
    """הפעלה ראשית"""
    parser = argparse.ArgumentParser(description='Backtest Trading Strategies')
    
    parser.add_argument('--strategy', '-s', 
                       choices=['trend_following', 'mean_reversion', 'all'],
                       default='all',
                       help='Strategy to backtest')
    
    parser.add_argument('--symbol', '-c', 
                       default='BTC',
                       help='Symbol to test (e.g., BTC, ETH)')
    
    parser.add_argument('--start-date', '-sd',
                       help='Start date (YYYY-MM-DD)')
    
    parser.add_argument('--end-date', '-ed',
                       help='End date (YYYY-MM-DD)')
    
    parser.add_argument('--initial-capital', '-ic',
                       type=float,
                       default=10000,
                       help='Initial capital')
    
    parser.add_argument('--optimize', '-o',
                       action='store_true',
                       help='Run parameter optimization')
    
    parser.add_argument('--plot', '-p',
                       action='store_true',
                       help='Plot results')
    
    args = parser.parse_args()
    
    # Initialize runner
    runner = BacktestRunner()
    
    print("🚀 Kraken Bot - Strategy Backtester")
    print("=" * 50)
    
    if args.optimize:
        # Run optimization
        if args.strategy == 'all':
            strategies = list(runner.strategies.keys())
        else:
            strategies = [args.strategy]
        
        for strategy in strategies:
            # Define parameter grid
            if strategy == 'trend_following':
                param_grid = {
                    'fast_ema': [10, 12, 15],
                    'slow_ema': [20, 26, 30],
                    'signal_ema': [7, 9, 11],
                    'atr_multiplier': [1.5, 2.0, 2.5]
                }
            elif strategy == 'mean_reversion':
                param_grid = {
                    'bb_period': [15, 20, 25],
                    'bb_std': [1.5, 2.0, 2.5],
                    'rsi_period': [10, 14, 20],
                    'zscore_threshold': [1.5, 2.0, 2.5]
                }
            else:
                param_grid = {}
            
            if param_grid:
                runner.optimize_parameters(strategy, args.symbol, param_grid)
    
    else:
        # Run backtest
        if args.strategy == 'all':
            # Compare all strategies
            comparison = runner.compare_strategies(
                args.symbol,
                start_date=args.start_date,
                end_date=args.end_date
            )
            
            print("\n📊 Strategy Comparison:")
            print("=" * 80)
            print(comparison.to_string(index=False))
            
            # Save comparison
            runner.save_results({'comparison': comparison.to_dict()}, 
                              f"comparison_{args.symbol}.json")
        
        else:
            # Run single strategy
            results = runner.run_backtest(
                args.strategy,
                args.symbol,
                start_date=args.start_date,
                end_date=args.end_date,
                initial_capital=args.initial_capital
            )
            
            if results:
                # Display results
                print("\n📊 Backtest Results:")
                print("=" * 50)
                print(f"Total Return: {results['total_return']:.2f}%")
                print(f"Sharpe Ratio: {results['sharpe_ratio']:.4f}")
                print(f"Max Drawdown: {results['max_drawdown']:.2f}%")
                print(f"Win Rate: {results['win_rate']:.2f}%")
                print(f"Number of Trades: {results['num_trades']}")
                
                # Plot if requested
                if args.plot:
                    runner.plot_results(results, 
                                      f"{args.strategy} - {args.symbol}")
                
                # Save results
                runner.save_results(results, 
                                  f"{args.strategy}_{args.symbol}.json")

if __name__ == '__main__':
    main()