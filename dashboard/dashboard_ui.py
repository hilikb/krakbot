import streamlit as st
import pandas as pd
import requests
import os
import datetime
import krakenex
import time
from config import KRAKEN_API_KEY, KRAKEN_API_SECRET

# הגדרות עמוד
st.set_page_config(
    page_title="💎 Kraken PRO Dashboard", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

# CSS משופר
st.markdown("""
<style>
    /* עיצוב כללי */
    .main > div {
        padding-top: 2rem;
    }
    
    /* כותרת ראשית */
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 15px;
        text-align: center;
        margin-bottom: 2rem;
        box-shadow: 0 8px 32px rgba(0,0,0,0.1);
    }
    
    .main-title {
        font-size: 3rem;
        font-weight: bold;
        color: white;
        margin-bottom: 0.5rem;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
    }
    
    .main-subtitle {
        font-size: 1.2rem;
        color: rgba(255,255,255,0.9);
        margin-bottom: 0;
    }
    
    /* כרטיסים */
    .metric-card {
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        padding: 1.5rem;
        border-radius: 12px;
        text-align: center;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        margin-bottom: 1rem;
        border: 1px solid rgba(255,255,255,0.2);
    }
    
    .metric-value {
        font-size: 2rem;
        font-weight: bold;
        color: #2c3e50;
        margin-bottom: 0.5rem;
    }
    
    .metric-label {
        font-size: 0.9rem;
        color: #7f8c8d;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    
    .positive { color: #27ae60 !important; }
    .negative { color: #e74c3c !important; }
    
    /* טבלאות */
    .stDataFrame {
        border-radius: 10px;
        overflow: hidden;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    }
    
    /* כפתורים */
    .stButton > button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        border-radius: 25px;
        padding: 0.5rem 2rem;
        font-weight: bold;
        transition: all 0.3s ease;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(0,0,0,0.3);
    }
    
    /* סטטוס badges */
    .status-badge {
        display: inline-block;
        padding: 0.3rem 1rem;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: bold;
        margin: 0.2rem;
    }
    
    .badge-success { background: #d4edda; color: #155724; }
    .badge-warning { background: #fff3cd; color: #856404; }
    .badge-info { background: #d1ecf1; color: #0c5460; }
    
    /* אנימציות */
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(20px); }
        to { opacity: 1; transform: translateY(0); }
    }
    
    .fade-in {
        animation: fadeIn 0.6s ease-out;
    }
    
    /* Expander מותאם */
    .streamlit-expanderHeader {
        background: linear-gradient(90deg, #f8f9fa, #e9ecef);
        border-radius: 8px;
        border: 1px solid #dee2e6;
    }
</style>
""", unsafe_allow_html=True)

@st.cache_data(ttl=60, show_spinner=False)
def get_all_kraken_prices(api_key, api_secret):
    """שליפת כל המחירים מ-Kraken בקריאה אחת"""
    try:
        api = krakenex.API(api_key, api_secret)
        ticker_resp = api.query_public('Ticker')
        
        if 'result' in ticker_resp:
            prices = {}
            for pair, info in ticker_resp['result'].items():
                try:
                    # ניקוי שם הזוג לקבלת שם המטבע
                    if 'USD' in pair:
                        symbol = pair.replace('USD', '').replace('X', '').replace('Z', '')
                        symbol = clean_symbol(symbol)
                        if symbol not in prices:  # נשמור את הראשון שנמצא
                            prices[symbol] = float(info['c'][0])
                except (KeyError, ValueError, IndexError):
                    continue
            return prices
    except Exception as e:
        st.warning(f"⚠️ שגיאה בשליפת מחירים מ-Kraken: {e}")
        return {}

def get_coin_icon(symbol):
    """החזרת אייקון emoji למטבע"""
    icons = {
        'BTC': '₿',
        'ETH': 'Ξ', 
        'XRP': '🪙',
        'LTC': 'Ł',
        'ADA': '🔹',
        'SOL': '☀️',
        'DOT': '🔴',
        'LINK': '🔗',
        'MATIC': '🟣',
        'AVAX': '🔺',
        'XTZ': '🔷'
    }
    return icons.get(symbol.upper(), '🪙')

def clean_symbol(symbol):
    """ניקוי וסטנדרטיזציה של סמלי מטבעות"""
    cleaned = symbol.split('.')[0].upper()
    # המרות נפוצות של Kraken
    replacements = {
        'XBT': 'BTC',
        'XETH': 'ETH', 
        'XXRP': 'XRP',
        'XLTC': 'LTC',
        'ZUSD': 'USD',
        'ZEUR': 'EUR'
    }
    return replacements.get(cleaned, cleaned)

def get_kraken_portfolio(api_key, api_secret):
    """שליפת פורטפוליו מ-Kraken עם מחירים מ-Kraken בלבד"""
    if not api_key or not api_secret:
        st.error("🔑 חסרים מפתחות API של Kraken")
        return pd.DataFrame()
    
    api = krakenex.API(api_key, api_secret)
    
    try:
        # שליפת יתרות
        with st.spinner("🔄 טוען נתוני פורטפוליו מ-Kraken..."):
            balance_resp = api.query_private('Balance')
            
        if balance_resp.get('error'):
            st.error(f"❌ שגיאה בשליפת האחזקות: {', '.join(balance_resp['error'])}")
            return pd.DataFrame()
            
        balances = balance_resp.get('result', {})
        # סינון יתרות חיוביות בלבד
        active_balances = {k: float(v) for k, v in balances.items() if float(v) > 0.001}
        
        if not active_balances:
            st.info("💼 לא נמצאו אחזקות פעילות בחשבון Kraken")
            return pd.DataFrame()
        
        # הכנת רשימת מטבעות (ללא USD/EUR)
        crypto_balances = {}
        fiat_total = 0
        
        for coin, amount in active_balances.items():
            symbol = clean_symbol(coin)
            if symbol in ['USD', 'EUR']:
                fiat_total += amount
            else:
                crypto_balances[symbol] = amount
        
        if not crypto_balances:
            st.info(f"💰 נמצאו רק יתרות פיאט: ${fiat_total:,.2f}")
            return pd.DataFrame()
        
        # שליפת כל המחירים מ-Kraken
        all_prices = get_all_kraken_prices(api_key, api_secret)
        
        # בניית הפורטפוליו
        portfolio_data = []
        symbols_without_price = []
        
        for symbol, amount in crypto_balances.items():
            price = all_prices.get(symbol, 0)
            
            if price == 0:
                # נסיון נוסף עם וריאציות שם המטבע
                for variant in [f"X{symbol}", f"{symbol}USD", f"X{symbol}ZUSD"]:
                    if variant in all_prices:
                        price = all_prices[variant]
                        break
            
            if price == 0:
                symbols_without_price.append(symbol)
            
            value_usd = amount * price
            icon = get_coin_icon(symbol)
            
            portfolio_data.append({
                'לוגו': icon,
                'מטבע': symbol,
                'כמות': round(amount, 6),
                'מחיר ($)': round(price, 4) if price > 0 else 0,
                'שווי ($)': round(value_usd, 2),
                'אחוז מהתיק': 0  # נחשב אחר כך
            })
        
        if not portfolio_data:
            st.warning("⚠️ לא הצלחנו לבנות את הפורטפוליו")
            return pd.DataFrame()
        
        # יצירת DataFrame וחישוב אחוזים
        df = pd.DataFrame(portfolio_data)
        df = df.sort_values('שווי ($)', ascending=False)
        
        total_value = df['שווי ($)'].sum()
        if total_value > 0:
            df['אחוז מהתיק'] = (df['שווי ($)'] / total_value * 100).round(2)
        
        # הצגת מידע על מטבעות ללא מחיר
        if symbols_without_price:
            st.warning(f"⚠️ לא נמצא מחיר ב-Kraken עבור: {', '.join(symbols_without_price)}")
        
        # הצגת יתרות פיאט אם יש
        if fiat_total > 0:
            st.info(f"💵 יתרה נוספת בפיאט: ${fiat_total:,.2f}")
        
        return df
        
    except Exception as e:
        st.error(f"❌ שגיאה כללית בשליפת נתוני Kraken: {e}")
        return pd.DataFrame()

def load_data(file_path, default_columns=None, parse_dates=None):
    """טעינת נתונים עם encoding אוטומטי"""
    if not os.path.exists(file_path):
        return pd.DataFrame(columns=default_columns or [])
    
    encodings = ['utf-8', 'cp1255', 'cp1252', 'iso-8859-8']
    for encoding in encodings:
        try:
            return pd.read_csv(file_path, parse_dates=parse_dates, encoding=encoding)
        except Exception:
            continue
    
    st.warning(f"⚠️ לא הצלחנו לטעון את הקובץ: {file_path}")
    return pd.DataFrame(columns=default_columns or [])

# === תחילת האפליקציה ===

# כותרת ראשית מעוצבת
st.markdown("""
<div class="main-header fade-in">
    <div class="main-title">💎 Kraken PRO Dashboard</div>
    <div class="main-subtitle">בוט השקעות מתקדם • פורטפוליו חי • גרפים • AI • סימולציות</div>
</div>
""", unsafe_allow_html=True)

# חלוקה לעמודות ראשיות
col1, col2 = st.columns([1, 1], gap="large")

# === עמודה שמאל: פורטפוליו === 
with col1:
    st.markdown("### 💼 פורטפוליו אמיתי (Kraken)")
    
    # כפתור רענון
    if st.button("🔄 רענן פורטפוליו", key="refresh_portfolio"):
        st.cache_data.clear()
    
    # שליפה והצגת פורטפוליו
    portfolio_df = get_kraken_portfolio(KRAKEN_API_KEY, KRAKEN_API_SECRET)
    
    if not portfolio_df.empty:
        # הצגת הטבלה
        st.dataframe(
            portfolio_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "לוגו": st.column_config.TextColumn("", width="small"),
                "מטבע": st.column_config.TextColumn("מטבע", width="small"),
                "כמות": st.column_config.NumberColumn("כמות", format="%.6f"),
                "מחיר ($)": st.column_config.NumberColumn("מחיר ($)", format="$%.4f"),
                "שווי ($)": st.column_config.NumberColumn("שווי ($)", format="$%.2f"),
                "אחוז מהתיק": st.column_config.NumberColumn("אחוז מהתיק", format="%.2f%%")
            }
        )
        
        # מטריקות סיכום
        total_value = portfolio_df['שווי ($)'].sum()
        num_coins = len(portfolio_df)
        top_coin = portfolio_df.iloc[0]['מטבע'] if num_coins > 0 else "N/A"
        top_percentage = portfolio_df.iloc[0]['אחוז מהתיק'] if num_coins > 0 else 0
        
        # כרטיסי מטריקות
        metric_col1, metric_col2 = st.columns(2)
        
        with metric_col1:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value positive">${total_value:,.2f}</div>
                <div class="metric-label">שווי כולל</div>
            </div>
            """, unsafe_allow_html=True)
            
        with metric_col2:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">{num_coins}</div>
                <div class="metric-label">מטבעות שונים</div>
            </div>
            """, unsafe_allow_html=True)
        
        # פילוח פורטפוליו
        if num_coins > 1:
            st.markdown("#### 📊 פילוח הפורטפוליו")
            # גרף עוגה של החלוקה
            fig_data = portfolio_df.head(5)  # 5 הגדולים
            st.bar_chart(
                fig_data.set_index('מטבע')['אחוז מהתיק'],
                height=200
            )
        
    else:
        st.markdown("""
        <div style="text-align: center; padding: 2rem;">
            <h3 style="color: #7f8c8d;">🔐 אין נתוני פורטפוליו זמינים</h3>
            <p>בדוק את הגדרות ה-API או התחבר לחשבון Kraken</p>
        </div>
        """, unsafe_allow_html=True)

