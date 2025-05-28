#!/usr/bin/env python3
"""
Kraken Trading Bot v2.0 - Main Entry Point
==========================================
מערכת מסחר אוטומטית מתקדמת עם AI
"""

import os
import sys
import time
import logging
import argparse
import threading
import subprocess
from datetime import datetime
from typing import Dict, List, Optional
import json

# הגדרת נתיבים
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

# ייבוא מודולים
try:
    from config import Config
    from modules.git_manager import GitManager
except ImportError:
    print("❌ Error importing modules. Make sure all files are in place.")
    print("   Run: pip install -r requirements.txt")
    sys.exit(1)

# הגדרת לוגר
logger = Config.setup_logging('main')

class TradingBotManager:
    """מנהל ראשי למערכת הבוט"""
    
    def __init__(self):
        self.version = "2.0.0"
        self.workers = {}
        self.processes = {}
        self.running = False
        self.mode = None
        
        # בדיקת סביבה
        self._check_environment()
        
    def _check_environment(self):
        """בדיקת סביבת העבודה"""
        # בדיקת תיקיות
        required_dirs = ['data', 'logs', 'models', 'dashboards', 'modules']
        for dir_name in required_dirs:
            dir_path = os.path.join(BASE_DIR, dir_name)
            if not os.path.exists(dir_path):
                os.makedirs(dir_path, exist_ok=True)
                logger.info(f"Created directory: {dir_name}")
        
        # בדיקת קבצי הגדרות
        if not os.path.exists('.env'):
            if os.path.exists('.env.example'):
                logger.warning(".env file not found. Copy .env.example to .env and add your keys.")
            else:
                self._create_env_example()
                
        # בדיקת מפתחות
        if not Config.validate_keys():
            logger.warning("Some API keys are missing. Limited functionality available.")
    
    def _create_env_example(self):
        """יצירת קובץ .env.example"""
        content = """# Kraken API Credentials
KRAKEN_API_KEY=your_kraken_api_key_here
KRAKEN_API_SECRET=your_kraken_api_secret_here

# Optional APIs
OPENAI_API_KEY=your_openai_key_here
CRYPTOPANIC_API_KEY=your_cryptopanic_key_here

# Settings
LOG_LEVEL=INFO
"""
        with open('.env.example', 'w') as f:
            f.write(content)
        logger.info("Created .env.example file")
    
    def print_banner(self):
        """הצגת באנר פתיחה"""
        banner = f"""
╔═══════════════════════════════════════════════════════════════╗
║                  💎 Kraken Trading Bot v{self.version} 💎                  ║
║                                                               ║
║           Advanced AI-Powered Crypto Trading System           ║
║                    With Autonomous Trading                    ║
╚═══════════════════════════════════════════════════════════════╝
        """
        print(banner)
    
    def show_menu(self):
        """תפריט ראשי משופר"""
        self.print_banner()
        
        print("\n🎯 Main Menu:")
        print("═" * 50)
        
        menu_options = [
            ("1", "🚀 Quick Start - Simple Dashboard", "simple_dashboard"),
            ("2", "📊 Data Collection Only", "collect_data"),
            ("3", "🤖 AI Trading Dashboard", "ai_dashboard"),
            ("4", "🔄 Full System (Collection + Dashboard)", "full_system"),
            ("5", "🧪 Run Simulations", "simulations"),
            ("6", "📈 Market Analysis", "analysis"),
            ("7", "⚙️  Settings & Configuration", "settings"),
            ("8", "🔧 Debug & Test Connection", "debug"),
            ("9", "📚 Documentation", "docs"),
            ("0", "🚪 Exit", "exit")
        ]
        
        for key, desc, _ in menu_options:
            print(f"  {key}. {desc}")
        
        print("\n" + "═" * 50)
        choice = input("\n👉 Your choice: ").strip()
        
        # מיפוי בחירות
        choice_map = {opt[0]: opt[2] for opt in menu_options}
        return choice_map.get(choice, "invalid")
    
    def run_simple_dashboard(self):
        """הפעלת דאשבורד פשוט"""
        dashboard_path = os.path.join(BASE_DIR, 'dashboards', 'simple_dashboard.py')
        
        if not os.path.exists(dashboard_path):
            # נסה מיקום חלופי
            dashboard_path = os.path.join(BASE_DIR, 'simple_dashboard.py')
        
        if os.path.exists(dashboard_path):
            print("\n🚀 Starting Simple Dashboard...")
            print("📌 Opening browser at http://localhost:8501")
            
            process = subprocess.Popen([
                sys.executable, "-m", "streamlit", "run", dashboard_path
            ])
            
            self.processes['dashboard'] = process
            
            print("\n✅ Dashboard is running!")
            print("Press Ctrl+C to stop")
            
            try:
                process.wait()
            except KeyboardInterrupt:
                print("\n⏹️  Stopping dashboard...")
                process.terminate()
        else:
            print(f"❌ Dashboard file not found: {dashboard_path}")
    
    def run_data_collection(self):
        """הפעלת איסוף נתונים"""
        print("\n📊 Starting Data Collection...")
        
        # Market Collector
        def run_market_collector():
            try:
                from modules.market_collector import run_collector
                logger.info("Market Collector started")
                run_collector(interval=30)
            except Exception as e:
                logger.error(f"Market Collector error: {e}")
        
        # News Collector
        def run_news_collector():
            try:
                from modules.news_collector import NewsCollector
                logger.info("News Collector started")
                
                collector = NewsCollector(
                    currencies=['BTC', 'ETH', 'SOL', 'ADA', 'DOT'],
                    max_posts=50
                )
                
                while True:
                    collector.fetch_and_save()
                    time.sleep(300)  # 5 minutes
            except Exception as e:
                logger.error(f"News Collector error: {e}")
        
        # הפעלת threads
        market_thread = threading.Thread(target=run_market_collector, daemon=True)
        news_thread = threading.Thread(target=run_news_collector, daemon=True)
        
        market_thread.start()
        news_thread.start()
        
        print("✅ Data collection started:")
        print("   • Market data: Every 30 seconds")
        print("   • News: Every 5 minutes")
        print("\nPress Ctrl+C to stop")
        
        try:
            while True:
                time.sleep(10)
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Collecting data...")
        except KeyboardInterrupt:
            print("\n⏹️  Stopping data collection...")
    
    def run_ai_dashboard(self):
        """הפעלת דאשבורד AI מתקדם"""
        dashboard_path = os.path.join(BASE_DIR, 'dashboards', 'advanced_dashboard.py')
        
        if os.path.exists(dashboard_path):
            print("\n🤖 Starting AI Trading Dashboard...")
            print("⚠️  Warning: This includes autonomous trading features!")
            
            confirm = input("Continue? (yes/no): ").lower()
            if confirm != 'yes':
                return
            
            process = subprocess.Popen([
                sys.executable, "-m", "streamlit", "run", dashboard_path
            ])
            
            self.processes['ai_dashboard'] = process
            
            print("\n✅ AI Dashboard is running!")
            print("📌 Open browser at http://localhost:8501")
            
            try:
                process.wait()
            except KeyboardInterrupt:
                process.terminate()
        else:
            print("❌ AI Dashboard not found. Using simple dashboard instead.")
            self.run_simple_dashboard()
    
    def run_simulations(self):
        """הפעלת סימולציות"""
        print("\n🧪 Simulation Module")
        
        try:
            from modules.simulation_runner import main_menu
            main_menu()
        except ImportError:
            print("❌ Simulation module not found")
            print("Running basic simulation instead...")
            
            # סימולציה בסיסית
            from modules.simulation_core import optimize_simulation_params
            print("\n📊 Running parameter optimization...")
            optimize_simulation_params()
    
    def show_analysis(self):
        """הצגת ניתוח שוק"""
        print("\n📈 Market Analysis")
        
        try:
            from modules.market_collector import MarketCollector
            collector = MarketCollector()
            
            # שליפת נתונים
            prices = collector.get_combined_prices(['BTC', 'ETH', 'SOL'])
            
            if prices:
                print("\n💰 Current Prices:")
                print("═" * 40)
                for symbol, data in prices.items():
                    print(f"{symbol}: ${data['price']:,.2f} ({data.get('change_pct_24h', 0):+.2f}%)")
            else:
                print("❌ No market data available")
                
        except Exception as e:
            print(f"❌ Error: {e}")
    
    def show_settings(self):
        """הצגת הגדרות"""
        print("\n⚙️  Settings & Configuration")
        print("═" * 50)
        
        # מפתחות API
        print("\n🔑 API Keys:")
        print(f"  • Kraken: {'✅ Configured' if Config.KRAKEN_API_KEY else '❌ Missing'}")
        print(f"  • OpenAI: {'✅ Configured' if Config.OPENAI_API_KEY else '⚠️  Optional'}")
        print(f"  • CryptoPanic: {'✅ Configured' if Config.CRYPTOPANIC_API_KEY else '⚠️  Optional'}")
        
        # הגדרות מסחר
        print("\n💰 Trading Settings:")
        for key, value in Config.DEFAULT_TRADING_PARAMS.items():
            print(f"  • {key}: {value}")
        
        # מצב קבצים
        print("\n📁 Data Files:")
        data_files = ['market_live.csv', 'market_history.csv', 'news_feed.csv']
        for file in data_files:
            path = os.path.join(Config.DATA_DIR, file)
            if os.path.exists(path):
                size = os.path.getsize(path) / 1024  # KB
                print(f"  • {file}: ✅ {size:.1f} KB")
            else:
                print(f"  • {file}: ❌ Not found")
        
        input("\nPress Enter to continue...")
    
    def run_debug(self):
        """הפעלת כלי דיבאג"""
        print("\n🔧 Debug & Test Tools")
        
        debug_script = os.path.join(BASE_DIR, 'modules', 'debug_kraken.py')
        
        if os.path.exists(debug_script):
            subprocess.run([sys.executable, debug_script])
        else:
            print("❌ Debug tool not found")
    
    def show_docs(self):
        """הצגת תיעוד"""
        print("\n📚 Documentation")
        print("═" * 50)
        
        docs = [
            ("1", "🚀 Quick Start Guide", "quick_start"),
            ("2", "📊 Dashboard Usage", "dashboard"),
            ("3", "🤖 AI Trading Features", "ai_features"),
            ("4", "⚙️  API Configuration", "api_config"),
            ("5", "🔧 Troubleshooting", "troubleshooting")
        ]
        
        for key, title, _ in docs:
            print(f"  {key}. {title}")
        
        choice = input("\nSelect topic (or Enter to go back): ").strip()
        
        if choice == "1":
            print("\n🚀 Quick Start Guide:")
            print("1. Copy .env.example to .env")
            print("2. Add your Kraken API keys")
            print("3. Run: python main.py")
            print("4. Choose option 1 for Simple Dashboard")
        elif choice == "2":
            print("\n📊 Dashboard Usage:")
            print("• Simple Dashboard: View portfolio and market data")
            print("• AI Dashboard: Advanced features with trading")
            print("• Refresh: Click the refresh button or wait 60s")
        
        input("\nPress Enter to continue...")
    
    def run(self):
        """הפעלה ראשית"""
        while True:
            choice = self.show_menu()
            
            if choice == "exit":
                print("\n👋 Goodbye!")
                break
            elif choice == "simple_dashboard":
                self.run_simple_dashboard()
            elif choice == "collect_data":
                self.run_data_collection()
            elif choice == "ai_dashboard":
                self.run_ai_dashboard()
            elif choice == "full_system":
                # הפעל איסוף נתונים ברקע
                thread = threading.Thread(target=self.run_data_collection, daemon=True)
                thread.start()
                # הפעל דאשבורד
                self.run_ai_dashboard()
                self.run_simulations()
                self.show_analysis()
            elif choice == "simulations":
                self.run_simulations()
            elif choice == "analysis":
                self.show_analysis()
            elif choice == "settings":
                self.show_settings()
            elif choice == "debug":
                self.run_debug()
            elif choice == "docs":
                self.show_docs()
            else:
                print("❌ Invalid choice. Please try again.")
                time.sleep(1)
    
    def cleanup(self):
        """ניקוי לפני יציאה"""
        # סגירת תהליכים
        for name, process in self.processes.items():
            if process and process.poll() is None:
                logger.info(f"Terminating {name}")
                process.terminate()
        
        # שמירת מצב
        state = {
            'last_run': datetime.now().isoformat(),
            'version': self.version
        }
        
        state_file = os.path.join(Config.DATA_DIR, 'bot_state.json')
        with open(state_file, 'w') as f:
            json.dump(state, f, indent=2)

