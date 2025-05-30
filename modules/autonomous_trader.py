import threading
import time
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from typing import Dict, List, Optional
import logging
import json
from queue import Queue, PriorityQueue
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config

logger = Config.setup_logging('risk_management')

class RiskManager:
    """מנהל סיכונים מתקדם"""
    
    def __init__(self, initial_balance: float = 10000):
        self.initial_balance = initial_balance
        self.current_balance = initial_balance
        
        # Risk parameters
        self.max_daily_loss_pct = 0.02  # 2% max daily loss
        self.max_position_size_pct = 0.1  # 10% max per position
        self.max_total_exposure_pct = 0.5  # 50% max total exposure
        self.correlation_limit = 0.7  # Max correlation between positions
        
        # Position tracking
        self.active_positions = {}
        self.daily_pnl = 0
        self.max_drawdown = 0
        self.peak_balance = initial_balance
        
        # Risk metrics history
        self.risk_history = []
        
        # Emergency flags
        self.emergency_stop = False
        self.risk_alerts = []
        
    def validate_new_position(self, symbol: str, amount: float, 
                            current_price: float, strategy: str) -> Dict:
        """בדיקת תקינות פוזיציה חדשה"""
        
        validation_result = {
            'approved': False,
            'adjusted_amount': amount,
            'warnings': [],
            'reasons': []
        }
        
        # Check if emergency stop is active
        if self.emergency_stop:
            validation_result['reasons'].append("Emergency stop active")
            return validation_result
        
        # Check daily loss limit
        if self.daily_pnl < -(self.max_daily_loss_pct * self.initial_balance):
            validation_result['reasons'].append("Daily loss limit exceeded")
            return validation_result
        
        # Check position size limit
        position_value = amount
        max_position_value = self.current_balance * self.max_position_size_pct
        
        if position_value > max_position_value:
            adjusted_amount = max_position_value
            validation_result['adjusted_amount'] = adjusted_amount
            validation_result['warnings'].append(
                f"Position size reduced from ${amount:.2f} to ${adjusted_amount:.2f}"
            )
        
        # Check total exposure
        current_exposure = sum(pos['current_value'] for pos in self.active_positions.values())
        new_exposure = current_exposure + validation_result['adjusted_amount']
        max_exposure = self.current_balance * self.max_total_exposure_pct
        
        if new_exposure > max_exposure:
            available_exposure = max_exposure - current_exposure
            if available_exposure <= 0:
                validation_result['reasons'].append("Maximum total exposure reached")
                return validation_result
            
            validation_result['adjusted_amount'] = available_exposure
            validation_result['warnings'].append(
                f"Position size adjusted to fit exposure limit: ${available_exposure:.2f}"
            )
        
        # Check correlation with existing positions
        correlation_warning = self._check_position_correlation(symbol, strategy)
        if correlation_warning:
            validation_result['warnings'].append(correlation_warning)
        
        # Check market volatility
        volatility_check = self._check_market_volatility(symbol)
        if volatility_check['high_volatility']:
            vol_adjustment = validation_result['adjusted_amount'] * 0.7  # Reduce by 30%
            validation_result['adjusted_amount'] = vol_adjustment
            validation_result['warnings'].append(
                f"High volatility detected - position reduced to ${vol_adjustment:.2f}"
            )
        
        validation_result['approved'] = True
        return validation_result
    
    def _check_position_correlation(self, symbol: str, strategy: str) -> Optional[str]:
        """בדיקת קורלציה בין פוזיציות"""
        
        # Check strategy concentration
        strategy_count = sum(1 for pos in self.active_positions.values() 
                           if pos.get('strategy') == strategy)
        
        if strategy_count >= 3:
            return f"High concentration in {strategy} strategy ({strategy_count} positions)"
        
        # Check symbol correlation (simplified)
        crypto_groups = {
            'major': ['BTC', 'ETH'],
            'defi': ['UNI', 'AAVE', 'SUSHI', 'COMP'],
            'layer1': ['SOL', 'AVAX', 'DOT', 'ADA'],
            'gaming': ['SAND', 'MANA', 'AXS']
        }
        
        current_symbol_group = None
        for group, symbols in crypto_groups.items():
            if symbol in symbols:
                current_symbol_group = group
                break
        
        if current_symbol_group:
            same_group_positions = [
                pos for pos in self.active_positions.values()
                if any(pos['symbol'] in symbols for symbols in crypto_groups.values()
                      if pos['symbol'] in crypto_groups.get(current_symbol_group, []))
            ]
            
            if len(same_group_positions) >= 2:
                return f"High correlation risk - {len(same_group_positions)} positions in {current_symbol_group} sector"
        
        return None
    
    def _check_market_volatility(self, symbol: str) -> Dict:
        """בדיקת תנודתיות שוק"""
        try:
            # Load recent price data
            if os.path.exists(Config.MARKET_LIVE_FILE):
                df = pd.read_csv(Config.MARKET_LIVE_FILE)
                symbol_data = df[df['pair'].str.contains(f"{symbol}USD", na=False)]
                
                if not symbol_data.empty:
                    recent_changes = symbol_data['change_pct_24h'].tail(5)
                    volatility = recent_changes.std()
                    
                    return {
                        'volatility': volatility,
                        'high_volatility': volatility > 10  # More than 10% std dev
                    }
            
            return {'volatility': 5, 'high_volatility': False}
            
        except Exception as e:
            logger.error(f"Error checking volatility: {e}")
            return {'volatility': 5, 'high_volatility': False}
    
    def update_position(self, symbol: str, position_data: Dict):
        """עדכון פוזיציה קיימת"""
        self.active_positions[symbol] = position_data
        
        # Update current balance based on unrealized PnL
        total_unrealized_pnl = sum(pos.get('unrealized_pnl', 0) 
                                 for pos in self.active_positions.values())
        self.current_balance = self.initial_balance + self.daily_pnl + total_unrealized_pnl
        
        # Update drawdown
        if self.current_balance > self.peak_balance:
            self.peak_balance = self.current_balance
        
        current_drawdown = (self.peak_balance - self.current_balance) / self.peak_balance
        self.max_drawdown = max(self.max_drawdown, current_drawdown)
        
    def close_position(self, symbol: str, realized_pnl: float):
        """סגירת פוזיציה"""
        if symbol in self.active_positions:
            del self.active_positions[symbol]
        
        self.daily_pnl += realized_pnl
        self.current_balance = self.initial_balance + self.daily_pnl
    
    def check_risk_limits(self) -> List[Dict]:
        """בדיקת מגבלות סיכון"""
        alerts = []
        
        # Check daily loss limit
        daily_loss_pct = abs(self.daily_pnl) / self.initial_balance
        if daily_loss_pct > self.max_daily_loss_pct * 0.8:  # 80% of limit
            alerts.append({
                'type': 'daily_loss_warning',
                'severity': 'high' if daily_loss_pct > self.max_daily_loss_pct else 'medium',
                'message': f"Daily loss at {daily_loss_pct*100:.1f}% (limit: {self.max_daily_loss_pct*100}%)",
                'action': 'reduce_position_sizes' if daily_loss_pct < self.max_daily_loss_pct else 'stop_trading'
            })
        
        # Check drawdown
        if self.max_drawdown > 0.15:  # 15% drawdown
            alerts.append({
                'type': 'drawdown_warning',
                'severity': 'high',
                'message': f"Maximum drawdown: {self.max_drawdown*100:.1f}%",
                'action': 'review_strategy'
            })
        
        # Check position concentration
        if self.active_positions:
            total_exposure = sum(pos['current_value'] for pos in self.active_positions.values())
            exposure_pct = total_exposure / self.current_balance
            
            if exposure_pct > self.max_total_exposure_pct * 0.9:  # 90% of limit
                alerts.append({
                    'type': 'exposure_warning',
                    'severity': 'medium',
                    'message': f"Total exposure: {exposure_pct*100:.1f}% (limit: {self.max_total_exposure_pct*100}%)",
                    'action': 'reduce_new_positions'
                })
        
        # Check for margin call risk (if applicable)
        if self.current_balance < self.initial_balance * 0.5:  # 50% of initial
            alerts.append({
                'type': 'margin_risk',
                'severity': 'critical',
                'message': f"Account balance down to {self.current_balance/self.initial_balance*100:.1f}% of initial",
                'action': 'emergency_liquidation'
            })
        
        self.risk_alerts = alerts
        return alerts
    
    def calculate_optimal_position_size(self, signal_confidence: float, 
                                      symbol_volatility: float, 
                                      strategy_performance: float) -> float:
        """חישוב גודל פוזיציה אופטימלי"""
        
        # Kelly Criterion calculation
        win_rate = max(strategy_performance, 0.5)  # Minimum 50%
        avg_win = 0.03  # 3% average win
        avg_loss = 0.015  # 1.5% average loss
        
        kelly_fraction = (win_rate * avg_win - (1 - win_rate) * avg_loss) / avg_win
        kelly_fraction = max(0, min(kelly_fraction, 0.2))  # Cap at 20%
        
        # Adjust for confidence
        confidence_multiplier = signal_confidence
        
        # Adjust for volatility
        volatility_multiplier = 1 / (1 + symbol_volatility / 10)
        
        # Base position size
        base_size_pct = 0.05  # 5% base
        
        optimal_size_pct = (base_size_pct + kelly_fraction * 0.5) * confidence_multiplier * volatility_multiplier
        
        # Apply maximum limits
        optimal_size_pct = min(optimal_size_pct, self.max_position_size_pct)
        
        return self.current_balance * optimal_size_pct
    
    def get_risk_report(self) -> Dict:
        """דוח סיכונים מפורט"""
        
        # Current risk metrics
        current_exposure = sum(pos['current_value'] for pos in self.active_positions.values())
        exposure_pct = current_exposure / self.current_balance if self.current_balance > 0 else 0
        
        daily_loss_pct = abs(self.daily_pnl) / self.initial_balance
        
        # Position analysis
        position_analysis = {}
        for symbol, pos in self.active_positions.items():
            position_analysis[symbol] = {
                'size_pct': pos['current_value'] / self.current_balance,
                'unrealized_pnl': pos.get('unrealized_pnl', 0),
                'days_held': (datetime.now() - pos.get('entry_time', datetime.now())).days,
                'risk_score': self._calculate_position_risk_score(pos)
            }
        
        return {
            'timestamp': datetime.now(),
            'account_summary': {
                'initial_balance': self.initial_balance,
                'current_balance': self.current_balance,
                'daily_pnl': self.daily_pnl,
                'daily_pnl_pct': self.daily_pnl / self.initial_balance * 100,
                'total_return_pct': (self.current_balance - self.initial_balance) / self.initial_balance * 100,
                'max_drawdown_pct': self.max_drawdown * 100
            },
            'risk_metrics': {
                'current_exposure_pct': exposure_pct * 100,
                'daily_loss_pct': daily_loss_pct * 100,
                'position_count': len(self.active_positions),
                'emergency_stop_active': self.emergency_stop
            },
            'position_analysis': position_analysis,
            'risk_alerts': self.risk_alerts,
            'recommendations': self._generate_risk_recommendations()
        }
    
    def _calculate_position_risk_score(self, position: Dict) -> float:
        """חישוב ניקוד סיכון לפוזיציה"""
        risk_score = 0
        
        # Size risk
        size_pct = position['current_value'] / self.current_balance
        if size_pct > 0.15:  # More than 15%
            risk_score += 2
        elif size_pct > 0.1:  # More than 10%
            risk_score += 1
        
        # Unrealized loss risk
        unrealized_pnl = position.get('unrealized_pnl', 0)
        if unrealized_pnl < -position['current_value'] * 0.1:  # More than 10% loss
            risk_score += 2
        elif unrealized_pnl < -position['current_value'] * 0.05:  # More than 5% loss
            risk_score += 1
        
        # Time risk
        days_held = (datetime.now() - position.get('entry_time', datetime.now())).days
        if days_held > 7:  # Holding more than a week
            risk_score += 1
        
        return min(risk_score, 5)  # Cap at 5
    
    def _generate_risk_recommendations(self) -> List[str]:
        """יצירת המלצות ניהול סיכונים"""
        recommendations = []
        
        # Daily loss recommendations
        daily_loss_pct = abs(self.daily_pnl) / self.initial_balance
        if daily_loss_pct > self.max_daily_loss_pct * 0.7:
            recommendations.append("Consider reducing position sizes - approaching daily loss limit")
        
        # Drawdown recommendations
        if self.max_drawdown > 0.1:
            recommendations.append("Review strategy - significant drawdown detected")
        
        # Position concentration
        if self.active_positions:
            largest_position_pct = max(pos['current_value'] / self.current_balance 
                                     for pos in self.active_positions.values())
            if largest_position_pct > 0.2:
                recommendations.append("Diversify portfolio - large position concentration detected")
        
        # Performance based
        if self.daily_pnl < 0 and len(self.active_positions) > 3:
            recommendations.append("Consider reducing number of simultaneous positions")
        
        return recommendations
    
    def activate_emergency_stop(self, reason: str):
        """הפעלת עצירת חירום"""
        self.emergency_stop = True
        
        alert = {
            'type': 'emergency_stop',
            'severity': 'critical',
            'message': f"Emergency stop activated: {reason}",
            'timestamp': datetime.now(),
            'action': 'close_all_positions'
        }
        
        self.risk_alerts.append(alert)
        logger.critical(f"EMERGENCY STOP ACTIVATED: {reason}")
    
    def deactivate_emergency_stop(self):
        """ביטול עצירת חירום"""
        self.emergency_stop = False
        logger.info("Emergency stop deactivated")
    
    def save_risk_state(self, filepath: str = None):
        """שמירת מצב ניהול סיכונים"""
        if filepath is None:
            filepath = os.path.join(Config.DATA_DIR, 'risk_manager_state.json')
        
        state = {
            'timestamp': datetime.now().isoformat(),
            'initial_balance': self.initial_balance,
            'current_balance': self.current_balance,
            'daily_pnl': self.daily_pnl,
            'max_drawdown': self.max_drawdown,
            'peak_balance': self.peak_balance,
            'emergency_stop': self.emergency_stop,
            'active_positions_count': len(self.active_positions),
            'risk_alerts_count': len(self.risk_alerts)
        }
        
        try:
            with open(filepath, 'w') as f:
                json.dump(state, f, indent=2)
            logger.info(f"Risk state saved to {filepath}")
        except Exception as e:
            logger.error(f"Failed to save risk state: {e}")


