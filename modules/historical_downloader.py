import pandas as pd
import time
from pycoingecko import CoinGeckoAPI
from datetime import datetime
import os
from tqdm import tqdm

def get_historical_df(coin_id, vs_currency='usd', days='max', interval='daily'):
    cg = CoinGeckoAPI()
    data = cg.get_coin_market_chart_by_id(id=coin_id, vs_currency=vs_currency, days=days, interval=interval)
    prices = data['prices']
    volumes = data['total_volumes']
    df = pd.DataFrame(prices, columns=['timestamp', 'price'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df['pair'] = f"{coin_id.upper()}{vs_currency.upper()}"
    df['volume'] = [v[1] for v in volumes]
    return df

def auto_download_history(top_n=50, vs_currency='usd', outfile='data/market_history.csv', coins_list=None, log_file='logs/history_downloader.log'):
    cg = CoinGeckoAPI()
    if coins_list is None:
        coins = cg.get_coins_markets(vs_currency=vs_currency, order='market_cap_desc', per_page=top_n, page=1)
        coins_ids = [coin['id'] for coin in coins]
    else:
        coins_ids = coins_list

    results = []
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(f"{now} — התחלת הורדת היסטוריה {len(coins_ids)} מטבעות\n")
    print(f"⏳ {now} — מוריד היסטוריה ל-{len(coins_ids)} מטבעות...")

    for coin_id in tqdm(coins_ids):
        try:
            df = get_historical_df(coin_id, vs_currency=vs_currency, days='max')
            results.append(df)
            time.sleep(1)
        except Exception as e:
            print(f"שגיאה במטבע {coin_id}: {e}")
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(f"{now} — שגיאה במטבע {coin_id}: {e}\n")

    if results:
        bigdf = pd.concat(results, ignore_index=True)
        # שמור (דריסה, זה קובץ היסטוריה נקי)
        bigdf.to_csv(outfile, index=False)
        msg = f"{now} — היסטוריה נשמרה ל־{outfile} ({len(bigdf)} שורות)\n"
        print("✅", msg)
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(msg)
    else:
        print("לא הורדו נתונים.")
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(f"{now} — לא הורדו נתונים.\n")

if __name__ == "__main__":
    auto_download_history(top_n=50, vs_currency='usd', outfile='data/market_history.csv')
