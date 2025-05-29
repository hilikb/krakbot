#!/usr/bin/env python3
"""
Kraken Trading Bot v2.1 - Main Entry Point (Hybrid WebSocket + HTTP)
====================================================================
מערכת מסחר אוטומטית מתקדמת עם AI ואיסוף נתונים היברידי
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

# ייבוא המודול ההיברידי החדש
try:
    from modules.hybrid_market_collector import HybridMarketCollector, run_hybrid_collector, RealTimePriceUpdate
    HYBRID_AVAILABLE = True
    print("✅ Hybrid WebSocket + HTTP collector available")
except ImportError as e:
    print(f"⚠️  Hybrid collector not available: {e}")
    HYBRID_AVAILABLE = False
    # Fallback to original collector
    try:
        from modules.market_collector import MarketCollector, run_collector
    except ImportError:
        print("❌ No market collector available!")
        sys.exit(1)

# הגדרת לוגר
logger = Config.setup_logging('main')

class EnhancedTradingBotManager:
    """מנהל ראשי למערכת הבוט עם תמיכה היברידית"""
    
    def __init__(self):
        self.version = "2.1.0-hybrid"
        self.workers = {}
        self.processes = {}
        self.running = False
        self.mode = None
        
        # Hybrid collector
        self.hybrid_collector = None
        
        # בדיקת סביבה מתקדמת
        self._check_environment()
        
    def _check_environment(self):
        """בדיקת סביבת עבודה עם תמיכה היברידית"""
        print("🔍 Checking system environment...")
        
        # בדיקת Python version
        if sys.version_info < (3, 8):
            print("⚠️  Warning: Python 3.8+ recommended")
        
        # בדיקת dependencies קריטיים עם WebSocket
        critical_packages = [
            ('pandas', 'Data manipulation'),
            ('numpy', 'Numerical computing'),
            ('krakenex', 'Kraken API'),
            ('streamlit', 'Dashboard framework'),
            ('websockets', 'WebSocket client'),
            ('asyncio', 'Async support')
        ]
        
        missing_packages = []
        for package, description in critical_packages:
            try:
                if package == 'asyncio':
                    import asyncio
                else:
                    __import__(package)
                print(f"✅ {package} - {description}")
            except ImportError:
                missing_packages.append(package)
                print(f"❌ {package} - {description} (MISSING)")
        
        if missing_packages:
            print(f"\n⚠️  Missing packages: {', '.join(missing_packages)}")
            if 'websockets' in missing_packages:
                print("📦 Install WebSocket support: pip install websockets")
        
        # בדיקת תכונות היברידיות
        if HYBRID_AVAILABLE:
            print("🚀 Hybrid WebSocket + HTTP collector: ✅ AVAILABLE")
        else:
            print("⚠️  Hybrid collector: ❌ NOT AVAILABLE (fallback to HTTP only)")
        
        # בדיקת מפתחות API
        try:
            api_status = Config.validate_keys()
            if api_status:
                print("✅ API keys configured")
            else:
                print("⚠️  Some API keys missing - limited functionality")
        except Exception as e:
            print(f"⚠️  Error checking API keys: {e}")
    
    def print_banner(self):
        """הצגת באנר פתיחה עם תכונות היברידיות"""
        hybrid_status = "🚀 HYBRID MODE" if HYBRID_AVAILABLE else "📡 HTTP MODE"
        
        banner = f"""
