import os
import pandas as pd
import time
from datetime import datetime
from binance.client import Client
from tqdm import tqdm

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')
os.makedirs(DATA_DIR, exist_ok=True)
OUTFILE = os.path.join(DATA_DIR, 'market_history.csv')

def get_all_symbols(quote_asset='USDT'):
    client = Client()
    info = client.get_exchange_info()
    symbols = [s['symbol'] for s in info['symbols'] if s['status'] == 'TRADING' and s['quoteAsset'] == quote_asset]
    return symbols

def get_binance_ohlc(symbol, interval='1d', start_str='1 Jan 2007', end_str=None):
    client = Client()
    try:
        klines = client.get_historical_klines(symbol=symbol, interval=interval, start_str=start_str, end_str=end_str)
        df = pd.DataFrame(klines, columns=[
            'open_time', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_asset_volume', 'number_of_trades',
            'taker_buy_base', 'taker_buy_quote', 'ignore'
        ])
        df['timestamp'] = pd.to_datetime(df['open_time'], unit='ms')
        df['pair'] = symbol
        df['price'] = df['close'].astype(float)
        df['high_24h'] = df['high'].astype(float)
        df['low_24h'] = df['low'].astype(float)
        df['volume'] = df['volume'].astype(float)
        return df[['timestamp','pair','price','volume','high_24h','low_24h']]
    except Exception as e:
        print(f"שגיאה ב-{symbol}: {e}")
        return None

def download_binance_history_all(outfile=OUTFILE, start_str='1 Jan 2007'):
    all_dfs = []
    symbols = get_all_symbols(quote_asset='USDT')
    print(f"⏳ מוריד היסטוריה ל-{len(symbols)} מטבעות/זוגות (USDT).")
    for symbol in tqdm(symbols):
        df = get_binance_ohlc(symbol, start_str=start_str)
        if df is not None and not df.empty:
            all_dfs.append(df)
            time.sleep(0.2)  # להימנע מ־rate limit
    if all_dfs:
        bigdf = pd.concat(all_dfs, ignore_index=True)
        bigdf.to_csv(outfile, index=False)
        print(f"✅ שמרתי קובץ היסטוריה מלא: {outfile} ({len(bigdf)} שורות)")
    else:
        print("❌ לא נשמרו נתונים.")

if __name__ == "__main__":
    download_binance_history_all(outfile=OUTFILE, start_str='1 Jan 2007')
