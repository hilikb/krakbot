#!/usr/bin/env python3
"""
Kraken Trading Bot v2.0 - Main Entry Point (Updated & Fixed)
============================================================
מערכת מסחר אוטומטית מתקדמת עם AI - גרסה מתוקנת
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

# הגדרת נתיבים תקינים
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODULES_DIR = os.path.join(BASE_DIR, 'modules')
DASHBOARDS_DIR = os.path.join(BASE_DIR, 'dashboards')

# הוספת נתיבים ל-Python path
for path in [BASE_DIR, MODULES_DIR, DASHBOARDS_DIR]:
    if path not in sys.path:
        sys.path.insert(0, path)

# ייבוא מודולים עם טיפול בשגיאות
try:
    from config import Config
except ImportError:
    print("❌ Config module not found. Please ensure config.py exists.")
    sys.exit(1)

# הגדרת לוגר
logger = Config.setup_logging('main')

class TradingBotManager:
    """מנהל ראשי למערכת הבוט - גרסה מתוקנת"""
    
    def __init__(self):
        self.version = "2.0.1"
        self.workers = {}
        self.processes = {}
        self.running = False
        self.mode = None
        
        # בדיקת סביבה מתקדמת
        self._check_environment()
        
    def _check_environment(self):
        """בדיקת סביבת העבודה המתקדמת"""
        print("🔍 Checking system environment...")
        
        # בדיקת Python version
        if sys.version_info < (3, 8):
            print("⚠️  Warning: Python 3.8+ recommended")
        
        # בדיקת תיקיות
        required_dirs = {
            'data': 'Data storage',
            'logs': 'Log files', 
            'modules': 'Core modules',
            'dashboards': 'Dashboard files',
            'models': 'ML models (optional)'
        }
        
        for dir_name, description in required_dirs.items():
            dir_path = os.path.join(BASE_DIR, dir_name)
            if not os.path.exists(dir_path):
                os.makedirs(dir_path, exist_ok=True)
                logger.info(f"Created directory: {dir_name} ({description})")
            else:
                print(f"✅ {dir_name}/ - {description}")
        
        # בדיקת dependencies קריטיים
        critical_packages = [
            ('pandas', 'Data manipulation'),
            ('numpy', 'Numerical computing'),
            ('krakenex', 'Kraken API'),
            ('streamlit', 'Dashboard framework')
        ]
        
        missing_packages = []
        for package, description in critical_packages:
            try:
                __import__(package)
                print(f"✅ {package} - {description}")
            except ImportError:
                missing_packages.append(package)
                print(f"❌ {package} - {description} (MISSING)")
        
        if missing_packages:
            print(f"\n⚠️  Missing packages: {', '.join(missing_packages)}")
            print("Run: pip install -r requirements.txt")
        
        # בדיקת קבצי הגדרות
        if not os.path.exists('.env'):
            if os.path.exists('.env.example'):
                print("⚠️  .env file not found. Copy .env.example to .env and add your keys.")
            else:
                self._create_env_example()
        else:
            print("✅ .env configuration file found")
        
        # בדיקת מפתחות API - גרסה מתוקנת
        try:
            api_status = Config.validate_keys()
            if api_status:
                print("✅ API keys configured")
            else:
                print("⚠️  Some API keys missing - limited functionality")
        except Exception as e:
            print(f"⚠️  Error checking API keys: {e}")
    
    def _create_env_example(self):
        """יצירת קובץ .env.example מתקדם"""
        content = '''# Kraken API Credentials (Required for live trading)
KRAKEN_API_KEY=your_kraken_api_key_here
KRAKEN_API_SECRET=your_kraken_api_secret_here

# Optional AI Features
OPENAI_API_KEY=your_openai_key_here
CRYPTOPANIC_API_KEY=your_cryptopanic_key_here

# System Settings
LOG_LEVEL=INFO
DEMO_MODE=true
AUTO_BACKUP=true

# Trading Parameters
DEFAULT_RISK_LEVEL=5
MAX_DAILY_TRADES=20
STOP_LOSS_PERCENT=5
TAKE_PROFIT_PERCENT=10
'''
        
        with open('.env.example', 'w') as f:
            f.write(content)
        logger.info("Created .env.example file")
        print("✅ Created .env.example - copy to .env and configure")
    
    def print_banner(self):
        """הצגת באנר פתיחה משופר"""
        banner = f"""
