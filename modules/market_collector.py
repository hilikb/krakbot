import krakenex
import pandas as pd
import time
import os
from datetime import datetime
from config import KRAKEN_API_KEY, KRAKEN_API_SECRET

api = krakenex.API(KRAKEN_API_KEY, KRAKEN_API_SECRET)

# רשימת מטבעות Stable שברצונך לדלג עליהם
STABLE_COINS = ['USDT', 'USDC', 'DAI', 'USDP', 'TUSD', 'USD']

def get_all_pairs():
    pairs_data = api.query_public("AssetPairs")['result']
    all_pairs = []
    for pair, details in pairs_data.items():
        base = details['base']
        quote = details['quote']
        altname = details['altname']

        # בדיקה האם המטבעות יציבים (Stable)
        if not (base in STABLE_COINS or quote in STABLE_COINS):
            all_pairs.append(altname)
    return all_pairs

def fetch_market_price(pair):
    try:
        resp = api.query_public('Ticker', {'pair': pair})
        result = resp['result']
        ticker = result[list(result.keys())[0]]
        price = float(ticker['c'][0])
        volume = float(ticker['v'][1])
        high = float(ticker['h'][1])
        low = float(ticker['l'][1])
        return price, volume, high, low
    except Exception as e:
        print(f"Error fetching {pair}: {e}")
        return None, None, None, None

def run_collector(interval=30):
    pairs = get_all_pairs()
    os.makedirs('data', exist_ok=True)
    print(f"סריקת {len(pairs)} זוגות מטבעות ללא Stable Coins...")

    while True:
        market_snapshot = []
        now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')

        for pair in pairs:
            price, volume, high, low = fetch_market_price(pair)
            if price is None:
                continue

            market_snapshot.append({
                'time': now,
                'pair': pair,
                'price': price,
                'volume': volume,
                'high_24h': high,
                'low_24h': low
            })

            print(f"[{now}] {pair} מחיר: {price} נפח: {volume}")

        if market_snapshot:
            df = pd.DataFrame(market_snapshot)
            df.to_csv('data/market_live.csv', mode='a', header=not os.path.exists('data/market_live.csv'), index=False)

        time.sleep(interval)
