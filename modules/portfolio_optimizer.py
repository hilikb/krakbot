import numpy as np
import pandas as pd
from scipy.optimize import minimize
from typing import Dict, List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)

class PortfolioOptimizer:
    """מייטב תיק השקעות מתקדם"""
    
    def __init__(self):
        self.risk_free_rate = 0.02  # 2% annual
        self.optimization_methods = [
            'mean_variance',
            'risk_parity',
            'maximum_sharpe',
            'minimum_volatility'
        ]
        
    def calculate_portfolio_metrics(self, weights: np.array, 
                                  returns: pd.DataFrame) -> Dict:
        """חישוב מטריקות תיק"""
        portfolio_return = np.sum(returns.mean() * weights) * 252
        portfolio_std = np.sqrt(np.dot(weights.T, np.dot(returns.cov() * 252, weights)))
        sharpe_ratio = (portfolio_return - self.risk_free_rate) / portfolio_std
        
        return {
            'annual_return': portfolio_return,
            'annual_volatility': portfolio_std,
            'sharpe_ratio': sharpe_ratio
        }
    
    def optimize_portfolio(self, returns: pd.DataFrame, 
                         method: str = 'maximum_sharpe',
                         constraints: Optional[Dict] = None) -> Dict:
        """אופטימיזציה של תיק השקעות"""
        n_assets = len(returns.columns)
        
        # Initial guess (equal weights)
        initial_weights = np.array([1/n_assets] * n_assets)
        
        # Constraints
        if constraints is None:
            constraints = {
                'min_weight': 0.01,  # Minimum 1% per asset
                'max_weight': 0.40   # Maximum 40% per asset
            }
        
        # Optimization constraints
        cons = [
            {'type': 'eq', 'fun': lambda x: np.sum(x) - 1}  # Sum to 1
        ]
        
        # Bounds
        bounds = tuple(
            (constraints['min_weight'], constraints['max_weight']) 
            for _ in range(n_assets)
        )
        
        # Optimization function
        if method == 'maximum_sharpe':
            def neg_sharpe(weights):
                metrics = self.calculate_portfolio_metrics(weights, returns)
                return -metrics['sharpe_ratio']
            
            result = minimize(
                neg_sharpe, 
                initial_weights,
                method='SLSQP',
                bounds=bounds,
                constraints=cons
            )
            
        elif method == 'minimum_volatility':
            def portfolio_vol(weights):
                return np.sqrt(np.dot(weights.T, np.dot(returns.cov() * 252, weights)))
            
            result = minimize(
                portfolio_vol,
                initial_weights,
                method='SLSQP',
                bounds=bounds,
                constraints=cons
            )
            
        elif method == 'risk_parity':
            result = self._risk_parity_optimization(returns, bounds, cons)
            
        else:  # mean_variance
            result = self._mean_variance_optimization(
                returns, 
                target_return=0.15,
                bounds=bounds,
                constraints=cons
            )
        
        # Calculate final metrics
        optimal_weights = result.x
        metrics = self.calculate_portfolio_metrics(optimal_weights, returns)
        
        return {
            'weights': dict(zip(returns.columns, optimal_weights)),
            'metrics': metrics,
            'optimization_method': method,
            'success': result.success
        }
    
    def _risk_parity_optimization(self, returns: pd.DataFrame, 
                                 bounds: tuple, constraints: list) -> object:
        """אופטימיזציית Risk Parity"""
        def risk_parity_objective(weights):
            # Calculate portfolio volatility
            portfolio_vol = np.sqrt(np.dot(weights.T, np.dot(returns.cov() * 252, weights)))
            
            # Calculate marginal contributions to risk
            marginal_contrib = np.dot(returns.cov() * 252, weights) / portfolio_vol
            
            # Risk contributions
            contrib = weights * marginal_contrib
            
            # We want equal risk contribution
            # Minimize the sum of squared differences from equal contribution
            target_contrib = portfolio_vol / len(weights)
            return np.sum((contrib - target_contrib) ** 2)
        
        initial_weights = np.array([1/len(returns.columns)] * len(returns.columns))
        
        return minimize(
            risk_parity_objective,
            initial_weights,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints
        )
    
    def _mean_variance_optimization(self, returns: pd.DataFrame,
                                   target_return: float,
                                   bounds: tuple,
                                   constraints: list) -> object:
        """אופטימיזציית Mean-Variance"""
        # Add return constraint
        cons = constraints.copy()
        cons.append({
            'type': 'eq',
            'fun': lambda x: np.sum(returns.mean() * x) * 252 - target_return
        })
        
        def portfolio_variance(weights):
            return np.dot(weights.T, np.dot(returns.cov() * 252, weights))
        
        initial_weights = np.array([1/len(returns.columns)] * len(returns.columns))
        
        return minimize(
            portfolio_variance,
            initial_weights,
            method='SLSQP',
            bounds=bounds,
            constraints=cons
        )
    
    def efficient_frontier(self, returns: pd.DataFrame, 
                          n_points: int = 50) -> pd.DataFrame:
        """חישוב Efficient Frontier"""
        # Get min and max possible returns
        min_ret = returns.mean().min() * 252
        max_ret = returns.mean().max() * 252
        
        target_returns = np.linspace(min_ret, max_ret, n_points)
        
        results = []
        
        for target in target_returns:
            try:
                opt = self._mean_variance_optimization(
                    returns,
                    target_return=target,
                    bounds=tuple((0, 1) for _ in range(len(returns.columns))),
                    constraints=[{'type': 'eq', 'fun': lambda x: np.sum(x) - 1}]
                )
                
                if opt.success:
                    metrics = self.calculate_portfolio_metrics(opt.x, returns)
                    results.append({
                        'target_return': target,
                        'actual_return': metrics['annual_return'],
                        'volatility': metrics['annual_volatility'],
                        'sharpe_ratio': metrics['sharpe_ratio']
                    })
            except:
                continue
        
        return pd.DataFrame(results)
    
    def rebalance_recommendations(self, current_weights: Dict[str, float],
                                optimal_weights: Dict[str, float],
                                threshold: float = 0.05) -> Dict:
        """המלצות לאיזון מחדש"""
        recommendations = {
            'rebalance_needed': False,
            'trades': [],
            'total_turnover': 0
        }
        
        total_change = 0
        
        for asset in current_weights:
            current = current_weights.get(asset, 0)
            optimal = optimal_weights.get(asset, 0)
            change = optimal - current
            
            if abs(change) > threshold:
                recommendations['rebalance_needed'] = True
                
                action = 'BUY' if change > 0 else 'SELL'
                recommendations['trades'].append({
                    'asset': asset,
                    'action': action,
                    'current_weight': current,
                    'target_weight': optimal,
                    'change': change,
                    'change_percent': change * 100
                })
            
            total_change += abs(change)
        
        recommendations['total_turnover'] = total_change
        
        return recommendations
    
    def calculate_var(self, returns: pd.DataFrame, 
                     weights: np.array,
                     confidence_level: float = 0.95,
                     time_horizon: int = 1) -> Dict:
        """חישוב Value at Risk"""
        # Portfolio returns
        portfolio_returns = (returns * weights).sum(axis=1)
        
        # Historical VaR
        var_historical = np.percentile(
            portfolio_returns, 
            (1 - confidence_level) * 100
        ) * np.sqrt(time_horizon)
        
        # Parametric VaR (assuming normal distribution)
        mean_return = portfolio_returns.mean()
        std_return = portfolio_returns.std()
        
        from scipy import stats
        z_score = stats.norm.ppf(1 - confidence_level)
        var_parametric = (mean_return + z_score * std_return) * np.sqrt(time_horizon)
        
        # Conditional VaR (Expected Shortfall)
        returns_below_var = portfolio_returns[portfolio_returns <= var_historical]
        cvar = returns_below_var.mean() if len(returns_below_var) > 0 else var_historical
        
        return {
            'var_historical': var_historical,
            'var_parametric': var_parametric,
            'cvar': cvar,
            'confidence_level': confidence_level,
            'time_horizon': time_horizon
        }
    
    def stress_test(self, returns: pd.DataFrame,
                   weights: np.array,
                   scenarios: Optional[Dict] = None) -> Dict:
        """בדיקות מצוקה לתיק"""
        if scenarios is None:
            scenarios = {
                'market_crash': -0.20,      # 20% drop
                'flash_crash': -0.10,       # 10% sudden drop
                'black_swan': -0.30,        # 30% extreme event
                'volatility_spike': 2.0,    # Double volatility
                'correlation_breakdown': 1.0 # All correlations to 1
            }
        
        results = {}
        portfolio_value = 100  # Starting with $100
        
        for scenario_name, impact in scenarios.items():
            if scenario_name == 'volatility_spike':
                # Increase volatility
                stressed_returns = returns * impact
            elif scenario_name == 'correlation_breakdown':
                # Set all correlations to 1
                stressed_returns = returns.copy()
                mean_return = returns.mean(axis=1)
                for col in stressed_returns.columns:
                    stressed_returns[col] = mean_return
            else:
                # Apply percentage drop
                stressed_returns = returns * (1 + impact)
            
            # Calculate portfolio impact
            portfolio_return = (stressed_returns * weights).sum(axis=1).mean()
            new_value = portfolio_value * (1 + portfolio_return)
            loss = portfolio_value - new_value
            
            results[scenario_name] = {
                'impact': impact,
                'portfolio_loss': loss,
                'portfolio_loss_pct': (loss / portfolio_value) * 100,
                'new_portfolio_value': new_value
            }
        
        return results