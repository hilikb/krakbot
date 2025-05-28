import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import json
from tqdm import tqdm

# הוספת נתיב למודולים
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config
from modules.simulation_core import SimulationEngine
from modules.ai_advisor import AIAdvisor

logger = Config.setup_logging('simulation_runner')

class SimulationRunner:
    """מנהל הרצת סימולציות עם ממשק משופר"""
    
    def __init__(self):
        self.results_history = []
        self.ai_advisor = AIAdvisor(api_key=Config.OPENAI_API_KEY)
        
    def load_market_data(self, symbol: str, days: int = 30, 
                        use_live: bool = True) -> pd.DataFrame:
        """טעינת נתוני שוק לסימולציה"""
        data_frames = []
        
        # טעינת היסטוריה
        if os.path.exists(Config.MARKET_HISTORY_FILE):
            try:
                hist_df = pd.read_csv(Config.MARKET_HISTORY_FILE)
                hist_df['timestamp'] = pd.to_datetime(hist_df['timestamp'])
                
                # סינון לפי מטבע ותקופה
                symbol_pattern = f"{symbol}USD"
                hist_df = hist_df[hist_df['pair'].str.contains(symbol_pattern, na=False)]
                
                if not hist_df.empty:
                    # סינון לפי תאריך
                    cutoff_date = datetime.now() - timedelta(days=days)
                    hist_df = hist_df[hist_df['timestamp'] >= cutoff_date]
                    data_frames.append(hist_df)
                    
            except Exception as e:
                logger.error(f"Error loading history: {e}")
        
        # טעינת נתונים חיים
        if use_live and os.path.exists(Config.MARKET_LIVE_FILE):
            try:
                live_df = pd.read_csv(Config.MARKET_LIVE_FILE)
                live_df['timestamp'] = pd.to_datetime(live_df['timestamp'])
                
                # סינון לפי מטבע
                symbol_pattern = f"{symbol}USD"
                live_df = live_df[live_df['pair'].str.contains(symbol_pattern, na=False)]
                
                if not live_df.empty:
                    data_frames.append(live_df)
                    
            except Exception as e:
                logger.error(f"Error loading live data: {e}")
        
        # איחוד ומיון
        if data_frames:
            df = pd.concat(data_frames, ignore_index=True)
            df = df.drop_duplicates(subset=['timestamp'])
            df = df.sort_values('timestamp').reset_index(drop=True)
            
            # וידוא שיש מספיק נתונים
            if len(df) < 50:
                logger.warning(f"Only {len(df)} data points found for {symbol}")
                
            return df
        else:
            logger.error(f"No data found for {symbol}")
            return pd.DataFrame()
    
    def run_single_simulation(self, 
                            symbol: str,
                            strategy: str,
                            params: Dict,
                            days: int = 30,
                            use_live: bool = True) -> Dict:
        """הרצת סימולציה בודדת"""
        
        # טעינת נתונים
        df = self.load_market_data(symbol, days, use_live)
        if df.empty:
            return {
                'status': 'failed',
                'error': 'No data available'
            }
        
        # הרצת סימולציה
        engine = SimulationEngine(
            initial_balance=params.get('initial_balance', 1000),
            take_profit=params.get('take_profit', 0.1),
            stop_loss=params.get('stop_loss', 0.05),
            max_positions=params.get('max_positions', 2)
        )
        
        start_time = datetime.now()
        results = engine.run_simulation(df, strategy=strategy)
        end_time = datetime.now()
        
        # הכנת תוצאות מורחבות
        simulation_result = {
            'id': f"SIM_{start_time.strftime('%Y%m%d_%H%M%S')}_{symbol}",
            'symbol': symbol,
            'strategy': strategy,
            'params': params,
            'start_time': start_time,
            'end_time': end_time,
            'duration_seconds': (end_time - start_time).total_seconds(),
            'data_points': len(df),
            'date_range': {
                'start': df['timestamp'].min().isoformat(),
                'end': df['timestamp'].max().isoformat()
            },
            'status': 'completed',
            'initial_balance': params['initial_balance'],
            'final_balance': results['final_balance'],
            'profit_pct': results['total_profit_pct'],
            'profit_amount': results['final_balance'] - params['initial_balance'],
            'trades_count': len(results['trade_log']),
            'trade_log': results['trade_log']
        }
        
        # חישוב מטריקות נוספות
        if not results['trade_log'].empty:
            trades_df = results['trade_log']
            winning_trades = trades_df[trades_df['profit_pct'] > 0]
            losing_trades = trades_df[trades_df['profit_pct'] < 0]
            
            simulation_result['metrics'] = {
                'win_rate': len(winning_trades) / len(trades_df) * 100,
                'avg_win': winning_trades['profit_pct'].mean() * 100 if not winning_trades.empty else 0,
                'avg_loss': losing_trades['profit_pct'].mean() * 100 if not losing_trades.empty else 0,
                'max_win': winning_trades['profit_pct'].max() * 100 if not winning_trades.empty else 0,
                'max_loss': losing_trades['profit_pct'].min() * 100 if not losing_trades.empty else 0,
                'total_wins': len(winning_trades),
                'total_losses': len(losing_trades)
            }
        else:
            simulation_result['metrics'] = {
                'win_rate': 0,
                'avg_win': 0,
                'avg_loss': 0,
                'max_win': 0,
                'max_loss': 0,
                'total_wins': 0,
                'total_losses': 0
            }
        
        # שמירה להיסטוריה
        self.results_history.append(simulation_result)
        self._save_simulation_log(simulation_result)
        
        return simulation_result
    
    def run_batch_simulations(self,
                            symbols: List[str],
                            strategies: List[str],
                            params_grid: List[Dict],
                            days: int = 30) -> pd.DataFrame:
        """הרצת מספר סימולציות במקביל"""
        
        total_sims = len(symbols) * len(strategies) * len(params_grid)
        logger.info(f"Starting batch simulation: {total_sims} simulations")
        
        results = []
        with tqdm(total=total_sims, desc="Running simulations") as pbar:
            for symbol in symbols:
                for strategy in strategies:
                    for params in params_grid:
                        result = self.run_single_simulation(
                            symbol=symbol,
                            strategy=strategy,
                            params=params,
                            days=days
                        )
                        results.append(result)
                        pbar.update(1)
        
        # יצירת DataFrame מסכם
        summary_data = []
        for r in results:
            if r['status'] == 'completed':
                summary_data.append({
                    'symbol': r['symbol'],
                    'strategy': r['strategy'],
                    'initial_balance': r['initial_balance'],
                    'final_balance': r['final_balance'],
                    'profit_pct': r['profit_pct'] * 100,
                    'trades': r['trades_count'],
                    'win_rate': r['metrics']['win_rate'],
                    'take_profit': r['params']['take_profit'],
                    'stop_loss': r['params']['stop_loss'],
                    'max_positions': r['params']['max_positions']
                })
        
        summary_df = pd.DataFrame(summary_data)
        return summary_df
    
    def get_ai_analysis(self, simulation_result: Dict) -> str:
        """קבלת ניתוח AI לתוצאות הסימולציה"""
        if not Config.OPENAI_API_KEY:
            return "AI analysis not available (OpenAI API key not configured)"
            
        try:
            analysis = self.ai_advisor.ask_for_advice(
                simulation_result,
                strategy_name=simulation_result['strategy']
            )
            return analysis
        except Exception as e:
            logger.error(f"AI analysis error: {e}")
            return f"AI analysis failed: {str(e)}"
    
    def _save_simulation_log(self, result: Dict):
        """שמירת תוצאות סימולציה ללוג"""
        log_data = {
            'id': result['id'],
            'symbol': result['symbol'],
            'strategy': result['strategy'],
            'start_time': result['start_time'].isoformat(),
            'end_time': result['end_time'].isoformat(),
            'status': result['status'],
            'init_balance': result['initial_balance'],
            'final_balance': result['final_balance'],
            'profit_pct': result['profit_pct'],
            'trades_count': result['trades_count'],
            'params': json.dumps(result['params'])
        }
        
        try:
            df = pd.DataFrame([log_data])
            header = not os.path.exists(Config.SIMULATION_LOG_FILE)
            df.to_csv(
                Config.SIMULATION_LOG_FILE,
                mode='a',
                header=header,
                index=False
            )
        except Exception as e:
            logger.error(f"Failed to save simulation log: {e}")
    
    def display_results(self, result: Dict):
        """הצגת תוצאות סימולציה בצורה ברורה"""
        print("\n" + "="*60)
        print(f"📊 תוצאות סימולציה: {result['id']}")
        print("="*60)
        
        # נתונים כלליים
        print(f"\n🪙 מטבע: {result['symbol']}")
        print(f"📈 אסטרטגיה: {result['strategy']}")
        print(f"⏱️  משך: {result['duration_seconds']:.1f} שניות")
        print(f"📅 טווח נתונים: {result['data_points']} נקודות")
        
        # תוצאות פיננסיות
        print(f"\n💰 תוצאות פיננסיות:")
        print(f"  • הון התחלתי: ${result['initial_balance']:,.2f}")
        print(f"  • יתרה סופית: ${result['final_balance']:,.2f}")
        
        profit_emoji = "🟢" if result['profit_pct'] > 0 else "🔴"
        print(f"  • רווח/הפסד: {profit_emoji} {result['profit_pct']*100:+.2f}% (${result['profit_amount']:+,.2f})")
        
        # מטריקות מסחר
        if result['trades_count'] > 0:
            metrics = result['metrics']
            print(f"\n📊 מטריקות מסחר:")
            print(f"  • מספר עסקאות: {result['trades_count']}")
            print(f"  • אחוז הצלחה: {metrics['win_rate']:.1f}%")
            print(f"  • רווח ממוצע: {metrics['avg_win']:.2f}%")
            print(f"  • הפסד ממוצע: {metrics['avg_loss']:.2f}%")
            print(f"  • רווח מקסימלי: {metrics['max_win']:.2f}%")
            print(f"  • הפסד מקסימלי: {metrics['max_loss']:.2f}%")
        
        # פרמטרים
        print(f"\n⚙️  פרמטרים:")
        print(f"  • Take Profit: {result['params']['take_profit']*100}%")
        print(f"  • Stop Loss: {result['params']['stop_loss']*100}%")
        print(f"  • פוזיציות מקסימום: {result['params']['max_positions']}")
        
        print("\n" + "="*60)


