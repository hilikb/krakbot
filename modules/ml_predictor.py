# modules/ml_predictor.py - גרסה מעודכנת
import numpy as np
import pandas as pd
import joblib
import os
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import logging
import json

logger = logging.getLogger(__name__)

class MLPredictor:
    """מנבא מחירים מבוסס Machine Learning - גרסה אמיתית"""
    
    def __init__(self):
        self.models = {}
        self.scalers = {}
        self.metadata = {}
        self.model_path = 'models/trained/'
        self._load_models()
        
    def _load_models(self):
        """טעינת מודלים מאומנים"""
        if not os.path.exists(self.model_path):
            logger.warning(f"Model directory not found: {self.model_path}")
            return
        
        # חיפוש מודלים
        for file in os.listdir(self.model_path):
            if file.endswith('_metadata.json'):
                # טעינת metadata
                symbol = file.split('_')[0]
                hours = int(file.split('_')[1].replace('h', ''))
                
                with open(os.path.join(self.model_path, file), 'r') as f:
                    metadata = json.load(f)
                
                # טעינת המודל הטוב ביותר
                best_model_name = metadata['best_model']
                model_file = f"{symbol}_{hours}h_{best_model_name}.pkl"
                scaler_file = f"{symbol}_{hours}h_scaler.pkl"
                
                model_path = os.path.join(self.model_path, model_file)
                scaler_path = os.path.join(self.model_path, scaler_file)
                
                if os.path.exists(model_path) and os.path.exists(scaler_path):
                    key = f"{symbol}_{hours}h"
                    self.models[key] = joblib.load(model_path)
                    self.scalers[key] = joblib.load(scaler_path)
                    self.metadata[key] = metadata
                    
                    logger.info(f"Loaded model: {key} ({best_model_name})")
        
        if not self.models:
            logger.warning("No trained models found!")
    
    def prepare_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """הכנת features מנתונים חדשים"""
        # יש להשתמש באותן features כמו באימון
        features = pd.DataFrame()
        
        # Features בסיסיים
        features['returns'] = df['price'].pct_change()
        features['log_returns'] = np.log(df['price'] / df['price'].shift(1))
        
        # Moving averages
        for window in [5, 10, 20, 50]:
            sma = df['price'].rolling(window).mean()
            features[f'price_to_sma_{window}'] = df['price'] / sma
        
        # RSI
        features['rsi'] = self.calculate_rsi(df['price'])
        
        # Bollinger Bands
        bb_upper, bb_middle, bb_lower = self.calculate_bollinger_bands(df['price'])
        features['bb_position'] = (df['price'] - bb_lower) / (bb_upper - bb_lower)
        
        # Volume features
        if 'volume' in df.columns:
            features['volume_sma'] = df['volume'].rolling(20).mean()
            features['volume_ratio'] = df['volume'] / features['volume_sma']
        else:
            features['volume_ratio'] = 1.0
        
        # Volatility
        features['volatility'] = features['returns'].rolling(20).std()
        
        # Time features
        features['hour'] = df.index.hour if hasattr(df.index, 'hour') else 0
        features['day_of_week'] = df.index.dayofweek if hasattr(df.index, 'dayofweek') else 0
        features['month'] = df.index.month if hasattr(df.index, 'month') else 1
        
        # Lag features
        for i in [1, 2, 3, 5, 10]:
            features[f'returns_lag_{i}'] = features['returns'].shift(i)
            features[f'volume_lag_{i}'] = features['volume_ratio'].shift(i)
        
        return features.dropna()
    
    def calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """חישוב RSI"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))
    
    def calculate_bollinger_bands(self, prices: pd.Series, window: int = 20, num_std: float = 2):
        """חישוב Bollinger Bands"""
        sma = prices.rolling(window).mean()
        std = prices.rolling(window).std()
        upper = sma + (std * num_std)
        lower = sma - (std * num_std)
        return upper, sma, lower
    
    def predict_price(self, symbol: str, hours_ahead: int = 24) -> Dict:
        """חיזוי מחיר עתידי - שימוש במודל אמיתי"""
        model_key = f"{symbol}_{hours_ahead}h"
        
        # בדיקה אם יש מודל מאומן
        if model_key not in self.models:
            logger.warning(f"No trained model for {model_key}")
            # אם אין מודל, נחזיר mock (כמו קודם)
            return self._mock_prediction(symbol, hours_ahead)
        
        # טעינת נתונים אחרונים
        df = self._load_recent_data(symbol)
        if df is None or len(df) < 100:
            logger.warning(f"Insufficient data for {symbol}")
            return self._mock_prediction(symbol, hours_ahead)
        
        # הכנת features
        features_df = self.prepare_features(df)
        
        # בחירת features לפי המודל
        model_features = self.metadata[model_key]['features']
        
        # וידוא שכל ה-features קיימים
        missing_features = set(model_features) - set(features_df.columns)
        if missing_features:
            logger.warning(f"Missing features: {missing_features}")
            return self._mock_prediction(symbol, hours_ahead)
        
        # Features אחרונים
        last_features = features_df[model_features].iloc[-1:].values
        
        # Scaling
        scaler = self.scalers[model_key]
        features_scaled = scaler.transform(last_features)
        
        # חיזוי
        model = self.models[model_key]
        prediction = model.predict(features_scaled)[0]
        
        # המרת חיזוי התשואה למחיר
        current_price = df['price'].iloc[-1]
        predicted_price = current_price * (1 + prediction)
        
        # חישוב confidence interval (פשוט לדוגמה)
        # במציאות כדאי להשתמש ב-quantile regression או bootstrap
        uncertainty = abs(prediction) * 0.5  # 50% מהחיזוי
        
        # יצירת time series לתצוגה
        historical_dates = pd.date_range(
            end=datetime.now(),
            periods=50,
            freq='H'
        )
        historical_prices = df['price'].tail(50).values
        
        prediction_dates = pd.date_range(
            start=datetime.now(),
            periods=hours_ahead,
            freq='H'
        )
        
        # יצירת נתיב חיזוי (אינטרפולציה פשוטה)
        predicted_prices = np.linspace(
            current_price,
            predicted_price,
            hours_ahead
        )
        
        # הוספת רעש קטן לריאליזם
        noise = np.random.normal(0, current_price * 0.001, hours_ahead)
        predicted_prices += noise
        
        # Confidence bounds
        upper_bound = predicted_prices * (1 + uncertainty)
        lower_bound = predicted_prices * (1 - uncertainty)
        
        # מטריקות המודל
        model_metadata = self.metadata[model_key]
        model_results = model_metadata['results'][model_metadata['best_model']]
        
        return {
            'symbol': symbol,
            'current_price': current_price,
            'target_price': predicted_price,
            'price_change': predicted_price - current_price,
            'price_change_pct': prediction * 100,
            'confidence': (1 - uncertainty) * 100,  # המרה לאחוזים
            'model_accuracy': model_results['test_direction_accuracy'] * 100,
            'model_r2': model_results['test_r2'],
            'historical_dates': historical_dates.tolist(),
            'historical_prices': historical_prices.tolist(),
            'prediction_dates': prediction_dates.tolist(),
            'predicted_prices': predicted_prices.tolist(),
            'upper_bound': upper_bound.tolist(),
            'lower_bound': lower_bound.tolist(),
            'features_used': model_features[:10],  # Top 10 features
            'model_type': model_metadata['best_model'],
            'training_date': model_metadata['train_date'],
            'is_real_prediction': True  # להבדיל מ-mock
        }
    
    def _load_recent_data(self, symbol: str) -> Optional[pd.DataFrame]:
        """טעינת נתונים אחרונים לחיזוי"""
        try:
            # נסה לטעון מ-market_live או market_history
            live_file = 'data/market_live.csv'
            history_file = 'data/market_history.csv'
            
            df_list = []
            
            for file in [live_file, history_file]:
                if os.path.exists(file):
                    df = pd.read_csv(file)
                    df = df[df['pair'] == f'{symbol}USD']
                    if not df.empty:
                        df_list.append(df)
            
            if df_list:
                df = pd.concat(df_list, ignore_index=True)
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df = df.sort_values('timestamp').drop_duplicates(subset=['timestamp'])
                df = df.set_index('timestamp')
                
                # צריך לפחות 100 נקודות
                if len(df) >= 100:
                    return df.tail(200)  # קח את ה-200 האחרונות
            
            return None
            
        except Exception as e:
            logger.error(f"Error loading data for {symbol}: {e}")
            return None
    
    def _mock_prediction(self, symbol: str, hours_ahead: int) -> Dict:
        """חיזוי מדומה כ-fallback"""
        # הקוד הקיים שלך...
        current_price = 48000 if symbol == 'BTC' else 2500
        
        # Generate prediction
        trend = np.random.choice([-1, 1])
        volatility = np.random.uniform(0.01, 0.05)
        
        price_change = trend * volatility * current_price
        target_price = current_price + price_change
        
        # Generate time series
        num_points = 50
        historical_dates = pd.date_range(end='now', periods=num_points, freq='H')
        historical_prices = current_price + np.cumsum(
            np.random.normal(0, current_price * 0.001, num_points)
        )
        
        prediction_dates = pd.date_range(
            start='now', 
            periods=hours_ahead, 
            freq='H'
        )
        
        # Generate prediction path
        predicted_prices = np.linspace(
            current_price, 
            target_price, 
            hours_ahead
        ) + np.random.normal(0, current_price * 0.0005, hours_ahead)
        
        # Confidence bounds
        confidence = np.random.uniform(70, 90)
        uncertainty = (1 - confidence/100) * abs(price_change)
        
        return {
            'symbol': symbol,
            'current_price': current_price,
            'target_price': target_price,
            'price_change': price_change,
            'price_change_pct': (price_change / current_price) * 100,
            'confidence': confidence,
            'model_accuracy': np.random.uniform(75, 95),
            'historical_dates': historical_dates.tolist(),
            'historical_prices': historical_prices.tolist(),
            'prediction_dates': prediction_dates.tolist(),
            'predicted_prices': predicted_prices.tolist(),
            'upper_bound': (predicted_prices + uncertainty).tolist(),
            'lower_bound': (predicted_prices - uncertainty).tolist(),
            'features_used': [
                'Price momentum',
                'Technical indicators',
                'Volume patterns',
                'Market sentiment',
                'Time patterns'
            ],
            'is_real_prediction': False  # זה mock
        }
    
    def get_model_info(self) -> Dict:
        """מידע על המודלים הזמינים"""
        info = {
            'available_models': list(self.models.keys()),
            'model_details': {}
        }
        
        for key, metadata in self.metadata.items():
            info['model_details'][key] = {
                'symbol': metadata['symbol'],
                'target_hours': metadata['target_hours'],
                'best_model': metadata['best_model'],
                'accuracy': metadata['results'][metadata['best_model']]['test_direction_accuracy'],
                'r2_score': metadata['results'][metadata['best_model']]['test_r2'],
                'training_date': metadata['train_date'],
                'data_points': metadata['data_points']
            }
        
        return info