import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import krakenex
import time
from datetime import datetime, timedelta
import os
import sys
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
import joblib
import json

# הוספת נתיב למודולים
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config
from modules.ai_trading_engine import AITradingEngine
from modules.autonomous_trader import EnhancedAutonomousTrader as AutonomousTrader
from modules.ml_predictor import MLPredictor
from modules.portfolio_optimizer import PortfolioOptimizer

# הגדרות עמוד משופרות
st.set_page_config(
    page_title="💎 Kraken AI Trading System", 
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'About': "Advanced AI-Powered Crypto Trading Platform v3.0"
    }
)

# CSS מקצועי עם dark mode
st.markdown("""
<style>
    /* Dark Mode Theme */
    :root {
        --bg-primary: #0e1117;
        --bg-secondary: #1a1d29;
        --bg-card: #262730;
        --text-primary: #ffffff;
        --text-secondary: #b8bcc8;
        --accent-green: #00ff88;
        --accent-red: #ff3366;
        --accent-blue: #00b4d8;
        --accent-gold: #ffd60a;
        --gradient-primary: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        --gradient-success: linear-gradient(135deg, #00ff88 0%, #00b4d8 100%);
        --gradient-danger: linear-gradient(135deg, #ff3366 0%, #ff6b6b 100%);
    }
    
    /* Main container */
    .stApp {
        background-color: var(--bg-primary);
        color: var(--text-primary);
    }
    
    /* Professional header */
    .main-header {
        background: var(--bg-secondary);
        padding: 2rem;
        border-radius: 20px;
        margin-bottom: 2rem;
        border: 1px solid rgba(255,255,255,0.1);
        position: relative;
        overflow: hidden;
    }
    
    .main-header::before {
        content: '';
        position: absolute;
        top: -50%;
        left: -50%;
        width: 200%;
        height: 200%;
        background: radial-gradient(circle, rgba(102,126,234,0.1) 0%, transparent 70%);
        animation: pulse 4s ease-in-out infinite;
    }
    
    /* Trading cards */
    .trading-card {
        background: var(--bg-card);
        border-radius: 16px;
        padding: 1.5rem;
        margin-bottom: 1rem;
        border: 1px solid rgba(255,255,255,0.1);
        transition: all 0.3s ease;
        position: relative;
        overflow: hidden;
    }
    
    .trading-card:hover {
        transform: translateY(-2px);
        border-color: var(--accent-blue);
        box-shadow: 0 8px 32px rgba(0,180,216,0.2);
    }
    
    /* Metric displays */
    .metric-display {
        background: linear-gradient(135deg, rgba(255,255,255,0.05) 0%, rgba(255,255,255,0.02) 100%);
        border-radius: 12px;
        padding: 1.2rem;
        text-align: center;
        border: 1px solid rgba(255,255,255,0.1);
    }
    
    .metric-value {
        font-size: 2.5rem;
        font-weight: 700;
        margin: 0.5rem 0;
    }
    
    .metric-label {
        font-size: 0.9rem;
        color: var(--text-secondary);
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    
    /* Price indicators */
    .price-up { color: var(--accent-green); }
    .price-down { color: var(--accent-red); }
    .price-neutral { color: var(--text-secondary); }
    
    /* Status badges */
    .status-badge {
        display: inline-block;
        padding: 0.4rem 1rem;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 600;
        margin: 0.2rem;
    }
    
    .badge-active {
        background: rgba(0,255,136,0.2);
        color: var(--accent-green);
        border: 1px solid var(--accent-green);
    }
    
    .badge-pending {
        background: rgba(255,214,10,0.2);
        color: var(--accent-gold);
        border: 1px solid var(--accent-gold);
    }
    
    .badge-error {
        background: rgba(255,51,102,0.2);
        color: var(--accent-red);
        border: 1px solid var(--accent-red);
    }
    
    /* AI status indicator */
    .ai-status {
        position: fixed;
        bottom: 2rem;
        right: 2rem;
        background: var(--bg-card);
        padding: 1rem;
        border-radius: 50px;
        display: flex;
        align-items: center;
        gap: 0.5rem;
        border: 2px solid var(--accent-green);
        z-index: 1000;
    }
    
    .ai-status-dot {
        width: 12px;
        height: 12px;
        border-radius: 50%;
        background: var(--accent-green);
        animation: pulse 2s infinite;
    }
    
    /* Animations */
    @keyframes pulse {
        0% { opacity: 1; transform: scale(1); }
        50% { opacity: 0.7; transform: scale(1.1); }
        100% { opacity: 1; transform: scale(1); }
    }
    
    @keyframes slideIn {
        from { transform: translateX(-100%); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }
    
    /* Sidebar styling */
    .css-1d391kg {
        background-color: var(--bg-secondary);
    }
    
    /* Buttons */
    .stButton > button {
        background: var(--gradient-primary);
        color: white;
        border: none;
        padding: 0.75rem 2rem;
        border-radius: 12px;
        font-weight: 600;
        transition: all 0.3s ease;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 24px rgba(102,126,234,0.4);
    }
    
    /* Tables */
    .dataframe {
        background: var(--bg-card);
        border-radius: 12px;
        overflow: hidden;
    }
    
    /* Scrollbar */
    ::-webkit-scrollbar {
        width: 10px;
        height: 10px;
    }
    
    ::-webkit-scrollbar-track {
        background: var(--bg-secondary);
    }
    
    ::-webkit-scrollbar-thumb {
        background: var(--accent-blue);
        border-radius: 5px;
    }
    
    /* Real-time indicator */
    .live-indicator {
        display: inline-flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0.5rem 1rem;
        background: rgba(0,255,136,0.1);
        border-radius: 20px;
        font-size: 0.85rem;
    }
    
    .live-dot {
        width: 8px;
        height: 8px;
        background: var(--accent-green);
        border-radius: 50%;
        animation: pulse 1s infinite;
    }
</style>
""", unsafe_allow_html=True)

