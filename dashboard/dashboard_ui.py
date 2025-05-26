import streamlit as st
import pandas as pd
import os
import matplotlib.pyplot as plt
import requests
from config import KRAKEN_API_KEY, KRAKEN_API_SECRET

st.set_page_config(page_title="💹 Kraken Pro Dashboard", layout="wide")

# --- Utility: קריאת קבצים (עם קידוד חכם) ---
def load_data(file, empty_cols=None, parse_dates=None):
    for enc in ['utf-8', 'cp1255', 'cp1252', 'iso-8859-8']:
        try:
            return pd.read_csv(file, parse_dates=parse_dates, encoding=enc)
        except Exception:
            continue
    return pd.DataFrame(columns=empty_cols or [])

# --- Utility: לוגו מטבע ע"י CoinGecko ---
@st.cache_data(show_spinner=False)
def get_coin_image(symbol):
    try:
        url = f"https://api.coingecko.com/api/v3/coins/list"
        coins = requests.get(url, timeout=10).json()
        coin_id = next((c['id'] for c in coins if c['symbol'].lower() == symbol.lower()), None)
        if not coin_id:
            return None
        data = requests.get(f"https://api.coingecko.com/api/v3/coins/{coin_id}", timeout=10).json()
        return data['image']['thumb']
    except Exception:
        return None

# --- Kraken Portfolio משופר עם טיפול חכם במחירים ---
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
        # תרגום סימנים: XBT->BTC וכו'
        symbol_map = {}
        all_pairs = []
        for coin in balances.keys():
            if coin in ['ZUSD', 'USD']:
                continue
            coin_fixed = coin.replace('XBT','BTC').replace('XETH','ETH').replace('XXRP','XRP').replace('XLTC','LTC').replace('ZUSD','USD')
            symbol_map[coin] = coin_fixed
            # קודם כל ננסה גם את COINUSD וגם XCOINZUSD (קרקן לפעמים דורש)
            all_pairs.append(f"{coin_fixed}USD")
            all_pairs.append(f"X{coin_fixed}ZUSD")
        # ניקוי כפילויות
        all_pairs = list(set(all_pairs))

        prices = {}
        # שליפת מחירים: נסה גם COINUSD וגם XCOINZUSD (טיפול בבאג של Kraken API)
        for i in range(0, len(all_pairs), 20):
            pair_batch = ','.join(all_pairs[i:i+20])
            price_resp = api.query_public('Ticker', {'pair': pair_batch})
            if 'result' in price_resp:
                for pair, info in price_resp['result'].items():
                    # הוצאת הסימול הנכון מתוך שם הזוג
                    if pair.endswith('USD'):
                        symbol = pair.replace('USD', '').replace('X', '').replace('Z', '')
                        prices[symbol] = float(info['c'][0])
            time.sleep(1)
        # אם עדיין אין מחיר, נביא אותו מ־CoinGecko (גיבוי!)
        def get_backup_price(symbol):
            try:
                r = requests.get(f"https://api.coingecko.com/api/v3/simple/price?ids={symbol.lower()}&vs_currencies=usd", timeout=6)
                p = r.json()
                return list(p.values())[0]['usd'] if p else 0
            except Exception:
                return 0
        portfolio = []
        for coin, amount in balances.items():
            symbol = symbol_map.get(coin, coin).upper()
            # מחיר חכם: נסה COIN, נסה BACKUP
            price = prices.get(symbol, 0)
            if price == 0:
                price = get_backup_price(symbol)
            value_usd = amount * price
            image_url = get_coin_image(symbol.lower())
            portfolio.append({
                '': f"![{symbol}]({image_url})" if image_url else '',
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

# --- נתיבים ---
MARKET_LIVE = "data/market_live.csv"
OPTIMIZATION_SUMMARY = "data/param_optimization_summary.csv"
NEWS_FEED = "data/news_feed.csv"

# --- HEADER עליון ---
st.markdown("""
<style>
.big-title {font-size:45px; font-weight:bold; color:#009fdf;}
.badge {display:inline-block; background:#222; color:#fff; border-radius:12px; padding:2px 15px; margin-right:10px;}
.divider {height:5px; background:linear-gradient(90deg,#00bfae 50%,#009fdf 100%); border-radius:3px;}
th,td {text-align:center !important;}
</style>
<div style='text-align:center;'>
    <span class='big-title'>💹 Kraken Pro Dashboard</span>
    <br><span style='font-size:20px; color:gray;'>בוט השקעות | פורטפוליו | ניתוח שוק | חדשות | סימולציות</span>
</div>
<div class="divider"></div>
""", unsafe_allow_html=True)
st.markdown("")

# --- PORTFOLIO + STATS (צד שמאל) ---
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
    else:
        st.warning("⚠️ אין אחזקות פעילות או שיש שגיאה ב־API.", icon="⚠️")

    # Badges מהירים למצב חשבון
    if not portf_df.empty and total_val > 0:
        biggest = portf_df.iloc[0]
        st.markdown(f"<span class='badge'>מטבע מוביל: {biggest['מטבע']}</span> <span class='badge'>שווי מוביל: ${biggest['שווי עדכני ($)']:.2f}</span>", unsafe_allow_html=True)

    st.markdown("")

# --- Market גרפים מתקדמים (ימין) ---
with col2:
    st.subheader("📊 שוק חי: מחירים וגרפים")
    market_df = load_data(MARKET_LIVE, ['timestamp','pair','price','volume','high_24h','low_24h'], parse_dates=['timestamp'])
    if not market_df.empty:
        pairs = sorted(market_df['pair'].unique())
        selected = st.multiselect("בחר מטבעות (עד 5):", pairs, default=pairs[:2], max_selections=5)
        st.markdown("---")
        for pair in selected:
            coin_df = market_df[market_df['pair']==pair].sort_values('timestamp')
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

# --- חדשות + סימולציות ---
st.markdown("<div class='divider'></div>", unsafe_allow_html=True)
with st.expander("📰 חדשות קריפטו מעודכנות"):
    news = load_data(NEWS_FEED, ['timestamp','title','url','currencies','sentiment','source'])
    if not news.empty:
        st.dataframe(news[['timestamp','title','currencies','sentiment','source']].head(10), use_container_width=True, hide_index=True)
    else:
        st.info("אין חדשות זמינות כרגע.", icon="ℹ️")

with st.expander("🧪 תוצאות אופטימיזציה / סימולציות"):
    sim = load_data(OPTIMIZATION_SUMMARY)
    if not sim.empty:
        st.dataframe(sim.sort_values('avg_profit_pct', ascending=False).head(12), use_container_width=True, hide_index=True)
    else:
        st.info("אין תוצאות אופטימיזציה אחרונות.", icon="ℹ️")

# --- FOOTER, רענון יפה ---
st.markdown("<div class='divider'></div>", unsafe_allow_html=True)
st.markdown("""
<div style='text-align:center; color:#888;'>
כל הזכויות שמורות 2024 • Kraken Pro AI Dashboard • Powered by Streamlit 🚀<br>
<a href="https://www.kraken.com/" target="_blank" style="color:#00bfae;">Visit Kraken Exchange 🌍</a>
</div>
""", unsafe_allow_html=True)

st.markdown("")
if st.button("🔄 רענן נתונים", type="primary"):
    st.toast("מרענן את כל הנתונים...", icon="🔄")
    st.experimental_rerun()