╔═══════════════════════════════════════════════════════════════╗
║                  💎 Kraken Trading Bot v{self.version} 💎                  ║
║                                                               ║
║         🤖 Advanced AI-Powered Crypto Trading System         ║
║              🚀 With Autonomous Trading Features             ║
║                                                               ║
║  📊 Real-time Data  🧠 ML Predictions  ⚡ Auto Trading      ║
╚═══════════════════════════════════════════════════════════════╝
        """
        print(banner)
    
    def show_menu(self):
        """תפריט ראשי משופר עם בדיקת זמינות - גרסה מתוקנת"""
        self.print_banner()
        
        print("\n🎯 Main Menu:")
        print("═" * 60)
        
        # בדיקת זמינות features - גרסה מתוקנת
        features_status = self._check_features_availability()
        
        menu_options = [
            ("1", "🚀 Quick Start - Simple Dashboard", "simple_dashboard", True),
            ("2", "📊 Data Collection System", "collect_data", features_status['data_collection']),
            ("3", "🤖 AI Trading Dashboard", "ai_dashboard", features_status['ai_features']),
            ("4", "🔄 Full System (All Components)", "full_system", features_status['full_system']),
            ("5", "🧪 Trading Simulations", "simulations", features_status['simulations']),
            ("6", "📈 Market Analysis Tools", "analysis", features_status['analysis']),
            ("7", "⚙️  System Configuration", "settings", True),
            ("8", "🪙 Symbol & Asset Manager", "symbols", features_status['data_collection']),
            ("9", "🔧 Debug & Diagnostics", "debug", True),
            ("10", "📚 Help & Documentation", "docs", True),
            ("0", "🚪 Exit System", "exit", True)
        ]
        
        for key, desc, _, available in menu_options:
            status = "✅" if available else "❌"
            color = "" if available else " (unavailable)"
            print(f"  {key}. {status} {desc}{color}")
        
        print("\n" + "═" * 60)
        
        # הצגת סטטוס מערכת
        self._show_system_status()
        
        choice = input("\n👉 Your choice: ").strip()
        
        # מיפוי בחירות
        choice_map = {opt[0]: opt[2] for opt in menu_options}
        return choice_map.get(choice, "invalid")
    
    def _check_features_availability(self):
        """בדיקת זמינות features - גרסה מתוקנת"""
        status = {
            'data_collection': True,
            'ai_features': bool(Config.get_api_key('OPENAI_API_KEY')),  # תוקן כאן!
            'simulations': True,
            'analysis': True,
            'full_system': True
        }
        
        # בדיקת modules זמינים
        try:
            from market_collector import MarketCollector
            status['data_collection'] = True
        except ImportError:
            status['data_collection'] = False
            logger.warning("Market collector module not available")
        
        try:
            from ai_trading_engine import AITradingEngine
            status['ai_features'] = status['ai_features'] and True
        except ImportError:
            status['ai_features'] = False
        
        status['full_system'] = all([
            status['data_collection'],
            status['simulations'],
            status['analysis']
        ])
        
        return status
    
    def _show_system_status(self):
        """הצגת סטטוס מערכת - גרסה מתוקנת"""
        print("\n📊 System Status:")
        print(f"  • Version: {self.version}")
        print(f"  • Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # API Keys status - גרסה מתוקנת
        kraken_key_status = Config.get_api_key_status('KRAKEN_API_KEY')
        openai_key_status = Config.get_api_key_status('OPENAI_API_KEY')
        
        print(f"  • API Keys: {'✅ Configured' if kraken_key_status.get('configured') else '❌ Missing'}")
        print(f"  • AI Features: {'✅ Available' if openai_key_status.get('configured') else '⚠️  Limited'}")
        
        # בדיקת קבצי נתונים
        data_files = ['market_live.csv', 'market_history.csv', 'news_feed.csv']
        data_status = []
        for file in data_files:
            path = os.path.join(Config.DATA_DIR, file)
            if os.path.exists(path):
                size = os.path.getsize(path) / 1024  # KB
                data_status.append(f"{file}({size:.1f}KB)")
        
        if data_status:
            print(f"  • Data Files: {len(data_status)} available")
        else:
            print("  • Data Files: None (will be created)")
    
    def run_simple_dashboard(self):
        """הפעלת דאשבורד פשוט עם בדיקות"""
        dashboard_paths = [
            os.path.join(DASHBOARDS_DIR, 'simple_dashboard.py'),
            os.path.join(BASE_DIR, 'simple_dashboard.py'),
            os.path.join(BASE_DIR, 'dashboards', 'simple_dashboard.py')
        ]
        
        dashboard_path = None
        for path in dashboard_paths:
            if os.path.exists(path):
                dashboard_path = path
                break
        
        if not dashboard_path:
            print("❌ Simple dashboard not found!")
            print("Expected locations:")
            for path in dashboard_paths:
                print(f"  - {path}")
            return
        
        print("\n🚀 Starting Simple Dashboard...")
        print(f"📍 Location: {dashboard_path}")
        print("🌐 Opening browser at http://localhost:8501")
        print("⏹️  Press Ctrl+C to stop")
        
        try:
            # בדיקת streamlit
            import streamlit
            
            process = subprocess.Popen([
                sys.executable, "-m", "streamlit", "run", dashboard_path,
                "--server.headless", "false",
                "--server.port", "8501",
                "--server.address", "localhost"
            ])
            
            self.processes['dashboard'] = process
            
            print("\n✅ Dashboard is running!")
            print("   • URL: http://localhost:8501")
            print("   • Press Ctrl+C to stop")
            
            try:
                process.wait()
            except KeyboardInterrupt:
                print("\n⏹️  Stopping dashboard...")
                process.terminate()
                process.wait(timeout=5)
                
        except ImportError:
            print("❌ Streamlit not installed. Run: pip install streamlit")
        except Exception as e:
            print(f"❌ Error starting dashboard: {e}")
    
    def run_data_collection(self):
        """הפעלת איסוף נתונים עם error handling"""
        print("\n📊 Initializing Data Collection System...")
        
        # בדיקת modules
        modules_status = {}
        
        try:
            from market_collector import MarketCollector, run_collector
            modules_status['market'] = True
            print("✅ Market collector available")
        except ImportError as e:
            modules_status['market'] = False
            print(f"❌ Market collector error: {e}")
        
        try:
            from news_collector import NewsCollector, run_news_monitor
            modules_status['news'] = True
            print("✅ News collector available")
        except ImportError as e:
            modules_status['news'] = False
            print(f"❌ News collector error: {e}")
        
        if not any(modules_status.values()):
            print("❌ No collection modules available")
            return
        
        print("\n🔄 Starting collection processes...")
        
        # Market Collector
        if modules_status['market']:
            def run_market_collector():
                try:
                    print("📊 Market Collector: Starting...")
                    run_collector(interval=30)
                except Exception as e:
                    logger.error(f"Market Collector error: {e}")
                    print(f"❌ Market Collector failed: {e}")
            
            market_thread = threading.Thread(target=run_market_collector, daemon=True)
            market_thread.start()
            print("✅ Market data collection started (30s intervals)")
        
        # News Collector
        if modules_status['news']:
            def run_news_collector():
                try:
                    print("📰 News Collector: Starting...")
                    run_news_monitor(interval=300)
                except Exception as e:
                    logger.error(f"News Collector error: {e}")
                    print(f"❌ News Collector failed: {e}")
            
            news_thread = threading.Thread(target=run_news_collector, daemon=True)
            news_thread.start()  
            print("✅ News collection started (5min intervals)")
        
        print("\n📊 Data Collection Status:")
        print("  • Market data: Every 30 seconds")
        print("  • News feed: Every 5 minutes")
        print("  • Files saved to: data/")
        print("\n⏹️  Press Ctrl+C to stop all collection")
        
        try:
            while True:
                time.sleep(10)
                current_time = datetime.now().strftime('%H:%M:%S')
                print(f"[{current_time}] ⚡ System running... (Ctrl+C to stop)")
        except KeyboardInterrupt:
            print("\n⏹️  Stopping data collection...")
            print("✅ Collection stopped")
    
    def run_ai_dashboard(self):
        """הפעלת דאשבורד AI מתקדם"""
        ai_dashboard_paths = [
            os.path.join(DASHBOARDS_DIR, 'advanced_dashboard.py'),
            os.path.join(BASE_DIR, 'advanced_dashboard.py')
        ]
        
        dashboard_path = None
        for path in ai_dashboard_paths:
            if os.path.exists(path):
                dashboard_path = path
                break
        
        if not dashboard_path:
            print("❌ AI Dashboard not found, falling back to simple dashboard...")
            self.run_simple_dashboard()
            return
        
        print("\n🤖 Starting AI Trading Dashboard...")
        print("⚠️  Warning: This includes autonomous trading features!")
        
        # בדיקת API keys - גרסה מתוקנת
        if not Config.get_api_key('KRAKEN_API_KEY'):
            print("⚠️  Note: No API keys - running in demo mode")
        
        confirm = input("\nContinue? (yes/no): ").lower()
        if confirm not in ['yes', 'y']:
            return
        
        try:
            process = subprocess.Popen([
                sys.executable, "-m", "streamlit", "run", dashboard_path,
                "--server.port", "8502"  # Different port for AI dashboard
            ])
            
            self.processes['ai_dashboard'] = process
            
            print("\n✅ AI Dashboard is running!")
            print("🌐 Open browser at http://localhost:8502")
            
            try:
                process.wait()
            except KeyboardInterrupt:
                print("\n⏹️  Stopping AI dashboard...")
                process.terminate()
                
        except Exception as e:
            print(f"❌ Error starting AI dashboard: {e}")
            print("Falling back to simple dashboard...")
            self.run_simple_dashboard()
    
    def run_full_system(self):
        """הפעלת מערכת מלאה עם ניהול תהליכים"""
        print("\n🚀 Starting Full Trading System...")
        print("="*50)
        
        # בדיקת דרישות
        print("🔍 Checking system requirements...")
        
        required_features = self._check_features_availability()
        missing_features = [k for k, v in required_features.items() if not v]
        
        if missing_features:
            print(f"⚠️  Some features unavailable: {', '.join(missing_features)}")
            print("System will run with available features only.")
            
            proceed = input("\nContinue? (yes/no): ").lower()
            if proceed not in ['yes', 'y']:
                return
        
        processes = []
        
        try:
            # 1. Start data collection
            if required_features['data_collection']:
                print("\n📊 Starting data collection...")
                data_thread = threading.Thread(
                    target=self.run_data_collection_background, 
                    daemon=True
                )
                data_thread.start()
                processes.append(('Data Collection', data_thread))
                time.sleep(2)  # Stagger startup
            
            # 2. Start dashboard
            print("\n🖥️  Starting dashboard...")
            dashboard_thread = threading.Thread(
                target=self.run_dashboard_background,
                daemon=True
            )
            dashboard_thread.start()
            processes.append(('Dashboard', dashboard_thread))
            
            # 3. Start AI dashboard if available
            if required_features['ai_features']:
                print("\n🤖 Starting AI dashboard...")
                ai_thread = threading.Thread(
                    target=self.run_ai_dashboard_background,
                    daemon=True
                )
                ai_thread.start()
                processes.append(('AI Dashboard', ai_thread))

            
            print("\n✅ Full system started!")
            print("📊 Components running:")
            for name, _ in processes:
                print(f"  • {name}")
            
            print("\n🌐 Access points:")
            print("  • Main Dashboard: http://localhost:8501")
            print("  • AI Dashboard: http://localhost:8502")
            
            print("\n⏹️  Press Ctrl+C to stop all components")
            
            # Keep main thread alive
            while True:
                time.sleep(30)
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 🔄 Full system running...")
                
        except KeyboardInterrupt:
            print("\n⏹️  Shutting down full system...")
            self._cleanup_processes()
            print("✅ Full system stopped")
    
    def run_data_collection_background(self):
        """איסוף נתונים ברקע"""
        try:
            from market_collector import run_collector
            run_collector(interval=30)
        except Exception as e:
            logger.error(f"Background data collection error: {e}")
    
    def run_dashboard_background(self):
        """דאשבורד ברקע"""
        try:
            dashboard_path = os.path.join(DASHBOARDS_DIR, 'simple_dashboard.py')
            if not os.path.exists(dashboard_path):
                dashboard_path = os.path.join(BASE_DIR, 'simple_dashboard.py')
            
            subprocess.run([
                sys.executable, "-m", "streamlit", "run", dashboard_path,
                "--server.headless", "true"
            ])
        except Exception as e:
            logger.error(f"Background dashboard error: {e}")
    
    def run_ai_dashboard_background(self):
        """הפעלת דאשבורד AI ברקע"""
        try:
            dashboard_path = os.path.join(DASHBOARDS_DIR, 'advanced_dashboard.py')
            if not os.path.exists(dashboard_path):
                logger.warning("AI dashboard file not found")
                return
        
            subprocess.run([
                sys.executable, "-m", "streamlit", "run", dashboard_path,
                "--server.headless", "true",
                "--server.port", "8502"
            ])
        except Exception as e:
            logger.error(f"Background AI dashboard error: {e}")

    def run_simulations(self):
        """הפעלת סימולציות"""
        print("\n🧪 Trading Simulation System")
        print("="*40)
        
        try:
            from simulation_runner import main_menu
            main_menu()
        except ImportError:
            print("❌ Simulation module not found")
            print("Running basic parameter optimization...")
            
            try:
                from simulation_core import optimize_simulation_params
                print("\n📊 Running parameter optimization...")
                optimize_simulation_params()
            except ImportError:
                print("❌ Simulation core not available")
                print("Please ensure simulation modules are in modules/ directory")
    
    def show_analysis(self):
        """הצגת ניתוח שוק"""
        print("\n📈 Market Analysis Tools")
        print("="*40)
        
        try:
            from market_collector import MarketCollector
            
            print("🔍 Initializing market analyzer...")
            collector = MarketCollector()
            
            # בדיקת זמינות נתונים
            symbols = ['BTC', 'ETH', 'SOL', 'ADA', 'DOT']
            print(f"📊 Analyzing {len(symbols)} major assets...")
            
            prices = collector.get_combined_prices(symbols)
            
            if prices:
                print("\n💰 Current Market Status:")
                print("-" * 50)
                
                for symbol, data in prices.items():
                    price = data['price']
                    change = data.get('change_pct_24h', 0)
                    volume = data.get('volume', 0)
                    
                    change_symbol = "🟢" if change > 0 else "🔴" if change < 0 else "⚪"
                    
                    print(f"{change_symbol} {symbol:6} | ${price:>10,.2f} | {change:>+6.2f}% | Vol: ${volume:>10,.0f}")
            
                # Market summary
                avg_change = sum(data.get('change_pct_24h', 0) for data in prices.values()) / len(prices)
                total_volume = sum(data.get('volume', 0) for data in prices.values())
                
                print("\n📊 Market Summary:")
                print(f"  • Average Change: {avg_change:+.2f}%")
                print(f"  • Total Volume: ${total_volume:,.0f}")
                print(f"  • Market Sentiment: {'Bullish' if avg_change > 0 else 'Bearish'}")
                
            else:
                print("❌ No market data available")
                print("💡 Try running data collection first (option 2)")
                
        except ImportError:
            print("❌ Market analysis modules not available")
        except Exception as e:
            print(f"❌ Analysis error: {e}")
        
        input("\nPress Enter to continue...")
    
    def _cleanup_processes(self):
        """ניקוי תהליכים"""
        for name, process in self.processes.items():
            if process and process.poll() is None:
                logger.info(f"Terminating {name}")
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
    
    def show_settings(self):
        """הצגת הגדרות מערכת מתקדמת - גרסה מתוקנת"""
        print("\n⚙️  System Settings & Configuration")
        print("="*60)
        
        # API Keys Status - גרסה מתוקנת
        print("\n🔑 API Configuration:")
        api_keys = [
            ('Kraken API Key', 'KRAKEN_API_KEY', 'Required for live trading'),
            ('Kraken API Secret', 'KRAKEN_API_SECRET', 'Required for live trading'),
            ('OpenAI API Key', 'OPENAI_API_KEY', 'Optional - AI features'),
            ('CryptoPanic API Key', 'CRYPTOPANIC_API_KEY', 'Optional - news analysis')
        ]
        
        for name, key_name, description in api_keys:
            key_status = Config.get_api_key_status(key_name)
            status = "✅ Configured" if key_status.get('configured') else "❌ Missing"
            masked_key = key_status.get('masked_value', 'Not set')
            print(f"  • {name:<20} | {status:<12} | {masked_key:<15} | {description}")
        
        # Trading Parameters - גרסה מתוקנת
        print("\n💰 Trading Parameters:")
        default_params = Config.DEFAULT_TRADING_PARAMS
        for key, value in default_params.items():
            print(f"  • {key:<20} | {value}")
        
        # System Status
        print("\n🖥️  System Information:")
        print(f"  • Python Version    | {sys.version.split()[0]}")
        print(f"  • Working Directory | {BASE_DIR}")
        print(f"  • Config File       | {'✅ Found' if os.path.exists('.env') else '❌ Missing'}")
        print(f"  • Data Directory    | {Config.DATA_DIR}")
        print(f"  • Logs Directory    | {Config.LOGS_DIR}")
        
        # File Status
        print("\n📁 Data Files Status:")
        data_files = [
            ('market_live.csv', 'Live market data'),
            ('market_history.csv', 'Historical market data'), 
            ('news_feed.csv', 'News and sentiment'),
            ('simulation_log.csv', 'Trading simulations'),
            ('trading_log.csv', 'Live trading history')
        ]
        
        for filename, description in data_files:
            path = os.path.join(Config.DATA_DIR, filename)
            if os.path.exists(path):
                size = os.path.getsize(path) / 1024  # KB
                age_hours = (time.time() - os.path.getmtime(path)) / 3600
                print(f"  • {filename:<20} | ✅ {size:>7.1f} KB | {age_hours:>5.1f}h old | {description}")
            else:
                print(f"  • {filename:<20} | ❌ Not found  |           | {description}")
        
        input("\nPress Enter to continue...")
    
    def _update_trading_symbols(self):
        """עדכון רשימת מטבעות למסחר - גרסה מתוקנת"""
        print("\n🪙 Symbol & Asset Manager")
        print("="*50)
        
        try:
            from market_collector import MarketCollector
            
            print("\n1. View current symbol configuration")
            print("2. Update symbol list from Kraken")
            print("3. Set custom symbol list")
            print("4. Reset to default symbols")
            print("5. Test symbol connectivity")
            
            choice = input("\nChoice: ").strip()
            
            if choice == '1':
                # הצגת הגדרות נוכחיות - גרסה מתוקנת
                print(f"\n📊 Current Configuration:")
                print(f"  • Use all symbols: {Config.TRADING_SETTINGS.get('use_all_symbols', False)}")
                print(f"  • Max symbols: {Config.TRADING_SETTINGS.get('max_symbols', 50)}")
                print(f"  • Priority symbols: {', '.join(Config.TRADING_SETTINGS.get('priority_symbols', []))}")
                print(f"  • Default coins: {', '.join(Config.DEFAULT_COINS)}")
                
            elif choice == '2':
                # עדכון מ-Kraken
                collector = MarketCollector()
                print("\n⏳ Fetching available symbols from Kraken...")
                
                try:
                    symbols = collector.get_all_available_symbols()
                    print(f"\n✅ Found {len(symbols)} available symbols")
                    print(f"Examples: {', '.join(symbols[:10])}...")
                    
                    if input("\nUpdate system to use all available symbols? (y/n): ").lower() == 'y':
                        Config.TRADING_SETTINGS['use_all_symbols'] = True
                        print("✅ Updated to use all available symbols")
                except Exception as e:
                    print(f"❌ Error fetching symbols: {e}")
                
            elif choice == '3':
                # רשימה מותאמת
                print("\nEnter symbols separated by commas (e.g., BTC,ETH,SOL):")
                custom_input = input("> ").upper().strip()
                
                if custom_input:
                    custom_symbols = [s.strip() for s in custom_input.split(',')]
                    Config.DEFAULT_COINS = custom_symbols
                    Config.TRADING_SETTINGS['use_all_symbols'] = False
                    print(f"\n✅ Set {len(custom_symbols)} custom symbols: {', '.join(custom_symbols)}")
                
            elif choice == '4':
                # איפוס לברירת מחדל
                Config.DEFAULT_COINS = ['BTC', 'ETH', 'SOL', 'ADA', 'DOT', 'MATIC', 'LINK', 'AVAX', 'XRP']
                Config.TRADING_SETTINGS['use_all_symbols'] = False
                print(f"\n✅ Reset to default symbols: {', '.join(Config.DEFAULT_COINS)}")
                
            elif choice == '5':
                # בדיקת קישוריות
                collector = MarketCollector()
                test_symbols = Config.DEFAULT_COINS[:5]
                
                print(f"\n🔍 Testing connectivity for: {', '.join(test_symbols)}")
                
                try:
                    prices = collector.get_combined_prices(test_symbols)
                    
                    if prices:
                        print("\n✅ Connectivity test successful:")
                        for symbol, data in prices.items():
                            print(f"  • {symbol}: ${data['price']:,.2f}")
                    else:
                        print("\n❌ Connectivity test failed")
                except Exception as e:
                    print(f"\n❌ Connectivity error: {e}")
                    
        except ImportError:
            print("❌ Market collector module not available")
        except Exception as e:
            print(f"❌ Error: {e}")
        
        input("\nPress Enter to continue...")
    
    def run_debug(self):
        """הפעלת כלי debug מתקדם"""
        print("\n🔧 System Diagnostics & Debug Tools")
        print("="*50)
        
        debug_options = [
            ("1", "🔍 Test Kraken API Connection", self._debug_kraken),
            ("2", "📊 Test Data Collection", self._debug_data_collection),
            ("3", "🖥️  Test Dashboard Components", self._debug_dashboard),
            ("4", "🧪 Test Simulation System", self._debug_simulations),
            ("5", "📁 Check File System", self._debug_filesystem),
            ("6", "🔧 Full System Diagnostics", self._debug_full_system)
        ]
        
        print("\nDiagnostic Options:")
        for key, desc, _ in debug_options:
            print(f"  {key}. {desc}")
        
        choice = input("\nSelect diagnostic (1-6): ").strip()
        
        debug_map = {opt[0]: opt[2] for opt in debug_options}
        debug_func = debug_map.get(choice)
        
        if debug_func:
            print("\n" + "="*50)
            debug_func()
        else:
            print("❌ Invalid choice")
    
    def _debug_kraken(self):
        """בדיקת Kraken API"""
        try:
            from debug_kraken import test_connection
            test_connection()
        except ImportError:
            print("❌ Debug Kraken module not found")
            # Basic API test - גרסה מתוקנת
            if Config.get_api_key('KRAKEN_API_KEY'):
                print("✅ API Key configured")
                print("💡 For full API test, ensure debug_kraken.py is available")
            else:
                print("❌ No API key configured")
    
    def _debug_data_collection(self):
        """בדיקת איסוף נתונים"""
        try:
            from market_collector import test_collector
            test_collector()
        except ImportError:
            print("❌ Market collector module not available")
        except Exception as e:
            print(f"❌ Data collection test failed: {e}")
    
    def _debug_dashboard(self):
        """בדיקת רכיבי דאשבורד"""
        print("🖥️  Testing Dashboard Components...")
        
        # בדיקת Streamlit
        try:
            import streamlit
            print("✅ Streamlit installed")
        except ImportError:
            print("❌ Streamlit not installed")
        
        # בדיקת קבצי דאשבורד
        dashboard_files = [
            ('Simple Dashboard', os.path.join(DASHBOARDS_DIR, 'simple_dashboard.py')),
            ('Advanced Dashboard', os.path.join(DASHBOARDS_DIR, 'advanced_dashboard.py'))
        ]
        
        for name, path in dashboard_files:
            if os.path.exists(path):
                print(f"✅ {name} found at {path}")
            else:
                print(f"❌ {name} not found at {path}")
    
    def _debug_simulations(self):
        """בדיקת מערכת סימולציות"""
        try:
            from simulation_core import SimulationEngine
            
            print("🧪 Testing simulation engine...")
            engine = SimulationEngine(initial_balance=1000)
            print("✅ Simulation engine initialized")
            
            # Test basic simulation
            import pandas as pd
            import numpy as np
            
            # Create dummy data
            dates = pd.date_range('2024-01-01', periods=100, freq='H')
            prices = 50000 + np.cumsum(np.random.randn(100) * 100)
            
            test_df = pd.DataFrame({
                'timestamp': dates,
                'price': prices,
                'volume': np.random.randint(1000, 10000, 100)
            })
            
            result = engine.run_simulation(test_df, strategy='rsi')
            print(f"✅ Test simulation completed")
            print(f"   Final balance: ${result['final_balance']:.2f}")
            print(f"   Profit: {result['total_profit_pct']*100:.2f}%")
            
        except ImportError:
            print("❌ Simulation modules not available")
        except Exception as e:
            print(f"❌ Simulation test failed: {e}")
    
    def _debug_filesystem(self):
        """בדיקת מערכת קבצים"""
        print("📁 File System Diagnostics...")
        
        # בדיקת תיקיות
        directories = ['data', 'logs', 'modules', 'dashboards', 'models']
        for directory in directories:
            path = os.path.join(BASE_DIR, directory)
            if os.path.exists(path):
                files = len(os.listdir(path))
                print(f"✅ {directory}/ - {files} files")
            else:
                print(f"❌ {directory}/ - missing")
        
        # בדיקת הרשאות
        test_file = os.path.join(Config.DATA_DIR, 'test_write.tmp')
        try:
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
            print("✅ File write permissions OK")
        except Exception as e:
            print(f"❌ File write permissions failed: {e}")
    
    def _debug_full_system(self):
        """בדיקה מלאה של המערכת"""
        print("🔧 Running Full System Diagnostics...")
        print("="*50)
        
        # Run all debug tests
        tests = [
            ("API Connection", self._debug_kraken),
            ("Data Collection", self._debug_data_collection),
            ("Dashboard", self._debug_dashboard),
            ("Simulations", self._debug_simulations),
            ("File System", self._debug_filesystem)
        ]
        
        for test_name, test_func in tests:
            print(f"\n🔍 Testing {test_name}...")
            try:
                test_func()
                print(f"✅ {test_name} - PASSED")
            except Exception as e:
                print(f"❌ {test_name} - FAILED: {e}")
        
        print("\n" + "="*50)
        print("✅ Full diagnostics complete!")
    
    def show_docs(self):
        """הצגת תיעוד מערכת"""
        print("\n📚 System Documentation & Help")
        print("="*50)
        
        docs_menu = [
            ("1", "🚀 Quick Start Guide"),
            ("2", "📊 Dashboard User Guide"),  
            ("3", "🤖 AI Trading Features"),
            ("4", "⚙️  API Configuration"),
            ("5", "🧪 Running Simulations"),
            ("6", "🔧 Troubleshooting Guide"),
            ("7", "📈 Market Analysis Tools"),
            ("8", "🔒 Security Best Practices")
        ]
        
        for key, title in docs_menu:
            print(f"  {key}. {title}")
        
        choice = input("\nSelect topic (1-8, or Enter to go back): ").strip()
        
        if choice == "1":
            self._show_quick_start_guide()
        elif choice == "2":
            self._show_dashboard_guide()
        elif choice == "3":
            self._show_ai_features_guide()
        elif choice == "4":
            self._show_api_config_guide()
        elif choice == "5":
            self._show_simulations_guide()
        elif choice == "6":
            self._show_troubleshooting_guide()
        elif choice == "7":
            self._show_analysis_guide()
        elif choice == "8":
            self._show_security_guide()
        
        if choice in ["1", "2", "3", "4", "5", "6", "7", "8"]:
            input("\nPress Enter to continue...")
    
    def _show_quick_start_guide(self):
        """מדריך התחלה מהירה"""
        print("\n🚀 Quick Start Guide")
        print("="*40)
        print("""