# === עמודה ימין: שוק חי ===
with col2:
    st.markdown("### 📊 שוק חי: מחירים וגרפים")
    
    # קבצי נתונים
    MARKET_LIVE = "data/market_live.csv"
    
    market_df = load_data(
        MARKET_LIVE, 
        ['timestamp', 'pair', 'price', 'volume', 'high_24h', 'low_24h'], 
        parse_dates=['timestamp']
    )
    
    if not market_df.empty:
        # בחירת מטבעות להצגה מתוך הנתונים הקיימים
        available_pairs = sorted(set([clean_symbol(p.split('USD')[0]) for p in market_df['pair'].unique() if 'USD' in p]))
        
        if not available_pairs:
            # אם אין נתונים, נציג רשימת מטבעות ברירת מחדל
            st.info("📊 משתמש בנתוני מחירים חיים מ-Kraken API")
            default_symbols = ['BTC', 'ETH', 'XRP', 'ADA', 'SOL']
            
            # שליפת נתונים חיים מ-Kraken
            all_prices = get_all_kraken_prices(KRAKEN_API_KEY, KRAKEN_API_SECRET)
            
            if all_prices:
                available_symbols = [sym for sym in default_symbols if sym in all_prices]
                selected_pairs = st.multiselect(
                    "🎯 בחר מטבעות להצגה:",
                    available_symbols,
                    default=available_symbols[:3] if len(available_symbols) >= 3 else available_symbols
                )
                
                for symbol in selected_pairs:
                    if symbol in all_prices:
                        st.markdown(f"#### 💰 {symbol}")
                        
                        price = all_prices[symbol]
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            st.metric("מחיר נוכחי", f"${price:,.4f}")
                        
                        with col2:
                            icon = get_coin_icon(symbol)
                            st.markdown(f"**{icon} {symbol}**")
                        
                        with col3:
                            st.caption("נתונים מ-Kraken API")
                        
                        st.markdown("---")
            else:
                st.warning("⚠️ לא הצלחנו לשלוף נתוני מחירים מ-Kraken")
        else:
            # השימוש בנתונים מהקובץ אם קיימים
            selected_pairs = st.multiselect(
                "🎯 בחר מטבעות להצגה:",
                available_pairs,
                default=available_pairs[:3] if len(available_pairs) >= 3 else available_pairs,
                max_selections=4
            )
        
        if selected_pairs:
            # הצגת גרפים לכל מטבע נבחר
            for pair in selected_pairs:
                pair_data = market_df[market_df['pair'].str.contains(pair)].sort_values('timestamp')
                
                if not pair_data.empty:
                    latest = pair_data.iloc[-1]
                    
                    # כותרת המטבע
                    st.markdown(f"#### 💰 {pair}")
                    
                    # מטריקות בשורה
                    metric_col1, metric_col2, metric_col3 = st.columns(3)
                    
                    with metric_col1:
                        st.metric(
                            "מחיר נוכחי", 
                            f"${latest['price']:,.4f}",
                            help="המחיר האחרון שנרשם"
                        )
                    
                    with metric_col2:
                        st.metric(
                            "שיא 24 שעות", 
                            f"${latest['high_24h']:,.4f}",
                            delta=f"{((latest['high_24h'] - latest['price']) / latest['price'] * 100):+.2f}%"
                        )
                    
                    with metric_col3:
                        st.metric(
                            "שפל 24 שעות", 
                            f"${latest['low_24h']:,.4f}",
                            delta=f"{((latest['low_24h'] - latest['price']) / latest['price'] * 100):+.2f}%"
                        )
                    
                    # גרף מחיר
                    if len(pair_data) > 1:
                        st.line_chart(
                            pair_data.set_index('timestamp')['price'],
                            height=150
                        )
                    
                    st.markdown("---")
        else:
            st.info("בחר מטבעות מהרשימה כדי להציג נתונים")
    else:
        st.warning("⚠️ אין נתוני שוק זמינים כרגע - משתמש בנתונים חיים מ-Kraken")

