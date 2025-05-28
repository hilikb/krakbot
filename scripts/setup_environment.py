#!/usr/bin/env python3
"""
Setup Environment Script
========================
סקריפט להגדרת סביבת העבודה ויצירת כל התיקיות הנדרשות
"""

import os
import sys
import json
import shutil
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def create_directory_structure():
    """יצירת מבנה תיקיות מלא"""
    
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # רשימת תיקיות ליצירה
    directories = [
        'data',
        'data/ai_states',
        'data/backtest_results',
        'data/exports',
        'logs',
        'logs/trading',
        'logs/analysis',
        'models',
        'models/trained',
        'models/scalers',
        'dashboards',
        'modules',
        'strategies',
        'tests',
        'docs',
        'scripts',
        'config'
    ]
    
    print("🔧 Creating directory structure...")
    
    for directory in directories:
        dir_path = os.path.join(base_dir, directory)
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
            print(f"✅ Created: {directory}")
            
            # Create __init__.py for Python packages
            if directory in ['modules', 'strategies', 'tests']:
                init_file = os.path.join(dir_path, '__init__.py')
                with open(init_file, 'w') as f:
                    f.write(f'"""{directory} package"""\n')
        else:
            print(f"📁 Exists: {directory}")

def create_initial_files():
    """יצירת קבצים ראשוניים בתיקיות"""
    
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # Create empty CSV files
    csv_files = {
        'data/market_live.csv': 'timestamp,pair,price,volume,high_24h,low_24h,change_24h,change_pct_24h,bid,ask,spread,trades_24h,source',
        'data/market_history.csv': 'timestamp,pair,price,volume,high_24h,low_24h,change_24h,change_pct_24h,bid,ask,spread,trades_24h,source',
        'data/news_feed.csv': 'id,published_at,timestamp,title,url,source,domain,currencies,kind,votes_positive,votes_negative,votes_important,votes_liked,votes_disliked,votes_lol,votes_toxic,votes_saved,comments,importance_score,sentiment,sentiment_polarity,sentiment_subjectivity,summary',
        'data/news_archive.csv': 'id,published_at,timestamp,title,url,source,domain,currencies,kind,votes_positive,votes_negative,votes_important,votes_liked,votes_disliked,votes_lol,votes_toxic,votes_saved,comments,importance_score,sentiment,sentiment_polarity,sentiment_subjectivity,summary',
        'data/simulation_log.csv': 'id,symbol,strategy,start_time,end_time,status,init_balance,final_balance,profit_pct,trades_count,params',
        'data/trading_log.csv': 'timestamp,mode,order_id,pair,side,price,volume,amount_usd,fee,status',
        'data/param_optimization_summary.csv': 'strategy,initial_balance,take_profit,stop_loss,max_positions,avg_profit_pct,max_profit_pct,min_profit_pct'
    }
    
    print("\n📄 Creating initial data files...")
    
    for file_path, headers in csv_files.items():
        full_path = os.path.join(base_dir, file_path)
        if not os.path.exists(full_path):
            with open(full_path, 'w') as f:
                f.write(headers + '\n')
            print(f"✅ Created: {file_path}")
        else:
            print(f"📄 Exists: {file_path}")
    
    # Create initial JSON files
    json_files = {
        'data/ai_states/ai_engine_state.json': {
            'mode': 'balanced',
            'risk_level': 5,
            'strategy_weights': {
                'trend_following': 0.25,
                'mean_reversion': 0.20,
                'momentum': 0.20,
                'pattern_recognition': 0.15,
                'sentiment_analysis': 0.10,
                'arbitrage': 0.10
            },
            'current_positions': {},
            'performance_history': [],
            'confidence_threshold': 0.7,
            'timestamp': datetime.now().isoformat()
        },
        'data/ai_states/autonomous_trader_state.json': {
            'timestamp': datetime.now().isoformat(),
            'config': {
                'mode': 'conservative',
                'risk_level': 5,
                'max_daily_trades': 20,
                'max_daily_loss': 1000,
                'min_confidence': 0.7,
                'position_timeout': 3600,
                'emergency_stop_loss': 0.05
            },
            'positions': {},
            'daily_trades': [],
            'daily_pnl': 0,
            'market_data': {}
        },
        'data/bot_state.json': {
            'last_run': datetime.now().isoformat(),
            'version': '2.0.0',
            'total_runs': 0,
            'last_backup': None
        }
    }
    
    print("\n📋 Creating initial JSON files...")
    
    for file_path, content in json_files.items():
        full_path = os.path.join(base_dir, file_path)
        if not os.path.exists(full_path):
            with open(full_path, 'w') as f:
                json.dump(content, f, indent=2)
            print(f"✅ Created: {file_path}")
        else:
            print(f"📋 Exists: {file_path}")

