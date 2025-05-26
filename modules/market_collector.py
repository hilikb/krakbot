import os
import pandas as pd
import time
from datetime import datetime
from binance.client import Client

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')
os.makedirs(DATA_DIR, exist_ok=True)
LIVE_FILE = os.path.join(DATA_DIR, 'market_live.csv')
HISTORY_FILE = os.path.join(DATA_DIR, 'market_history.csv')

def get_all_pairs_data():
    client = Client()
    info = client.get_exchange_info()
    symbols = [
        s['symbol'] for s in info['symbols']
        if s['status'] == 'TRADING' and s['quoteAsset'] == 'USDT'
    ]

    ticker_24h = {x['symbol']: x for x in client.get_ticker()} 
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    data = []
    for symbol in symbols:
        t = ticker_24h.get(symbol, {})
        data.append({
            'timestamp': now,
            'pair': symbol,
            'price': float(t.get('lastPrice', t.get('price', 0))),
            'volume': float(t.get('volume', 0)),
            'high_24h': float(t.get('highPrice', 0)),
            'low_24h': float(t.get('lowPrice', 0)),
        })
    return data

def run_collector(interval=10):
    print("Market Collector - Collecting data for all symbols")
    while True:
        data = get_all_pairs_data()
        df = pd.DataFrame(data)
        df.to_csv(LIVE_FILE, index=False, encoding='utf-8')

        if os.path.exists(HISTORY_FILE):
            try:
                keys_df = pd.read_csv(HISTORY_FILE, usecols=['timestamp', 'pair'], encoding='utf-8')
            except UnicodeDecodeError:
                keys_df = pd.read_csv(HISTORY_FILE, usecols=['timestamp', 'pair'], encoding='cp1255')
            merged = df.merge(keys_df, on=['timestamp', 'pair'], how='left', indicator=True)
            new_rows = df[merged['_merge'] == 'left_only']
            if not new_rows.empty:
                new_rows.to_csv(HISTORY_FILE, mode='a', index=False, header=False, encoding='utf-8')
        else:
            df.to_csv(HISTORY_FILE, index=False, encoding='utf-8')
        print(f"[{datetime.utcnow().strftime('%H:%M:%S')}] Saved {len(df)} symbols to live/history.")
        time.sleep(interval)

if __name__ == "__main__":
    run_collector()
