import requests
import pandas as pd
from datetime import datetime

class NewsCollector:
    def __init__(self, api_key, currencies=None, max_posts=50):
        self.api_key = api_key
        # רשימת מטבעות ראשונית, לדוג' ['BTC', 'ETH', 'SOL']
        self.currencies = currencies if currencies else ['BTC', 'ETH']
        self.max_posts = max_posts

    def fetch_cryptopanic_news(self):
        all_results = []
        url = "https://cryptopanic.com/api/v1/posts/"
        params = {
            "auth_token": self.api_key,
            "currencies": ','.join(self.currencies),
            "kind": "news",    # אפשר גם "media" או "all"
            "public": "true",
            "filter": "hot"    # אפשר 'rising', 'bullish', 'bearish', 'important' וכו'
        }
        try:
            resp = requests.get(url, params=params)
            data = resp.json()
            results = data.get('results', [])
            for news in results[:self.max_posts]:
                all_results.append({
                    'timestamp': news['published_at'],
                    'title': news['title'],
                    'url': news['url'],
                    'currencies': ','.join([c['code'] for c in news.get('currencies', [])]),
                    'sentiment': news.get('votes', {}).get('positive', 0) - news.get('votes', {}).get('negative', 0),
                    'source': news.get('source', {}).get('title', ''),
                    'domain': news.get('domain', ''),
                    'summary': news.get('slug', '')
                })
            return pd.DataFrame(all_results)
        except Exception as e:
            print(f"[שגיאת חדשות] {e}")
            return pd.DataFrame()

    def save_to_csv(self, df, path="data/news_feed.csv"):
        try:
            df.to_csv(path, index=False)
            print(f"✅ נשמרו {len(df)} חדשות עדכניות לקובץ: {path}")
        except Exception as e:
            print(f"[שגיאת שמירת חדשות] {e}")

    def fetch_and_save(self):
        df = self.fetch_cryptopanic_news()
        if not df.empty:
            self.save_to_csv(df)
        return df

# דוגמה לשימוש
if __name__ == "__main__":
    from config import CRYPTOPANIC_API_KEY

    collector = NewsCollector(api_key=CRYPTOPANIC_API_KEY, currencies=['BTC', 'ETH', 'SOL', 'DOGE'], max_posts=50)
    news_df = collector.fetch_and_save()
    print(news_df.head())