def create_config_files():
    """יצירת קבצי הגדרות"""
    
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # .env.example
    env_example = """# Kraken API Credentials
KRAKEN_API_KEY=your_kraken_api_key_here
KRAKEN_API_SECRET=your_kraken_api_secret_here

# Optional APIs
OPENAI_API_KEY=your_openai_key_here
CRYPTOPANIC_API_KEY=your_cryptopanic_key_here

# Trading Settings
LOG_LEVEL=INFO
TRADING_MODE=demo
MAX_DAILY_TRADES=20
MAX_DAILY_LOSS=1000

# Database (Future)
DB_HOST=localhost
DB_PORT=5432
DB_NAME=kraken_bot
DB_USER=postgres
DB_PASSWORD=your_password
"""
    
    env_path = os.path.join(base_dir, '.env.example')
    if not os.path.exists(env_path):
        with open(env_path, 'w') as f:
            f.write(env_example)
        print("✅ Created: .env.example")
    
    # .gitignore
    gitignore = """# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
ENV/
.venv

# IDE
.idea/
.vscode/
*.swp
*.swo

# Environment variables
.env
.env.local
.env.*.local

# Logs
logs/
*.log

# Data files
data/*.csv
data/*.json
!data/*_example.csv

# Models
models/trained/
models/*.pkl
models/*.joblib

# Temporary files
*.tmp
*.temp
.DS_Store
Thumbs.db

# Jupyter
.ipynb_checkpoints/

# Testing
.pytest_cache/
.coverage
htmlcov/

# Distribution
dist/
build/
*.egg-info/
"""
    
    gitignore_path = os.path.join(base_dir, '.gitignore')
    if not os.path.exists(gitignore_path):
        with open(gitignore_path, 'w') as f:
            f.write(gitignore)
        print("✅ Created: .gitignore")
    
    # requirements.txt
    requirements = """# Core Dependencies
pandas==2.0.3
numpy==1.24.3
python-dotenv==1.0.0

# Trading & API
krakenex==2.1.0
python-binance==1.0.17
ccxt==4.1.0

# Web & Dashboard
streamlit==1.28.0
plotly==5.17.0
dash==2.14.0

# Technical Analysis
ta==0.10.2
pandas-ta==0.3.14b0

# Machine Learning
scikit-learn==1.3.0
joblib==1.3.2
xgboost==2.0.0
lightgbm==4.1.0

# Deep Learning (Optional)
# tensorflow==2.13.0
# torch==2.0.1

# NLP & Sentiment
textblob==0.17.1
nltk==3.8.1
vaderSentiment==3.3.2

# Utilities
requests==2.31.0
tqdm==4.66.1
schedule==1.2.0
python-telegram-bot==20.5

# Testing
pytest==7.4.2
pytest-cov==4.1.0

# Documentation
sphinx==7.2.6
sphinx-rtd-theme==1.3.0

# Optional - AI
openai==0.28.0
"""
    
    req_path = os.path.join(base_dir, 'requirements.txt')
    if not os.path.exists(req_path):
        with open(req_path, 'w') as f:
            f.write(requirements)
        print("✅ Created: requirements.txt")

def create_example_strategies():
    """יצירת קבצי אסטרטגיה לדוגמה"""
    
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # __init__.py for strategies
    strategies_init = '''"""
Trading Strategies Package
=========================
"""

from .trend_following import TrendFollowingStrategy
from .mean_reversion import MeanReversionStrategy

__all__ = ['TrendFollowingStrategy', 'MeanReversionStrategy']
'''
    
    init_path = os.path.join(base_dir, 'strategies', '__init__.py')
    with open(init_path, 'w') as f:
        f.write(strategies_init)
    
    print("✅ Created: strategies/__init__.py")

def check_dependencies():
    """בדיקת תלויות"""
    print("\n🔍 Checking dependencies...")
    
    required_packages = {
        'pandas': 'pandas',
        'numpy': 'numpy',
        'streamlit': 'streamlit',
        'plotly': 'plotly',
        'krakenex': 'krakenex',
        'dotenv': 'python-dotenv'
    }
    
    missing = []
    
    for import_name, package_name in required_packages.items():
        try:
            __import__(import_name)
            print(f"✅ {package_name} - installed")
        except ImportError:
            print(f"❌ {package_name} - missing")
            missing.append(package_name)
    
    if missing:
        print(f"\n⚠️  Missing packages: {', '.join(missing)}")
        print("Run: pip install " + " ".join(missing))
    else:
        print("\n✅ All core dependencies installed!")

def main():
    """הפעלה ראשית"""
    print("🚀 Kraken Trading Bot - Environment Setup")
    print("=" * 50)
    
    # Create directories
    create_directory_structure()
    
    # Create initial files
    create_initial_files()
    
    # Create config files
    create_config_files()
    
    # Create example strategies
    create_example_strategies()
    
    # Check dependencies
    check_dependencies()
    
    print("\n" + "=" * 50)
    print("✅ Environment setup complete!")
    print("\nNext steps:")
    print("1. Copy .env.example to .env and add your API keys")
    print("2. Install missing dependencies: pip install -r requirements.txt")
    print("3. Run the bot: python main.py")
    
    # Create setup completion marker
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    marker_file = os.path.join(base_dir, '.setup_complete')
    with open(marker_file, 'w') as f:
        f.write(datetime.now().isoformat())

if __name__ == '__main__':
    main()