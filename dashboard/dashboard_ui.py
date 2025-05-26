import streamlit as st
import pandas as pd
import requests
import os
import datetime
from config import KRAKEN_API_KEY, KRAKEN_API_SECRET

st.set_page_config(page_title="💎 Kraken PRO Dashboard", layout="wide")

def load_data(file, empty_cols=None, parse_dates=None):
    for enc in ['utf-8', 'cp1255', 'cp1252', 'iso-8859-8']:
        try:
            return pd.read_csv(file, parse_dates=parse_dates, encoding=enc)
        except Exception:
            continue
    return pd.DataFrame(columns=empty_cols or [])

@st.cache_data(show_spinner=False)
def get_coin_image(symbol):
    try:
        url = f"https://api.coingecko.com/api/v3/coins/{symbol.lower()}"
        data = requests.get(url, timeout=10).json()
        if 'image' in data:
            return data['image']['thumb']
    except Exception:
        return None
    return None

def clean_symbol(symbol):
    return symbol.split('.')[0].upper()

def get_kraken_portfolio(api_key, api_secret):
    import krakenex, time
    api = krakenex.API(api_key, api_secret)
    try:
        balance_resp = api.query_private('Balance')
        if balance_resp.get('error') and balance_resp['error']:
            st.error(f"שגיאה בשליפת האחזקות: {balance_resp['error']}")
            return pd.DataFrame()
        balances = balance_resp['result']
        balances = {k: float(v) for k, v in balances.items() if float(v) > 0}
        if not balances:
            st.info("לא נמצאו אחזקות פעילות בחשבון Kraken.")
            return pd.DataFrame()
        symbol_map = {}
        all_pairs = []
        for coin in balances.keys():
            if coin in ['ZUSD', 'USD']:
                continue
            coin_fixed = coin.replace('XBT','BTC').replace('XETH','ETH').replace('XXRP','XRP').replace('XLTC','LTC').replace('ZUSD','USD')
            symbol_map[coin] = coin_fixed
            all_pairs.append(f"{coin_fixed}USD")
            all_pairs.append(f"X{coin_fixed}ZUSD")
        all_pairs = list(set(all_pairs))
        prices = {}
        for i in range(0, len(all_pairs), 20):
            pair_batch = ','.join(all_pairs[i:i+20])
            price_resp = api.query_public('Ticker', {'pair': pair_batch})
            if 'result' in price_resp:
                for pair, info in price_resp['result'].items():
                    symbol = pair.replace('USD','').replace('X','').replace('Z','').replace('.S','').replace('.F','').replace('.M','').replace('.U','').replace('.N','').replace('.X','').replace('.Z','').upper()
                    prices[symbol] = float(info['c'][0])
            time.sleep(0.5)
        def get_backup_price(symbol):
            try:
                url = f"https://api.coingecko.com/api/v3/simple/price?ids={symbol.lower()}&vs_currencies=usd"
                r = requests.get(url, timeout=6)
                p = r.json()
                return list(p.values())[0]['usd'] if p else 0
            except Exception:
                return 0
        portfolio = []
        for coin, amount in balances.items():
            symbol_raw = symbol_map.get(coin, coin).upper()
            symbol = clean_symbol(symbol_raw)
            price = prices.get(symbol, 0)
            if price == 0:
                price = get_backup_price(symbol)
            value_usd = amount * price
            img_url = get_coin_image(symbol.lower())
            portfolio.append({
                '': f"![{symbol}]({img_url})" if img_url else '',
                'מטבע': symbol,
                'כמות': amount,
                'מחיר נוכחי ($)': price,
                'שווי עדכני ($)': value_usd,
            })
        portf_df = pd.DataFrame(portfolio)
        portf_df.sort_values('שווי עדכני ($)', ascending=False, inplace=True)
        return portf_df
    except Exception as e:
        st.error(f"שגיאת Kraken API: {e}")
        return pd.DataFrame()

MARKET_LIVE = "data/market_live.csv"
OPTIMIZATION_SUMMARY = "data/param_optimization_summary.csv"
NEWS_FEED = "data/news_feed.csv"
SIM_LOG = "data/simulation_log.csv"

# --- HEADER מקצועי --- #
st.markdown("""
<style>
.big-title {font-size:45px; font-weight:bold; color:#009fdf;}
.badge {display:inline-block; background:#292e35; color:#fff; border-radius:16px; padding:4px 18px; margin-right:14px;}
.divider {height:5px; background:linear-gradient(90deg,#00bfae 50%,#009fdf 100%); border-radius:3px;}
th,td {text-align:center !important;}
</style>
<div style='text-align:center;'>
    <span class='big-title'>💎 Kraken PRO Dashboard</span>
    <br><span style='font-size:22px; color:gray;'>בוט השקעות מתקדם • פורטפוליו חי • גרפים • AI • סימולציות</span>
</div>
<div class="divider"></div>
""", unsafe_allow_html=True)

col1, col2 = st.columns([2,3], gap="large")

with col1:
    st.subheader("💼 פורטפוליו אמיתי (Kraken)")
    portf_df = get_kraken_portfolio(KRAKEN_API_KEY, KRAKEN_API_SECRET)
    if not portf_df.empty:
        st.data_editor(
            portf_df,
            use_container_width=True,
            hide_index=True,
            column_config={"": st.column_config.ImageColumn("סמל", help="לוגו/אייקון של המטבע")}
        )
        total_val = portf_df['שווי עדכני ($)'].sum()
        st.metric("💲 שווי התיק", f"${total_val:,.2f}", help="סך הכל שווי הדולרי של הפורטפוליו")
        st.markdown(f"<span class='badge'>מטבעות שונים בתיק: {portf_df.shape[0]}</span>", unsafe_allow_html=True)
        if total_val > 0:
            st.markdown(f"<span class='badge'>המטבע המוביל: {portf_df.iloc[0]['מטבע']}</span>", unsafe_allow_html=True)
    else:
        st.warning("⚠️ אין אחזקות פעילות או שיש שגיאה ב־API.", icon="⚠️")