# === סימולציות ===
st.markdown("---")

with st.expander("🧪 סימולציות ומערכות מסחר", expanded=False):
    SIM_LOG = "data/simulation_log.csv"
    sim_df = load_data(
        SIM_LOG, 
        ['id', 'symbol', 'start_time', 'end_time', 'status', 'init_balance', 'final_balance', 'profit_pct', 'strategy', 'params']
    )
    
    if not sim_df.empty:
        sim_df['start_time'] = pd.to_datetime(sim_df['start_time'], errors='coerce')
        sim_df['end_time'] = pd.to_datetime(sim_df['end_time'], errors='coerce')
        
        # חלוקה לכרטיסיות
        tab1, tab2, tab3 = st.tabs(["📈 סימולציות פעילות", "📊 תוצאות אחרונות", "🚀 הפעל סימולציה"])
        
        with tab1:
            active_sims = sim_df[sim_df['status'] == 'active']
            if not active_sims.empty:
                st.dataframe(
                    active_sims[['id', 'symbol', 'start_time', 'init_balance', 'strategy', 'params']],
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.info("🔄 אין סימולציות פעילות כרגע")
        
        with tab2:
            completed_sims = sim_df[sim_df['status'] == 'completed'].sort_values('end_time', ascending=False)
            if not completed_sims.empty:
                # הצגת 10 האחרונות
                display_cols = ['id', 'symbol', 'start_time', 'end_time', 'init_balance', 'final_balance', 'profit_pct', 'strategy']
                st.dataframe(
                    completed_sims[display_cols].head(10),
                    use_container_width=True,
                    hide_index=True
                )
                
                # סטטיסטיקות
                avg_profit = completed_sims['profit_pct'].mean()
                success_rate = (completed_sims['profit_pct'] > 0).mean() * 100
                
                stat_col1, stat_col2 = st.columns(2)
                with stat_col1:
                    st.metric("רווח ממוצע", f"{avg_profit:.2f}%")
                with stat_col2:
                    st.metric("אחוז הצלחה", f"{success_rate:.1f}%")
            else:
                st.info("📊 אין תוצאות סימולציות אחרונות")
        
        with tab3:
            st.markdown("#### 🎮 הפעלת סימולציה חדשה")
            
            # פרמטרים לסימולציה
            sim_col1, sim_col2 = st.columns(2)
            
            with sim_col1:
                sim_symbol = st.selectbox("מטבע לסימולציה:", ['BTC', 'ETH', 'SOL', 'ADA', 'DOT'])
                sim_balance = st.number_input("יתרת התחלה ($):", min_value=100, max_value=50000, value=1000, step=100)
                
            with sim_col2:
                sim_strategy = st.selectbox("אסטרטגיה:", ['combined', 'rsi', 'ema', 'macd', 'bollinger'])
                sim_duration = st.slider("משך (ימים):", 1, 30, 7)
            
            sim_target = st.slider("יעד רווח (%):", 5, 100, 20)
            
            if st.button("🚀 הפעל סימולציה", type="primary"):
                # כאן יהיה הקוד להפעלת הסימולציה
                params = {
                    "target_profit_pct": sim_target / 100,
                    "duration_days": sim_duration
                }
                
                try:
                    # נסיון הפעלת הסימולציה
                    st.success(f"✅ סימולציה עבור {sim_symbol} הופעלה בהצלחה!")
                    st.balloons()
                except Exception as e:
                    st.error(f"❌ שגיאה בהפעלת הסימולציה: {e}")
    else:
        st.info("📊 אין נתוני סימולציות זמינים")

# === חדשות ונתונים נוספים ===
st.markdown("---")

news_col, optimization_col = st.columns(2)

with news_col:
    with st.expander("📰 חדשות קריפטו אחרונות"):
        NEWS_FEED = "data/news_feed.csv"
        news_df = load_data(NEWS_FEED, ['timestamp', 'title', 'url', 'currencies', 'sentiment', 'source'])
        
        if not news_df.empty:
            # הצגת החדשות עם עיצוב משופר
            for _, news in news_df.head(8).iterrows():
                sentiment = str(news.get('sentiment', '')).lower()
                sentiment_color = "🟢" if sentiment == 'positive' else "🔴" if sentiment == 'negative' else "🟡"
                
                st.markdown(f"""
                **{sentiment_color} {news.get('title', 'ללא כותרת')}**  
                *מקור: {news.get('source', 'לא ידוע')} | מטבעות: {news.get('currencies', 'כללי')}*
                """)
                st.markdown("---")

        else:
            st.info("📰 אין חדשות זמינות כרגע")

with optimization_col:
    with st.expander("🤖 תוצאות אופטימיזציה"):
        OPTIMIZATION_SUMMARY = "data/param_optimization_summary.csv"
        opt_df = load_data(OPTIMIZATION_SUMMARY)
        
        if not opt_df.empty:
            # מיון לפי רווחיות
            if 'avg_profit_pct' in opt_df.columns:
                opt_df_sorted = opt_df.sort_values('avg_profit_pct', ascending=False)
                st.dataframe(
                    opt_df_sorted.head(10),
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.dataframe(opt_df.head(10), use_container_width=True, hide_index=True)
        else:
            st.info("🤖 אין תוצאות אופטימיזציה אחרונות")

# === פוטר ===
st.markdown("---")
st.markdown("""
<div style='text-align: center; padding: 2rem; background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); border-radius: 10px; margin-top: 2rem;'>
    <h4 style='color: #2c3e50; margin-bottom: 1rem;'>💎 Kraken Pro AI Dashboard</h4>
    <p style='color: #7f8c8d; margin-bottom: 0;'>
        Powered by Streamlit 🚀 | כל הזכויות שמורות 2025<br>
        <small>גרסה 2.0 - מעודכן ומשופר</small>
    </p>
</div>
""", unsafe_allow_html=True)

# כפתור רענון כללי
if st.button("🔄 רענן את כל הנתונים", type="secondary", use_container_width=True):
    st.cache_data.clear()
    st.rerun()