╔═══════════════════════════════════════════════════════════════╗
║                💎 Kraken Trading Bot v{self.version} 💎                ║
║                                                               ║
║        🤖 Advanced AI-Powered Crypto Trading System          ║
║            {hybrid_status:<20} ⚡ Real-Time Data            ║
║                                                               ║
║  📊 Live Prices  🧠 ML Predictions  ⚡ Auto Trading         ║
╚═══════════════════════════════════════════════════════════════╝
        """
        print(banner)
    
    def show_menu(self):
        """תפריט ראשי עם אפשרויות היברידיות"""
        self.print_banner()
        
        print("\n🎯 Main Menu:")
        print("═" * 60)
        
        # בדיקת זמינות features
        features_status = self._check_features_availability()
        
        menu_options = [
            ("1", "🚀 Quick Start - Simple Dashboard", "simple_dashboard", True),
            ("2", "📊 Hybrid Data Collection (WebSocket + HTTP)", "hybrid_collect_data", HYBRID_AVAILABLE),
            ("3", "📈 Classic Data Collection (HTTP Only)", "collect_data", True),
            ("4", "🤖 AI Trading Dashboard", "ai_dashboard", features_status['ai_features']),
            ("5", "🔄 Full Hybrid System", "hybrid_full_system", HYBRID_AVAILABLE),
            ("6", "🧪 Trading Simulations", "simulations", features_status['simulations']),
            ("7", "📈 Market Analysis Tools", "analysis", features_status['analysis']),
            ("8", "⚙️  System Configuration", "settings", True),
            ("9", "🪙 Symbol & Asset Manager", "symbols", features_status['data_collection']),
            ("10", "🔧 Debug & Diagnostics", "debug", True),
            ("11", "📚 Help & Documentation", "docs", True),
            ("0", "🚪 Exit System", "exit", True)
        ]
        
        for key, desc, _, available in menu_options:
            status = "✅" if available else "❌"
            color = "" if available else " (unavailable)"
            
            # הדגשת אפשרויות היברידיות
            if "Hybrid" in desc and available:
                desc = f"🌟 {desc}"
            
            print(f"  {key}. {status} {desc}{color}")
        
        print("\n" + "═" * 60)
        
        # הצגת סטטוס מערכת מעודכן
        self._show_system_status()
        
        choice = input("\n👉 Your choice: ").strip()
        
        # מיפוי בחירות
        choice_map = {opt[0]: opt[2] for opt in menu_options}
        return choice_map.get(choice, "invalid")
    
    def _check_features_availability(self):
        """בדיקת זמינות features עם תמיכה היברידית"""
        status = {
            'data_collection': True,
            'hybrid_collection': HYBRID_AVAILABLE,
            'ai_features': bool(Config.get_api_key('OPENAI_API_KEY')),
            'simulations': True,
            'analysis': True,
            'full_system': True
        }
        
        # בדיקת modules זמינים
        try:
            if HYBRID_AVAILABLE:
                from hybrid_market_collector import HybridMarketCollector
                status['hybrid_collection'] = True
            else:
                from market_collector import MarketCollector
                status['data_collection'] = True
        except ImportError:
            status['data_collection'] = False
            status['hybrid_collection'] = False
        
        try:
            from ai_trading_engine import AITradingEngine
            status['ai_features'] = status['ai_features'] and True
        except ImportError:
            status['ai_features'] = False
        
        status['full_system'] = any([
            status['data_collection'],
            status['hybrid_collection'],
            status['simulations'],
            status['analysis']
        ])
        
        return status
    
    def _show_system_status(self):
        """הצגת סטטוס מערכת עם מידע היברידי"""
        print("\n📊 System Status:")
        print(f"  • Version: {self.version}")
        print(f"  • Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Collector status
        if HYBRID_AVAILABLE:
            print("  • Data Collection: 🚀 Hybrid Mode (WebSocket + HTTP)")
        else:
            print("  • Data Collection: 📡 HTTP Mode Only")
        
        # API Keys status
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
    
    def run_hybrid_data_collection(self):
        """הפעלת איסוף נתונים היברידי חדש"""
        if not HYBRID_AVAILABLE:
            print("❌ Hybrid collection not available. Falling back to HTTP collection.")
            self.run_data_collection()
            return
        
        print("\n🚀 Starting Hybrid Data Collection System...")
        print("📡 WebSocket: Real-time price updates")
        print("🌐 HTTP: Account data, history, fallback")
        
        # בחירת סמלים
        websocket_max = Config.HYBRID_CONFIG['websocket_max_symbols']  # 80
        max_symbols = Config.SYMBOL_CONFIG['max_symbols']  # 600
        
        # קבלת כל הסמלים
        all_symbols = Config.DEFAULT_COINS[:max_symbols]
        ws_symbols = all_symbols[:websocket_max]
        http_symbols = all_symbols[websocket_max:]
        
        print(f"\n📊 Total symbols to track: {len(all_symbols)}")
        print(f"   ⚡ WebSocket (Real-time): {len(ws_symbols)} symbols")
        print(f"   📡 HTTP (Every 2 min): {len(http_symbols)} symbols")
        print(f"   WebSocket symbols: {', '.join(ws_symbols[:10])}{'...' if len(ws_symbols) > 10 else ''}")
        
        # התחלת collector
        try:
            print("\n⏳ Initializing hybrid collector...")
            
            # יצירת callback לניטור
            def on_price_update(price_update: RealTimePriceUpdate):
                if hasattr(on_price_update, 'counter'):
                    on_price_update.counter += 1
                else:
                    on_price_update.counter = 1
                
                # הדפסה כל 50 עדכונים כדי לא לספאם
                if on_price_update.counter % 50 == 0:
                    print(f"💰 [{on_price_update.counter}] {price_update.symbol}: "
                          f"${price_update.price:,.2f} ({price_update.change_24h_pct:+.2f}%) "
                          f"[{price_update.source}]")
            
            # יצירת ה-collector עם כל הסמלים
            self.hybrid_collector = HybridMarketCollector(
                symbols=all_symbols,  # שולחים את כל הסמלים
                api_key=Config.get_api_key('KRAKEN_API_KEY'),
                api_secret=Config.get_api_key('KRAKEN_API_SECRET')
            )
            
            # הוספת callback
            self.hybrid_collector.add_data_callback(on_price_update)
            
            # התחלה
            self.hybrid_collector.start()
            
            print("✅ Hybrid collector started successfully!")
            print("\n📊 Collection Status:")
            print(f"  • WebSocket: Connecting to Kraken for {len(ws_symbols)} symbols...")
            print(f"  • HTTP: Will update {len(http_symbols)} symbols every {Config.HYBRID_CONFIG['http_update_interval']}s")
            print("  • Database: Storing all updates")
            print("  • CSV Files: Updated for compatibility")
            
            print("\n⏹️  Press Ctrl+C to stop collection")
            
            # לולאת ניטור
            while True:
                time.sleep(30)  # כל 30 שניות
                
                stats = self.hybrid_collector.get_statistics()
                current_time = datetime.now().strftime('%H:%M:%S')
                
                print(f"\n[{current_time}] 📊 Hybrid Collection Stats:")
                print(f"  • Total Updates: {stats['total_updates']}")
                print(f"  • WebSocket Updates: {stats['websocket_updates']}")
                print(f"  • HTTP Updates: {stats['http_updates']}")
                print(f"  • Updates/Min: {stats.get('updates_per_minute', 0):.1f}")
                print(f"  • WebSocket Status: {stats['websocket_status']}")
                print(f"  • Active Symbols: {stats['active_symbols']}/{len(all_symbols)}")
                
        except KeyboardInterrupt:
            print("\n⏹️  Stopping hybrid collection...")
        except Exception as e:
            print(f"❌ Error in hybrid collection: {e}")
            logger.error(f"Hybrid collection error: {e}")
        finally:
            if self.hybrid_collector:
                self.hybrid_collector.stop()
                print("✅ Hybrid collector stopped")
    def run_data_collection(self):
        """הפעלת איסוף נתונים קלאסי (HTTP בלבד)"""
        print("\n📊 Starting Classic Data Collection System (HTTP)...")
        
        # ייבוא המודול הקלאסי
        try:
            from modules.market_collector import MarketCollector, run_collector
        except ImportError:
            print("❌ Classic market collector not available")
            return
        
        try:
            from modules.news_collector import run_news_monitor
            news_available = True
        except ImportError:
            news_available = False
            print("⚠️  News collector not available")
        
        print("\n🔄 Starting collection processes...")
        
        # Market Collector
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
        if news_available:
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
        
        print("\n📊 Classic Collection Status:")
        print("  • Market data: Every 30 seconds")
        if news_available:
            print("  • News feed: Every 5 minutes")
        print("  • Files saved to: data/")
        print("\n⏹️  Press Ctrl+C to stop all collection")
        
        try:
            while True:
                time.sleep(30)
                current_time = datetime.now().strftime('%H:%M:%S')
                print(f"[{current_time}] ⚡ Classic collection running... (Ctrl+C to stop)")
        except KeyboardInterrupt:
            print("\n⏹️  Stopping classic data collection...")
            print("✅ Collection stopped")
    
    def run_hybrid_full_system(self):
        """הפעלת מערכת היברידית מלאה"""
        if not HYBRID_AVAILABLE:
            print("❌ Hybrid mode not available. Falling back to classic full system.")
            self.run_full_system()
            return
        
        print("\n🚀 Starting Full Hybrid Trading System...")
        print("=" * 60)
        
        print("🌟 Hybrid Features:")
        print("  • Real-time WebSocket price feeds")
        print("  • HTTP fallback and account data")
        print("  • Advanced AI trading engine")
        print("  • Interactive dashboards")
        print("  • Autonomous trading capabilities")
        
        # בדיקת דרישות
        required_features = self._check_features_availability()
        missing_features = [k for k, v in required_features.items() if not v and k != 'data_collection']
        
        if missing_features:
            print(f"⚠️  Some features unavailable: {', '.join(missing_features)}")
            proceed = input("\nContinue with available features? (yes/no): ").lower()
            if proceed not in ['yes', 'y']:
                return
        
        processes = []
        
        try:
            # 1. Start hybrid data collection
            print("\n🚀 Starting hybrid data collection...")
            data_thread = threading.Thread(
                target=self._run_hybrid_data_background,
                daemon=True
            )
            data_thread.start()
            processes.append(('Hybrid Data Collection', data_thread))
            time.sleep(3)  # Allow time to initialize
            
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
            
            print("\n✅ Full hybrid system started!")
            print("📊 Components running:")
            for name, _ in processes:
                print(f"  • {name}")
            
            print("\n🌐 Access points:")
            print("  • Main Dashboard: http://localhost:8501")
            print("  • AI Dashboard: http://localhost:8502")
            
            print("\n⏹️  Press Ctrl+C to stop all components")
            
            # Keep main thread alive with status updates
            while True:
                time.sleep(60)
                current_time = datetime.now().strftime('%H:%M:%S')
                
                # Get hybrid stats if available
                status_info = ""
                if self.hybrid_collector:
                    try:
                        stats = self.hybrid_collector.get_statistics()
                        status_info = f" | Updates: {stats['total_updates']} | WS: {stats['websocket_status']}"
                    except:
                        pass
                
                print(f"[{current_time}] 🔄 Full hybrid system running{status_info}...")
        
        except KeyboardInterrupt:
            print("\n⏹️  Shutting down full hybrid system...")
            self._cleanup_processes()
            print("✅ Full hybrid system stopped")
    
    def _run_hybrid_data_background(self):
        """איסוף נתונים היברידי ברקע"""
        try:
            symbols = Config.DEFAULT_COINS[:600]  # מגבלה לביצועים
            
            self.hybrid_collector = HybridMarketCollector(
                symbols=symbols,
                api_key=Config.get_api_key('KRAKEN_API_KEY'),
                api_secret=Config.get_api_key('KRAKEN_API_SECRET')
            )
            
            self.hybrid_collector.start()
            
            # Keep the collector running
            while True:
                time.sleep(60)
                
        except Exception as e:
            logger.error(f"Background hybrid data collection error: {e}")
    
    def run_full_system(self):
        """הפעלת מערכת קלאסית מלאה"""
        print("\n🚀 Starting Full Classic Trading System...")
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
            # 1. Start classic data collection
            if required_features['data_collection']:
                print("\n📊 Starting classic data collection...")
                data_thread = threading.Thread(
                    target=self.run_data_collection_background,
                    daemon=True
                )
                data_thread.start()
                processes.append(('Data Collection', data_thread))
                time.sleep(2)
            
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
            
            print("\n✅ Full classic system started!")
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
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 🔄 Full classic system running...")
                
        except KeyboardInterrupt:
            print("\n⏹️  Shutting down full classic system...")
            self._cleanup_processes()
            print("✅ Full classic system stopped")
    
    def run_data_collection_background(self):
        """איסוף נתונים קלאסי ברקע"""
        try:
            from modules.market_collector import run_collector
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
    
    def run_simple_dashboard(self):
        """הפעלת דאשבורד פשוט עם תמיכה היברידית"""
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
            return
        
        print("\n🚀 Starting Simple Dashboard...")
        print(f"📍 Location: {dashboard_path}")
        
        # הוסף משתני סביבה לדאשבורד
        env = os.environ.copy()
        if HYBRID_AVAILABLE:
            env['HYBRID_MODE'] = 'true'
        
        print("🌐 Opening browser at http://localhost:8501")
        print("⏹️  Press Ctrl+C to stop")
        
        try:
            import streamlit
            
            process = subprocess.Popen([
                sys.executable, "-m", "streamlit", "run", dashboard_path,
                "--server.headless", "false",
                "--server.port", "8501",
                "--server.address", "localhost"
            ], env=env)
            
            self.processes['dashboard'] = process
            
            print("\n✅ Dashboard is running!")
            print("   • URL: http://localhost:8501")
            if HYBRID_AVAILABLE:
                print("   • Mode: 🚀 Hybrid (WebSocket + HTTP)")
            else:
                print("   • Mode: 📡 HTTP Only")
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
    
    def run_simulations(self):
        """הפעלת סימולציות"""
        print("\n🧪 Trading Simulation System")
        print("="*40)
        
        try:
            from modules.simulation_runner import main_menu
            main_menu()
        except ImportError:
            print("❌ Simulation module not found")
            print("Running basic parameter optimization...")
            
            try:
                from modules.simulation_core import optimize_simulation_params
                print("\n📊 Running parameter optimization...")
                optimize_simulation_params()
            except ImportError:
                print("❌ Simulation core not available")
    
    def show_analysis(self):
        """הצגת ניתוח שוק עם נתונים היברידיים"""
        print("\n📈 Market Analysis Tools")
        print("="*40)
        
        try:
            if HYBRID_AVAILABLE and self.hybrid_collector:
                print("🚀 Using Hybrid Data (Real-time)")
                
                # קבלת נתונים מה-collector ההיברידי
                latest_prices = self.hybrid_collector.get_latest_prices()
                
                if latest_prices:
                    print("\n💰 Real-Time Market Status:")
                    print("-" * 60)
                    
                    for symbol, price_data in list(latest_prices.items())[:10]:
                        change_symbol = "🟢" if price_data.change_24h_pct > 0 else "🔴" if price_data.change_24h_pct < 0 else "⚪"
                        
                        print(f"{change_symbol} {symbol:6} | ${price_data.price:>12,.2f} | "
                              f"{price_data.change_24h_pct:>+6.2f}% | "
                              f"Vol: {price_data.volume:>12,.0f} | "
                              f"[{price_data.source}]")
                    
                    # סטטיסטיקות
                    stats = self.hybrid_collector.get_statistics()
                    print(f"\n📊 Collection Stats:")
                    print(f"  • Total Updates: {stats['total_updates']}")
                    print(f"  • WebSocket Status: {stats['websocket_status']}")
                    print(f"  • Updates per Minute: {stats.get('updates_per_minute', 0):.1f}")
                    
                else:
                    print("❌ No real-time data available yet")
                    
            else:
                # Fallback לcollector קלאסי
                print("📡 Using Classic Data Collection")
                
                try:
                    from modules.market_collector import MarketCollector
                    
                    collector = MarketCollector()
                    symbols = ['BTC', 'ETH', 'SOL', 'ADA', 'DOT']
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
                        print("💡 Try running data collection first")
                        
                except ImportError:
                    print("❌ Market analysis modules not available")
                
        except Exception as e:
            print(f"❌ Analysis error: {e}")
        
        input("\nPress Enter to continue...")
    
    def show_settings(self):
        """הגדרות מערכת עם אפשרויות היברידיות"""
        print("\n⚙️  System Settings & Configuration")
        print("="*60)
        
        # System Mode
        print("\n🚀 System Mode:")
        if HYBRID_AVAILABLE:
            print("  • Data Collection: 🌟 Hybrid Mode Available")
            print("    - WebSocket: Real-time price feeds")
            print("    - HTTP: Account data, history, fallback")
        else:
            print("  • Data Collection: 📡 HTTP Mode Only")
            print("    - Missing: websockets package")
        
        # API Keys Status
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
        
        # Trading Parameters
        print("\n💰 Trading Parameters:")
        default_params = Config.DEFAULT_TRADING_PARAMS
        for key, value in default_params.items():
            print(f"  • {key:<20} | {value}")
        
        # System Information
        print("\n🖥️  System Information:")
        print(f"  • Python Version    | {sys.version.split()[0]}")
        print(f"  • Working Directory | {BASE_DIR}")
        print(f"  • Config File       | {'✅ Found' if os.path.exists('.env') else '❌ Missing'}")
        print(f"  • Data Directory    | {Config.DATA_DIR}")
        print(f"  • Logs Directory    | {Config.LOGS_DIR}")
        
        # WebSocket Support
        print(f"  • WebSocket Support | {'✅ Available' if HYBRID_AVAILABLE else '❌ Missing'}")
        
        # File Status
        print("\n📁 Data Files Status:")
        data_files = [
            ('market_live.csv', 'Live market data'),
            ('market_history.csv', 'Historical market data'), 
            ('hybrid_market_data.db', 'Hybrid database'),
            ('news_feed.csv', 'News and sentiment'),
            ('simulation_log.csv', 'Trading simulations'),
            ('trading_log.csv', 'Live trading history')
        ]
        
        for filename, description in data_files:
            path = os.path.join(Config.DATA_DIR, filename)
            if os.path.exists(path):
                size = os.path.getsize(path) / 1024  # KB
                age_hours = (time.time() - os.path.getmtime(path)) / 3600
                print(f"  • {filename:<25} | ✅ {size:>7.1f} KB | {age_hours:>5.1f}h old | {description}")
            else:
                print(f"  • {filename:<25} | ❌ Not found  |           | {description}")
        
        input("\nPress Enter to continue...")
  
    def _update_trading_symbols(self):
        """ניהול סמלי מסחר"""
        print("\n🪙 Symbol & Asset Manager")
        print("="*40)
        
        # הצגת סמלים נוכחיים
        print("\nCurrent Trading Symbols:")
        current_symbols = Config.DEFAULT_COINS
        for i, symbol in enumerate(current_symbols, 1):
            print(f"  {i}. {symbol}")
        
        print("\nOptions:")
        print("1. View all available symbols")
        print("2. Add symbol to watchlist")
        print("3. Remove symbol from watchlist")
        print("4. Reset to default symbols")
        print("5. Back to main menu")
        
        choice = input("\nYour choice: ").strip()
        
        if choice == "1":
            # הצגת כל הסמלים הזמינים
            print("\n📋 All Available Symbols:")
            try:
                if self.hybrid_collector:
                    symbols = self.hybrid_collector.get_all_available_symbols()
                else:
                    from modules.market_collector import MarketCollector
                    collector = MarketCollector()
                    symbols = collector.get_all_available_symbols()
                
                for i, symbol in enumerate(symbols, 1):
                    print(f"  {i}. {symbol}")
                    if i % 10 == 0:
                        print()  # רווח כל 10 סמלים
            except Exception as e:
                print(f"❌ Error getting symbols: {e}")
        
        elif choice == "2":
            # הוספת סמל
            new_symbol = input("\nEnter symbol to add (e.g., BTC): ").upper()
            if new_symbol and new_symbol not in current_symbols:
                current_symbols.append(new_symbol)
                print(f"✅ Added {new_symbol} to watchlist")
            else:
                print("❌ Symbol already exists or invalid")
        
        elif choice == "3":
            # הסרת סמל
            remove_symbol = input("\nEnter symbol to remove: ").upper()
            if remove_symbol in current_symbols:
                current_symbols.remove(remove_symbol)
                print(f"✅ Removed {remove_symbol} from watchlist")
            else:
                print("❌ Symbol not found")
        
        elif choice == "4":
            # איפוס לברירת מחדל
            Config.DEFAULT_COINS = ['BTC', 'ETH', 'SOL', 'ADA', 'DOT', 'MATIC', 'LINK', 'AVAX', 'XRP', 'ATOM']
            print("✅ Reset to default symbols")
        
        input("\nPress Enter to continue...")
    def run_debug(self):
        """כלי debug עם בדיקות היברידיות"""
        print("\n🔧 System Diagnostics & Debug Tools")
        print("="*50)
        
        debug_options = [
            ("1", "🔍 Test Kraken API Connection", self._debug_kraken),
            ("2", "📊 Test Classic Data Collection", self._debug_data_collection),
            ("3", "🚀 Test Hybrid Data Collection", self._debug_hybrid_collection),
            ("4", "🖥️  Test Dashboard Components", self._debug_dashboard),
            ("5", "🧪 Test Simulation System", self._debug_simulations),
            ("6", "📁 Check File System", self._debug_filesystem),
            ("7", "🌐 Test WebSocket Connection", self._debug_websocket),
            ("8", "🔧 Full System Diagnostics", self._debug_full_system)
        ]
        
        print("\nDiagnostic Options:")
        for key, desc, _ in debug_options:
            available = "✅" if key != "3" or HYBRID_AVAILABLE else "❌"
            if key == "7" and not HYBRID_AVAILABLE:
                available = "❌"
            print(f"  {key}. {available} {desc}")
        
        choice = input("\nSelect diagnostic (1-8): ").strip()
        
        debug_map = {opt[0]: opt[2] for opt in debug_options}
        debug_func = debug_map.get(choice)
        
        if debug_func:
            print("\n" + "="*50)
            debug_func()
        else:
            print("❌ Invalid choice")
    
    def _debug_hybrid_collection(self):
        """בדיקת איסוף היברידי"""
        if not HYBRID_AVAILABLE:
            print("❌ Hybrid collection not available")
            print("Missing: websockets package")
            print("Install: pip install websockets")
            return
        
        print("🚀 Testing Hybrid Data Collection...")
        
        try:
            from modules.hybrid_market_collector import HybridMarketCollector
            
            print("✅ Hybrid collector module imported")
            
            # בדיקה קצרה
            test_symbols = ['BTC', 'ETH']
            print(f"🧪 Creating test collector for {test_symbols}...")
            
            collector = HybridMarketCollector(
                symbols=test_symbols,
                api_key=Config.get_api_key('KRAKEN_API_KEY'),
                api_secret=Config.get_api_key('KRAKEN_API_SECRET')
            )
            
            print("✅ Hybrid collector created successfully")
            
            # Test callback
            update_count = 0
            def test_callback(price_update):
                nonlocal update_count
                update_count += 1
                print(f"  📊 Update {update_count}: {price_update.symbol} = ${price_update.price:.2f}")
            
            collector.add_data_callback(test_callback)
            
            print("🚀 Starting collector for 10 seconds...")
            collector.start()
            
            # המתנה קצרה
            time.sleep(10)
            
            # בדיקת סטטיסטיקות
            stats = collector.get_statistics()
            print(f"\n📊 Test Results:")
            print(f"  • Total Updates: {stats['total_updates']}")
            print(f"  • WebSocket Status: {stats['websocket_status']}")
            print(f"  • Active Symbols: {stats['active_symbols']}")
            
            # עצירה
            collector.stop()
            print("✅ Hybrid collection test completed")
            
        except Exception as e:
            print(f"❌ Hybrid collection test failed: {e}")
    
    def _debug_websocket(self):
        """בדיקת חיבור WebSocket"""
        if not HYBRID_AVAILABLE:
            print("❌ WebSocket support not available")
            return
        
        print("🌐 Testing WebSocket Connection...")
        
        try:
            import asyncio
            import websockets
            
            async def test_ws():
                try:
                    print("🔗 Connecting to Kraken WebSocket...")
                    async with websockets.connect("wss://ws.kraken.com") as websocket:
                        print("✅ WebSocket connection successful")
                        
                        # Test subscription
                        sub_msg = {
                            "event": "subscribe",
                            "pair": ["XBT/USD"],
                            "subscription": {"name": "ticker"}
                        }
                        
                        await websocket.send(json.dumps(sub_msg))
                        print("📡 Subscription message sent")
                        
                        # Wait for responses
                        for i in range(3):
                            response = await asyncio.wait_for(websocket.recv(), timeout=5)
                            data = json.loads(response)
                            print(f"📨 Response {i+1}: {data.get('event', 'data')}")
                        
                        print("✅ WebSocket test completed successfully")
                        
                except asyncio.TimeoutError:
                    print("⏰ WebSocket timeout - connection might be slow")
                except Exception as e:
                    print(f"❌ WebSocket test failed: {e}")
            
            # הרצת הבדיקה
            asyncio.run(test_ws())
            
        except ImportError:
            print("❌ WebSocket modules not available")
        except Exception as e:
            print(f"❌ WebSocket test error: {e}")
    
    def _debug_data_collection(self):
        """בדיקת איסוף נתונים קלאסי"""
        try:
            from modules.market_collector import MarketCollector
            
            print("📊 Testing Classic Data Collection...")
            collector = MarketCollector()
            
            # Test basic functionality
            symbols = ['BTC', 'ETH']
            prices = collector.get_combined_prices(symbols)
            
            if prices:
                print("✅ Classic data collection working")
                for symbol, data in prices.items():
                    print(f"  • {symbol}: ${data['price']:,.2f}")
            else:
                print("❌ No data received")
                
        except ImportError:
            print("❌ Classic market collector not available")
        except Exception as e:
            print(f"❌ Classic data collection test failed: {e}")
    
    def _debug_kraken(self):
        """בדיקת Kraken API"""
        try:
            from modules.debug_kraken import test_connection
            test_connection()
        except ImportError:
            print("❌ Debug Kraken module not found")
            if Config.get_api_key('KRAKEN_API_KEY'):
                print("✅ API Key configured")
            else:
                print("❌ No API key configured")
    
    def _debug_dashboard(self):
        """בדיקת רכיבי דאשבורד"""
        print("🖥️  Testing Dashboard Components...")
        
        try:
            import streamlit
            print("✅ Streamlit installed")
        except ImportError:
            print("❌ Streamlit not installed")
        
        dashboard_files = [
            ('Simple Dashboard', os.path.join(DASHBOARDS_DIR, 'simple_dashboard.py')),
            ('Advanced Dashboard', os.path.join(DASHBOARDS_DIR, 'advanced_dashboard.py'))
        ]
        
        for name, path in dashboard_files:
            if os.path.exists(path):
                print(f"✅ {name} found")
            else:
                print(f"❌ {name} not found at {path}")
    
    def _debug_simulations(self):
        """בדיקת מערכת סימולציות"""
        try:
            from modules.simulation_core import SimulationEngine
            
            print("🧪 Testing simulation engine...")
            engine = SimulationEngine(initial_balance=1000)
            print("✅ Simulation engine initialized")
            
        except ImportError:
            print("❌ Simulation modules not available")
        except Exception as e:
            print(f"❌ Simulation test failed: {e}")
    
    def _debug_filesystem(self):
        """בדיקת מערכת קבצים"""
        print("📁 File System Diagnostics...")
        
        directories = ['data', 'logs', 'modules', 'dashboards']
        for directory in directories:
            path = os.path.join(BASE_DIR, directory)
            if os.path.exists(path):
                files = len(os.listdir(path))
                print(f"✅ {directory}/ - {files} files")
            else:
                print(f"❌ {directory}/ - missing")
        
        # Test write permissions
        test_file = os.path.join(Config.DATA_DIR, 'test_write.tmp')
        try:
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
            print("✅ File write permissions OK")
        except Exception as e:
            print(f"❌ File write permissions failed: {e}")
    
    def _debug_full_system(self):
        """בדיקה מלאה של המערכת עם תמיכה היברידית"""
        print("🔧 Running Full System Diagnostics...")
        print("="*50)
        
        tests = [
            ("API Connection", self._debug_kraken),
            ("Classic Data Collection", self._debug_data_collection),
            ("Dashboard Components", self._debug_dashboard),
            ("Simulations", self._debug_simulations),
            ("File System", self._debug_filesystem)
        ]
        
        if HYBRID_AVAILABLE:
            tests.insert(2, ("Hybrid Data Collection", self._debug_hybrid_collection))
            tests.insert(3, ("WebSocket Connection", self._debug_websocket))
        
        for test_name, test_func in tests:
            print(f"\n🔍 Testing {test_name}...")
            try:
                test_func()
                print(f"✅ {test_name} - PASSED")
            except Exception as e:
                print(f"❌ {test_name} - FAILED: {e}")
        
        print(f"\n{'='*50}")
        if HYBRID_AVAILABLE:
            print("✅ Full diagnostics complete (Hybrid Mode)")
        else:
            print("✅ Full diagnostics complete (Classic Mode)")
    
    def show_docs(self):
        """תיעוד מערכת עם מידע היברידי"""
        print("\n📚 System Documentation & Help")
        print("="*50)
        
        docs_menu = [
            ("1", "🚀 Quick Start Guide"),
            ("2", "📊 Dashboard User Guide"),  
            ("3", "🤖 AI Trading Features"),
            ("4", "⚙️  API Configuration"),
            ("5", "🌟 Hybrid Mode Guide (WebSocket + HTTP)"),
            ("6", "🧪 Running Simulations"),
            ("7", "🔧 Troubleshooting Guide"),
            ("8", "📈 Market Analysis Tools"),
            ("9", "🔒 Security Best Practices")
        ]
        
        for key, title in docs_menu:
            available = "✅" if key != "5" or HYBRID_AVAILABLE else "❌"
            print(f"  {key}. {available} {title}")
        
        choice = input("\nSelect topic (1-9, or Enter to go back): ").strip()
        
        if choice == "5":
            self._show_hybrid_guide()
        elif choice == "7":
            self._show_troubleshooting_guide_hybrid()
        else:
            # Use existing documentation methods
            if choice == "1":
                self._show_quick_start_guide()
            # Add other documentation methods as needed
        
        if choice in ["1", "2", "3", "4", "5", "6", "7", "8", "9"]:
            input("\nPress Enter to continue...")
    
    def _show_hybrid_guide(self):
        """מדריך מצב היברידי"""
        if not HYBRID_AVAILABLE:
            print("\n❌ Hybrid Mode Not Available")
            print("Missing: websockets package")
            print("Install: pip install websockets")
            return
        
        print("\n🌟 Hybrid Mode Guide (WebSocket + HTTP)")
        print("="*50)
        print("""
