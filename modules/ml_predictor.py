import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
import joblib
import os
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import logging

logger = logging.getLogger(__name__)

class MLPredictor:
    """מנבא מחירים מבוסס Machine Learning"""
    
    def __init__(self):
        self.models = {}
        self.scalers = {}
        self.feature_importance = {}
        self.model_path = 'models/'
        os.makedirs(self.model_path, exist_ok=True)
        
    def prepare_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """הכנת פיצ'רים למודל"""
        features = pd.DataFrame()
        
        # Price features
        features['returns'] = df['price'].pct_change()
        features['log_returns'] = np.log(df['price'] / df['price'].shift(1))
        
        # Moving averages
        for window in [5, 10, 20, 50]:
            features[f'sma_{window}'] = df['price'].rolling(window).mean()
            features[f'ema_{window}'] = df['price'].ewm(span=window).mean()
            
        # Technical indicators
        features['rsi'] = self.calculate_rsi(df['price'])
        features['macd'], features['macd_signal'] = self.calculate_macd(df['price'])
        
        # Volatility
        features['volatility'] = features['returns'].rolling(20).std()
        features['atr'] = self.calculate_atr(df)
        
        # Volume features
        if 'volume' in df.columns:
            features['volume_sma'] = df['volume'].rolling(20).mean()
            features['volume_ratio'] = df['volume'] / features['volume_sma']
        
        # Time features
        features['hour'] = df.index.hour
        features['day_of_week'] = df.index.dayofweek
        features['month'] = df.index.month
        
        # Lag features
        for lag in [1, 2, 3, 5, 10]:
            features[f'returns_lag_{lag}'] = features['returns'].shift(lag)
            
        return features.dropna()
    
    def calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """חישוב RSI"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))
    
    def calculate_macd(self, prices: pd.Series) -> Tuple[pd.Series, pd.Series]:
        """חישוב MACD"""
        ema_12 = prices.ewm(span=12).mean()
        ema_26 = prices.ewm(span=26).mean()
        macd = ema_12 - ema_26
        signal = macd.ewm(span=9).mean()
        return macd, signal
    
    def calculate_atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """חישוב Average True Range"""
        high_low = df['high_24h'] - df['low_24h']
        high_close = abs(df['high_24h'] - df['price'].shift())
        low_close = abs(df['low_24h'] - df['price'].shift())
        
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        return true_range.rolling(period).mean()
    
    def train_model(self, symbol: str, df: pd.DataFrame, 
                   target_hours: int = 24) -> Dict:
        """אימון מודל חיזוי"""
        logger.info(f"Training ML model for {symbol}")
        
        # Prepare features
        features_df = self.prepare_features(df)
        
        # Create target (future price)
        target = df['price'].shift(-target_hours)
        
        # Align data
        valid_idx = features_df.index.intersection(target.dropna().index)
        X = features_df.loc[valid_idx]
        y = target.loc[valid_idx]
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, shuffle=False
        )
        
        # Scale features
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)
        
        # Train multiple models
        models = {
            'rf': RandomForestRegressor(n_estimators=100, max_depth=10, random_state=42),
            'gb': GradientBoostingRegressor(n_estimators=100, max_depth=5, random_state=42),
            'nn': MLPRegressor(hidden_layer_sizes=(100, 50), max_iter=1000, random_state=42)
        }
        
        results = {}
        best_score = -np.inf
        best_model = None
        
        for name, model in models.items():
            model.fit(X_train_scaled, y_train)
            score = model.score(X_test_scaled, y_test)
            results[name] = {
                'score': score,
                'predictions': model.predict(X_test_scaled)
            }
            
            if score > best_score:
                best_score = score
                best_model = model
        
        # Save best model
        self.models[symbol] = best_model
        self.scalers[symbol] = scaler
        
        # Feature importance for tree-based models
        if hasattr(best_model, 'feature_importances_'):
            self.feature_importance[symbol] = pd.DataFrame({
                'feature': X.columns,
                'importance': best_model.feature_importances_
            }).sort_values('importance', ascending=False)
        
        # Save model
        joblib.dump(best_model, f"{self.model_path}{symbol}_model.pkl")
        joblib.dump(scaler, f"{self.model_path}{symbol}_scaler.pkl")
        
        return {
            'symbol': symbol,
            'best_model': type(best_model).__name__,
            'accuracy': best_score,
            'results': results
        }
    
    def predict_price(self, symbol: str, hours_ahead: int = 24) -> Dict:
        """חיזוי מחיר עתידי"""
        # Load or train model
        if symbol not in self.models:
            # Load historical data and train
            # For now, return mock prediction
            return self._mock_prediction(symbol, hours_ahead)
        
        # Real prediction would go here
        model = self.models[symbol]
        scaler = self.scalers[symbol]
        
        # Get latest features
        # features = self.prepare_features(latest_data)
        # scaled_features = scaler.transform(features)
        # prediction = model.predict(scaled_features)
        
        return self._mock_prediction(symbol, hours_ahead)
    
    def _mock_prediction(self, symbol: str, hours_ahead: int) -> Dict:
        """חיזוי מדומה לדוגמה"""
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
            ]
        }
    
    def batch_predict(self, symbols: List[str], hours_ahead: int = 24) -> Dict:
        """חיזוי עבור מספר סימבולים"""
        predictions = {}
        
        for symbol in symbols:
            predictions[symbol] = self.predict_price(symbol, hours_ahead)
        
        return predictions
    
    def evaluate_predictions(self, symbol: str) -> Dict:
        """הערכת דיוק חיזויים קודמים"""
        # In real implementation, would load past predictions and compare
        return {
            'symbol': symbol,
            'predictions_made': np.random.randint(50, 200),
            'average_accuracy': np.random.uniform(70, 85),
            'best_timeframe': '4 hours',
            'directional_accuracy': np.random.uniform(55, 75)
        }