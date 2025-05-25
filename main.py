import threading
import time
import logging
import os
import subprocess
import sys

# הגדרת תיקיות ברירת מחדל
os.makedirs('data', exist_ok=True)
os.makedirs('logs', exist_ok=True)

# לוג בסיסי
logging.basicConfig(
    filename='logs/bot_main.log',
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

def log(msg):
    print(msg)
    logging.info(msg)

# --- Market Collector Worker ---
def run_market_collector():
    from modules.market_collector import run_collector
    log("[MarketCollector] התחיל לפעול…")
    run_collector(interval=30)

# --- News Collector Worker ---
def run_news_collector():
    from config import CRYPTOPANIC_API_KEY
    from modules.news_collector import NewsCollector
    log("[NewsCollector] התחיל למשוך חדשות…")
    news = NewsCollector(api_key=CRYPTOPANIC_API_KEY, currencies=['BTC','ETH','SOL','DOGE'])
    while True:
        news.fetch_and_save()
        time.sleep(60*5)  # עדכון חדשות כל 5 דקות

# --- Dashboard Worker ---
def run_dashboard():
    dashboard_script = os.path.join('dashboard', 'dashboard_ui.py')
    if not os.path.exists(dashboard_script):
        print(f"[שגיאה] לא נמצא: {dashboard_script}")
        return
    subprocess.Popen([sys.executable, "-m", "streamlit", "run", dashboard_script])
    print("⚡️ Streamlit Dashboard רץ כעת. פתח דפדפן וגש ל- http://localhost:8501")

# --- Daily History Downloader Worker (CoinGecko/Old) ---
def run_history_scheduler():
    from modules.history_scheduler import run_daily_history_update
    log("[HistoryScheduler] הורדה אוטומטית של היסטוריה — פעם ביום.")
    run_daily_history_update(hour=2, minute=0)

# --- Binance All History Downloader Worker (חדש ומקיף) ---
def run_binance_history_downloader():
    from modules.binance_history_downloader import download_binance_history_all
    log("[BinanceHistoryDownloader] הורדה מלאה של כל ההיסטוריה מכל המטבעות (Binance USDT)...")
    download_binance_history_all()  # לא צריך hour/minute, רץ ומסיים (יכול לקחת זמן)

# --- הפעלת כל ה-workers במקביל ---
def run_all_workers(with_dashboard=False, with_history_scheduler=False):
    threads = []
    t1 = threading.Thread(target=run_market_collector, daemon=True)
    threads.append(t1)
    t2 = threading.Thread(target=run_news_collector, daemon=True)
    threads.append(t2)
    if with_history_scheduler:
        t3 = threading.Thread(target=run_history_scheduler, daemon=True)
        threads.append(t3)
    if with_dashboard:
        run_dashboard()
    for t in threads:
        t.start()
    while True:
        time.sleep(5)
        log("הכל תקין — הלולאות פועלות.")

# --- תפריט הפעלה נוח ---
def main():
    print("""
===============================
   Kraken Crypto Bot - MAIN
===============================
בחר מה להפעיל:
1. איסוף נתוני שוק חי בלבד
2. חדשות קריפטו בלבד
3. הכל יחד (מומלץ)
4. Dashboard גרפי בלבד
5. הכל יחד + Dashboard
6. Scheduler — הורדה יומית אוטומטית של היסטוריית כל המטבעות (CoinGecko)
7. הכל יחד + Dashboard + Scheduler היסטוריה
8. הורדה מלאה של כל ההיסטוריה מכל המטבעות מבינאנס (כל הזוגות USDT, כל הזמנים)
q. יציאה
""")
    opt = input("הקלד בחירה: ").strip().lower()
    if opt == '1':
        run_market_collector()
    elif opt == '2':
        run_news_collector()
    elif opt == '3':
        run_all_workers(with_dashboard=False, with_history_scheduler=False)
    elif opt == '4':
        run_dashboard()
    elif opt == '5':
        run_all_workers(with_dashboard=True, with_history_scheduler=False)
    elif opt == '6':
        run_history_scheduler()
    elif opt == '7':
        run_all_workers(with_dashboard=True, with_history_scheduler=True)
    elif opt == '8':
        run_binance_history_downloader()
    elif opt == 'q':
        print("יציאה.")
    else:
        print("בחירה לא תקינה.")
        time.sleep(1)
        main()

if __name__ == '__main__':
    main()