def main():
    """נקודת כניסה ראשית"""
    parser = argparse.ArgumentParser(
        description='Kraken Trading Bot v2.0'
    )
    
    parser.add_argument(
        '--mode',
        choices=['dashboard', 'collect', 'simulate', 'debug'],
        help='Direct mode execution'
    )
    
    parser.add_argument(
        '--no-git',
        action='store_true',
        help='Disable git auto-update'
    )
    
    args = parser.parse_args()
    
    # Git auto-update
    if not args.no_git and os.path.exists('.git'):
        try:
            git = GitManager()
            git.auto_update()
        except Exception as e:
            logger.warning(f"Git update failed: {e}")
    
    # יצירת מנהל
    bot_manager = TradingBotManager()
    
    try:
        # מצב ישיר או תפריט
        if args.mode:
            if args.mode == 'dashboard':
                bot_manager.run_simple_dashboard()
            elif args.mode == 'collect':
                bot_manager.run_data_collection()
            elif args.mode == 'simulate':
                bot_manager.run_simulations()
            elif args.mode == 'debug':
                bot_manager.run_debug()
        else:
            # תפריט אינטראקטיבי
            bot_manager.run()
    
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
    finally:
        bot_manager.cleanup()
        print("\n✅ Cleanup complete. Goodbye!")

if __name__ == '__main__':
    main()