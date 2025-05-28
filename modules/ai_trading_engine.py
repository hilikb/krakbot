import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
import logging
from datetime import datetime, timedelta
import json
import os
import sys
from dataclasses import dataclass
from enum import Enum

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config

logger = Config.setup_logging('ai_trading_engine')

class TradingMode(Enum):
    """מצבי מסחר של ה-AI"""
    CONSERVATIVE = "conservative"
    BALANCED = "balanced"
    AGGRESSIVE = "aggressive"
    CUSTOM = "custom"

@dataclass
class TradingSignal:
    """אות מסחר מה-AI"""
    timestamp: datetime
    symbol: str
    action: str  # buy/sell/hold
    confidence: float  # 0-1
    suggested_amount: float
    entry_price: float
    stop_loss: float
    take_profit: float
    strategy: str
    reasoning: str

class AITradingEngine:
    """מנוע מסחר מבוסס AI"""
    
    def __init__(self):
        self.mode = TradingMode.BALANCED
        self.risk_level = 5  # 1-10
        self.active_strategies = []
        self.performance_history = []
        self.current_positions = {}
        self.market_state = {}
        
        # AI parameters
        self.confidence_threshold = 0.7
        self.max_positions = 5
        self.position_sizing_model = "kelly_criterion"
        
        # Strategy weights
        self.strategy_weights = {
            "trend_following": 0.25,
            "mean_reversion": 0.20,
            "momentum": 0.20,
            "pattern_recognition": 0.15,
            "sentiment_analysis": 0.10,
            "arbitrage": 0.10
        }
        
        # Load pre-trained models if available
        self.models = self._load_models()
        
    def _load_models(self) -> Dict:
        """טעינת מודלים של ML"""
        models = {}
        
        # כאן צריך לטעון מודלים אמיתיים
        # לדוגמה: joblib.load('models/trend_predictor.pkl')
        
        return models
    
    def analyze_market(self, symbol: str, timeframe: str = '1h') -> Dict:
        """ניתוח שוק מקיף עבור סמל"""
        logger.info(f"Analyzing market for {symbol}")
        
        analysis = {
            'symbol': symbol,
            'timestamp': datetime.now(),
            'timeframe': timeframe,
            'indicators': {},
            'patterns': [],
            'sentiment': {},
            'signals': []
        }
        
        # Technical indicators
        analysis['indicators'] = self._calculate_indicators(symbol, timeframe)
        
        # Pattern recognition
        analysis['patterns'] = self._detect_patterns(symbol, timeframe)
        
        # Sentiment analysis
        analysis['sentiment'] = self._analyze_sentiment(symbol)
        
        # Generate trading signals
        analysis['signals'] = self._generate_signals(analysis)
        
        return analysis
    
    def _calculate_indicators(self, symbol: str, timeframe: str) -> Dict:
        """חישוב אינדיקטורים טכניים"""
        # בפועל, כאן צריך לחשב אינדיקטורים אמיתיים
        # כרגע מחזיר נתונים לדוגמה
        
        return {
            'rsi': np.random.uniform(30, 70),
            'macd': {
                'macd': np.random.uniform(-1, 1),
                'signal': np.random.uniform(-1, 1),
                'histogram': np.random.uniform(-0.5, 0.5)
            },
            'bollinger_bands': {
                'upper': 50000,
                'middle': 48000,
                'lower': 46000,
                'position': 0.6  # 0-1 where price is relative to bands
            },
            'ema': {
                'ema_9': 48500,
                'ema_21': 48200,
                'ema_50': 47800,
                'ema_200': 46000
            },
            'volume': {
                'current': 1000000,
                'average': 800000,
                'trend': 'increasing'
            },
            'atr': 500,  # Average True Range
            'adx': 35,   # Average Directional Index
            'stochastic': {
                'k': 65,
                'd': 60
            }
        }
    
    def _detect_patterns(self, symbol: str, timeframe: str) -> List[Dict]:
        """זיהוי פטרנים טכניים"""
        patterns = []
        
        # דוגמאות לפטרנים
        possible_patterns = [
            {'name': 'Head and Shoulders', 'reliability': 0.75, 'direction': 'bearish'},
            {'name': 'Double Bottom', 'reliability': 0.80, 'direction': 'bullish'},
            {'name': 'Ascending Triangle', 'reliability': 0.70, 'direction': 'bullish'},
            {'name': 'Flag Pattern', 'reliability': 0.65, 'direction': 'continuation'},
            {'name': 'Cup and Handle', 'reliability': 0.72, 'direction': 'bullish'}
        ]
        
        # סימולציה של זיהוי פטרן
        if np.random.random() > 0.5:
            pattern = np.random.choice(possible_patterns)
            pattern['detected_at'] = datetime.now()
            pattern['confidence'] = np.random.uniform(0.6, 0.9)
            patterns.append(pattern)
        
        return patterns
    
    def _analyze_sentiment(self, symbol: str) -> Dict:
        """ניתוח סנטימנט משולב"""
        return {
            'news_sentiment': np.random.uniform(-1, 1),  # -1 to 1
            'social_sentiment': np.random.uniform(-1, 1),
            'fear_greed_index': np.random.randint(0, 100),
            'whale_activity': np.random.choice(['accumulating', 'distributing', 'neutral']),
            'retail_sentiment': np.random.uniform(-1, 1),
            'overall_sentiment': np.random.uniform(-1, 1)
        }
    
    def _generate_signals(self, analysis: Dict) -> List[TradingSignal]:
        """יצירת אותות מסחר מבוססי AI"""
        signals = []
        
        # Trend following signal
        if self._check_trend_signal(analysis):
            signals.append(self._create_trend_signal(analysis))
        
        # Mean reversion signal
        if self._check_mean_reversion_signal(analysis):
            signals.append(self._create_mean_reversion_signal(analysis))
        
        # Pattern-based signal
        if analysis['patterns']:
            signals.append(self._create_pattern_signal(analysis))
        
        # Sentiment-based signal
        if abs(analysis['sentiment']['overall_sentiment']) > 0.5:
            signals.append(self._create_sentiment_signal(analysis))
        
        # Filter signals by confidence
        signals = [s for s in signals if s and s.confidence >= self.confidence_threshold]
        
        # Combine signals using ensemble method
        if signals:
            return [self._ensemble_signals(signals)]
        
        return []
    
    def _check_trend_signal(self, analysis: Dict) -> bool:
        """בדיקת תנאים לאות מגמה"""
        indicators = analysis['indicators']
        
        # Check if EMAs are aligned
        ema_aligned = (indicators['ema']['ema_9'] > indicators['ema']['ema_21'] > 
                      indicators['ema']['ema_50'] > indicators['ema']['ema_200'])
        
        # Check if ADX shows strong trend
        strong_trend = indicators['adx'] > 25
        
        return ema_aligned and strong_trend
    
    def _check_mean_reversion_signal(self, analysis: Dict) -> bool:
        """בדיקת תנאים לאות חזרה לממוצע"""
        indicators = analysis['indicators']
        
        # Check if RSI is oversold/overbought
        rsi_extreme = indicators['rsi'] < 30 or indicators['rsi'] > 70
        
        # Check if price is outside Bollinger Bands
        bb_extreme = indicators['bollinger_bands']['position'] < 0.1 or \
                    indicators['bollinger_bands']['position'] > 0.9
        
        return rsi_extreme and bb_extreme
    
    def _create_trend_signal(self, analysis: Dict) -> TradingSignal:
        """יצירת אות מסחר מבוסס מגמה"""
        current_price = 48000  # בפועל לקחת מנתונים אמיתיים
        
        return TradingSignal(
            timestamp=datetime.now(),
            symbol=analysis['symbol'],
            action='buy' if analysis['indicators']['ema']['ema_9'] > analysis['indicators']['ema']['ema_21'] else 'sell',
            confidence=0.75,
            suggested_amount=self._calculate_position_size(analysis),
            entry_price=current_price,
            stop_loss=current_price * 0.98,
            take_profit=current_price * 1.03,
            strategy='trend_following',
            reasoning='Strong trend detected with aligned EMAs and high ADX'
        )
    
    def _create_mean_reversion_signal(self, analysis: Dict) -> TradingSignal:
        """יצירת אות חזרה לממוצע"""
        current_price = 48000
        rsi = analysis['indicators']['rsi']
        
        if rsi < 30:  # Oversold
            action = 'buy'
            stop_loss = current_price * 0.97
            take_profit = current_price * 1.02
        else:  # Overbought
            action = 'sell'
            stop_loss = current_price * 1.03
            take_profit = current_price * 0.98
        
        return TradingSignal(
            timestamp=datetime.now(),
            symbol=analysis['symbol'],
            action=action,
            confidence=0.70,
            suggested_amount=self._calculate_position_size(analysis),
            entry_price=current_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            strategy='mean_reversion',
            reasoning=f'RSI at extreme level ({rsi:.1f}), expecting reversal'
        )
    
    def _create_pattern_signal(self, analysis: Dict) -> TradingSignal:
        """יצירת אות מבוסס פטרן"""
        pattern = analysis['patterns'][0]
        current_price = 48000
        
        if pattern['direction'] == 'bullish':
            action = 'buy'
            stop_loss = current_price * 0.97
            take_profit = current_price * 1.05
        else:
            action = 'sell'
            stop_loss = current_price * 1.03
            take_profit = current_price * 0.95
        
        return TradingSignal(
            timestamp=datetime.now(),
            symbol=analysis['symbol'],
            action=action,
            confidence=pattern['confidence'],
            suggested_amount=self._calculate_position_size(analysis),
            entry_price=current_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            strategy='pattern_recognition',
            reasoning=f"{pattern['name']} pattern detected with {pattern['confidence']:.0%} confidence"
        )
    
    def _create_sentiment_signal(self, analysis: Dict) -> TradingSignal:
        """יצירת אות מבוסס סנטימנט"""
        sentiment = analysis['sentiment']['overall_sentiment']
        current_price = 48000
        
        return TradingSignal(
            timestamp=datetime.now(),
            symbol=analysis['symbol'],
            action='buy' if sentiment > 0 else 'sell',
            confidence=abs(sentiment),
            suggested_amount=self._calculate_position_size(analysis),
            entry_price=current_price,
            stop_loss=current_price * (0.97 if sentiment > 0 else 1.03),
            take_profit=current_price * (1.03 if sentiment > 0 else 0.97),
            strategy='sentiment_analysis',
            reasoning=f"Strong {'positive' if sentiment > 0 else 'negative'} sentiment detected"
        )
    
    def _ensemble_signals(self, signals: List[TradingSignal]) -> TradingSignal:
        """שילוב מספר אותות לאות אחד חזק"""
        # Calculate weighted average based on strategy weights and confidence
        total_weight = 0
        weighted_confidence = 0
        
        buy_signals = [s for s in signals if s.action == 'buy']
        sell_signals = [s for s in signals if s.action == 'sell']
        
        # Determine action based on majority
        if len(buy_signals) > len(sell_signals):
            action = 'buy'
            relevant_signals = buy_signals
        elif len(sell_signals) > len(buy_signals):
            action = 'sell'
            relevant_signals = sell_signals
        else:
            action = 'hold'
            relevant_signals = signals
        
        # Calculate ensemble confidence
        for signal in relevant_signals:
            weight = self.strategy_weights.get(signal.strategy, 0.1) * signal.confidence
            weighted_confidence += weight
            total_weight += self.strategy_weights.get(signal.strategy, 0.1)
        
        ensemble_confidence = weighted_confidence / total_weight if total_weight > 0 else 0
        
        # Average entry, stop loss, and take profit
        avg_entry = np.mean([s.entry_price for s in relevant_signals])
        avg_stop_loss = np.mean([s.stop_loss for s in relevant_signals])
        avg_take_profit = np.mean([s.take_profit for s in relevant_signals])
        
        return TradingSignal(
            timestamp=datetime.now(),
            symbol=signals[0].symbol,
            action=action,
            confidence=ensemble_confidence,
            suggested_amount=np.mean([s.suggested_amount for s in relevant_signals]),
            entry_price=avg_entry,
            stop_loss=avg_stop_loss,
            take_profit=avg_take_profit,
            strategy='ensemble',
            reasoning=f"Ensemble of {len(signals)} signals: " + 
                     ", ".join([f"{s.strategy}({s.confidence:.0%})" for s in signals])
        )
    
    def _calculate_position_size(self, analysis: Dict) -> float:
        """חישוב גודל פוזיציה אופטימלי"""
        # Kelly Criterion או Fixed Fractional
        base_amount = 1000  # Base position size
        
        # Adjust based on confidence and risk
        risk_multiplier = 1 + (self.risk_level - 5) * 0.1
        
        # Volatility adjustment
        atr = analysis['indicators']['atr']
        volatility_factor = 1 / (1 + atr / 1000)  # Lower position size in high volatility
        
        position_size = base_amount * risk_multiplier * volatility_factor
        
        # Apply mode-specific adjustments
        if self.mode == TradingMode.CONSERVATIVE:
            position_size *= 0.5
        elif self.mode == TradingMode.AGGRESSIVE:
            position_size *= 1.5
        
        return round(position_size, 2)
    
    def execute_signal(self, signal: TradingSignal) -> Dict:
        """ביצוע אות מסחר"""
        logger.info(f"Executing signal: {signal.action} {signal.symbol} @ {signal.entry_price}")
        
        # בפועל, כאן צריך להתחבר למערכת המסחר
        # כרגע מחזיר סימולציה
        
        execution_result = {
            'signal_id': f"{signal.symbol}_{signal.timestamp.timestamp()}",
            'status': 'executed',
            'executed_price': signal.entry_price * np.random.uniform(0.999, 1.001),
            'executed_amount': signal.suggested_amount,
            'timestamp': datetime.now(),
            'order_id': f"ORDER_{np.random.randint(100000, 999999)}"
        }
        
        # Update position tracking
        self.current_positions[signal.symbol] = {
            'entry_price': execution_result['executed_price'],
            'amount': execution_result['executed_amount'],
            'stop_loss': signal.stop_loss,
            'take_profit': signal.take_profit,
            'strategy': signal.strategy,
            'entry_time': execution_result['timestamp']
        }
        
        return execution_result
    
    def manage_positions(self) -> List[Dict]:
        """ניהול פוזיציות פתוחות"""
        actions = []
        
        for symbol, position in self.current_positions.items():
            current_price = self._get_current_price(symbol)
            
            # Check stop loss
            if current_price <= position['stop_loss']:
                actions.append({
                    'symbol': symbol,
                    'action': 'close',
                    'reason': 'stop_loss_hit',
                    'price': current_price,
                    'pnl': self._calculate_pnl(position, current_price)
                })
            
            # Check take profit
            elif current_price >= position['take_profit']:
                actions.append({
                    'symbol': symbol,
                    'action': 'close',
                    'reason': 'take_profit_hit',
                    'price': current_price,
                    'pnl': self._calculate_pnl(position, current_price)
                })
            
            # Check for trailing stop
            elif self._should_apply_trailing_stop(position, current_price):
                new_stop = self._calculate_trailing_stop(position, current_price)
                position['stop_loss'] = new_stop
                actions.append({
                    'symbol': symbol,
                    'action': 'update_stop',
                    'new_stop': new_stop,
                    'reason': 'trailing_stop'
                })
            
            # Check for position adjustment based on new analysis
            analysis = self.analyze_market(symbol)
            if self._should_adjust_position(position, analysis):
                adjustment = self._calculate_position_adjustment(position, analysis)
                actions.append({
                    'symbol': symbol,
                    'action': 'adjust',
                    'adjustment': adjustment,
                    'reason': 'market_conditions_changed'
                })
        
        return actions
    
    def _get_current_price(self, symbol: str) -> float:
        """קבלת מחיר נוכחי"""
        # בפועל לקחת מ-API
        return 48000 + np.random.uniform(-1000, 1000)
    
    def _calculate_pnl(self, position: Dict, current_price: float) -> float:
        """חישוב רווח/הפסד"""
        entry_value = position['entry_price'] * position['amount']
        current_value = current_price * position['amount']
        return current_value - entry_value
    
    def _should_apply_trailing_stop(self, position: Dict, current_price: float) -> bool:
        """בדיקה אם להפעיל trailing stop"""
        profit_pct = (current_price - position['entry_price']) / position['entry_price']
        return profit_pct > 0.02  # 2% profit
    
    def _calculate_trailing_stop(self, position: Dict, current_price: float) -> float:
        """חישוב trailing stop חדש"""
        # 1% below current price
        return current_price * 0.99
    
    def _should_adjust_position(self, position: Dict, analysis: Dict) -> bool:
        """בדיקה אם לשנות פוזיציה"""
        # Check if market conditions changed significantly
        if analysis['signals']:
            latest_signal = analysis['signals'][0]
            
            # If signal direction changed
            if position['amount'] > 0 and latest_signal.action == 'sell':
                return True
            elif position['amount'] < 0 and latest_signal.action == 'buy':
                return True
        
        return False
    
    def _calculate_position_adjustment(self, position: Dict, analysis: Dict) -> Dict:
        """חישוב שינוי בפוזיציה"""
        if analysis['signals']:
            signal = analysis['signals'][0]
            
            if signal.confidence > 0.8:
                # Increase position
                return {
                    'type': 'increase',
                    'amount': position['amount'] * 0.5
                }
            elif signal.confidence < 0.5:
                # Reduce position
                return {
                    'type': 'reduce',
                    'amount': position['amount'] * 0.5
                }
        
        return {'type': 'hold', 'amount': 0}
    
    def get_performance_metrics(self) -> Dict:
        """קבלת מטריקות ביצועים"""
        # בפועל לחשב מנתונים אמיתיים
        # כרגע מחזיר נתונים לדוגמה
        
        return {
            'daily_pnl': np.random.uniform(-500, 1500),
            'daily_pnl_pct': np.random.uniform(-2, 5),
            'win_rate': np.random.uniform(45, 65),
            'win_rate_change': np.random.uniform(-5, 5),
            'total_trades': np.random.randint(50, 200),
            'trades_today': np.random.randint(5, 20),
            'sharpe_ratio': np.random.uniform(0.5, 2.5),
            'max_drawdown': np.random.uniform(5, 15),
            'profit_factor': np.random.uniform(1.2, 2.0),
            'average_win': np.random.uniform(100, 500),
            'average_loss': np.random.uniform(50, 200),
            'largest_win': np.random.uniform(500, 2000),
            'largest_loss': np.random.uniform(200, 800),
            'consecutive_wins': np.random.randint(0, 10),
            'consecutive_losses': np.random.randint(0, 5),
            'risk_reward_ratio': np.random.uniform(1.5, 3.0)
        }
    
    def optimize_strategy_weights(self, historical_performance: pd.DataFrame):
        """אופטימיזציה של משקולות אסטרטגיות"""
        # Calculate performance for each strategy
        strategy_performance = {}
        
        for strategy in self.strategy_weights.keys():
            strategy_data = historical_performance[
                historical_performance['strategy'] == strategy
            ]
            
            if not strategy_data.empty:
                win_rate = (strategy_data['pnl'] > 0).mean()
                avg_return = strategy_data['pnl'].mean()
                sharpe = avg_return / strategy_data['pnl'].std() if strategy_data['pnl'].std() > 0 else 0
                
                # Combined score
                score = win_rate * 0.3 + (avg_return / 1000) * 0.5 + sharpe * 0.2
                strategy_performance[strategy] = max(0.05, score)  # Minimum 5% weight
        
        # Normalize weights
        total_score = sum(strategy_performance.values())
        if total_score > 0:
            self.strategy_weights = {
                strategy: score / total_score 
                for strategy, score in strategy_performance.items()
            }
        
        logger.info(f"Updated strategy weights: {self.strategy_weights}")
    
    def save_state(self, filepath: str = 'ai_engine_state.json'):
        """שמירת מצב המנוע"""
        state = {
            'mode': self.mode.value,
            'risk_level': self.risk_level,
            'strategy_weights': self.strategy_weights,
            'current_positions': self.current_positions,
            'performance_history': self.performance_history[-100:],  # Last 100 records
            'confidence_threshold': self.confidence_threshold,
            'timestamp': datetime.now().isoformat()
        }
        
        with open(filepath, 'w') as f:
            json.dump(state, f, indent=2, default=str)
        
        logger.info(f"AI engine state saved to {filepath}")
    
    def load_state(self, filepath: str = 'ai_engine_state.json'):
        """טעינת מצב שמור"""
        try:
            with open(filepath, 'r') as f:
                state = json.load(f)
            
            self.mode = TradingMode(state.get('mode', 'balanced'))
            self.risk_level = state.get('risk_level', 5)
            self.strategy_weights = state.get('strategy_weights', self.strategy_weights)
            self.current_positions = state.get('current_positions', {})
            self.performance_history = state.get('performance_history', [])
            self.confidence_threshold = state.get('confidence_threshold', 0.7)
            
            logger.info(f"AI engine state loaded from {filepath}")
            
        except FileNotFoundError:
            logger.warning(f"State file {filepath} not found, using defaults")
        except Exception as e:
            logger.error(f"Error loading state: {e}")
    
    def generate_report(self) -> Dict:
        """יצירת דוח ביצועים מפורט"""
        metrics = self.get_performance_metrics()
        
        report = {
            'timestamp': datetime.now(),
            'mode': self.mode.value,
            'risk_level': self.risk_level,
            'performance_metrics': metrics,
            'active_positions': len(self.current_positions),
            'position_details': self.current_positions,
            'strategy_weights': self.strategy_weights,
            'recommendations': self._generate_recommendations(metrics)
        }
        
        return report
    
    def _generate_recommendations(self, metrics: Dict) -> List[str]:
        """יצירת המלצות על סמך ביצועים"""
        recommendations = []
        
        # Win rate recommendations
        if metrics['win_rate'] < 40:
            recommendations.append("Consider reducing position sizes - win rate is below 40%")
        elif metrics['win_rate'] > 60:
            recommendations.append("Excellent win rate! Consider slightly increasing position sizes")
        
        # Sharpe ratio recommendations  
        if metrics['sharpe_ratio'] < 1:
            recommendations.append("Low Sharpe ratio - consider adjusting risk parameters")
        elif metrics['sharpe_ratio'] > 2:
            recommendations.append("Great risk-adjusted returns! Current strategy is working well")
        
        # Drawdown recommendations
        if metrics['max_drawdown'] > 20:
            recommendations.append("High drawdown detected - implement stricter risk management")
        
        # Consecutive losses
        if metrics['consecutive_losses'] > 3:
            recommendations.append("Multiple consecutive losses - consider pausing trading to reassess")
        
        return recommendations