def run_interactive_simulation():
    """הרצת סימולציה אינטראקטיבית"""
    runner = SimulationRunner()
    
    print("\n🧪 מערכת סימולציות מסחר")
    print("="*40)
    
    # בחירת מטבע
    available_coins = Config.DEFAULT_COINS
    print("\nמטבעות זמינים:")
    for i, coin in enumerate(available_coins, 1):
        print(f"  {i}. {coin}")
    
    coin_idx = int(input("\nבחר מטבע (מספר): ")) - 1
    symbol = available_coins[coin_idx]
    
    # בחירת אסטרטגיה
    strategies = [
        ('combined', 'משולבת - כל האינדיקטורים'),
        ('rsi', 'RSI - Relative Strength Index'),
        ('ema', 'EMA - Exponential Moving Average'),
        ('macd', 'MACD'),
        ('bollinger', 'Bollinger Bands'),
        ('sma', 'SMA - Simple Moving Average')
    ]
    
    print("\nאסטרטגיות זמינות:")
    for i, (key, desc) in enumerate(strategies, 1):
        print(f"  {i}. {desc}")
    
    strat_idx = int(input("\nבחר אסטרטגיה (מספר): ")) - 1
    strategy = strategies[strat_idx][0]
    
    # פרמטרים
    print("\nהגדרת פרמטרים:")
    initial_balance = float(input("  הון התחלתי ($) [1000]: ") or 1000)
    take_profit = float(input("  יעד רווח (%) [10]: ") or 10) / 100
    stop_loss = float(input("  סטופ לוס (%) [5]: ") or 5) / 100
    max_positions = int(input("  פוזיציות מקסימום [2]: ") or 2)
    days = int(input("  תקופה בימים [30]: ") or 30)
    
    params = {
        'initial_balance': initial_balance,
        'take_profit': take_profit,
        'stop_loss': stop_loss,
        'max_positions': max_positions
    }
    
    # הרצה
    print("\n⏳ מריץ סימולציה...")
    result = runner.run_single_simulation(
        symbol=symbol,
        strategy=strategy,
        params=params,
        days=days
    )
    
    # הצגת תוצאות
    if result['status'] == 'completed':
        runner.display_results(result)
        
        # הצעת ניתוח AI
        if input("\n🤖 לקבל ניתוח AI? (y/n): ").lower() == 'y':
            print("\n⏳ מנתח תוצאות...")
            analysis = runner.get_ai_analysis(result)
            print("\n🤖 ניתוח AI:")
            print("-" * 40)
            print(analysis)
            print("-" * 40)
        
        # שמירת תוצאות מפורטות
        if input("\n💾 לשמור תוצאות מפורטות? (y/n): ").lower() == 'y':
            filename = f"simulation_{result['id']}.json"
            filepath = os.path.join(Config.DATA_DIR, filename)
            
            # הכנת נתונים לשמירה
            save_data = result.copy()
            if 'trade_log' in save_data and isinstance(save_data['trade_log'], pd.DataFrame):
                save_data['trade_log'] = save_data['trade_log'].to_dict('records')
            
            # המרת תאריכים לפורמט string
            for key in ['start_time', 'end_time']:
                if key in save_data and hasattr(save_data[key], 'isoformat'):
                    save_data[key] = save_data[key].isoformat()
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, indent=2, ensure_ascii=False)
            
            print(f"✅ נשמר בקובץ: {filename}")
        
        # הצעת סימולציות נוספות
        if input("\n🔄 להריץ סימולציה נוספת? (y/n): ").lower() == 'y':
            run_interactive_simulation()
    
    else:
        print(f"\n❌ הסימולציה נכשלה: {result.get('error', 'Unknown error')}")


