import streamlit as st
import pandas as pd
import os
import matplotlib.pyplot as plt

st.set_page_config(page_title="Crypto Bot Dashboard", layout="wide")

# -- Utility functions --
def load_data(file, empty_cols=None):
    if not os.path.exists(file):
        if empty_cols:
            return pd.DataFrame(columns=empty_cols)
        else:
            return pd.DataFrame()
    return pd.read_csv(file)

# -- Load market data --
market_path = "data/market_live.csv"
market_df = load_data(market_path, empty_cols=['time', 'pair', 'price', 'volume', 'high_24h', 'low_24h'])

st.title("🚀 Crypto Bot Dashboard")
st.markdown("### 🔸 נתוני שוק חיים")
if not market_df.empty:
    # הצגת מטבעות מובילים בלבד (לדוג' לפי נפח)
    top_coins = market_df.groupby('pair').tail(1).sort_values('volume', ascending=False).head(10)
    st.dataframe(top_coins[['pair', 'price', 'volume', 'high_24h', 'low_24h']], use_container_width=True)
else:
    st.warning("לא נמצאו נתוני שוק חיים.")

# -- גרף דינמי לפי בחירת מטבע --
if not market_df.empty:
    coin_options = market_df['pair'].unique().tolist()
    selected_coin = st.selectbox("בחר מטבע לצפייה בגרף", coin_options, index=0)
    coin_data = market_df[market_df['pair'] == selected_coin]
    st.write(f"**גרף מחירים למטבע {selected_coin}:**")
    fig, ax = plt.subplots()
    ax.plot(pd.to_datetime(coin_data['time']), coin_data['price'], label=selected_coin)
    ax.set_xlabel("זמן")
    ax.set_ylabel("מחיר")
    ax.legend()
    st.pyplot(fig)

# -- חדשות עדכניות --
news_path = "data/news_feed.csv"
news_df = load_data(news_path, empty_cols=['timestamp','title','url','currencies','sentiment','source','domain','summary'])

with st.expander("📰 חדשות קריפטו אחרונות"):
    if not news_df.empty:
        st.write(news_df[['timestamp','title','currencies','sentiment','source']].head(15))
    else:
        st.info("לא נמצאו חדשות. הפעל את news_collector.")

# -- סימולציה חיה --
st.markdown("---")
st.subheader("📊 הפעל סימולציית מסחר על מטבע נבחר:")

sim_coin = st.selectbox("בחר מטבע לסימולציה", coin_options, key="simcoin")
sim_balance = st.number_input("סכום פתיחה ($)", min_value=100, max_value=50000, value=1000, step=100)
sim_strategy = st.selectbox("אסטרטגיה", ['combined', 'rsi', 'ema', 'macd', 'bollinger', 'stochastic'])
run_sim = st.button("🚦 הרץ סימולציה")

if run_sim:
    # טעינת המודולים
    from modules.strategy_engine import StrategyEngine
    from modules.simulation_core import SimulationEngine

    coin_df = market_df[market_df['pair'] == sim_coin].copy()
    if len(coin_df) < 20:
        st.error("לא מספיק נתונים לסימולציה.")
    else:
        se = StrategyEngine(coin_df)
        signals = se.generate_signals(strategy=sim_strategy)
        sim = SimulationEngine(initial_balance=sim_balance)
        results = sim.run_simulation(signals, strategy=sim_strategy)
        st.success(f"יתרת סיום: ${results['final_balance']:.2f}")
        st.info(f"אחוז רווח: {results['total_profit_pct']*100:.2f}%")
        st.write("פירוט טריידים:")
        st.dataframe(results['trade_log'].tail(10), use_container_width=True)

# -- רענון נתונים --
if st.button("🔄 רענן נתונים"):
    st.experimental_rerun()

st.markdown("---")
st.caption("פיתוח: Kraken Crypto Bot AI | Powered by Streamlit")