1. INSTALLATION:
   • Ensure Python 3.8+ is installed
   • Run: pip install -r requirements.txt
   • Copy .env.example to .env

2. API CONFIGURATION:
   • Get Kraken API key from kraken.com
   • Add your keys to .env file:
     KRAKEN_API_KEY=your_key_here
     KRAKEN_API_SECRET=your_secret_here

3. FIRST RUN:
   • Test system: python test_system.py
   • Start simple dashboard: python main.py → option 1
   • Access at: http://localhost:8501

4. NEXT STEPS:
   • Try data collection (option 2)
   • Run trading simulations (option 5)
   • Explore market analysis (option 6)

5. LIVE TRADING (ADVANCED):
   • Ensure API keys are configured
   • Start with small amounts
   • Use AI dashboard (option 3)
        """)
    
    def _show_dashboard_guide(self):
        """מדריך דאשבורד"""
        print("\n📊 Dashboard User Guide")
        print("="*40)
        print("""
SIMPLE DASHBOARD:
• Portfolio overview with real-time balances
• Price charts and market data
• Automatic refresh every 60 seconds
• Mobile-friendly responsive design

ADVANCED AI DASHBOARD:
• All simple dashboard features PLUS:
• AI trading signals and recommendations
• Machine learning price predictions
• Autonomous trading controls
• Advanced market analysis tools
• Portfolio optimization suggestions

