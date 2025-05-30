# scripts/prepare_ml_data.py
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config

def prepare_training_data(symbol='BTC', days=365):
    """הכנת נתונים לאימון מודל ML"""
    
    # טעינת נתונים היסטוריים
    history_file = os.path.join(Config.DATA_DIR, 'market_history.csv')
    
    if not os.path.exists(history_file):
        print("❌ No historical data found! Run data collection first.")
        return None
    
    # טעינת הנתונים
    df = pd.read_csv(history_file)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # סינון לפי סמל
    df = df[df['pair'] == f'{symbol}USD'].copy()
    df = df.sort_values('timestamp')
    
    print(f"📊 Loaded {len(df)} records for {symbol}")
    
    # הכנת features
    df = create_features(df)
    
    # הסרת NaN
    df = df.dropna()
    
    # שמירה
    output_file = os.path.join(Config.DATA_DIR, f'{symbol}_ml_ready.csv')
    df.to_csv(output_file, index=False)
    print(f"✅ Saved ML-ready data to {output_file}")
    
    return df

def create_features(df):
    """יצירת features לML"""
    
    # Features בסיסיים
    df['returns'] = df['price'].pct_change()
    df['log_returns'] = np.log(df['price'] / df['price'].shift(1))
    
    # Moving averages
    for window in [5, 10, 20, 50, 100]:
        df[f'sma_{window}'] = df['price'].rolling(window).mean()
        df[f'price_to_sma_{window}'] = df['price'] / df[f'sma_{window}']
    
    # RSI
    df['rsi'] = calculate_rsi(df['price'])
    
    # Bollinger Bands
    df['bb_upper'], df['bb_middle'], df['bb_lower'] = calculate_bollinger_bands(df['price'])
    df['bb_position'] = (df['price'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])
    
    # Volume features
    df['volume_sma'] = df['volume'].rolling(20).mean()
    df['volume_ratio'] = df['volume'] / df['volume_sma']
    
    # Volatility
    df['volatility'] = df['returns'].rolling(20).std()
    
    # Time features
    df['hour'] = df['timestamp'].dt.hour
    df['day_of_week'] = df['timestamp'].dt.dayofweek
    df['month'] = df['timestamp'].dt.month
    
    # Lag features
    for i in [1, 2, 3, 5, 10]:
        df[f'returns_lag_{i}'] = df['returns'].shift(i)
        df[f'volume_lag_{i}'] = df['volume_ratio'].shift(i)
    
    # Target - מחיר בעוד X שעות
    for hours in [1, 4, 24, 48]:
        df[f'target_{hours}h'] = df['price'].shift(-hours)
        df[f'target_return_{hours}h'] = (df[f'target_{hours}h'] - df['price']) / df['price']
    
    return df

def calculate_rsi(prices, period=14):
    """חישוב RSI"""
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_bollinger_bands(prices, window=20, num_std=2):
    """חישוב Bollinger Bands"""
    sma = prices.rolling(window).mean()
    std = prices.rolling(window).std()
    upper = sma + (std * num_std)
    lower = sma - (std * num_std)
    return upper, sma, lower

if __name__ == "__main__":
    # הכנת נתונים למספר מטבעות
    symbols = ['BTC', 'ETH', 'SOL']
    
    for symbol in symbols:
        print(f"\n🔄 Preparing data for {symbol}...")
        prepare_training_data(symbol)