def run_optimization_wizard():
    """אשף אופטימיזציה אינטראקטיבי"""
    runner = SimulationRunner()
    
    print("\n🔧 אשף אופטימיזציה")
    print("="*40)
    
    # בחירת מטבעות
    print("\nבחר מטבעות לאופטימיזציה:")
    print("1. מטבע בודד")
    print("2. Top 5 מטבעות")
    print("3. כל המטבעות הזמינים")
    
    choice = input("\nבחירה: ")
    
    if choice == '1':
        available_coins = Config.DEFAULT_COINS
        print("\nמטבעות זמינים:")
        for i, coin in enumerate(available_coins, 1):
            print(f"  {i}. {coin}")
        coin_idx = int(input("\nבחר מטבע (מספר): ")) - 1
        symbols = [available_coins[coin_idx]]
    elif choice == '2':
        symbols = Config.DEFAULT_COINS[:5]
    else:
        symbols = Config.DEFAULT_COINS
    
    # בחירת אסטרטגיות
    print("\nבחר אסטרטגיות לבדיקה:")
    print("1. כל האסטרטגיות")
    print("2. רק אסטרטגיה משולבת")
    print("3. בחירה מותאמת")
    
    choice = input("\nבחירה: ")
    
    if choice == '1':
        strategies = ['combined', 'rsi', 'ema', 'macd', 'bollinger', 'sma']
    elif choice == '2':
        strategies = ['combined']
    else:
        all_strategies = ['combined', 'rsi', 'ema', 'macd', 'bollinger', 'sma']
        strategies = []
        print("\nסמן אסטרטגיות (y/n):")
        for strat in all_strategies:
            if input(f"  {strat}? ").lower() == 'y':
                strategies.append(strat)
    
    # הגדרת טווחי פרמטרים
    print("\nהגדרת טווחי פרמטרים:")
    
    # Take Profit
    tp_values = []
    tp_input = input("Take Profit (%) [5,10,15]: ") or "5,10,15"
    tp_values = [float(x)/100 for x in tp_input.split(',')]
    
    # Stop Loss
    sl_values = []
    sl_input = input("Stop Loss (%) [2,5,10]: ") or "2,5,10"
    sl_values = [float(x)/100 for x in sl_input.split(',')]
    
    # Max Positions
    mp_values = []
    mp_input = input("Max Positions [1,2,3]: ") or "1,2,3"
    mp_values = [int(x) for x in mp_input.split(',')]
    
    # Initial Balance
    balance = float(input("Initial Balance ($) [1000]: ") or 1000)
    
    # Days
    days = int(input("Period (days) [30]: ") or 30)
    
    # יצירת גריד פרמטרים
    params_grid = []
    for tp in tp_values:
        for sl in sl_values:
            for mp in mp_values:
                params_grid.append({
                    'initial_balance': balance,
                    'take_profit': tp,
                    'stop_loss': sl,
                    'max_positions': mp
                })
    
    total_sims = len(symbols) * len(strategies) * len(params_grid)
    print(f"\n📊 סה״כ סימולציות: {total_sims}")
    
    if input("להתחיל? (y/n): ").lower() != 'y':
        return
    
    # הרצת אופטימיזציה
    print("\n⏳ מריץ אופטימיזציה...")
    results_df = runner.run_batch_simulations(
        symbols=symbols,
        strategies=strategies,
        params_grid=params_grid,
        days=days
    )
    
    # הצגת תוצאות
    print("\n📊 תוצאות אופטימיזציה:")
    print("="*60)
    
    if not results_df.empty:
        # מיון לפי רווח
        results_df = results_df.sort_values('profit_pct', ascending=False)
        
        # Top 10 תוצאות
        print("\n🏆 Top 10 תוצאות:")
        print(results_df.head(10).to_string(index=False))
        
        # סטטיסטיקות כלליות
        print("\n📈 סטטיסטיקות כלליות:")
        print(f"  • רווח ממוצע: {results_df['profit_pct'].mean():.2f}%")
        print(f"  • רווח מקסימלי: {results_df['profit_pct'].max():.2f}%")
        print(f"  • הפסד מקסימלי: {results_df['profit_pct'].min():.2f}%")
        print(f"  • אחוז רווחיות: {(results_df['profit_pct'] > 0).mean()*100:.1f}%")
        
        # הטוב ביותר לכל אסטרטגיה
        print("\n🎯 הטוב ביותר לכל אסטרטגיה:")
        for strategy in strategies:
            strat_df = results_df[results_df['strategy'] == strategy]
            if not strat_df.empty:
                best = strat_df.iloc[0]
                print(f"\n{strategy}:")
                print(f"  • מטבע: {best['symbol']}")
                print(f"  • רווח: {best['profit_pct']:.2f}%")
                print(f"  • TP: {best['take_profit']*100}%, SL: {best['stop_loss']*100}%")
                print(f"  • פוזיציות: {best['max_positions']}")
        
        # שמירת תוצאות
        if input("\n💾 לשמור תוצאות אופטימיזציה? (y/n): ").lower() == 'y':
            filename = f"optimization_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            filepath = os.path.join(Config.DATA_DIR, filename)
            results_df.to_csv(filepath, index=False)
            print(f"✅ נשמר בקובץ: {filename}")
    
    else:
        print("❌ לא התקבלו תוצאות")