NAVIGATION:
• Use sidebar for different sections
• Click refresh button for latest data
• Hover over charts for detailed info
• Use filters to customize views

TROUBLESHOOTING:
• If dashboard won't load: check Streamlit installation
• If no data shown: run data collection first
• If API errors: verify .env configuration
        """)
    
    def _show_ai_features_guide(self):
        """מדריך תכונות AI"""
        print("\n🤖 AI Trading Features Guide")
        print("="*40)
        print("""
AI TRADING MODES:
• Conservative: Low risk, steady gains
• Balanced: Medium risk/reward ratio  
• Aggressive: High risk, high potential returns
• Custom: User-defined parameters

TRADING STRATEGIES:
• Trend Following: Rides market momentum
• Mean Reversion: Profits from price corrections
• Pattern Recognition: Identifies chart patterns
• Sentiment Analysis: Uses news sentiment
• Arbitrage Detection: Finds price differences

MACHINE LEARNING:
• Price prediction models
• Risk assessment algorithms
• Portfolio optimization
• Automated strategy selection

SAFETY FEATURES:
• Demo mode for testing
• Position size limits
• Daily loss limits
• Emergency stop functionality

REQUIREMENTS:
• OpenAI API key (optional but recommended)
• Sufficient account balance
• Proper risk management settings
        """)
    
    def _show_api_config_guide(self):
        """מדריך הגדרת API"""
        print("\n⚙️  API Configuration Guide")
        print("="*40)
        print("""
