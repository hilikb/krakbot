import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import logging
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
import hashlib

# Load environment variables
load_dotenv()

class ConfigurationError(Exception):
    """Custom exception for configuration errors"""
    pass

class SecurityConfig:
    """מחלקת אבטחה מתקדמת"""
    
    @staticmethod
    def validate_api_key(key: str, key_name: str) -> bool:
        """בדיקת תקינות מפתח API"""
        if not key:
            return False
        
        # Basic validation rules
        min_length = 16
        if len(key) < min_length:
            logging.warning(f"{key_name} seems too short")
            return False
        
        # Check for obviously fake keys
        fake_patterns = ['your_key_here', 'example', 'test', 'fake', 'demo']
        if any(pattern in key.lower() for pattern in fake_patterns):
            logging.warning(f"{key_name} appears to be a placeholder")
            return False
        
        return True
    
    @staticmethod
    def mask_sensitive_value(value: str, visible_chars: int = 4) -> str:
        """הסתרת ערכים רגישים"""
        if not value or len(value) <= visible_chars:
            return "*" * 8
        return value[:visible_chars] + "*" * (len(value) - visible_chars * 2) + value[-visible_chars:]

class AdvancedConfig:
    """מחלקת קונפיגורציה מתקדמת עם בקרת אבטחה ותיעוד"""
    
    # Base directories
    BASE_DIR = Path(__file__).parent.absolute()
    DATA_DIR = BASE_DIR / 'data'
    LOGS_DIR = BASE_DIR / 'logs'
    MODELS_DIR = BASE_DIR / 'models'
    STRATEGIES_DIR = BASE_DIR / 'strategies'
    CONFIG_DIR = BASE_DIR / 'config'
    
    # API Keys with validation
    _api_keys = {}
    _api_key_status = {}
    
    def __init__(self):
        self._setup_directories()
        self._load_api_keys()
        self._load_trading_config()
        self._setup_logging_advanced()
        self._validate_configuration()
    
    def _setup_directories(self):
        """יצירת תיקיות נדרשות"""
        directories = [
            self.DATA_DIR,
            self.LOGS_DIR,
            self.MODELS_DIR,
            self.STRATEGIES_DIR,
            self.CONFIG_DIR,
            self.DATA_DIR / 'backups',
            self.DATA_DIR / 'exports',
            self.LOGS_DIR / 'trading',
            self.LOGS_DIR / 'analysis',
            self.MODELS_DIR / 'trained',
            self.MODELS_DIR / 'scalers'
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
    
    def _load_api_keys(self):
        """טעינת מפתחות API עם בדיקת תקינות"""
        api_keys_config = {
            'KRAKEN_API_KEY': {
                'env_var': 'KRAKEN_API_KEY',
                'required': False,
                'description': 'Kraken exchange API key'
            },
            'KRAKEN_API_SECRET': {
                'env_var': 'KRAKEN_API_SECRET',
                'required': False,
                'description': 'Kraken exchange API secret'
            },
            'OPENAI_API_KEY': {
                'env_var': 'OPENAI_API_KEY',
                'required': False,
                'description': 'OpenAI API key for AI features'
            },
            'CRYPTOPANIC_API_KEY': {
                'env_var': 'CRYPTOPANIC_API_KEY',
                'required': False,
                'description': 'CryptoPanic API key for news'
            },
            'BINANCE_API_KEY': {
                'env_var': 'BINANCE_API_KEY',
                'required': False,
                'description': 'Binance API key (optional)'
            },
            'BINANCE_API_SECRET': {
                'env_var': 'BINANCE_API_SECRET',
                'required': False,
                'description': 'Binance API secret (optional)'
            }
        }
        
        for key_name, config in api_keys_config.items():
            value = os.getenv(config['env_var'], '')
            self._api_keys[key_name] = value
            
            # Validate key
            is_valid = SecurityConfig.validate_api_key(value, key_name)
            self._api_key_status[key_name] = {
                'configured': bool(value),
                'valid': is_valid,
                'required': config['required'],
                'description': config['description'],
                'masked_value': SecurityConfig.mask_sensitive_value(value) if value else None
            }
    
    def _load_trading_config(self):
        """טעינת הגדרות מסחר מתקדמות"""
        # Default trading parameters with enhanced settings
        self.TRADING_PARAMS = {
            'risk_management': {
                'max_daily_loss_pct': float(os.getenv('MAX_DAILY_LOSS_PCT', '0.02')),
                'max_position_size_pct': float(os.getenv('MAX_POSITION_SIZE_PCT', '0.10')),
                'max_total_exposure_pct': float(os.getenv('MAX_TOTAL_EXPOSURE_PCT', '0.50')),
                'stop_loss_pct': float(os.getenv('DEFAULT_STOP_LOSS_PCT', '0.03')),
                'take_profit_pct': float(os.getenv('DEFAULT_TAKE_PROFIT_PCT', '0.06')),
                'trailing_stop_pct': float(os.getenv('TRAILING_STOP_PCT', '0.02'))
            },
            
            'position_management': {
                'max_positions': int(os.getenv('MAX_POSITIONS', '5')),
                'min_trade_amount': float(os.getenv('MIN_TRADE_AMOUNT', '25')),
                'position_timeout_hours': int(os.getenv('POSITION_TIMEOUT_HOURS', '24')),
                'rebalance_threshold_pct': float(os.getenv('REBALANCE_THRESHOLD_PCT', '0.05'))
            },
            
            'signal_filtering': {
                'min_confidence': float(os.getenv('MIN_SIGNAL_CONFIDENCE', '0.75')),
                'max_correlation': float(os.getenv('MAX_POSITION_CORRELATION', '0.70')),
                'volume_filter_min': float(os.getenv('MIN_VOLUME_USD', '100000')),
                'spread_filter_max_pct': float(os.getenv('MAX_SPREAD_PCT', '0.02'))
            },
            
            'market_hours': {
                'trading_enabled_24_7': os.getenv('TRADING_24_7', 'true').lower() == 'true',
                'maintenance_hours': os.getenv('MAINTENANCE_HOURS', '02:00-03:00'),
                'high_activity_hours': os.getenv('HIGH_ACTIVITY_HOURS', '08:00-20:00')
            }
        }
        
        # Symbol configuration
        self.SYMBOL_CONFIG = {
            'default_symbols': self._load_symbol_list('DEFAULT_SYMBOLS', 
                ['BTC', 'ETH', 'SOL', 'ADA', 'DOT', 'MATIC', 'LINK', 'AVAX', 'XRP', 'ATOM']),
            'priority_symbols': self._load_symbol_list('PRIORITY_SYMBOLS', 
                ['BTC', 'ETH', 'SOL']),
            'excluded_symbols': self._load_symbol_list('EXCLUDED_SYMBOLS', 
                ['LUNA', 'UST', 'FTT']),
            'max_symbols': int(os.getenv('MAX_SYMBOLS', '600')),
            'symbol_rotation_enabled': os.getenv('SYMBOL_ROTATION', 'true').lower() == 'true'
        }
        
        # ⭐ הוספה חדשה - Hybrid Mode Settings ⭐
        self.HYBRID_CONFIG = {
            'websocket_max_symbols': int(os.getenv('WEBSOCKET_MAX_SYMBOLS', '80')),
            'http_update_interval': int(os.getenv('HTTP_UPDATE_INTERVAL', '120')),
            'websocket_priority_symbols': self._load_symbol_list('WEBSOCKET_PRIORITY_SYMBOLS', 
                ['BTC', 'ETH', 'SOL', 'USDT', 'USDC', 'ADA', 'DOT', 'MATIC', 'LINK', 'AVAX']),
            'enable_http_fallback': os.getenv('ENABLE_HTTP_FALLBACK', 'true').lower() == 'true',
            'enable_parallel_http': os.getenv('ENABLE_PARALLEL_HTTP', 'true').lower() == 'true',
            'websocket_reconnect_attempts': int(os.getenv('WEBSOCKET_RECONNECT_ATTEMPTS', '5')),
            'http_batch_size': int(os.getenv('HTTP_BATCH_SIZE', '20')),
            'stale_data_threshold': int(os.getenv('STALE_DATA_THRESHOLD', '120'))  # seconds
        }
        
        # Data collection settings
        self.DATA_COLLECTION = {
            'market_update_interval': int(os.getenv('MARKET_UPDATE_INTERVAL', '30')),
            'news_update_interval': int(os.getenv('NEWS_UPDATE_INTERVAL', '300')),
            'history_cleanup_days': int(os.getenv('HISTORY_CLEANUP_DAYS', '30')),
            'data_quality_min_score': float(os.getenv('DATA_QUALITY_MIN_SCORE', '0.7')),
            'backup_enabled': os.getenv('DATA_BACKUP_ENABLED', 'true').lower() == 'true',
            'backup_interval_hours': int(os.getenv('BACKUP_INTERVAL_HOURS', '24'))
        }
        
        # Simple attributes for backward compatibility
        self.DEFAULT_COINS = self.SYMBOL_CONFIG['default_symbols']
        self.DEFAULT_TRADING_PARAMS = {
            'min_trade_amount': self.TRADING_PARAMS['position_management']['min_trade_amount'],
            'max_trade_percent': self.TRADING_PARAMS['risk_management']['max_position_size_pct'],
            'stop_loss_percent': self.TRADING_PARAMS['risk_management']['stop_loss_pct'] * 100,
            'take_profit_percent': self.TRADING_PARAMS['risk_management']['take_profit_pct'] * 100
        }
        
        # Trading settings for compatibility
        self.TRADING_SETTINGS = {
            'use_all_symbols': os.getenv('USE_ALL_SYMBOLS', 'false').lower() == 'true',
            'max_symbols': self.SYMBOL_CONFIG['max_symbols'],
            'priority_symbols': self.SYMBOL_CONFIG['priority_symbols']
        }
        
    
    def _load_symbol_list(self, env_var: str, default: List[str]) -> List[str]:
        """טעינת רשימת סמלים מ-environment"""
        env_value = os.getenv(env_var)
        if env_value:
            return [s.strip().upper() for s in env_value.split(',')]
        return default
    
    def _setup_logging_advanced(self):
        """הגדרת לוגינג מתקדמת"""
        self.LOGGING_CONFIG = {
            'level': os.getenv('LOG_LEVEL', 'INFO').upper(),
            'format': os.getenv('LOG_FORMAT', 
                '%(asctime)s [%(levelname)s] %(name)s:%(lineno)d - %(message)s'),
            'date_format': '%Y-%m-%d %H:%M:%S',
            'max_file_size_mb': int(os.getenv('LOG_MAX_FILE_SIZE_MB', '50')),
            'backup_count': int(os.getenv('LOG_BACKUP_COUNT', '5')),
            'console_logging': os.getenv('CONSOLE_LOGGING', 'true').lower() == 'true',
            'file_logging': os.getenv('FILE_LOGGING', 'true').lower() == 'true',
            'structured_logging': os.getenv('STRUCTURED_LOGGING', 'false').lower() == 'true'
        }
    
    def _validate_configuration(self):
        """בדיקת תקינות הגדרות"""
        errors = []
        warnings = []
        
        # Validate trading parameters
        if self.TRADING_PARAMS['risk_management']['max_daily_loss_pct'] > 0.1:
            warnings.append("Daily loss limit exceeds 10% - high risk setting")
        
        if self.TRADING_PARAMS['position_management']['max_positions'] > 10:
            warnings.append("Maximum positions set very high - may impact performance")
        
        # Validate API keys for critical functions
        if not self.get_api_key('KRAKEN_API_KEY'):
            warnings.append("No Kraken API key - live trading disabled")
        
        # Validate directories
        if not os.access(self.DATA_DIR, os.W_OK):
            errors.append(f"Data directory not writable: {self.DATA_DIR}")
        
        # Log results
        if errors:
            for error in errors:
                logging.error(f"Configuration error: {error}")
            raise ConfigurationError(f"Configuration errors: {'; '.join(errors)}")
        
        if warnings:
            for warning in warnings:
                logging.warning(f"Configuration warning: {warning}")
    
    # API Key Management
    def get_api_key(self, key_name: str) -> str:
        """קבלת מפתח API"""
        return self._api_keys.get(key_name, '')
    
    def get_api_key_status(self, key_name: str) -> Dict:
        """קבלת סטטוס מפתח API"""
        return self._api_key_status.get(key_name, {})
    
    def get_all_api_status(self) -> Dict:
        """קבלת סטטוס כל המפתחות"""
        return self._api_key_status.copy()
    
    def validate_keys(self) -> bool:
        """בדיקת תקינות מפתחות API - הוספנו את המתודה החסרה"""
        # Check if at least one API key is configured and valid
        for key_name, status in self._api_key_status.items():
            if status.get('configured') and status.get('valid'):
                return True
        return False
    
    # File Paths
    @property
    def MARKET_LIVE_FILE(self) -> Path:
        return self.DATA_DIR / 'market_live.csv'
    
    @property
    def MARKET_HISTORY_FILE(self) -> Path:
        return self.DATA_DIR / 'market_history.csv'
    
    @property
    def NEWS_FEED_FILE(self) -> Path:
        return self.DATA_DIR / 'news_feed.csv'
    
    @property
    def TRADING_LOG_FILE(self) -> Path:
        return self.DATA_DIR / 'trading_log.csv'
    
    @property
    def SIMULATION_LOG_FILE(self) -> Path:
        return self.DATA_DIR / 'simulation_log.csv'
    
    @property
    def BACKUP_DIR(self) -> Path:
        return self.DATA_DIR / 'backups'
        
    @property
    def WEBSOCKET_MAX_SYMBOLS(self) -> int:
        """מספר מקסימלי של סמלים לWebSocket"""
        return self.HYBRID_CONFIG['websocket_max_symbols']

    @property
    def HTTP_UPDATE_INTERVAL(self) -> int:
        """אינטרוול עדכון HTTP בשניות"""
        return self.HYBRID_CONFIG['http_update_interval']

    @property
    def WEBSOCKET_PRIORITY_SYMBOLS(self) -> List[str]:
        """סמלים בעדיפות גבוהה לWebSocket"""
        return self.HYBRID_CONFIG['websocket_priority_symbols']    
        
    # Logging Setup
    def setup_logging(self, module_name: str) -> logging.Logger:
        """הגדרת לוגר למודול ספציפי עם הגדרות מתקדמות"""
        logger = logging.getLogger(module_name)
        
        # Prevent duplicate handlers
        if logger.handlers:
            return logger
        
        logger.setLevel(getattr(logging, self.LOGGING_CONFIG['level']))
        
        formatter = logging.Formatter(
            self.LOGGING_CONFIG['format'],
            datefmt=self.LOGGING_CONFIG['date_format']
        )
        
        # File handler with rotation
        if self.LOGGING_CONFIG['file_logging']:
            try:
                from logging.handlers import RotatingFileHandler
                
                log_file = self.LOGS_DIR / f'{module_name}.log'
                file_handler = RotatingFileHandler(
                    log_file,
                    maxBytes=self.LOGGING_CONFIG['max_file_size_mb'] * 1024 * 1024,
                    backupCount=self.LOGGING_CONFIG['backup_count'],
                    encoding='utf-8'
                )
                file_handler.setFormatter(formatter)
                logger.addHandler(file_handler)
            except Exception as e:
                print(f"Warning: Could not setup file logging: {e}")
        
        # Console handler
        if self.LOGGING_CONFIG['console_logging']:
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)
        
        return logger
    
    # Configuration Management
    def save_config_snapshot(self) -> str:
        """שמירת snapshot של ההגדרות"""
        snapshot = {
            'timestamp': datetime.now().isoformat(),
            'trading_params': self.TRADING_PARAMS,
            'symbol_config': self.SYMBOL_CONFIG,
            'data_collection': self.DATA_COLLECTION,
            'logging_config': self.LOGGING_CONFIG,
            'api_keys_status': {
                key: {k: v for k, v in status.items() if k != 'masked_value'}
                for key, status in self._api_key_status.items()
            }
        }
        
        # Create hash for integrity check
        config_str = json.dumps(snapshot, sort_keys=True)
        config_hash = hashlib.sha256(config_str.encode()).hexdigest()
        snapshot['config_hash'] = config_hash
        
        # Save to file
        snapshot_file = self.CONFIG_DIR / f'config_snapshot_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        with open(snapshot_file, 'w') as f:
            json.dump(snapshot, f, indent=2)
        
        return str(snapshot_file)
    
    def get_config_summary(self) -> Dict:
        """סיכום הגדרות למטרות ניטור"""
        return {
            'api_keys': {
                key: status['configured'] and status['valid']
                for key, status in self._api_key_status.items()
            },
            'trading_enabled': (
                self._api_key_status.get('KRAKEN_API_KEY', {}).get('valid', False)
            ),
            'ai_features_enabled': (
                self._api_key_status.get('OPENAI_API_KEY', {}).get('valid', False)
            ),
            'news_features_enabled': (
                self._api_key_status.get('CRYPTOPANIC_API_KEY', {}).get('valid', False)
            ),
            'max_positions': self.TRADING_PARAMS['position_management']['max_positions'],
            'risk_level': {
                'daily_loss_limit': self.TRADING_PARAMS['risk_management']['max_daily_loss_pct'],
                'position_size_limit': self.TRADING_PARAMS['risk_management']['max_position_size_pct']
            },
            'symbols_count': len(self.SYMBOL_CONFIG['default_symbols']),
            'data_collection_interval': self.DATA_COLLECTION['market_update_interval'],
            # ⭐ הוסף את אלה ⭐
            'hybrid_mode': {
                'websocket_symbols': self.WEBSOCKET_MAX_SYMBOLS,
                'http_interval': self.HTTP_UPDATE_INTERVAL,
                'total_symbols': self.SYMBOL_CONFIG['max_symbols']
            }
        }
    
    def update_config_value(self, section: str, key: str, value: Any) -> bool:
        """עדכון ערך הגדרה דינמי"""
        try:
            if hasattr(self, section):
                config_section = getattr(self, section)
                if isinstance(config_section, dict) and key in config_section:
                    old_value = config_section[key]
                    config_section[key] = value
                    
                    logging.info(f"Config updated: {section}.{key} = {old_value} -> {value}")
                    return True
            
            logging.warning(f"Failed to update config: {section}.{key}")
            return False
            
        except Exception as e:
            logging.error(f"Error updating config: {e}")
            return False
    
    def validate_trading_hours(self) -> bool:
        """בדיקת שעות מסחר נוכחיות"""
        if self.TRADING_PARAMS['market_hours']['trading_enabled_24_7']:
            return True
        
        # Check if we're in maintenance hours
        maintenance = self.TRADING_PARAMS['market_hours']['maintenance_hours']
        current_time = datetime.now().strftime("%H:%M")
        
        if '-' in maintenance:
            start_time, end_time = maintenance.split('-')
            if start_time <= current_time <= end_time:
                return False
        
        return True
    
    # Environment and Health Checks
    def health_check(self) -> Dict:
        """בדיקת בריאות המערכת"""
        health_status = {
            'timestamp': datetime.now().isoformat(),
            'status': 'healthy',
            'issues': [],
            'warnings': []
        }
        
        # Check directories
        for dir_name, dir_path in [
            ('data', self.DATA_DIR),
            ('logs', self.LOGS_DIR),
            ('models', self.MODELS_DIR)
        ]:
            if not dir_path.exists():
                health_status['issues'].append(f"Directory missing: {dir_name}")
            elif not os.access(dir_path, os.W_OK):
                health_status['issues'].append(f"Directory not writable: {dir_name}")
        
        # Check API keys
        critical_keys = ['KRAKEN_API_KEY', 'KRAKEN_API_SECRET']
        for key in critical_keys:
            if not self._api_key_status.get(key, {}).get('valid'):
                health_status['warnings'].append(f"API key not configured: {key}")
        
        # Check disk space
        try:
            import shutil
            disk_usage = shutil.disk_usage(self.DATA_DIR)
            free_space_gb = disk_usage.free / (1024**3)
            if free_space_gb < 1:  # Less than 1GB
                health_status['issues'].append(f"Low disk space: {free_space_gb:.1f}GB free")
            elif free_space_gb < 5:  # Less than 5GB
                health_status['warnings'].append(f"Disk space getting low: {free_space_gb:.1f}GB free")
        except Exception as e:
            health_status['warnings'].append(f"Could not check disk space: {e}")
        
        # Set overall status
        if health_status['issues']:
            health_status['status'] = 'unhealthy'
        elif health_status['warnings']:
            health_status['status'] = 'warning'
        
        return health_status

