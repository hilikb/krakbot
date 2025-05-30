# scripts/train_ml_model.py
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split, TimeSeriesSplit
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
import xgboost as xgb
import joblib
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config

class ModelTrainer:
    def __init__(self, symbol='BTC'):
        self.symbol = symbol
        self.models = {}
        self.scalers = {}
        self.feature_importance = {}
        self.model_dir = os.path.join(Config.MODELS_DIR, 'trained')
        os.makedirs(self.model_dir, exist_ok=True)
    
    def load_data(self):
        """טעינת נתונים מוכנים"""
        data_file = os.path.join(Config.DATA_DIR, f'{self.symbol}_ml_ready.csv')
        
        if not os.path.exists(data_file):
            raise FileNotFoundError(f"Data file not found: {data_file}")
        
        df = pd.read_csv(data_file)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        return df
    
    def prepare_features_target(self, df, target_hours=24):
        """הכנת features ו-target"""
        
        # בחירת features
        feature_columns = [
            'returns', 'log_returns',
            'rsi', 'bb_position',
            'volatility', 'volume_ratio',
            'hour', 'day_of_week', 'month'
        ]
        
        # הוספת moving averages
        for window in [5, 10, 20, 50]:
            feature_columns.append(f'price_to_sma_{window}')
        
        # הוספת lag features
        for i in [1, 2, 3, 5, 10]:
            feature_columns.append(f'returns_lag_{i}')
            feature_columns.append(f'volume_lag_{i}')
        
        # Target
        target_column = f'target_return_{target_hours}h'
        
        # סינון רק שורות עם כל הנתונים
        valid_mask = df[feature_columns + [target_column]].notna().all(axis=1)
        
        X = df.loc[valid_mask, feature_columns]
        y = df.loc[valid_mask, target_column]
        timestamps = df.loc[valid_mask, 'timestamp']
        
        return X, y, timestamps, feature_columns
    
    def train_models(self, target_hours=24):
        """אימון מודלים שונים"""
        print(f"\n🚀 Training models for {self.symbol} - {target_hours}h prediction")
        
        # טעינת נתונים
        df = self.load_data()
        X, y, timestamps, feature_names = self.prepare_features_target(df, target_hours)
        
        print(f"📊 Data shape: {X.shape}")
        print(f"📅 Date range: {timestamps.min()} to {timestamps.max()}")
        
        # חלוקה לtrain/test (זמנית)
        split_date = timestamps.quantile(0.8)
        train_mask = timestamps < split_date
        
        X_train = X[train_mask]
        X_test = X[~train_mask]
        y_train = y[train_mask]
        y_test = y[~train_mask]
        
        print(f"🔄 Train size: {len(X_train)}, Test size: {len(X_test)}")
        
        # Scaling
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)
        
        # שמירת scaler
        scaler_path = os.path.join(self.model_dir, f'{self.symbol}_{target_hours}h_scaler.pkl')
        joblib.dump(scaler, scaler_path)
        
        # אימון מודלים
        models = {
            'RandomForest': RandomForestRegressor(
                n_estimators=100,
                max_depth=10,
                min_samples_split=20,
                random_state=42,
                n_jobs=-1
            ),
            'GradientBoosting': GradientBoostingRegressor(
                n_estimators=100,
                max_depth=5,
                learning_rate=0.1,
                random_state=42
            ),
            'XGBoost': xgb.XGBRegressor(
                n_estimators=100,
                max_depth=6,
                learning_rate=0.1,
                random_state=42
            )
        }
        
        results = {}
        
        for name, model in models.items():
            print(f"\n🔧 Training {name}...")
            
            # אימון
            model.fit(X_train_scaled, y_train)
            
            # חיזוי
            y_pred_train = model.predict(X_train_scaled)
            y_pred_test = model.predict(X_test_scaled)
            
            # מטריקות
            train_mse = mean_squared_error(y_train, y_pred_train)
            test_mse = mean_squared_error(y_test, y_pred_test)
            train_mae = mean_absolute_error(y_train, y_pred_train)
            test_mae = mean_absolute_error(y_test, y_pred_test)
            train_r2 = r2_score(y_train, y_pred_train)
            test_r2 = r2_score(y_test, y_pred_test)
            
            # אחוז דיוק כיוון
            train_direction_acc = ((y_train > 0) == (y_pred_train > 0)).mean()
            test_direction_acc = ((y_test > 0) == (y_pred_test > 0)).mean()
            
            results[name] = {
                'train_mse': train_mse,
                'test_mse': test_mse,
                'train_mae': train_mae,
                'test_mae': test_mae,
                'train_r2': train_r2,
                'test_r2': test_r2,
                'train_direction_accuracy': train_direction_acc,
                'test_direction_accuracy': test_direction_acc
            }
            
            print(f"📊 Results for {name}:")
            print(f"   Test R²: {test_r2:.4f}")
            print(f"   Test MAE: {test_mae:.4f}")
            print(f"   Direction Accuracy: {test_direction_acc:.2%}")
            
            # שמירת feature importance
            if hasattr(model, 'feature_importances_'):
                self.feature_importance[name] = pd.DataFrame({
                    'feature': feature_names,
                    'importance': model.feature_importances_
                }).sort_values('importance', ascending=False)
            
            # שמירת המודל
            model_path = os.path.join(
                self.model_dir, 
                f'{self.symbol}_{target_hours}h_{name}.pkl'
            )
            joblib.dump(model, model_path)
            print(f"💾 Saved model to {model_path}")
        
        # בחירת המודל הטוב ביותר
        best_model_name = max(results, key=lambda x: results[x]['test_direction_accuracy'])
        print(f"\n🏆 Best model: {best_model_name}")
        
        # שמירת metadata
        metadata = {
            'symbol': self.symbol,
            'target_hours': target_hours,
            'train_date': datetime.now().isoformat(),
            'features': feature_names,
            'results': results,
            'best_model': best_model_name,
            'data_points': len(X),
            'train_size': len(X_train),
            'test_size': len(X_test)
        }
        
        import json
        metadata_path = os.path.join(
            self.model_dir,
            f'{self.symbol}_{target_hours}h_metadata.json'
        )
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        return results
    
    def plot_feature_importance(self):
        """ציור חשיבות features"""
        import matplotlib.pyplot as plt
        
        for model_name, importance_df in self.feature_importance.items():
            plt.figure(figsize=(10, 6))
            top_features = importance_df.head(15)
            
            plt.barh(top_features['feature'], top_features['importance'])
            plt.xlabel('Importance')
            plt.title(f'Feature Importance - {model_name} ({self.symbol})')
            plt.tight_layout()
            
            plot_path = os.path.join(
                self.model_dir,
                f'{self.symbol}_feature_importance_{model_name}.png'
            )
            plt.savefig(plot_path)
            print(f"📊 Saved feature importance plot to {plot_path}")
            plt.close()

if __name__ == "__main__":
    # אימון מודלים
    for symbol in ['BTC', 'ETH', 'SOL']:
        print(f"\n{'='*60}")
        print(f"Training models for {symbol}")
        print('='*60)
        
        trainer = ModelTrainer(symbol)
        
        try:
            # אימון למספר טווחי זמן
            for hours in [1, 4, 24]:
                trainer.train_models(target_hours=hours)
            
            # ציור feature importance
            trainer.plot_feature_importance()
            
        except Exception as e:
            print(f"❌ Error training {symbol}: {e}")