KRAKEN API SETUP:
1. Login to kraken.com
2. Go to Settings → API
3. Create new API key with permissions:
   • Query Funds
   • Query Open Orders and Trades
   • Create & Modify Orders (for live trading)
4. Add to .env file:
   KRAKEN_API_KEY=your_key_here
   KRAKEN_API_SECRET=your_secret_here

OPTIONAL APIS:
• OpenAI (for AI features):
  OPENAI_API_KEY=sk-...
• CryptoPanic (for news):
  CRYPTOPANIC_API_KEY=your_key_here

SECURITY TIPS:
• Never share your API keys
• Use IP restrictions if possible
• Start with query-only permissions
• Monitor API usage regularly
• Keep .env file secure and private

TESTING:
• Use debug option (9) to test connection
• Start with demo mode
• Verify balances show correctly
        """)
    
    def _show_simulations_guide(self):
        """מדריך סימולציות"""
        print("\n🧪 Trading Simulations Guide")
        print("="*40)
        print("""
SIMULATION TYPES:
• Single Strategy Test: Test one strategy
• Multi-Strategy Comparison: Compare strategies
• Parameter Optimization: Find best settings
• Portfolio Backtest: Test full portfolio

AVAILABLE STRATEGIES:
• Combined: Uses multiple indicators
• RSI: Relative Strength Index
• EMA: Exponential Moving Average
• MACD: Moving Average Convergence Divergence
• Bollinger Bands: Volatility bands
• SMA: Simple Moving Average