WHAT IS HYBRID MODE?
• Combines WebSocket real-time feeds with HTTP API calls
• WebSocket: Live price updates (sub-second latency)
• HTTP: Account data, trading history, fallback
• Best of both worlds: Speed + Reliability

ADVANTAGES:
• ⚡ Real-time price updates (no 30-second delays)
• 📉 Lower bandwidth usage
• 🔄 Automatic fallback to HTTP if WebSocket fails
• 💰 Instant trading signal generation
• 📊 Better market analysis with live data

HOW TO USE:
1. Choose "Hybrid Data Collection" from main menu
2. System automatically connects to WebSocket feeds
3. HTTP used for account data and fallback
4. Dashboard shows real-time updates

REQUIREMENTS:
• Python websockets package: pip install websockets
• Stable internet connection
• Kraken API keys (optional but recommended)

TROUBLESHOOTING:
• If WebSocket fails, system falls back to HTTP
• Check firewall settings for WebSocket connections
• Monitor logs for connection status

PERFORMANCE:
• Expect 10-100x faster price updates
• Reduced server load on Kraken
• More accurate trading signals
        """)
    
    def _show_troubleshooting_guide_hybrid(self):
        """מדריך פתרון בעיות עם תמיכה היברידית"""
        print("\n🔧 Troubleshooting Guide (Hybrid Mode)")
        print("="*50)
        print("""
