import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import krakenex
import numpy as np
from datetime import datetime
import time
import os
import sys
import threading
import queue

# הוספת נתיב למודולים
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config

# בדיקת זמינות WebSocket
try:
    from modules.market_collector import HybridMarketCollector, RealTimePriceUpdate
    WEBSOCKET_AVAILABLE = True
except ImportError:
    WEBSOCKET_AVAILABLE = False
    from modules.market_collector import MarketCollector

# הגדרת עמוד
st.set_page_config(
    page_title="💎 Kraken Portfolio Dashboard", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

# CSS פשוט עם אינדיקטור WebSocket
st.markdown("""
<style>
    .big-font {
        font-size: 24px !important;
        font-weight: bold;
    }
    .medium-font {
        font-size: 18px !important;
    }
    .green {
        color: #00ff88;
    }
    .red {
        color: #ff3366;
    }
    .websocket-indicator {
        position: fixed;
        bottom: 20px;
        right: 20px;
        background: #1e1e1e;
        border: 2px solid #00ff88;
        border-radius: 20px;
        padding: 10px 20px;
        display: flex;
        align-items: center;
        gap: 10px;
        z-index: 1000;
    }
    .ws-dot {
        width: 10px;
        height: 10px;
        border-radius: 50%;
        background: #00ff88;
        animation: pulse 2s infinite;
    }
    @keyframes pulse {
        0% { opacity: 1; }
        50% { opacity: 0.5; }
        100% { opacity: 1; }
    }
</style>
""", unsafe_allow_html=True)

class KrakenDashboard:
    def __init__(self):
        self.api = None
        if Config.get_api_key('KRAKEN_API_KEY') and Config.get_api_key('KRAKEN_API_SECRET'):
            self.api = krakenex.API(Config.get_api_key('KRAKEN_API_KEY'), Config.get_api_key('KRAKEN_API_SECRET'))
        
        # WebSocket support
        self.use_websocket = WEBSOCKET_AVAILABLE and os.getenv('HYBRID_MODE', 'false').lower() == 'true'
        self.hybrid_collector = None
        self.price_queue = queue.Queue()
        
        # אתחול WebSocket אם זמין
        if self.use_websocket and 'ws_collector' not in st.session_state:
            self._init_websocket()
    
    def _init_websocket(self):
        """אתחול WebSocket collector"""
        try:
            symbols = ['BTC', 'ETH', 'SOL', 'ADA', 'DOT']
            self.hybrid_collector = HybridMarketCollector(
                symbols=symbols,
                api_key=Config.get_api_key('KRAKEN_API_KEY'),
                api_secret=Config.get_api_key('KRAKEN_API_SECRET')
            )
            
            # הוספת callback
            def on_price_update(update: RealTimePriceUpdate):
                self.price_queue.put(update)
            
            self.hybrid_collector.add_data_callback(on_price_update)
            
            # התחלה בthread נפרד
            thread = threading.Thread(target=self.hybrid_collector.start, daemon=True)
            thread.start()
            
            st.session_state.ws_collector = self.hybrid_collector
            st.session_state.ws_active = True
            
        except Exception as e:
            st.error(f"Failed to initialize WebSocket: {e}")
            self.use_websocket = False
    
    def clean_symbol(self, symbol):
        """ניקוי סמלי מטבעות"""
        cleaned = symbol.upper().replace('X', '').replace('Z', '')
        if '.' in cleaned:
            cleaned = cleaned.split('.')[0]
        
        replacements = {
            'XBT': 'BTC', 'XETH': 'ETH', 'XXRP': 'XRP',
            'XLTC': 'LTC', 'ZUSD': 'USD', 'ZEUR': 'EUR',
            'USDTM': 'USDT', 'USDCM': 'USDC'
        }
        
        for old, new in replacements.items():
            if cleaned.startswith(old):
                return new
                
        return cleaned
    
    def get_websocket_prices(self):
        """קבלת מחירים מ-WebSocket"""
        if not self.use_websocket or not st.session_state.get('ws_collector'):
            return {}
        
        try:
            return st.session_state.ws_collector.get_latest_prices()
        except:
            return {}
    
    def get_portfolio_data(self):
        """שליפת נתוני פורטפוליו עם תמיכת WebSocket"""
        if not self.api:
            return None, None, None
        
        try:
            # יתרות
            balance_resp = self.api.query_private('Balance')
            if balance_resp.get('error'):
                st.error(f"Error: {balance_resp['error']}")
                return None, None, None
            
            balances = balance_resp.get('result', {})
            
            # מחירים - העדפה ל-WebSocket
            ws_prices = self.get_websocket_prices() if self.use_websocket else {}
            
            # HTTP fallback for missing prices
            ticker_resp = self.api.query_public('Ticker')
            
            # עיבוד נתונים
            portfolio = []
            total_value_usd = 0
            prices = {}
            
            # עיבוד מחירים
            if 'result' in ticker_resp:
                for pair, info in ticker_resp['result'].items():
                    if 'USD' in pair:
                        symbol = self.clean_symbol(pair.replace('USD', '').replace('ZUSD', ''))
                        
                        # בדיקה אם יש מחיר WebSocket עדכני יותר
                        if symbol in ws_prices:
                            ws_data = ws_prices[symbol]
                            prices[symbol] = {
                                'price': ws_data.price,
                                'change_24h': ws_data.change_24h_pct,
                                'source': 'websocket'
                            }
                        elif symbol not in prices:
                            try:
                                current = float(info['c'][0])
                                open_price = float(info.get('o', current))
                                change = ((current - open_price) / open_price * 100) if open_price > 0 else 0
                                
                                prices[symbol] = {
                                    'price': current,
                                    'change_24h': change,
                                    'source': 'http'
                                }
                            except:
                                continue
            
            # עיבוד יתרות
            for asset, amount in balances.items():
                amount = float(amount)
                if amount < 0.0001:
                    continue
                
                symbol = self.clean_symbol(asset)
                
                # פיאט
                if symbol in ['USD', 'EUR', 'GBP']:
                    total_value_usd += amount
                    continue
                
                # קריפטו
                price_info = prices.get(symbol, {'price': 1.0 if symbol in ['USDT', 'USDC'] else 0})
                price = price_info['price']
                
                if price > 0:
                    value = amount * price
                    portfolio.append({
                        'Symbol': symbol,
                        'Amount': amount,
                        'Price': price,
                        'Value': value,
                        'Change': price_info.get('change_24h', 0),
                        'Source': price_info.get('source', 'unknown')
                    })
                    total_value_usd += value
            
            # מיון וחישוב אחוזים
            if portfolio:
                df = pd.DataFrame(portfolio).sort_values('Value', ascending=False)
                df['Percentage'] = (df['Value'] / total_value_usd * 100)
                return df, total_value_usd, prices
            
            return pd.DataFrame(), total_value_usd, prices
            
        except Exception as e:
            st.error(f"Error: {str(e)}")
            return None, None, None

def main():
    st.title("💎 Kraken Portfolio Dashboard")
    
    # הוספת אינדיקטור WebSocket
    if WEBSOCKET_AVAILABLE and st.session_state.get('ws_active'):
        st.markdown("""
        <div class="websocket-indicator">
            <div class="ws-dot"></div>
            <span style="color: #00ff88; font-weight: bold;">WebSocket LIVE</span>
        </div>
        """, unsafe_allow_html=True)
    
    dashboard = KrakenDashboard()
    
    # בדיקת חיבור
    if not dashboard.api:
        st.error("❌ No API connection. Please set KRAKEN_API_KEY and KRAKEN_API_SECRET environment variables.")
        st.stop()
    
    # כפתור רענון עם auto-refresh option
    col1, col2, col3 = st.columns([1, 1, 4])
    with col1:
        if st.button("🔄 Refresh", type="primary"):
            st.cache_data.clear()
            st.rerun()
    
    with col2:
        auto_refresh = st.checkbox("Auto refresh", value=dashboard.use_websocket)
        if auto_refresh and not dashboard.use_websocket:
            st_autorefresh(interval=5000, key="auto_refresh")
    
    # שליפת נתונים
    with st.spinner("Loading portfolio data..."):
        portfolio_df, total_value, prices = dashboard.get_portfolio_data()
    
    if portfolio_df is None:
        st.stop()
    
    # מטריקות ראשיות עם אינדיקטור מקור
    st.markdown("## 📊 Portfolio Overview")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Value", f"${total_value:,.2f}")
    
    with col2:
        num_assets = len(portfolio_df) if not portfolio_df.empty else 0
        st.metric("Assets", num_assets)
    
    with col3:
        if not portfolio_df.empty:
            avg_change = portfolio_df['Change'].mean()
            st.metric("Avg 24h Change", f"{avg_change:+.2f}%", delta=f"{avg_change:+.2f}%")
        else:
            st.metric("Avg 24h Change", "0%")
    
    with col4:
        if not portfolio_df.empty:
            top_asset = portfolio_df.iloc[0]['Symbol']
            st.metric("Top Asset", top_asset)
        else:
            st.metric("Top Asset", "N/A")
    
    # תצוגת פורטפוליו עם אינדיקטור מקור נתונים
    if not portfolio_df.empty:
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.markdown("### 💰 Holdings")
            
            # הוספת עמודת מקור נתונים
            display_df = portfolio_df.copy()
            
            # אייקון לפי מקור
            display_df['📡'] = display_df['Source'].apply(
                lambda x: '⚡' if x == 'websocket' else '📊'
            )
            
            display_df['Price'] = display_df['Price'].apply(lambda x: f"${x:,.4f}")
            display_df['Value'] = display_df['Value'].apply(lambda x: f"${x:,.2f}")
            display_df['Amount'] = display_df['Amount'].apply(lambda x: f"{x:.6f}")
            display_df['Percentage'] = display_df['Percentage'].apply(lambda x: f"{x:.1f}%")
            display_df['Change'] = display_df['Change'].apply(lambda x: f"{x:+.2f}%")
            
            # הסרת עמודת Source המקורית
            display_df = display_df.drop('Source', axis=1)
            
            st.dataframe(
                display_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "📡": st.column_config.TextColumn(
                        "Source",
                        help="⚡ = WebSocket (Real-time), 📊 = HTTP"
                    ),
                    "Change": st.column_config.TextColumn(
                        "24h Change",
                        help="24 hour price change"
                    )
                }
            )
            
            # הוספת מקרא
            st.caption("⚡ = Real-time WebSocket data | 📊 = HTTP data")
        
        with col2:
            st.markdown("### 📊 Distribution")
            
            # Pie chart
            fig = px.pie(
                portfolio_df,
                values='Value',
                names='Symbol',
                hole=0.4,
                color_discrete_sequence=px.colors.sequential.Viridis
            )
            
            fig.update_traces(
                textposition='inside',
                textinfo='percent+label',
                hovertemplate='<b>%{label}</b><br>Value: $%{value:,.2f}<br>Percent: %{percent}<extra></extra>'
            )
            
            fig.update_layout(
                showlegend=True,
                height=400,
                margin=dict(l=0, r=0, t=0, b=0)
            )
            
            st.plotly_chart(fig, use_container_width=True)
    
    # נתוני שוק עם WebSocket
    st.markdown("## 📈 Market Prices")
    
    if dashboard.use_websocket:
        ws_prices = dashboard.get_websocket_prices()
        if ws_prices:
            st.markdown("### ⚡ Real-Time WebSocket Feed")
            
            # יצירת DataFrame מנתוני WebSocket
            ws_data = []
            for symbol, update in ws_prices.items():
                ws_data.append({
                    'Symbol': symbol,
                    'Price': f"${update.price:,.2f}",
                    'Change 24h': f"{update.change_24h_pct:+.2f}%",
                    'Bid': f"${update.bid:,.2f}",
                    'Ask': f"${update.ask:,.2f}",
                    'Volume': f"{update.volume:,.0f}",
                    'Last Update': update.timestamp.strftime('%H:%M:%S')
                })
            
            if ws_data:
                ws_df = pd.DataFrame(ws_data)
                st.dataframe(ws_df, use_container_width=True, hide_index=True)
    
    # פוטר עם סטטיסטיקות
    st.markdown("---")
    
    if dashboard.use_websocket and st.session_state.get('ws_collector'):
        stats = st.session_state.ws_collector.get_statistics()
        st.caption(
            f"Last update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | "
            f"WebSocket: {stats.get('websocket_status', 'N/A')} | "
            f"Updates: {stats.get('total_updates', 0)} | "
            f"Mode: {'⚡ Hybrid' if dashboard.use_websocket else '📊 HTTP'}"
        )
    else:
        st.caption(f"Last update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Mode: 📊 HTTP Only")

# Auto refresh for non-websocket mode
try:
    from streamlit_autorefresh import st_autorefresh
except ImportError:
    def st_autorefresh(interval, key):
        pass

if __name__ == "__main__":
    main()