PARAMETERS TO OPTIMIZE:
• Initial Balance: Starting capital
• Take Profit: Profit target percentage
• Stop Loss: Maximum loss percentage
• Max Positions: Number of concurrent trades

INTERPRETING RESULTS:
• Total Return: Overall profit/loss
• Win Rate: Percentage of profitable trades
• Sharpe Ratio: Risk-adjusted returns
• Max Drawdown: Largest losing streak

BEST PRACTICES:
• Test multiple time periods
• Use realistic transaction costs
• Consider market conditions
• Don't over-optimize parameters
        """)
    
    def _show_troubleshooting_guide(self):
        """מדריך פתרון בעיות"""
        print("\n🔧 Troubleshooting Guide")
        print("="*40)
        print("""
COMMON ISSUES:

1. "Module not found" errors:
   → Run: pip install -r requirements.txt
   → Check file locations in modules/ directory

2. API connection failed:
   → Verify API keys in .env file
   → Check internet connection
   → Test with debug option (9)

3. Dashboard won't start:
   → Install Streamlit: pip install streamlit
   → Check port 8501 is available
   → Try different port: streamlit run --server.port 8502

4. No market data:
   → Run data collection first (option 2)
   → Check API key permissions
   → Verify data/ directory exists

5. Simulations fail:
   → Ensure historical data is available
   → Check simulation modules in modules/
   → Try with smaller datasets