# Create global instance
config = AdvancedConfig()

# Export commonly used values for backward compatibility
KRAKEN_API_KEY = config.get_api_key('KRAKEN_API_KEY')
KRAKEN_API_SECRET = config.get_api_key('KRAKEN_API_SECRET')
OPENAI_API_KEY = config.get_api_key('OPENAI_API_KEY')
CRYPTOPANIC_API_KEY = config.get_api_key('CRYPTOPANIC_API_KEY')

# Export config instance as Config for backward compatibility
Config = config

def create_env_template():
    """יצירת template לקובץ .env"""
    template = """# Kraken API Configuration (Required for live trading)
KRAKEN_API_KEY=your_kraken_api_key_here
KRAKEN_API_SECRET=your_kraken_api_secret_here

# Optional API Keys
OPENAI_API_KEY=your_openai_api_key_here
CRYPTOPANIC_API_KEY=your_cryptopanic_api_key_here
BINANCE_API_KEY=your_binance_api_key_here
BINANCE_API_SECRET=your_binance_api_secret_here

# Trading Risk Management
MAX_DAILY_LOSS_PCT=0.02
MAX_POSITION_SIZE_PCT=0.10
MAX_TOTAL_EXPOSURE_PCT=0.50
DEFAULT_STOP_LOSS_PCT=0.03
DEFAULT_TAKE_PROFIT_PCT=0.06

# Position Management
MAX_POSITIONS=5
MIN_TRADE_AMOUNT=25
POSITION_TIMEOUT_HOURS=24

# Signal Filtering
MIN_SIGNAL_CONFIDENCE=0.75
MAX_POSITION_CORRELATION=0.70
MIN_VOLUME_USD=100000

# Symbols Configuration
DEFAULT_SYMBOLS=BTC,ETH,SOL,ADA,DOT,MATIC,LINK,AVAX,XRP,ATOM
PRIORITY_SYMBOLS=BTC,ETH,SOL
EXCLUDED_SYMBOLS=LUNA,UST,FTT
MAX_SYMBOLS=50

# Data Collection
MARKET_UPDATE_INTERVAL=30
NEWS_UPDATE_INTERVAL=300
HISTORY_CLEANUP_DAYS=30
DATA_QUALITY_MIN_SCORE=0.7

# Symbols Configuration
DEFAULT_SYMBOLS=BTC,ETH,SOL,ADA,DOT,MATIC,LINK,AVAX,XRP,ATOM
PRIORITY_SYMBOLS=BTC,ETH,SOL
EXCLUDED_SYMBOLS=LUNA,UST,FTT
MAX_SYMBOLS=50

# ⭐ הוסף את אלה ⭐
# Hybrid Mode Configuration
WEBSOCKET_MAX_SYMBOLS=80
WEBSOCKET_PRIORITY_SYMBOLS=BTC,ETH,SOL,USDT,USDC,ADA,DOT,MATIC,LINK,AVAX
HTTP_UPDATE_INTERVAL=120
ENABLE_HTTP_FALLBACK=true
ENABLE_PARALLEL_HTTP=true
USE_ALL_SYMBOLS=false

# Logging
LOG_LEVEL=INFO
CONSOLE_LOGGING=true
FILE_LOGGING=true
LOG_MAX_FILE_SIZE_MB=50
LOG_BACKUP_COUNT=5

# System Settings
TRADING_24_7=true
DATA_BACKUP_ENABLED=true
BACKUP_INTERVAL_HOURS=24
"""
    
    env_file = Path('.env.example')
    if not env_file.exists():
        with open(env_file, 'w') as f:
            f.write(template)
        print(f"✅ Created {env_file}")
        print("📝 Copy this file to .env and configure your settings")

if __name__ == '__main__':
    create_env_template()
    
    # Print configuration summary
    summary = config.get_config_summary()
    print("\n📊 Configuration Summary:")
    print(f"  • Trading Enabled: {summary['trading_enabled']}")
    print(f"  • AI Features: {summary['ai_features_enabled']}")
    print(f"  • News Features: {summary['news_features_enabled']}")
    print(f"  • Max Positions: {summary['max_positions']}")
    print(f"  • Symbols: {summary['symbols_count']}")
    
    # Health check
    health = config.health_check()
    print(f"\n🏥 System Health: {health['status'].upper()}")
    if health['issues']:
        print("  Issues:")
        for issue in health['issues']:
            print(f"    ❌ {issue}")
    if health['warnings']:
        print("  Warnings:")
        for warning in health['warnings']:
            print(f"    ⚠️  {warning}")