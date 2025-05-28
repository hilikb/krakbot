import os
from dotenv import load_dotenv
import logging

# טעינת משתני סביבה מקובץ .env
load_dotenv()

# הגדרת לוגר
logger = logging.getLogger(__name__)

class Config:
    """מחלקת קונפיגורציה מרכזית עם אבטחה משופרת"""
    
    # API Keys - נטענים ממשתני סביבה בלבד!
    KRAKEN_API_KEY = os.getenv('KRAKEN_API_KEY', '')
    KRAKEN_API_SECRET = os.getenv('KRAKEN_API_SECRET', '')
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
    CRYPTOPANIC_API_KEY = os.getenv('CRYPTOPANIC_API_KEY', '')
    
    # בדיקת תקינות מפתחות
    @classmethod
    def validate_keys(cls):
        """בדיקה שכל המפתחות הקריטיים קיימים"""
        missing_keys = []
        
        if not cls.KRAKEN_API_KEY:
            missing_keys.append('KRAKEN_API_KEY')
        if not cls.KRAKEN_API_SECRET:
            missing_keys.append('KRAKEN_API_SECRET')
            
        if missing_keys:
            logger.warning(f"Missing API keys: {', '.join(missing_keys)}")
            logger.info("Please set them in .env file or environment variables")
            
        return len(missing_keys) == 0
    
    # הגדרות מסחר
    DEFAULT_TRADING_PARAMS = {
        'initial_balance': 1000,
        'take_profit': 0.1,  # 10%
        'stop_loss': 0.05,   # 5%
        'max_positions': 2,
        'min_trade_amount': 10,  # מינימום $10 לטרייד
        'max_trade_percent': 0.25  # מקסימום 25% מהיתרה בטרייד אחד
    }
    
    # הגדרות איסוף נתונים
    COLLECTOR_SETTINGS = {
        'market_update_interval': 30,  # שניות
        'news_update_interval': 300,   # 5 דקות
        'history_update_hour': 2,      # 2 AM UTC
        'max_retries': 3,
        'retry_delay': 2
    }
    
    # רשימת מטבעות ברירת מחדל
    DEFAULT_COINS = ['BTC', 'ETH', 'SOL', 'ADA', 'DOT', 'MATIC', 'LINK', 'AVAX', 'XRP']
    
    # הגדרות נתיבים
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DATA_DIR = os.path.join(BASE_DIR, 'data')
    LOGS_DIR = os.path.join(BASE_DIR, 'logs')
    
    # קבצי נתונים
    MARKET_LIVE_FILE = os.path.join(DATA_DIR, 'market_live.csv')
    MARKET_HISTORY_FILE = os.path.join(DATA_DIR, 'market_history.csv')
    NEWS_FEED_FILE = os.path.join(DATA_DIR, 'news_feed.csv')
    SIMULATION_LOG_FILE = os.path.join(DATA_DIR, 'simulation_log.csv')
    TRADING_LOG_FILE = os.path.join(DATA_DIR, 'trading_log.csv')
    OPTIMIZATION_SUMMARY_FILE = os.path.join(DATA_DIR, 'param_optimization_summary.csv')
    
    # הגדרות לוגינג
    LOG_FORMAT = '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    
    @classmethod
    def setup_directories(cls):
        """יצירת תיקיות נדרשות"""
        os.makedirs(cls.DATA_DIR, exist_ok=True)
        os.makedirs(cls.LOGS_DIR, exist_ok=True)
        
    @classmethod
    def get_log_file(cls, module_name):
        """החזרת נתיב לקובץ לוג לפי שם מודול"""
        return os.path.join(cls.LOGS_DIR, f'{module_name}.log')
        
    @classmethod
    def setup_logging(cls, module_name):
        """הגדרת לוגינג למודול ספציפי"""
        log_file = cls.get_log_file(module_name)
        
        logging.basicConfig(
            level=getattr(logging, cls.LOG_LEVEL),
            format=cls.LOG_FORMAT,
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        
        return logging.getLogger(module_name)

# יצירת תיקיות בטעינת המודול
Config.setup_directories()

# יצירת קובץ .env לדוגמה אם לא קיים
env_example = """# Kraken API credentials
KRAKEN_API_KEY=your_kraken_api_key_here
KRAKEN_API_SECRET=your_kraken_api_secret_here

# OpenAI API key (for AI advisor)
OPENAI_API_KEY=your_openai_api_key_here

# CryptoPanic API key (for news)
CRYPTOPANIC_API_KEY=your_cryptopanic_api_key_here

# Logging level (DEBUG, INFO, WARNING, ERROR)
LOG_LEVEL=INFO
"""

if not os.path.exists('.env') and not os.path.exists('.env.example'):
    with open('.env.example', 'w') as f:
        f.write(env_example)
    logger.info("Created .env.example file. Copy it to .env and add your API keys.")

# ייצוא לתאימות אחורה
KRAKEN_API_KEY = Config.KRAKEN_API_KEY
KRAKEN_API_SECRET = Config.KRAKEN_API_SECRET
OPENAI_API_KEY = Config.OPENAI_API_KEY
CRYPTOPANIC_API_KEY = Config.CRYPTOPANIC_API_KEY