COMMON ISSUES:

1. WebSocket Connection Failed:
   → Check internet connection
   → Verify firewall allows WebSocket connections
   → Try restarting the hybrid collector
   → Check logs for detailed error messages

2. "Hybrid collector not available":
   → Install websockets: pip install websockets
   → Restart the application
   → Check Python version (3.8+ recommended)

3. WebSocket connects but no data:
   → Check symbol subscriptions
   → Verify Kraken WebSocket service status
   → System will fallback to HTTP automatically

4. High CPU usage with WebSocket:
   → Reduce number of tracked symbols
   → Check for memory leaks in logs
   → Consider using HTTP-only mode temporarily

5. Data inconsistencies:
   → WebSocket and HTTP data may have slight differences
   → This is normal due to timing
   → Hybrid system prioritizes WebSocket data

6. API rate limiting:
   → WebSocket reduces API calls significantly
   → HTTP fallback respects rate limits
   → Account data still uses HTTP (unavoidable)

HYBRID-SPECIFIC DEBUGGING:
• Use Debug menu option "Test Hybrid Data Collection"
• Check WebSocket connection with "Test WebSocket Connection"
• Monitor logs for connection status changes
• Watch for fallback messages in console

GETTING HELP:
• Enable debug logging for detailed information
• Check system diagnostics (debug option)
• WebSocket issues are often network-related
• Consider running in HTTP-only mode as fallback
        """)
    
    def _show_quick_start_guide(self):
        """מדריך התחלה מהירה עם היברידי"""
        print("\n🚀 Quick Start Guide")
        print("="*40)
        
        mode_info = "🌟 Hybrid Mode" if HYBRID_AVAILABLE else "📡 HTTP Mode"
        
        print(f"""