6. AI features not working:
   → Add OpenAI API key to .env
   → Check AI model availability
   → Reduce complexity of requests

GETTING HELP:
• Use system diagnostics (debug option)
• Check log files in logs/ directory
• Verify system requirements
• Test individual components separately
        """)
    
    def _show_analysis_guide(self):
        """מדריך כלי ניתוח"""
        print("\n📈 Market Analysis Tools Guide")
        print("="*40)
        print("""
AVAILABLE ANALYSIS:
• Real-time price monitoring
• Technical indicators (RSI, MACD, etc.)
• Volume analysis
• Market sentiment from news
• Portfolio performance tracking

TECHNICAL INDICATORS:
• RSI: Momentum oscillator (0-100)
• MACD: Trend-following momentum
• Bollinger Bands: Volatility indicator
• Moving Averages: Trend direction
• Volume: Market participation

MARKET SENTIMENT:
• News sentiment analysis
• Social media sentiment
• Fear & Greed Index
• Whale movement tracking

PORTFOLIO ANALYSIS:
• Asset allocation breakdown
• Performance attribution
• Risk metrics calculation
• Correlation analysis

USING THE DATA:
• Combine multiple indicators
• Look for confluences
• Consider market context
• Use proper risk management
• Keep historical perspective
        """)
    
    def _show_security_guide(self):
        """מדריך אבטחה"""
        print("\n🔒 Security Best Practices")
        print("="*40)
        print("""