with col2:
    st.subheader("📊 שוק חי: מחירים וגרפים")
    market_df = load_data(MARKET_LIVE, ['timestamp','pair','price','volume','high_24h','low_24h'], parse_dates=['timestamp'])
    if not market_df.empty:
        pairs = sorted(set([clean_symbol(p) for p in market_df['pair'].unique()]))
        selected = st.multiselect("בחר מטבעות (עד 5):", pairs, default=pairs[:2], max_selections=5)
        st.markdown("---")
        for pair in selected:
            coin_df = market_df[market_df['pair'].str.startswith(pair)].sort_values('timestamp')
            colL, colR = st.columns([3,1])
            with colL:
                st.line_chart(coin_df.set_index('timestamp')['price'], height=180)
            with colR:
                st.metric("📈 מחיר עדכני", f"${coin_df['price'].iloc[-1]:,.4f}")
                st.metric("📉 שפל 24ש", f"${coin_df['low_24h'].iloc[-1]:,.4f}")
                st.metric("📈 שיא 24ש", f"${coin_df['high_24h'].iloc[-1]:,.4f}")
            st.area_chart(coin_df.set_index('timestamp')['volume'], height=60)
            st.markdown("---")
    else:
        st.error("⚠️ אין נתוני שוק זמינים.")

st.markdown("<div class='divider'></div>", unsafe_allow_html=True)

# --- סימולציות (ניהול מלא) --- #
with st.expander("🧪 סימולציות חיות/היסטוריות", expanded=True):
    # --- תצוגת סטטוס סימולציות חיות/היסטוריות --- #
    sim_df = load_data(SIM_LOG, ['id', 'symbol', 'start_time', 'end_time', 'status', 'init_balance', 'final_balance', 'profit_pct', 'strategy', 'params'])
    sim_df['start_time'] = pd.to_datetime(sim_df['start_time'], errors='coerce')
    sim_df['end_time'] = pd.to_datetime(sim_df['end_time'], errors='coerce')
    live_sims = sim_df[sim_df['status']=='active']
    finished_sims = sim_df[sim_df['status']=='completed']
    st.subheader("📋 סימולציות פעילות כרגע")
    if not live_sims.empty:
        st.dataframe(live_sims[['id','symbol','start_time','init_balance','strategy','params']], use_container_width=True, hide_index=True)
    else:
        st.info("אין סימולציות פעילות כרגע.")

    st.subheader("📈 תוצאות סימולציות קודמות")
    if not finished_sims.empty:
        st.dataframe(finished_sims.sort_values('end_time', ascending=False).head(10)[['id','symbol','start_time','end_time','init_balance','final_balance','profit_pct','strategy']], use_container_width=True, hide_index=True)
    else:
        st.info("אין תוצאות סימולציות אחרונות.")

    st.markdown("---")

    # --- הרצת סימולציה בלייב מהדאשבורד --- #
    st.subheader("🚦 הפעל סימולציה חדשה (דמו)")
    sim_coin = st.selectbox("בחר מטבע לסימולציה", sorted(set(sim_df['symbol'].unique()) | set(pairs)))
    sim_balance = st.number_input("יתרת התחלה ($)", min_value=100, max_value=10000, value=1000, step=100)
    sim_strategy = st.selectbox("אסטרטגיה", ['combined', 'rsi', 'ema', 'macd', 'bollinger', 'stochastic'])
    sim_profit = st.number_input("יעד רווח (%)", min_value=1, max_value=100, value=20)
    sim_duration = st.number_input("משך (ימים)", min_value=1, max_value=60, value=7)
    sim_params = {
        "target_profit_pct": sim_profit/100,
        "duration_days": sim_duration
    }
    if st.button("▶️ הפעל סימולציה"):
        try:
            from modules.simulation_core import run_single_simulation
            run_single_simulation(symbol=sim_coin, initial_balance=sim_balance, strategy=sim_strategy, params=sim_params)
            st.success(f"סימולציה למטבע {sim_coin} יצאה לדרך!")
        except Exception as e:
            st.error(f"שגיאה בהרצת סימולציה: {e}")

st.markdown("<div class='divider'></div>", unsafe_allow_html=True)

with st.expander("📰 חדשות קריפטו עדכניות"):
    news = load_data(NEWS_FEED, ['timestamp','title','url','currencies','sentiment','source'])
    if not news.empty:
        st.dataframe(news[['timestamp','title','currencies','sentiment','source']].head(12), use_container_width=True, hide_index=True)
    else:
        st.info("אין חדשות זמינות כרגע.", icon="ℹ️")

with st.expander("🤖 תוצאות אופטימיזציה"):
    sim = load_data(OPTIMIZATION_SUMMARY)
    if not sim.empty:
        st.dataframe(sim.sort_values('avg_profit_pct', ascending=False).head(12), use_container_width=True, hide_index=True)
    else:
        st.info("אין תוצאות אופטימיזציה אחרונות.", icon="ℹ️")

st.markdown("<div class='divider'></div>", unsafe_allow_html=True)
st.markdown("""
<div style='text-align:center; color:#888;'>
כל הזכויות שמורות 2025 • Kraken Pro AI Dashboard • Powered by Streamlit 🚀
</div>
""", unsafe_allow_html=True)

if st.button("🔄 רענן נתונים", type="primary"):
    st.toast("מרענן נתונים...", icon="🔄")
    st.rerun()