CURRENT MODE: {mode_info}

1. INSTALLATION:
   • Ensure Python 3.8+ is installed
   • Run: pip install -r requirements.txt
   • For Hybrid Mode: pip install websockets
   • Copy .env.example to .env

2. API CONFIGURATION:
   • Get Kraken API key from kraken.com
   • Add your keys to .env file:
     KRAKEN_API_KEY=your_key_here
     KRAKEN_API_SECRET=your_secret_here

3. FIRST RUN:
   • Test system: python main.py → option 10 (Debug)
   • Start dashboard: python main.py → option 1
   • Access at: http://localhost:8501

4. DATA COLLECTION:
   • Hybrid Mode: python main.py → option 2 (Real-time)
   • Classic Mode: python main.py → option 3 (30s intervals)

5. ADVANCED FEATURES:
   • AI Trading: option 4 (requires OpenAI API key)
   • Full System: option 5 (Hybrid) or option 6 (Classic)
   • Simulations: option 6

6. MONITORING:
   • Check logs/ directory for detailed information
   • Use debug options for troubleshooting
   • Monitor system resources with hybrid mode
        """)
    
    def _cleanup_processes(self):
        """ניקוי תהליכים כולל היברידי"""
        # Stop hybrid collector
        if self.hybrid_collector:
            try:
                self.hybrid_collector.stop()
                logger.info("Hybrid collector stopped")
            except Exception as e:
                logger.error(f"Error stopping hybrid collector: {e}")
        
        # Stop other processes
        for name, process in self.processes.items():
            if process and process.poll() is None:
                logger.info(f"Terminating {name}")
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
    
    def run(self):
        """הפעלה ראשית עם תמיכה היברידית"""
        while True:
            try:
                choice = self.show_menu()
                
                if choice == "exit":
                    print("\n👋 Thank you for using Kraken Trading Bot!")
                    if HYBRID_AVAILABLE:
                        print("🌟 Hybrid Mode: WebSocket + HTTP")
                    print("💎 Safe trading!")
                    break
                    
                elif choice == "simple_dashboard":
                    self.run_simple_dashboard()
                    
                elif choice == "hybrid_collect_data":
                    self.run_hybrid_data_collection()
                    
                elif choice == "collect_data":
                    self.run_data_collection()
                    
                elif choice == "ai_dashboard":
                    self.run_ai_dashboard()  # You'll need to implement this
                    
                elif choice == "hybrid_full_system":
                    self.run_hybrid_full_system()
                    
                elif choice == "simulations":
                    self.run_simulations()
                    
                elif choice == "analysis":
                    self.show_analysis()
                    
                elif choice == "settings":
                    self.show_settings()
                    
                elif choice == "symbols":
                    self._update_trading_symbols()  # You'll need to implement this
                    
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
    """נקודת כניסה ראשית מעודכנת"""
    parser = argparse.ArgumentParser(
        description='Kraken Trading Bot v2.1 - Hybrid WebSocket + HTTP Trading System',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                    # Interactive menu
  python main.py --mode dashboard   # Direct to dashboard
  python main.py --mode hybrid      # Start hybrid data collection
  python main.py --mode collect     # Start classic data collection
  python main.py --mode simulate    # Run simulations
  python main.py --mode debug       # System diagnostics
        """
    )
    
    parser.add_argument(
        '--mode',
        choices=['dashboard', 'hybrid', 'collect', 'simulate', 'debug', 'full'],
        help='Direct mode execution'
    )
    
    parser.add_argument(
        '--symbols',
        nargs='+',
        help='Symbols to track (e.g., BTC ETH SOL)'
    )
    
    parser.add_argument(
        '--no-git',
        action='store_true',
        help='Disable git auto-update'
    )
    
    parser.add_argument(
        '--version',
        action='version',
        version='Kraken Trading Bot v2.1.0-hybrid'
    )
    
    args = parser.parse_args()
    
    # Initialize bot manager
    try:
        bot_manager = EnhancedTradingBotManager()
    except Exception as e:
        print(f"❌ Failed to initialize system: {e}")
        return
    
    try:
        # Direct mode execution
        if args.mode:
            print(f"🚀 Starting in {args.mode} mode...")
            
            if args.mode == 'dashboard':
                bot_manager.run_simple_dashboard()
            elif args.mode == 'hybrid':
                if HYBRID_AVAILABLE:
                    bot_manager.run_hybrid_data_collection()
                else:
                    print("❌ Hybrid mode not available, falling back to classic")
                    bot_manager.run_data_collection()
            elif args.mode == 'collect':
                bot_manager.run_data_collection()
            elif args.mode == 'simulate':
                bot_manager.run_simulations()
            elif args.mode == 'debug':
                bot_manager.run_debug()
            elif args.mode == 'full':
                if HYBRID_AVAILABLE:
                    bot_manager.run_hybrid_full_system()
                else:
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
        if HYBRID_AVAILABLE:
            print("🌟 Hybrid WebSocket + HTTP support was available")
        print("💎 Thank you for using Kraken Trading Bot!")

if __name__ == '__main__':
    main()