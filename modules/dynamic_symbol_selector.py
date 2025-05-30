import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)

class DynamicSymbolSelector:
    """בוחר סמלים דינמי על פי נתוני שוק"""
    
    def __init__(self):
        self.market_data_cache = {}
        self.performance_history = defaultdict(list)
        self.last_selection_time = None
        self.current_websocket_symbols = []
        
    def select_symbols(self, 
                      available_symbols: List[str], 
                      websocket_limit: int = 80,
                      algorithm: str = 'volume_volatility') -> Tuple[List[str], List[str]]:
        """
        בחירת סמלים דינמית לפי אלגוריתם
        Returns: (websocket_symbols, http_symbols)
        """
        
        # שליפת נתוני שוק עדכניים
        market_data = self._fetch_market_data(available_symbols)
        
        if algorithm == 'volume':
            scores = self._score_by_volume(market_data)
        elif algorithm == 'volatility':
            scores = self._score_by_volatility(market_data)
        elif algorithm == 'volume_volatility':
            scores = self._score_by_volume_and_volatility(market_data)
        elif algorithm == 'ai_based':
            scores = self._score_by_ai_prediction(market_data)
        else:
            scores = self._score_by_volume(market_data)
        
        # מיון לפי ציון
        sorted_symbols = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        
        # בחירת סמלים ל-WebSocket (הכי חשובים)
        websocket_symbols = [symbol for symbol, _ in sorted_symbols[:websocket_limit]]
        
        # השאר ל-HTTP
        http_symbols = [symbol for symbol, _ in sorted_symbols[websocket_limit:]]
        
        # עדכון היסטוריה
        self._update_selection_history(websocket_symbols)
        
        logger.info(f"🎯 Dynamic selection complete:")
        logger.info(f"   Top 5 WebSocket: {websocket_symbols[:5]}")
        logger.info(f"   Algorithm: {algorithm}")
        
        return websocket_symbols, http_symbols
    
    def _fetch_market_data(self, symbols: List[str]) -> pd.DataFrame:
        """שליפת נתוני שוק עדכניים"""
        try:
            # נסה לטעון מקובץ CSV עדכני
            df = pd.read_csv('data/market_live.csv')
            df = df[df['pair'].str.replace('USD', '').isin(symbols)]
            
            # חישוב מטריקות נוספות
            df['volume_usd'] = df['volume'] * df['price']
            df['volatility'] = df['change_pct_24h'].abs()
            df['spread_pct'] = (df['spread'] / df['price']) * 100
            
            return df
            
        except Exception as e:
            logger.error(f"Error fetching market data: {e}")
            return pd.DataFrame()
    
    def _score_by_volume(self, market_data: pd.DataFrame) -> Dict[str, float]:
        """ניקוד לפי נפח מסחר"""
        scores = {}
        
        if market_data.empty:
            return scores
        
        # נרמול נפח מסחר
        max_volume = market_data['volume_usd'].max()
        
        for _, row in market_data.iterrows():
            symbol = row['pair'].replace('USD', '')
            # ניקוד לפי נפח (0-100)
            volume_score = (row['volume_usd'] / max_volume) * 100
            scores[symbol] = volume_score
        
        return scores
    
    def _score_by_volatility(self, market_data: pd.DataFrame) -> Dict[str, float]:
        """ניקוד לפי תנודתיות"""
        scores = {}
        
        if market_data.empty:
            return scores
        
        for _, row in market_data.iterrows():
            symbol = row['pair'].replace('USD', '')
            # ניקוד לפי תנודתיות - יותר תנודתי = יותר הזדמנויות
            volatility_score = min(row['volatility'] * 10, 100)  # Cap at 100
            scores[symbol] = volatility_score
        
        return scores
    
    def _score_by_volume_and_volatility(self, market_data: pd.DataFrame) -> Dict[str, float]:
        """ניקוד משולב - נפח ותנודתיות"""
        scores = {}
        
        if market_data.empty:
            return scores
        
        # נרמול
        max_volume = market_data['volume_usd'].max()
        
        for _, row in market_data.iterrows():
            symbol = row['pair'].replace('USD', '')
            
            # 60% נפח, 40% תנודתיות
            volume_score = (row['volume_usd'] / max_volume) * 60
            volatility_score = min(row['volatility'] * 4, 40)  # Max 40 points
            
            # בונוס לspread נמוך (עד 10 נקודות)
            spread_bonus = max(0, 10 - row['spread_pct'] * 10)
            
            total_score = volume_score + volatility_score + spread_bonus
            scores[symbol] = total_score
        
        return scores
    
    def _score_by_ai_prediction(self, market_data: pd.DataFrame) -> Dict[str, float]:
        """ניקוד מבוסס AI - עתידי"""
        # כאן אפשר להוסיף מודל ML שמנבא אילו מטבעות יהיו הכי רווחיים
        # לעת עתה, נשתמש באלגוריתם המשולב
        return self._score_by_volume_and_volatility(market_data)
    
    def _update_selection_history(self, selected_symbols: List[str]):
        """עדכון היסטוריית בחירה"""
        self.last_selection_time = datetime.now()
        self.current_websocket_symbols = selected_symbols
        
        # שמירת היסטוריה לניתוח עתידי
        for symbol in selected_symbols:
            self.performance_history[symbol].append({
                'timestamp': self.last_selection_time,
                'selected': True
            })
    
    def should_rotate_symbols(self, rotation_interval: int) -> bool:
        """בדיקה אם צריך לעשות רוטציה"""
        if not self.last_selection_time:
            return True
        
        time_since_last = (datetime.now() - self.last_selection_time).seconds
        return time_since_last >= rotation_interval