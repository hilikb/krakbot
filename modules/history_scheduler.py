import time
from datetime import datetime
from modules.historical_downloader import auto_download_history

def run_daily_history_update(hour=2, minute=0):
    """מריץ את ההורדה פעם ביום בשעה מסוימת (UTC)."""
    print(f"🔔 Scheduler פועל: יעד {hour:02d}:{minute:02d} UTC כל יום")
    while True:
        now = datetime.utcnow()
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if now > target:
            # יעד הבא — מחר
            target = target.replace(day=now.day + 1)
        wait_seconds = (target - now).total_seconds()
        if wait_seconds < 0:
            wait_seconds = 60  # פיקס קטן
        print(f"ההורדה תתבצע בעוד {wait_seconds/60:.1f} דקות ({int(wait_seconds)} שניות)")
        time.sleep(wait_seconds)
        print("🚀 הורדת היסטוריה רטרואקטיבית...")
        auto_download_history(top_n=50, vs_currency='usd', outfile='data/market_history.csv')
        print("🎯 בוצע. ההורדה הבאה — מחר.")

if __name__ == "__main__":
    run_daily_history_update(hour=2, minute=0)
