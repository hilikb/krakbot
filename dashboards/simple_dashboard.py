import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import krakenex
import numpy as np
from datetime import datetime
import time
import os

# הגדרות בסיסיות
KRAKEN_API_KEY = os.getenv('KRAKEN_API_KEY', '')
KRAKEN_API_SECRET = os.getenv('KRAKEN_API_SECRET', '')

# הגדרת עמוד
st.set_page_config(
    page_title="💎 Kraken Portfolio Dashboard", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

# CSS פשוט
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
</style>
""", unsafe_allow_html=True)

class KrakenDashboard:
    def __init__(self):
        self.api = None
        if KRAKEN_API_KEY and KRAKEN_API_SECRET:
            self.api = krakenex.API(KRAKEN_API_KEY, KRAKEN_API_SECRET)
    
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
    
    @st.cache_data(ttl=60)
    def get_portfolio_data(_self):
        """שליפת נתוני פורטפוליו"""
        if not _self.api:
            return None, None, None
        
        try:
            # יתרות
            balance_resp = _self.api.query_private('Balance')
            if balance_resp.get('error'):
                st.error(f"Error: {balance_resp['error']}")
                return None, None, None
            
            balances = balance_resp.get('result', {})
            
            # מחירים
            ticker_resp = _self.api.query_public('Ticker')
            
            # עיבוד נתונים
            portfolio = []
            total_value_usd = 0
            prices = {}
            
            # עיבוד מחירים
            if 'result' in ticker_resp:
                for pair, info in ticker_resp['result'].items():
                    if 'USD' in pair:
                        symbol = _self.clean_symbol(pair.replace('USD', '').replace('ZUSD', ''))
                        if symbol not in prices:
                            try:
                                current = float(info['c'][0])
                                open_price = float(info.get('o', current))
                                change = ((current - open_price) / open_price * 100) if open_price > 0 else 0
                                
                                prices[symbol] = {
                                    'price': current,
                                    'change_24h': change
                                }
                            except:
                                continue
            
            # עיבוד יתרות
            for asset, amount in balances.items():
                amount = float(amount)
                if amount < 0.0001:
                    continue
                
                symbol = _self.clean_symbol(asset)
                
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
                        'Change': price_info.get('change_24h', 0)
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
    
    dashboard = KrakenDashboard()
    
    # בדיקת חיבור
    if not dashboard.api:
        st.error("❌ No API connection. Please set KRAKEN_API_KEY and KRAKEN_API_SECRET environment variables.")
        st.stop()
    
    # כפתור רענון
    col1, col2, col3 = st.columns([1, 1, 4])
    with col1:
        if st.button("🔄 Refresh", type="primary"):
            st.cache_data.clear()
            st.rerun()
    
    # שליפת נתונים
    with st.spinner("Loading portfolio data..."):
        portfolio_df, total_value, prices = dashboard.get_portfolio_data()
    
    if portfolio_df is None:
        st.stop()
    
    # מטריקות ראשיות
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
    
    # תצוגת פורטפוליו
    if not portfolio_df.empty:
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.markdown("### 💰 Holdings")
            
            # עיצוב טבלה
            display_df = portfolio_df.copy()
            display_df['Price'] = display_df['Price'].apply(lambda x: f"${x:,.4f}")
            display_df['Value'] = display_df['Value'].apply(lambda x: f"${x:,.2f}")
            display_df['Amount'] = display_df['Amount'].apply(lambda x: f"{x:.6f}")
            display_df['Percentage'] = display_df['Percentage'].apply(lambda x: f"{x:.1f}%")
            display_df['Change'] = display_df['Change'].apply(lambda x: f"{x:+.2f}%")
            
            st.dataframe(
                display_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Change": st.column_config.TextColumn(
                        "24h Change",
                        help="24 hour price change"
                    )
                }
            )
        
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
    
    # נתוני שוק
    st.markdown("## 📈 Market Prices")
    
    if prices:
        # המרה למטריצה לheatmap
        price_data = []
        symbols = []
        
        for symbol, data in sorted(prices.items())[:15]:  # Top 15
            if symbol not in ['USD', 'EUR', 'GBP']:
                symbols.append(symbol)
                price_data.append([data.get('change_24h', 0)])
        
        if price_data:
            # Heatmap
            fig = go.Figure(data=go.Heatmap(
                z=price_data,
                x=['24h Change'],
                y=symbols,
                colorscale='RdYlGn',
                zmid=0,
                text=[[f"{val:.2f}%" for val in row] for row in price_data],
                texttemplate='%{text}',
                showscale=True,
                colorbar=dict(
                    title="Change %",
                    ticksuffix="%"
                )
            ))
            
            fig.update_layout(
                title="Market Changes (24h)",
                height=400,
                xaxis_title="",
                yaxis_title="Asset"
            )
            
            st.plotly_chart(fig, use_container_width=True)
    
    # פוטר
    st.markdown("---")
    st.caption(f"Last update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Kraken Portfolio Dashboard v1.0")

if __name__ == "__main__":
    main()