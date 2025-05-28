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
from modules.ai_trading_engine import AITradingEngine, TradingSignal
from modules.trading_executor import TradingExecutor
from modules.market_collector import MarketCollector

logger = Config.setup_logging('autonomous_trader')

class AutonomousTrader:
    """מערכת מסחר אוטונומית מלאה"""
    
    def __init__(self):
        self.ai_engine = AITradingEngine()
        self.executor = TradingExecutor(mode='demo')  # Start in demo mode
        self.market_collector = MarketCollector()
        self.signal_counter = 0 
        
        # Trading state
        self.is_trading = False
        self.trading_thread = None
        self.monitoring_thread = None
        
        # Configuration
        self.config = {
            'mode': 'conservative',
            'risk_level': 5,
            'strategies': ['trend_following', 'mean_reversion'],
            'max_daily_trades': 20,
            'max_daily_loss': 1000,
            'trading_hours': {
                'start': 0,  # 24/7 for crypto
                'end': 24
            },
            'min_confidence': 0.7,
            'position_timeout': 3600,  # 1 hour
            'emergency_stop_loss': 0.05  # 5%
        }
        
        # Performance tracking
        self.daily_trades = []
        self.daily_pnl = 0
        self.start_balance = 0
        
        # Signal queue
        self.signal_queue = PriorityQueue()
        
        # Active orders and positions
        self.active_orders = {}
        self.positions = {}
        
        # Market data cache
        self.market_data = {}
        self.last_market_update = {}
        
    def start_trading(self, mode: str = 'conservative', 
                     risk_level: int = 5,
                     strategies: List[str] = None):
        """התחלת מסחר אוטונומי"""
        if self.is_trading:
            logger.warning("Trading already active")
            return
        
        logger.info(f"Starting autonomous trading - Mode: {mode}, Risk: {risk_level}")
        
        # Update configuration
        self.config['mode'] = mode.lower()
        self.config['risk_level'] = risk_level
        if strategies:
            self.config['strategies'] = strategies
        
        # Update AI engine settings
        self.ai_engine.mode = mode
        self.ai_engine.risk_level = risk_level
        self.ai_engine.active_strategies = strategies or self.config['strategies']
        
        # Get starting balance
        balances = self.executor.get_balance()
        self.start_balance = balances.get('USD', 0) if isinstance(balances, dict) else 0
        
        # Start trading threads
        self.is_trading = True
        
        self.trading_thread = threading.Thread(
            target=self._trading_loop,
            daemon=True,
            name="TradingLoop"
        )
        self.trading_thread.start()
        
        self.monitoring_thread = threading.Thread(
            target=self._monitoring_loop,
            daemon=True,
            name="MonitoringLoop"
        )
        self.monitoring_thread.start()
        
        logger.info("Autonomous trading started successfully")
    
    def stop_trading(self):
        """הפסקת מסחר"""
        logger.info("Stopping autonomous trading...")
        
        self.is_trading = False
        
        # Close all positions
        self._close_all_positions("trading_stopped")
        
        # Wait for threads to complete
        if self.trading_thread:
            self.trading_thread.join(timeout=5)
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5)
        
        # Save state
        self._save_state()
        
        logger.info("Autonomous trading stopped")
    
    def _trading_loop(self):
        """לולאת מסחר ראשית"""
        logger.info("Trading loop started")
        
        while self.is_trading:
            try:
                # Check trading conditions
                if not self._should_trade():
                    time.sleep(10)
                    continue
                
                # Update market data
                self._update_market_data()
                
                # Analyze markets and generate signals
                signals = self._analyze_markets()
                
                # Add signals to queue
                for signal in signals:
                    priority = 1 - signal.confidence  # Higher confidence = higher priority
                    self.signal_counter += 1
                    self.signal_queue.put((priority, self.signal_counter, signal))
                
                # Process signals
                self._process_signals()
                
                # Manage existing positions
                self._manage_positions()
                
                # Risk management
                self._check_risk_limits()
                
                # Sleep interval based on market volatility
                sleep_time = self._calculate_sleep_interval()
                time.sleep(sleep_time)
                
            except Exception as e:
                logger.error(f"Error in trading loop: {e}", exc_info=True)
                time.sleep(30)
    
    def _monitoring_loop(self):
        """לולאת ניטור וניהול סיכונים"""
        logger.info("Monitoring loop started")
        
        while self.is_trading:
            try:
                # Monitor positions
                self._monitor_positions()
                
                # Check for emergency conditions
                self._check_emergency_conditions()
                
                # Update performance metrics
                self._update_performance_metrics()
                
                # Log status
                self._log_status()
                
                time.sleep(5)  # Check every 5 seconds
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}", exc_info=True)
                time.sleep(10)
    
    def _should_trade(self) -> bool:
        """בדיקה אם לסחור"""
        # Check if within trading hours
        current_hour = datetime.now().hour
        if not (self.config['trading_hours']['start'] <= 
                current_hour < self.config['trading_hours']['end']):
            return False
        
        # Check daily trade limit
        if len(self.daily_trades) >= self.config['max_daily_trades']:
            logger.warning("Daily trade limit reached")
            return False
        
        # Check daily loss limit
        if self.daily_pnl < -self.config['max_daily_loss']:
            logger.warning("Daily loss limit reached")
            return False
        
        # Check if market is too volatile
        if self._is_market_too_volatile():
            logger.warning("Market too volatile, pausing trading")
            return False
        
        return True
    
    def _update_market_data(self):
        """עדכון נתוני שוק"""
        symbols = ['BTC', 'ETH', 'SOL', 'ADA', 'DOT', 'MATIC']
        
        # Get latest prices
        prices = self.market_collector.get_combined_prices(symbols)
        
        for symbol, data in prices.items():
            self.market_data[symbol] = data
            self.last_market_update[symbol] = datetime.now()
    
    def _analyze_markets(self) -> List[TradingSignal]:
        """ניתוח שווקים ויצירת אותות"""
        all_signals = []
        
        # Analyze each symbol
        for symbol in self.market_data.keys():
            # Skip if we have max positions
            if len(self.positions) >= self.ai_engine.max_positions:
                break
            
            # Skip if already have position in this symbol
            if symbol in self.positions:
                continue
            
            # Analyze market
            analysis = self.ai_engine.analyze_market(symbol)
            
            # Get signals
            if analysis['signals']:
                all_signals.extend(analysis['signals'])
        
        # Filter by confidence
        filtered_signals = [
            s for s in all_signals 
            if s.confidence >= self.config['min_confidence']
        ]
        
        # Sort by confidence
        filtered_signals.sort(key=lambda x: x.confidence, reverse=True)
        
        return filtered_signals[:5]  # Max 5 signals at a time
    
    def _process_signals(self):
        """עיבוד אותות מהתור"""
        processed = 0
        max_per_cycle = 3
        
        while not self.signal_queue.empty() and processed < max_per_cycle:
            try:
                _, _, signal = self.signal_queue.get_nowait()
                
                # Skip if already have position
                if signal.symbol in self.positions:
                    continue
                
                # Validate signal is still valid
                if self._is_signal_valid(signal):
                    # Execute trade
                    result = self._execute_signal(signal)
                    
                    if result['status'] == 'success':
                        processed += 1
                        
                        # Track position
                        self.positions[signal.symbol] = {
                            'signal': signal,
                            'execution': result,
                            'entry_time': datetime.now(),
                            'pnl': 0
                        }
                        
                        # Log trade
                        self.daily_trades.append({
                            'timestamp': datetime.now(),
                            'symbol': signal.symbol,
                            'action': signal.action,
                            'price': result['price'],
                            'amount': result['amount']
                        })
                
            except Exception as e:
                logger.error(f"Error processing signal: {e}")
    
    def _is_signal_valid(self, signal: TradingSignal) -> bool:
        """בדיקת תקפות אות"""
        # Check if signal is not too old
        age = (datetime.now() - signal.timestamp).seconds
        if age > 300:  # 5 minutes
            return False
        
        # Check if price hasn't moved too much
        current_price = self.market_data.get(signal.symbol, {}).get('price', 0)
        if current_price:
            price_change = abs(current_price - signal.entry_price) / signal.entry_price
            if price_change > 0.02:  # 2%
                return False
        
        return True
    
    def _execute_signal(self, signal: TradingSignal) -> Dict:
        """ביצוע אות מסחר"""
        logger.info(f"Executing signal: {signal.action} {signal.symbol}")
        
        # Calculate actual amount based on risk management
        amount_usd = self._calculate_position_size(signal)
        
        # Execute order
        result = self.executor.execute_market_order(
            pair=f"{signal.symbol}USD",
            side=signal.action,
            amount_usd=amount_usd
        )
        
        return result
    
    def _calculate_position_size(self, signal: TradingSignal) -> float:
        """חישוב גודל פוזיציה בטוח"""
        # Get current balance
        balance = 10000  # ברירת מחדל אם אין גישה למאזן
        try:
            balance_data = self.executor.get_balance()
            if isinstance(balance_data, dict):
                balance = balance_data.get('USD', 10000)
            else:
                balance = 10000
        except:
            balance = 10000
        
        # Base position size from signal
        base_size = signal.suggested_amount
        
        # Apply risk limits
        max_position = balance * 0.1  # Max 10% per position
        
        # Adjust for daily PnL
        if self.daily_pnl < 0:
            # Reduce size if losing
            adjustment = 1 + (self.daily_pnl / balance)
            base_size *= max(0.5, adjustment)
        
        # Final size
        position_size = min(base_size, max_position, balance * 0.9)
        
        return max(10, position_size)  # Minimum $10
    
    def _manage_positions(self):
        """ניהול פוזיציות פתוחות"""
        for symbol, position in list(self.positions.items()):
            current_price = self.market_data.get(symbol, {}).get('price', 0)
            
            if not current_price:
                continue
            
            # Update PnL
            entry_price = position['execution']['price']
            amount = position['execution']['amount']
            
            if position['signal'].action == 'buy':
                pnl = (current_price - entry_price) * amount
            else:
                pnl = (entry_price - current_price) * amount
            
            position['pnl'] = pnl
            
            # Check exit conditions
            should_exit, reason = self._check_exit_conditions(position, current_price)
            
            if should_exit:
                self._close_position(symbol, reason)
    
    def _check_exit_conditions(self, position: Dict, current_price: float) -> tuple:
        """בדיקת תנאי יציאה"""
        signal = position['signal']
        entry_price = position['execution']['price']
        
        # Check stop loss
        if signal.action == 'buy':
            if current_price <= signal.stop_loss:
                return True, 'stop_loss'
        else:
            if current_price >= signal.stop_loss:
                return True, 'stop_loss'
        
        # Check take profit
        if signal.action == 'buy':
            if current_price >= signal.take_profit:
                return True, 'take_profit'
        else:
            if current_price <= signal.take_profit:
                return True, 'take_profit'
        
        # Check timeout
        position_age = (datetime.now() - position['entry_time']).seconds
        if position_age > self.config['position_timeout']:
            return True, 'timeout'
        
        # Check for reversal signal
        latest_analysis = self.ai_engine.analyze_market(position['signal'].symbol)
        if latest_analysis['signals']:
            latest_signal = latest_analysis['signals'][0]
            if latest_signal.action != signal.action and latest_signal.confidence > 0.8:
                return True, 'signal_reversal'
        
        return False, None
    
    def _close_position(self, symbol: str, reason: str):
        """סגירת פוזיציה"""
        logger.info(f"Closing position {symbol} - Reason: {reason}")
        
        position = self.positions.get(symbol)
        if not position:
            return
        
        # Execute closing order
        action = 'sell' if position['signal'].action == 'buy' else 'buy'
        
        result = self.executor.execute_market_order(
            pair=f"{symbol}USD",
            side=action,
            amount_usd=position['execution']['amount']
        )
        
        if result['status'] == 'success':
            # Update daily PnL
            self.daily_pnl += position['pnl']
            
            # Log closed position
            logger.info(f"Position closed - Symbol: {symbol}, PnL: ${position['pnl']:.2f}")
            
            # Remove from positions
            del self.positions[symbol]
    
    def _close_all_positions(self, reason: str):
        """סגירת כל הפוזיציות"""
        logger.warning(f"Closing all positions - Reason: {reason}")
        
        for symbol in list(self.positions.keys()):
            self._close_position(symbol, reason)
    
    def _monitor_positions(self):
        """ניטור פוזיציות לניהול סיכונים"""
        total_pnl = sum(p['pnl'] for p in self.positions.values())
        
        # Emergency stop if losing too much
        if total_pnl < -self.config['max_daily_loss'] * 0.5:
            logger.warning("Approaching daily loss limit")
            
            # Close losing positions
            for symbol, position in list(self.positions.items()):
                if position['pnl'] < 0:
                    self._close_position(symbol, 'risk_management')
    
    def _check_emergency_conditions(self):
        """בדיקת תנאי חירום"""
        # Check for flash crash
        for symbol, data in self.market_data.items():
            if 'change_pct_24h' in data:
                if abs(data['change_pct_24h']) > 20:  # 20% move
                    logger.error(f"Flash crash detected in {symbol}")
                    self._close_all_positions('flash_crash')
                    self.is_trading = False
                    break
        
        # Check connection
        if not self._check_api_connection():
            logger.error("API connection lost")
            self.is_trading = False
    
    def _is_market_too_volatile(self) -> bool:
        """בדיקת תנודתיות שוק"""
        # Simple volatility check based on recent price movements
        btc_data = self.market_data.get('BTC', {})
        
        if 'change_pct_24h' in btc_data:
            if abs(btc_data['change_pct_24h']) > 10:
                return True
        
        return False
    
    def _calculate_sleep_interval(self) -> int:
        """חישוב זמן המתנה דינמי"""
        # Base interval
        base_interval = 30
        
        # Adjust based on market activity
        if len(self.positions) > 0:
            # More frequent checks with open positions
            base_interval = 10
        
        # Adjust based on volatility
        avg_volatility = np.mean([
            abs(data.get('change_pct_24h', 0)) 
            for data in self.market_data.values()
        ])
        
        if avg_volatility > 5:
            base_interval = max(5, base_interval // 2)
        
        return base_interval
    
    def _check_risk_limits(self):
        """בדיקת מגבלות סיכון"""
        # Reset daily counters at midnight
        if datetime.now().hour == 0 and datetime.now().minute < 1:
            self.daily_trades = []
            self.daily_pnl = 0
        
        # Check position concentration
        if self.positions:
            balance = 10000  # ברירת מחדל
            try:
                balance_data = self.executor.get_balance()
                if isinstance(balance_data, dict):
                    balance = balance_data.get('USD', 10000)
            except:
                pass
            
            for symbol, position in self.positions.items():
                position_value = position['execution']['amount']
                concentration = position_value / balance
                
                if concentration > 0.3:  # 30% in one position
                    logger.warning(f"High concentration in {symbol}: {concentration:.1%}")
    
    def _update_performance_metrics(self):
        """עדכון מטריקות ביצועים"""
        # Calculate current metrics
        current_balance = 10000  # ברירת מחדל
        try:
            balance_data = self.executor.get_balance()
            if isinstance(balance_data, dict):
                current_balance = balance_data.get('USD', 10000)
        except:
            pass
            
        total_return = (current_balance - self.start_balance) / self.start_balance if self.start_balance > 0 else 0
        
        # Update AI engine with performance
        if len(self.daily_trades) > 10:
            performance_df = pd.DataFrame(self.daily_trades)
            # Add mock PnL data for optimization
            performance_df['pnl'] = np.random.normal(50, 100, len(performance_df))
            performance_df['strategy'] = 'trend_following'  # Mock strategy
            
            self.ai_engine.optimize_strategy_weights(performance_df)
    
    def _log_status(self):
        """רישום סטטוס מערכת"""
        if len(self.positions) > 0 or datetime.now().minute % 5 == 0:
            status = {
                'timestamp': datetime.now(),
                'is_trading': self.is_trading,
                'mode': self.config['mode'],
                'positions': len(self.positions),
                'daily_trades': len(self.daily_trades),
                'daily_pnl': self.daily_pnl,
                'position_details': {
                    symbol: {
                        'pnl': position['pnl'],
                        'age_minutes': (datetime.now() - position['entry_time']).seconds / 60
                    }
                    for symbol, position in self.positions.items()
                }
            }
            
            logger.info(f"Status: {json.dumps(status, default=str)}")
    
    def _check_api_connection(self) -> bool:
        """בדיקת חיבור API"""
        try:
            balance = self.executor.get_balance()
            return bool(balance)
        except:
            return False
    
    def _save_state(self):
        """שמירת מצב המערכת"""
        state = {
            'timestamp': datetime.now().isoformat(),
            'config': self.config,
            'positions': self.positions,
            'daily_trades': self.daily_trades,
            'daily_pnl': self.daily_pnl,
            'market_data': self.market_data
        }
        
        filepath = os.path.join(Config.DATA_DIR, 'autonomous_trader_state.json')
        
        with open(filepath, 'w') as f:
            json.dump(state, f, indent=2, default=str)
        
        logger.info(f"State saved to {filepath}")
    
    def get_status(self) -> Dict:
        """קבלת סטטוס נוכחי"""
        return {
            'is_trading': self.is_trading,
            'mode': self.config['mode'],
            'risk_level': self.config['risk_level'],
            'active_positions': len(self.positions),
            'daily_trades': len(self.daily_trades),
            'daily_pnl': self.daily_pnl,
            'positions': {
                symbol: {
                    'entry_price': pos['execution']['price'],
                    'current_pnl': pos['pnl'],
                    'strategy': pos['signal'].strategy,
                    'age_minutes': (datetime.now() - pos['entry_time']).seconds / 60
                }
                for symbol, pos in self.positions.items()
            }
        }