# Enhanced Autonomous Trader with better risk management
class EnhancedAutonomousTrader:
    """מסחר אוטונומי עם ניהול סיכונים משופר"""
    
    def __init__(self, initial_balance: float = 10000):
        # Initialize risk manager first
        self.risk_manager = RiskManager(initial_balance)
        
        # Other components
        from modules.ai_trading_engine import AITradingEngine
        from modules.trading_executor import TradingExecutor
        from modules.market_collector import MarketCollector
        
        self.ai_engine = AITradingEngine()
        self.executor = TradingExecutor(mode='real')
        self.market_collector = MarketCollector()
        
        # Enhanced configuration
        self.config = {
            'mode': 'conservative',
            'risk_level': 5,
            'max_daily_trades': 15,  # Reduced from 20
            'max_daily_loss': initial_balance * 0.02,  # 2% max loss
            'min_confidence': 0.75,  # Increased from 0.7
            'position_timeout': 3600,
            'emergency_stop_loss': 0.03,  # 3% emergency stop
            'rebalance_threshold': 0.05,  # 5% portfolio drift
            'max_correlation': 0.7
        }
        
        # Trading state
        self.is_trading = False
        self.positions = {}
        self.daily_trades = []
        
        # Performance tracking
        self.performance_metrics = {
            'total_trades': 0,
            'winning_trades': 0,
            'total_pnl': 0,
            'max_consecutive_losses': 0,
            'current_consecutive_losses': 0
        }
    
    def execute_signal_with_risk_check(self, signal):
        """ביצוע אות עם בדיקת סיכונים"""
        
        # Risk validation
        risk_check = self.risk_manager.validate_new_position(
            symbol=signal.symbol,
            amount=signal.suggested_amount,
            current_price=signal.entry_price,
            strategy=signal.strategy
        )
        
        if not risk_check['approved']:
            logger.warning(f"Signal rejected by risk manager: {risk_check['reasons']}")
            return {'status': 'rejected', 'reasons': risk_check['reasons']}
        
        # Adjust amount based on risk manager recommendations
        adjusted_amount = risk_check['adjusted_amount']
        if adjusted_amount != signal.suggested_amount:
            logger.info(f"Position size adjusted: ${signal.suggested_amount:.2f} -> ${adjusted_amount:.2f}")
            signal.suggested_amount = adjusted_amount
        
        # Log warnings
        for warning in risk_check['warnings']:
            logger.warning(warning)
        
        # Execute the trade
        result = self.executor.execute_market_order(
            pair=f"{signal.symbol}USD",
            side=signal.action,
            amount_usd=signal.suggested_amount
        )
        
        if result['status'] == 'success':
            # Update risk manager
            position_data = {
                'symbol': signal.symbol,
                'entry_price': result['price'],
                'current_value': signal.suggested_amount,
                'strategy': signal.strategy,
                'entry_time': datetime.now(),
                'stop_loss': signal.stop_loss,
                'take_profit': signal.take_profit,
                'unrealized_pnl': 0
            }
            
            self.risk_manager.update_position(signal.symbol, position_data)
            self.positions[signal.symbol] = position_data
        
        return result
    
    def monitor_risk_continuously(self):
        """ניטור רציף של סיכונים"""
        while self.is_trading:
            try:
                # Check risk limits
                risk_alerts = self.risk_manager.check_risk_limits()
                
                # Handle critical alerts
                for alert in risk_alerts:
                    if alert['severity'] == 'critical':
                        if alert['action'] == 'emergency_liquidation':
                            self._emergency_liquidation(alert['message'])
                        elif alert['action'] == 'stop_trading':
                            self._pause_trading(alert['message'])
                    
                    elif alert['severity'] == 'high':
                        if alert['action'] == 'reduce_position_sizes':
                            self._reduce_position_sizes()
                
                # Update position PnL
                self._update_position_pnl()
                
                # Save risk state periodically
                if datetime.now().minute % 15 == 0:  # Every 15 minutes
                    self.risk_manager.save_risk_state()
                
                time.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                logger.error(f"Error in risk monitoring: {e}")
                time.sleep(60)  # Wait longer on error
    
    def _emergency_liquidation(self, reason: str):
        """חיסול חירום של כל הפוזיציות"""
        logger.critical(f"EMERGENCY LIQUIDATION: {reason}")
        
        self.risk_manager.activate_emergency_stop(reason)
        
        # Close all positions immediately
        for symbol in list(self.positions.keys()):
            try:
                self._close_position(symbol, 'emergency_liquidation')
            except Exception as e:
                logger.error(f"Failed to close position {symbol}: {e}")
        
        # Stop trading
        self.is_trading = False
    
    def _pause_trading(self, reason: str):
        """השהיית מסחר זמנית"""
        logger.warning(f"TRADING PAUSED: {reason}")
        
        # Don't take new positions but keep monitoring existing ones
        self.config['min_confidence'] = 1.0  # Effectively disable new trades
        
        # Close losing positions
        for symbol, position in list(self.positions.items()):
            if position.get('unrealized_pnl', 0) < -position['current_value'] * 0.05:  # 5% loss
                self._close_position(symbol, 'risk_management')
    
    def _reduce_position_sizes(self):
        """הקטנת גדלי פוזיציות"""
        logger.info("Reducing position sizes due to risk alert")
        
        # Reduce largest positions first
        sorted_positions = sorted(
            self.positions.items(),
            key=lambda x: x[1]['current_value'],
            reverse=True
        )
        
        for symbol, position in sorted_positions[:3]:  # Top 3 largest
            if position['current_value'] > self.risk_manager.current_balance * 0.1:
                # Close 50% of position
                try:
                    partial_close_amount = position['current_value'] * 0.5
                    # Implement partial position closing logic here
                    logger.info(f"Reduced {symbol} position by 50%")
                except Exception as e:
                    logger.error(f"Failed to reduce {symbol} position: {e}")
    
    def _update_position_pnl(self):
        """עדכון רווח/הפסד בפוזיציות"""
        for symbol, position in self.positions.items():
            try:
                # Get current price (simplified - should use real market data)
                current_price = self._get_current_price(symbol)
                
                if current_price:
                    # Calculate unrealized PnL
                    if position.get('side') == 'buy':
                        pnl = (current_price - position['entry_price']) * (position['current_value'] / position['entry_price'])
                    else:
                        pnl = (position['entry_price'] - current_price) * (position['current_value'] / position['entry_price'])
                    
                    position['unrealized_pnl'] = pnl
                    
                    # Update risk manager
                    self.risk_manager.update_position(symbol, position)
                    
            except Exception as e:
                logger.error(f"Error updating PnL for {symbol}: {e}")
    
    def _get_current_price(self, symbol: str) -> Optional[float]:
        """קבלת מחיר נוכחי"""
        try:
            prices = self.market_collector.get_combined_prices([symbol])
            return prices.get(symbol, {}).get('price')
        except Exception as e:
            logger.error(f"Error getting price for {symbol}: {e}")
            return None
    
    def _close_position(self, symbol: str, reason: str):
        """סגירת פוזיציה"""
        if symbol not in self.positions:
            return
        
        position = self.positions[symbol]
        
        try:
            # Execute closing order
            result = self.executor.execute_market_order(
                pair=f"{symbol}USD",
                side='sell' if position.get('side') == 'buy' else 'buy',
                amount_usd=position['current_value']
            )
            
            if result['status'] == 'success':
                # Calculate realized PnL
                realized_pnl = position.get('unrealized_pnl', 0)
                
                # Update risk manager
                self.risk_manager.close_position(symbol, realized_pnl)
                
                # Remove from positions
                del self.positions[symbol]
                
                logger.info(f"Position {symbol} closed - Reason: {reason}, PnL: ${realized_pnl:.2f}")
                
        except Exception as e:
            logger.error(f"Failed to close position {symbol}: {e}")
    
    def get_enhanced_status(self) -> Dict:
        """סטטוס מסחר משופר עם מידע על סיכונים"""
        basic_status = {
            'is_trading': self.is_trading,
            'mode': self.config['mode'],
            'risk_level': self.config['risk_level'],
            'active_positions': len(self.positions),
            'daily_trades': len(self.daily_trades)
        }
        
        # Add risk report
        risk_report = self.risk_manager.get_risk_report()
        
        return {
            **basic_status,
            'risk_management': risk_report,
            'performance_metrics': self.performance_metrics,
            'emergency_status': {
                'emergency_stop_active': self.risk_manager.emergency_stop,
                'risk_alerts_count': len(self.risk_manager.risk_alerts),
                'critical_alerts': [alert for alert in self.risk_manager.risk_alerts 
                                  if alert['severity'] == 'critical']
            }
        }