def main_menu():
    """תפריט ראשי לסימולציות"""
    while True:
        print("\n🧪 מערכת סימולציות מסחר")
        print("="*40)
        print("1. הרצת סימולציה בודדת")
        print("2. אשף אופטימיזציה")
        print("3. צפייה בהיסטוריית סימולציות")
        print("4. ניתוח תוצאות קיימות")
        print("q. יציאה")
        
        choice = input("\nבחירה: ").lower()
        
        if choice == '1':
            run_interactive_simulation()
        elif choice == '2':
            run_optimization_wizard()
        elif choice == '3':
            view_simulation_history()
        elif choice == '4':
            analyze_existing_results()
        elif choice == 'q':
            break
        else:
            print("❌ בחירה לא תקינה")


def view_simulation_history():
    """צפייה בהיסטוריית סימולציות"""
    if not os.path.exists(Config.SIMULATION_LOG_FILE):
        print("\n❌ אין היסטוריית סימולציות")
        return
    
    try:
        df = pd.read_csv(Config.SIMULATION_LOG_FILE)
        df['start_time'] = pd.to_datetime(df['start_time'])
        df = df.sort_values('start_time', ascending=False)
        
        print(f"\n📊 היסטוריית סימולציות ({len(df)} סימולציות)")
        print("="*80)
        
        # הצגת 20 האחרונות
        display_df = df[['symbol', 'strategy', 'start_time', 'profit_pct', 'final_balance', 'trades_count']].head(20)
        display_df['profit_pct'] = display_df['profit_pct'] * 100
        
        print(display_df.to_string(index=False))
        
        # סטטיסטיקות
        print("\n📈 סטטיסטיקות כלליות:")
        print(f"  • סה״כ סימולציות: {len(df)}")
        print(f"  • רווח ממוצע: {df['profit_pct'].mean()*100:.2f}%")
        print(f"  • אחוז הצלחה: {(df['profit_pct'] > 0).mean()*100:.1f}%")
        
    except Exception as e:
        print(f"\n❌ שגיאה בטעינת היסטוריה: {e}")