class AdvancedTradingDashboard:
    """דאשבורד מסחר מתקדם עם AI"""
    
    def __init__(self):
        # אתחול מנועי AI
        self.ai_engine = AITradingEngine()
        self.auto_trader = AutonomousTrader()
        self.ml_predictor = MLPredictor()
        self.portfolio_optimizer = PortfolioOptimizer()
        
        # API connections
        self.api_key = Config.get_api_key('KRAKEN_API_KEY')
        self.api_secret = Config.get_api_key('KRAKEN_API_SECRET')
        self.api = None
        if self.api_key and self.api_secret:
            self.api = krakenex.API(self.api_key, self.api_secret)
        
        # State management
        if 'trading_active' not in st.session_state:
            st.session_state.trading_active = False
        if 'simulation_running' not in st.session_state:
            st.session_state.simulation_running = False
        if 'ai_mode' not in st.session_state:
            st.session_state.ai_mode = 'conservative'
    
    def get_portfolio_with_stablecoins(self):
        """שליפת פורטפוליו כולל USDT/USDC"""
        if not self.api:
            return pd.DataFrame(), 0, {}
            
        try:
            # שליפת יתרות
            balance_resp = self.api.query_private('Balance')
            if balance_resp.get('error'):
                st.error(f"Error: {balance_resp['error']}")
                return pd.DataFrame(), 0, {}
            
            balances = balance_resp.get('result', {})
            
            # שליפת כל המחירים
            ticker_resp = self.api.query_public('Ticker')
            prices = {}
            
            if 'result' in ticker_resp:
                for pair, info in ticker_resp['result'].items():
                    # טיפול במטבעות יציבים
                    if 'USDT' in pair and 'USD' in pair:
                        prices['USDT'] = {'price': float(info['c'][0])}
                    elif 'USDC' in pair and 'USD' in pair:
                        prices['USDC'] = {'price': float(info['c'][0])}
                    # מטבעות אחרים
                    elif 'USD' in pair:
                        symbol = self.clean_symbol(pair.replace('USD', ''))
                        if symbol not in prices:
                            prices[symbol] = {
                                'price': float(info['c'][0]),
                                'change_24h': self.safe_calculate_change(info),
                                'volume_24h': float(info.get('v', [0, 0])[1])
                            }
            
            # בניית פורטפוליו
            portfolio_data = []
            total_value = 0
            
            for asset, amount in balances.items():
                amount = float(amount)
                if amount < 0.0001:
                    continue
                    
                symbol = self.clean_symbol(asset)
                
                # טיפול במטבעות פיאט
                if symbol in ['USD', 'EUR', 'GBP']:
                    total_value += amount
                    continue
                
                # טיפול במטבעות יציבים
                if symbol in ['USDT', 'USDC', 'BUSD', 'DAI']:
                    # ברירת מחדל למטבעות יציבים היא $1
                    price = prices.get(symbol, {}).get('price', 1.0)
                    value = amount * price
                    
                    portfolio_data.append({
                        'סמל': symbol,
                        'שם': self.get_coin_name(symbol),
                        'כמות': amount,
                        'מחיר': price,
                        'שווי': value,
                        'שינוי 24ש': prices.get(symbol, {}).get('change_24h', 0),
                        'סוג': 'Stablecoin'
                    })
                    total_value += value
                    
                # מטבעות רגילים
                elif symbol in prices:
                    price_data = prices[symbol]
                    value = amount * price_data['price']
                    
                    portfolio_data.append({
                        'סמל': symbol,
                        'שם': self.get_coin_name(symbol),
                        'כמות': amount,
                        'מחיר': price_data['price'],
                        'שווי': value,
                        'שינוי 24ש': price_data.get('change_24h', 0),
                        'סוג': 'Crypto'
                    })
                    total_value += value
            
            df = pd.DataFrame(portfolio_data)
            if not df.empty:
                df = df.sort_values('שווי', ascending=False)
                df['אחוז'] = (df['שווי'] / total_value * 100)
            
            return df, total_value, balances
            
        except Exception as e:
            st.error(f"Error fetching portfolio: {e}")
            return pd.DataFrame(), 0, {}
    
    def safe_calculate_change(self, ticker_data):
        """חישוב בטוח של שינוי אחוזים"""
        try:
            current = float(ticker_data.get('c', [0])[0])
            if 'o' in ticker_data:
                open_price = float(ticker_data['o'])
                if open_price > 0:
                    return ((current - open_price) / open_price) * 100
            return 0
        except:
            return 0
    
    def clean_symbol(self, symbol):
        """ניקוי סמלי מטבעות"""
        # הסרת תווים מיוחדים
        cleaned = symbol.upper().replace('X', '').replace('Z', '')
        
        # הסרת סיומות
        if '.' in cleaned:
            cleaned = cleaned.split('.')[0]
        
        # מיפויים
        replacements = {
            'XBT': 'BTC',
            'XETH': 'ETH',
            'XXRP': 'XRP',
            'XLTC': 'LTC',
            'ZUSD': 'USD',
            'ZEUR': 'EUR',
            'USDTM': 'USDT',
            'USDCM': 'USDC'
        }
        
        return replacements.get(cleaned, cleaned)
    
    def get_coin_name(self, symbol):
        """מיפוי סמלים לשמות מלאים"""
        names = {
            'BTC': 'Bitcoin',
            'ETH': 'Ethereum',
            'USDT': 'Tether',
            'USDC': 'USD Coin',
            'XRP': 'Ripple',
            'ADA': 'Cardano',
            'SOL': 'Solana',
            'DOT': 'Polkadot',
            'MATIC': 'Polygon',
            'LINK': 'Chainlink',
            'AVAX': 'Avalanche',
            'ATOM': 'Cosmos',
            'UNI': 'Uniswap',
            'LTC': 'Litecoin',
            'BCH': 'Bitcoin Cash',
            'TRX': 'Tron',
            'XLM': 'Stellar',
            'ALGO': 'Algorand',
            'VET': 'VeChain',
            'FIL': 'Filecoin',
            'AAVE': 'Aave',
            'SAND': 'The Sandbox',
            'MANA': 'Decentraland',
            'LRC': 'Loopring',
            'CRV': 'Curve',
            'SUSHI': 'SushiSwap',
            'YFI': 'Yearn.finance',
            'COMP': 'Compound',
            'MKR': 'Maker',
            'SNX': 'Synthetix',
            'BUSD': 'Binance USD',
            'DAI': 'Dai'
        }
        return names.get(symbol, symbol)
    
    def display_header(self):
        """הצגת כותרת מקצועית"""
        st.markdown("""
        <div class="main-header">
            <h1 style="margin: 0; font-size: 2.5rem; font-weight: 800;">
                💎 Kraken AI Trading System
            </h1>
            <p style="margin: 0.5rem 0 0 0; font-size: 1.1rem; opacity: 0.9;">
                Advanced Autonomous Trading Platform with Machine Learning
            </p>
            <div class="live-indicator" style="margin-top: 1rem;">
                <div class="live-dot"></div>
                <span>LIVE TRADING</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    def display_portfolio_section(self):
        """תצוגת פורטפוליו מתקדמת"""
        st.markdown("## 💼 Portfolio Overview")
        
        # שליפת נתונים
        portfolio_df, total_value, raw_balances = self.get_portfolio_with_stablecoins()
        
        if portfolio_df.empty:
            st.warning("No portfolio data available")
            return
        
        # מטריקות ראשיות
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            st.markdown(f"""
            <div class="metric-display">
                <div class="metric-label">Total Value</div>
                <div class="metric-value price-up">${total_value:,.2f}</div>
            </div>
            """, unsafe_allow_html=True)
        
        # חישוב ערכים
        crypto_value = portfolio_df[portfolio_df['סוג'] == 'Crypto']['שווי'].sum()
        stable_value = portfolio_df[portfolio_df['סוג'] == 'Stablecoin']['שווי'].sum()
        avg_change = portfolio_df[portfolio_df['סוג'] == 'Crypto']['שינוי 24ש'].mean()
        
        with col2:
            st.markdown(f"""
            <div class="metric-display">
                <div class="metric-label">Crypto Assets</div>
                <div class="metric-value">${crypto_value:,.2f}</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            st.markdown(f"""
            <div class="metric-display">
                <div class="metric-label">Stablecoins</div>
                <div class="metric-value">${stable_value:,.2f}</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col4:
            change_class = "price-up" if avg_change > 0 else "price-down"
            st.markdown(f"""
            <div class="metric-display">
                <div class="metric-label">24h Change</div>
                <div class="metric-value {change_class}">{avg_change:+.2f}%</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col5:
            diversity = len(portfolio_df)
            st.markdown(f"""
            <div class="metric-display">
                <div class="metric-label">Assets</div>
                <div class="metric-value">{diversity}</div>
            </div>
            """, unsafe_allow_html=True)
        
        # גרפים
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # גרף עוגה אינטראקטיבי
            fig = go.Figure(data=[go.Pie(
                labels=portfolio_df['שם'],
                values=portfolio_df['שווי'],
                hole=.4,
                marker=dict(
                    colors=px.colors.sequential.Viridis,
                    line=dict(color='#000000', width=2)
                ),
                textinfo='label+percent',
                textposition='auto',
                hovertemplate='<b>%{label}</b><br>' +
                              'Value: $%{value:,.2f}<br>' +
                              'Percent: %{percent}<br>' +
                              '<extra></extra>'
            )])
            
            fig.update_layout(
                title="Portfolio Distribution",
                showlegend=True,
                height=400,
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font=dict(color='white')
            )
            
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # רשימת אחזקות
            st.markdown("### Holdings")
            for _, row in portfolio_df.iterrows():
                change_class = "price-up" if row['שינוי 24ש'] > 0 else "price-down"
                badge_class = "badge-active" if row['סוג'] == 'Crypto' else "badge-pending"
                
                st.markdown(f"""
                <div class="trading-card">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <h4 style="margin: 0;">{row['סמל']}</h4>
                            <p style="margin: 0; font-size: 0.9rem; opacity: 0.7;">{row['שם']}</p>
                        </div>
                        <span class="status-badge {badge_class}">{row['סוג']}</span>
                    </div>
                    <div style="margin-top: 1rem;">
                        <div style="display: flex; justify-content: space-between;">
                            <span>Amount:</span>
                            <span>{row['כמות']:.6f}</span>
                        </div>
                        <div style="display: flex; justify-content: space-between;">
                            <span>Price:</span>
                            <span>${row['מחיר']:,.4f}</span>
                        </div>
                        <div style="display: flex; justify-content: space-between;">
                            <span>Value:</span>
                            <span style="font-weight: bold;">${row['שווי']:,.2f}</span>
                        </div>
                        <div style="display: flex; justify-content: space-between;">
                            <span>24h:</span>
                            <span class="{change_class}">{row['שינוי 24ש']:+.2f}%</span>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
    
    def display_ai_trading_section(self):
        """סקציית מסחר אוטונומי עם AI"""
        st.markdown("## 🤖 AI Trading Engine")
        
        col1, col2, col3 = st.columns([1, 1, 1])
        
        with col1:
            # בחירת מצב AI
            ai_mode = st.selectbox(
                "AI Trading Mode",
                ["Conservative", "Balanced", "Aggressive", "Custom"],
                index=["Conservative", "Balanced", "Aggressive", "Custom"].index(
                    st.session_state.ai_mode.capitalize()
                )
            )
            st.session_state.ai_mode = ai_mode.lower()
            
            # הגדרות סיכון
            risk_level = st.slider("Risk Level", 1, 10, 5)
            max_position_size = st.number_input(
                "Max Position Size ($)",
                min_value=10,
                max_value=10000,
                value=1000,
                step=100
            )
        
        with col2:
            # אסטרטגיות AI
            st.markdown("### AI Strategies")
            
            strategies = {
                "Trend Following": st.checkbox("Trend Following", value=True),
                "Mean Reversion": st.checkbox("Mean Reversion", value=True),
                "Momentum": st.checkbox("Momentum Trading", value=False),
                "Arbitrage": st.checkbox("Arbitrage Detection", value=False),
                "Pattern Recognition": st.checkbox("Pattern Recognition", value=True),
                "Sentiment Analysis": st.checkbox("News Sentiment", value=True)
            }
            
            active_strategies = [s for s, active in strategies.items() if active]
        
        with col3:
            # סטטוס AI
            st.markdown("### AI Status")
            
            if st.session_state.trading_active:
                st.markdown("""
                <div class="trading-card" style="border-color: #00ff88;">
                    <h4 style="color: #00ff88; margin: 0;">🟢 AI ACTIVE</h4>
                    <p style="margin: 0.5rem 0;">Autonomous trading enabled</p>
                    <div style="margin-top: 1rem;">
                        <small>Mode: {}</small><br>
                        <small>Strategies: {}</small><br>
                        <small>Risk Level: {}/10</small>
                    </div>
                </div>
                """.format(
                    ai_mode,
                    len(active_strategies),
                    risk_level
                ), unsafe_allow_html=True)
            else:
                st.markdown("""
                <div class="trading-card" style="border-color: #ff3366;">
                    <h4 style="color: #ff3366; margin: 0;">🔴 AI INACTIVE</h4>
                    <p style="margin: 0.5rem 0;">Trading paused</p>
                </div>
                """, unsafe_allow_html=True)
            
            # כפתורי שליטה
            col_start, col_stop = st.columns(2)
            
            with col_start:
                if st.button("🚀 Start AI", type="primary", disabled=st.session_state.trading_active):
                    st.session_state.trading_active = True
                    self.auto_trader.start_trading(
                        mode=ai_mode,
                        risk_level=risk_level,
                        strategies=active_strategies
                    )
                    st.rerun()
            
            with col_stop:
                if st.button("🛑 Stop AI", type="secondary", disabled=not st.session_state.trading_active):
                    st.session_state.trading_active = False
                    self.auto_trader.stop_trading()
                    st.rerun()
        
        # תצוגת ביצועי AI
        if st.session_state.trading_active:
            st.markdown("### 📊 AI Performance")
            
            # סימולציה של נתוני ביצועים
            performance_data = self.ai_engine.get_performance_metrics()
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric(
                    "Today's P&L",
                    f"${performance_data.get('daily_pnl', 0):,.2f}",
                    f"{performance_data.get('daily_pnl_pct', 0):+.2f}%"
                )
            
            with col2:
                st.metric(
                    "Win Rate",
                    f"{performance_data.get('win_rate', 0):.1f}%",
                    f"{performance_data.get('win_rate_change', 0):+.1f}%"
                )
            
            with col3:
                st.metric(
                    "Total Trades",
                    performance_data.get('total_trades', 0),
                    f"+{performance_data.get('trades_today', 0)} today"
                )
            
            with col4:
                st.metric(
                    "Sharpe Ratio",
                    f"{performance_data.get('sharpe_ratio', 0):.2f}",
                    "Good" if performance_data.get('sharpe_ratio', 0) > 1 else "Low"
                )
    
    def display_ml_predictions(self):
        """תצוגת תחזיות Machine Learning"""
        st.markdown("## 🔮 ML Price Predictions")
        
        # בחירת מטבע לחיזוי
        col1, col2 = st.columns([1, 2])
        
        with col1:
            symbols = ['BTC', 'ETH', 'SOL', 'ADA', 'DOT', 'MATIC']
            selected_symbol = st.selectbox("Select Asset", symbols)
            
            timeframes = {
                "1 Hour": 1,
                "4 Hours": 4,
                "1 Day": 24,
                "1 Week": 168
            }
            selected_timeframe = st.selectbox("Prediction Timeframe", list(timeframes.keys()))
            
            if st.button("🔍 Generate Prediction", type="primary"):
                with st.spinner("Training ML model..."):
                    prediction = self.ml_predictor.predict_price(
                        selected_symbol,
                        timeframes[selected_timeframe]
                    )
                    st.session_state.last_prediction = prediction
        
        with col2:
            if hasattr(st.session_state, 'last_prediction'):
                pred = st.session_state.last_prediction
                
                # יצירת גרף חיזוי
                fig = go.Figure()
                
                # נתונים היסטוריים
                fig.add_trace(go.Scatter(
                    x=pred['historical_dates'],
                    y=pred['historical_prices'],
                    mode='lines',
                    name='Historical',
                    line=dict(color='#00b4d8', width=2)
                ))
                
                # חיזוי
                fig.add_trace(go.Scatter(
                    x=pred['prediction_dates'],
                    y=pred['predicted_prices'],
                    mode='lines+markers',
                    name='ML Prediction',
                    line=dict(color='#00ff88', width=3, dash='dash'),
                    marker=dict(size=8)
                ))
                
                # רצועת ביטחון
                fig.add_trace(go.Scatter(
                    x=pred['prediction_dates'] + pred['prediction_dates'][::-1],
                    y=pred['upper_bound'] + pred['lower_bound'][::-1],
                    fill='toself',
                    fillcolor='rgba(0,255,136,0.1)',
                    line=dict(color='rgba(255,255,255,0)'),
                    showlegend=False,
                    name='Confidence'
                ))
                
                fig.update_layout(
                    title=f"{selected_symbol} Price Prediction",
                    xaxis_title="Time",
                    yaxis_title="Price ($)",
                    hovermode='x unified',
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    font=dict(color='white'),
                    height=400
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                # מטריקות חיזוי
                col_a, col_b, col_c = st.columns(3)
                
                with col_a:
                    st.metric(
                        "Predicted Price",
                        f"${pred['target_price']:,.2f}",
                        f"{pred['price_change_pct']:+.2f}%"
                    )
                
                with col_b:
                    st.metric(
                        "Confidence",
                        f"{pred['confidence']:.1f}%",
                        "High" if pred['confidence'] > 80 else "Medium"
                    )
                
                with col_c:
                    st.metric(
                        "Model Accuracy",
                        f"{pred['model_accuracy']:.1f}%",
                        "R² Score"
                    )
    
    def display_simulations(self):
        """תצוגת סימולציות אוטומטיות"""
        st.markdown("## 🧪 Automated Simulations")
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.markdown("### Simulation Settings")
            
            # הגדרות סימולציה
            sim_capital = st.number_input(
                "Simulation Capital ($)",
                min_value=100,
                max_value=100000,
                value=10000,
                step=1000
            )
            
            sim_duration = st.slider(
                "Duration (days)",
                min_value=1,
                max_value=365,
                value=30
            )
            
            sim_strategies = st.multiselect(
                "Test Strategies",
                ["AI Combined", "Trend Following", "Mean Reversion", 
                 "Momentum", "Grid Trading", "DCA"],
                default=["AI Combined", "Trend Following"]
            )
            
            # הפעלת סימולציה
            if st.button("🚀 Run Simulations", type="primary"):
                st.session_state.simulation_running = True
                
                with st.spinner("Running simulations..."):
                    results = self.run_batch_simulations(
                        capital=sim_capital,
                        duration=sim_duration,
                        strategies=sim_strategies
                    )
                    st.session_state.sim_results = results
                    st.session_state.simulation_running = False
                    st.success("Simulations completed!")
        
        with col2:
            if hasattr(st.session_state, 'sim_results'):
                st.markdown("### Simulation Results")
                
                results = st.session_state.sim_results
                
                # תצוגת תוצאות
                fig = go.Figure()
                
                for strategy, data in results.items():
                    fig.add_trace(go.Scatter(
                        x=data['dates'],
                        y=data['portfolio_values'],
                        mode='lines',
                        name=strategy,
                        line=dict(width=2)
                    ))
                
                fig.update_layout(
                    title="Strategy Performance Comparison",
                    xaxis_title="Date",
                    yaxis_title="Portfolio Value ($)",
                    hovermode='x unified',
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    font=dict(color='white'),
                    height=400
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                # טבלת ביצועים
                performance_df = pd.DataFrame([
                    {
                        'Strategy': strategy,
                        'Final Value': f"${data['final_value']:,.2f}",
                        'Total Return': f"{data['total_return']:.2f}%",
                        'Sharpe Ratio': f"{data['sharpe_ratio']:.2f}",
                        'Max Drawdown': f"{data['max_drawdown']:.2f}%",
                        'Win Rate': f"{data['win_rate']:.1f}%"
                    }
                    for strategy, data in results.items()
                ])
                
                st.dataframe(
                    performance_df,
                    use_container_width=True,
                    hide_index=True
                )
    
    def display_market_analysis(self):
        """ניתוח שוק מתקדם"""
        st.markdown("## 📈 Advanced Market Analysis")
        
        # Market indicators
        col1, col2, col3, col4 = st.columns(4)
        
        # Fear & Greed Index (סימולציה)
        fear_greed = np.random.randint(20, 80)
        
        with col1:
            color = "#00ff88" if fear_greed > 50 else "#ff3366"
            st.markdown(f"""
            <div class="metric-display">
                <div class="metric-label">Fear & Greed Index</div>
                <div class="metric-value" style="color: {color};">{fear_greed}</div>
                <div style="font-size: 0.9rem; opacity: 0.7;">
                    {"Greed" if fear_greed > 50 else "Fear"}
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        # Market Cap
        with col2:
            st.markdown("""
            <div class="metric-display">
                <div class="metric-label">Total Market Cap</div>
                <div class="metric-value">$2.1T</div>
                <div style="font-size: 0.9rem; color: #00ff88;">+3.2%</div>
            </div>
            """, unsafe_allow_html=True)
        
        # BTC Dominance
        with col3:
            st.markdown("""
            <div class="metric-display">
                <div class="metric-label">BTC Dominance</div>
                <div class="metric-value">48.5%</div>
                <div style="font-size: 0.9rem; color: #ff3366;">-0.8%</div>
            </div>
            """, unsafe_allow_html=True)
        
        # Volume
        with col4:
            st.markdown("""
            <div class="metric-display">
                <div class="metric-label">24h Volume</div>
                <div class="metric-value">$89B</div>
                <div style="font-size: 0.9rem; color: #00ff88;">+12.5%</div>
            </div>
            """, unsafe_allow_html=True)
        
        # Market Heatmap
        st.markdown("### 🔥 Market Heatmap")
        
        # יצירת נתוני heatmap
        symbols = ['BTC', 'ETH', 'BNB', 'XRP', 'ADA', 'SOL', 'DOT', 'DOGE', 
                   'AVAX', 'MATIC', 'LINK', 'UNI', 'ATOM', 'LTC', 'BCH']
        
        heatmap_data = []
        for symbol in symbols:
            heatmap_data.append({
                'symbol': symbol,
                '1h': np.random.uniform(-5, 5),
                '24h': np.random.uniform(-10, 10),
                '7d': np.random.uniform(-20, 20),
                '30d': np.random.uniform(-30, 30),
                'volume': np.random.uniform(100, 1000)
            })
        
        heatmap_df = pd.DataFrame(heatmap_data)
        
        # יצירת heatmap
        fig = go.Figure(data=go.Heatmap(
            z=[heatmap_df['1h'], heatmap_df['24h'], heatmap_df['7d'], heatmap_df['30d']],
            x=heatmap_df['symbol'],
            y=['1 Hour', '24 Hours', '7 Days', '30 Days'],
            colorscale='RdYlGn',
            zmid=0,
            text=[[f"{v:.1f}%" for v in row] for row in 
                  [heatmap_df['1h'], heatmap_df['24h'], heatmap_df['7d'], heatmap_df['30d']]],
            texttemplate='%{text}',
            textfont={"size": 10},
            showscale=True,
            colorbar=dict(
                title=dict(
                    text="Change %",
                    side="right"
                ),
                tickmode="linear",
                tick0=-30,
                dtick=10
            )
        ))
        
        fig.update_layout(
            title="Price Change Heatmap",
            xaxis_title="Assets",
            yaxis_title="Timeframe",
            height=300,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='white')
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    def run_batch_simulations(self, capital, duration, strategies):
        """הרצת סימולציות מרובות"""
        results = {}
        
        for strategy in strategies:
            # סימולציה של תוצאות (במציאות יש להריץ סימולציה אמיתית)
            dates = pd.date_range(start='today', periods=duration, freq='D')
            
            # יצירת נתונים אקראיים לדוגמה
            returns = np.random.normal(0.002, 0.02, duration)
            portfolio_values = [capital]
            
            for r in returns:
                portfolio_values.append(portfolio_values[-1] * (1 + r))
            
            final_value = portfolio_values[-1]
            total_return = ((final_value - capital) / capital) * 100
            
            # חישוב מטריקות
            returns_series = pd.Series(returns)
            sharpe_ratio = (returns_series.mean() / returns_series.std()) * np.sqrt(252)
            max_drawdown = ((pd.Series(portfolio_values).cummax() - pd.Series(portfolio_values)) / 
                           pd.Series(portfolio_values).cummax()).max() * 100
            win_rate = (returns_series > 0).sum() / len(returns_series) * 100
            
            results[strategy] = {
                'dates': dates,
                'portfolio_values': portfolio_values[1:],
                'final_value': final_value,
                'total_return': total_return,
                'sharpe_ratio': sharpe_ratio,
                'max_drawdown': max_drawdown,
                'win_rate': win_rate
            }
        
        return results
    
    def display_ai_status_indicator(self):
        """מחוון סטטוס AI"""
        if st.session_state.trading_active:
            st.markdown("""
            <div class="ai-status">
                <div class="ai-status-dot"></div>
                <span style="font-weight: 600;">AI Trading Active</span>
            </div>
            """, unsafe_allow_html=True)

def main():
    dashboard = AdvancedTradingDashboard()
    
    # Header
    dashboard.display_header()
    
    # Sidebar
    with st.sidebar:
        st.markdown("## 🎛️ Control Panel")
        
        page = st.radio(
            "Navigation",
            ["📊 Dashboard", "💼 Portfolio", "🤖 AI Trading", 
             "🔮 ML Predictions", "🧪 Simulations", "📈 Market Analysis"],
            index=0
        )
        
        st.markdown("---")
        
        # Quick Stats
        st.markdown("### 📊 Quick Stats")
        
        # API Status
        if dashboard.api:
            st.success("✅ Kraken API Connected")
        else:
            st.error("❌ API Not Connected")
        
        # AI Status
        if st.session_state.trading_active:
            st.success("✅ AI Trading Active")
        else:
            st.info("⏸️ AI Trading Paused")
        
        # Time
        st.caption(f"Last Update: {datetime.now().strftime('%H:%M:%S')}")
        
        # Settings
        st.markdown("---")
        st.markdown("### ⚙️ Settings")
        
        auto_refresh = st.checkbox("Auto Refresh (30s)", value=True)
        dark_mode = st.checkbox("Dark Mode", value=True)
        
        if auto_refresh:
            time.sleep(30)
            st.rerun()
    
    # Main content based on selection
    if page == "📊 Dashboard":
        # Overview dashboard
        col1, col2 = st.columns([2, 1])
        
        with col1:
            dashboard.display_portfolio_section()
        
        with col2:
            dashboard.display_market_analysis()
        
        st.markdown("---")
        dashboard.display_ai_trading_section()
        
    elif page == "💼 Portfolio":
        dashboard.display_portfolio_section()
        
    elif page == "🤖 AI Trading":
        dashboard.display_ai_trading_section()
        
    elif page == "🔮 ML Predictions":
        dashboard.display_ml_predictions()
        
    elif page == "🧪 Simulations":
        dashboard.display_simulations()
        
    elif page == "📈 Market Analysis":
        dashboard.display_market_analysis()
    
    # AI Status Indicator
    dashboard.display_ai_status_indicator()

if __name__ == "__main__":
    main()