API SECURITY:
• Never commit .env files to git
• Use IP restrictions on API keys
• Rotate keys regularly
• Monitor API usage
• Start with read-only permissions
• Use separate keys for testing

TRADING SECURITY:
• Start with small amounts
• Use stop-loss orders
• Don't risk more than you can afford
• Test strategies thoroughly
• Keep emergency stops enabled
• Monitor positions regularly

SYSTEM SECURITY:
• Keep software updated
• Use strong passwords
• Enable 2FA on exchange accounts
• Regular backups of important data
• Secure your development environment

OPERATIONAL SECURITY:
• Review all trades before execution
• Understand all strategies being used
• Monitor system logs regularly
• Have contingency plans
• Keep manual override capabilities
        """)
    
    def run(self):
        """הפעלה ראשית עם error handling משופר"""
        while True:
            try:
                choice = self.show_menu()
                
                if choice == "exit":
                    print("\n👋 Thank you for using Kraken Trading Bot!")
                    print("💎 Safe trading!")
                    break
                    
                elif choice == "simple_dashboard":
                    self.run_simple_dashboard()
                    
                elif choice == "collect_data":
                    self.run_data_collection()
                    
                elif choice == "ai_dashboard":
                    self.run_ai_dashboard()
                    
                elif choice == "full_system":
                    self.run_full_system()
                    
                elif choice == "simulations":
                    self.run_simulations()
                    
                elif choice == "analysis":
                    self.show_analysis()
                    
                elif choice == "settings":
                    self.show_settings()
                    
                elif choice == "symbols":
                    self._update_trading_symbols()
                    
                elif choice == "debug":
                    self.run_debug()
                    
                elif choice == "docs":
                    self.show_docs()
                    
                elif choice == "invalid":
                    print("❌ Invalid choice. Please select a number from the menu.")
                    time.sleep(1)
                    
            except KeyboardInterrupt:
                print("\n\n⚠️  Interrupted by user")
                break
            except Exception as e:
                logger.error(f"Unexpected error in main loop: {e}", exc_info=True)
                print(f"❌ Unexpected error: {e}")
                print("The system will continue running...")
                time.sleep(2)
    
    def cleanup(self):
        """ניקוי משאבים"""
        try:
            self._cleanup_processes()
        except Exception as e:
            logger.error(f"Cleanup error: {e}")

def main():
    """נקודת כניסה ראשית משופרת"""
    parser = argparse.ArgumentParser(
        description='Kraken Trading Bot v2.0 - Advanced Crypto Trading System',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                    # Interactive menu
  python main.py --mode dashboard   # Direct to dashboard
  python main.py --mode collect     # Start data collection
  python main.py --mode simulate    # Run simulations
  python main.py --mode debug       # System diagnostics
        """
    )
    
    parser.add_argument(
        '--mode',
        choices=['dashboard', 'collect', 'simulate', 'debug', 'full'],
        help='Direct mode execution'
    )
    
    parser.add_argument(
        '--no-git',
        action='store_true',
        help='Disable git auto-update'
    )
    
    parser.add_argument(
        '--version',
        action='version',
        version='Kraken Trading Bot v2.0.1'
    )
    
    parser.add_argument(
        '--setup',
        action='store_true',
        help='Run initial system setup'
    )
    
    args = parser.parse_args()
    
    # System setup mode
    if args.setup:
        print("🏗️  Running initial system setup...")
        try:
            from setup_complete_system import main as setup_main
            setup_main()
        except ImportError:
            print("❌ Setup script not found. Please ensure setup_complete_system.py exists.")
        return
    
    # Git auto-update (optional)
    if not args.no_git and os.path.exists('.git'):
        try:
            from git_manager import GitManager
            git = GitManager()
            success, message = git.auto_update()
            if success:
                logger.info(f"Git update: {message}")
        except ImportError:
            logger.warning("Git manager not available")
        except Exception as e:
            logger.warning(f"Git update failed: {e}")
    
    # Initialize bot manager
    try:
        bot_manager = TradingBotManager()
    except Exception as e:
        print(f"❌ Failed to initialize system: {e}")
        print("💡 Try running with --setup flag first")
        return
    
    try:
        # Direct mode execution
        if args.mode:
            print(f"🚀 Starting in {args.mode} mode...")
            
            if args.mode == 'dashboard':
                bot_manager.run_simple_dashboard()
            elif args.mode == 'collect':
                bot_manager.run_data_collection()
            elif args.mode == 'simulate':
                bot_manager.run_simulations()
            elif args.mode == 'debug':
                bot_manager.run_debug()
            elif args.mode == 'full':
                bot_manager.run_full_system()
        else:
            # Interactive menu mode
            bot_manager.run()
    
    except KeyboardInterrupt:
        print("\n\n⚠️  System interrupted by user")
        print("🔄 Performing cleanup...")
        
    except Exception as e:
        logger.error(f"Critical system error: {e}", exc_info=True)
        print(f"❌ Critical error: {e}")
        print("🔧 Try running diagnostics: python main.py --mode debug")
        
    finally:
        # Cleanup
        try:
            bot_manager.cleanup()
        except:
            pass
        
        print("\n✅ System shutdown complete")
        print("💎 Thank you for using Kraken Trading Bot!")

if __name__ == '__main__':
    main()