def analyze_existing_results():
    """ניתוח תוצאות קיימות"""
    if not os.path.exists(Config.SIMULATION_LOG_FILE):
        print("\n❌ אין תוצאות לניתוח")
        return
    
    try:
        df = pd.read_csv(Config.SIMULATION_LOG_FILE)
        
        print("\n📊 ניתוח תוצאות סימולציות")
        print("="*60)
        
        # ניתוח לפי אסטרטגיה
        print("\n🎯 ביצועים לפי אסטרטגיה:")
        strategy_stats = df.groupby('strategy').agg({
            'profit_pct': ['mean', 'std', 'count'],
            'trades_count': 'mean'
        })
        strategy_stats.columns = ['רווח ממוצע', 'סטיית תקן', 'מספר סימולציות', 'עסקאות ממוצע']
        strategy_stats['רווח ממוצע'] *= 100
        strategy_stats['סטיית תקן'] *= 100
        print(strategy_stats.round(2))
        
        # ניתוח לפי מטבע
        print("\n💰 ביצועים לפי מטבע:")
        symbol_stats = df.groupby('symbol').agg({
            'profit_pct': ['mean', 'count']
        })
        symbol_stats.columns = ['רווח ממוצע %', 'מספר סימולציות']
        symbol_stats['רווח ממוצע %'] *= 100
        symbol_stats = symbol_stats.sort_values('רווח ממוצע %', ascending=False)
        print(symbol_stats.head(10).round(2))
        
        # המלצות
        print("\n💡 המלצות:")
        best_strategy = strategy_stats['רווח ממוצע'].idxmax()
        best_symbol = symbol_stats['רווח ממוצע %'].idxmax()
        
        print(f"  • האסטרטגיה הטובה ביותר: {best_strategy}")
        print(f"  • המטבע הרווחי ביותר: {best_symbol}")
        
    except Exception as e:
        print(f"\n❌ שגיאה בניתוח: {e}")


if __name__ == '__main__':
    main_menu()