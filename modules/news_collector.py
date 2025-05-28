import requests
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import logging
import os
import sys
import time
import json
from textblob import TextBlob
import re

# הוספת נתיב למודולים
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config

logger = Config.setup_logging('news_collector')

class NewsCollector:
    """איסוף וניתוח חדשות קריפטו משופר"""
    
    def __init__(self, 
                 api_key: Optional[str] = None,
                 currencies: Optional[List[str]] = None,
                 max_posts: int = 50,
                 analyze_sentiment: bool = True):
        
        self.api_key = api_key or Config.CRYPTOPANIC_API_KEY
        self.currencies = currencies or Config.DEFAULT_COINS[:10]
        self.max_posts = max_posts
        self.analyze_sentiment = analyze_sentiment
        
        # קבצי נתונים
        self.news_file = Config.NEWS_FEED_FILE
        self.archive_file = os.path.join(Config.DATA_DIR, 'news_archive.csv')
        
        # cache לניתוח סנטימנט
        self.sentiment_cache = {}
        
        # סטטיסטיקות
        self.stats = {
            'total_fetched': 0,
            'total_analyzed': 0,
            'errors': 0
        }
        
    def fetch_cryptopanic_news(self, 
                              filter_type: str = 'hot',
                              kind: str = 'news') -> pd.DataFrame:
        """שליפת חדשות מ-CryptoPanic API"""
        
        if not self.api_key:
            logger.warning("No CryptoPanic API key configured")
            return pd.DataFrame()
        
        url = "https://cryptopanic.com/api/v1/posts/"
        params = {
            "auth_token": self.api_key,
            "currencies": ','.join(self.currencies),
            "kind": kind,  # news, media, all
            "public": "true",
            "filter": filter_type  # hot, rising, bullish, bearish, important, saved, lol
        }
        
        try:
            logger.info(f"Fetching {filter_type} {kind} for {len(self.currencies)} currencies")
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            results = data.get('results', [])
            
            if not results:
                logger.warning("No news results returned")
                return pd.DataFrame()
            
            # עיבוד התוצאות
            news_data = []
            for item in results[:self.max_posts]:
                processed = self._process_news_item(item)
                if processed:
                    news_data.append(processed)
            
            df = pd.DataFrame(news_data)
            self.stats['total_fetched'] += len(df)
            
            return df
            
        except requests.exceptions.RequestException as e:
            logger.error(f"API request error: {e}")
            self.stats['errors'] += 1
            return pd.DataFrame()
        except Exception as e:
            logger.error(f"Unexpected error fetching news: {e}")
            self.stats['errors'] += 1
            return pd.DataFrame()
    
    def fetch_multiple_sources(self) -> pd.DataFrame:
        """שליפת חדשות ממספר מקורות/פילטרים"""
        all_news = []
        
        # פילטרים שונים לגיוון
        filters = ['hot', 'rising', 'important', 'bullish', 'bearish']
        
        for filter_type in filters:
            df = self.fetch_cryptopanic_news(filter_type=filter_type)
            if not df.empty:
                all_news.append(df)
                time.sleep(1)  # כיבוד rate limit
        
        if all_news:
            # איחוד והסרת כפילויות
            combined_df = pd.concat(all_news, ignore_index=True)
            combined_df = combined_df.drop_duplicates(subset=['url'], keep='first')
            
            # מיון לפי חשיבות וזמן
            combined_df = combined_df.sort_values(
                by=['importance_score', 'published_at'],
                ascending=[False, False]
            )
            
            return combined_df
        
        return pd.DataFrame()
    
    def _process_news_item(self, item: Dict) -> Optional[Dict]:
        """עיבוד פריט חדשות בודד"""
        try:
            # חילוץ מטבעות
            currencies = [c['code'] for c in item.get('currencies', [])]
            currencies_str = ','.join(currencies) if currencies else 'General'
            
            # חישוב ניקוד חשיבות
            votes = item.get('votes', {})
            importance_score = self._calculate_importance(votes, item)
            
            # ניתוח סנטימנט
            sentiment_data = self._analyze_sentiment(
                item.get('title', ''),
                item.get('summary', '') or item.get('body', '')
            ) if self.analyze_sentiment else {'sentiment': 'neutral', 'polarity': 0}
            
            processed = {
                'id': item.get('id'),
                'published_at': item.get('published_at'),
                'timestamp': datetime.now(),
                'title': item.get('title', ''),
                'url': item.get('url', ''),
                'source': item.get('source', {}).get('title', 'Unknown'),
                'domain': item.get('domain', ''),
                'currencies': currencies_str,
                'kind': item.get('kind', 'news'),
                'votes_positive': votes.get('positive', 0),
                'votes_negative': votes.get('negative', 0),
                'votes_important': votes.get('important', 0),
                'votes_liked': votes.get('liked', 0),
                'votes_disliked': votes.get('disliked', 0),
                'votes_lol': votes.get('lol', 0),
                'votes_toxic': votes.get('toxic', 0),
                'votes_saved': votes.get('saved', 0),
                'comments': votes.get('comments', 0),
                'importance_score': importance_score,
                'sentiment': sentiment_data['sentiment'],
                'sentiment_polarity': sentiment_data['polarity'],
                'sentiment_subjectivity': sentiment_data.get('subjectivity', 0.5),
                'summary': self._clean_text(item.get('summary', '') or item.get('body', ''))[:500]
            }
            
            return processed
            
        except Exception as e:
            logger.error(f"Error processing news item: {e}")
            return None
    
    def _calculate_importance(self, votes: Dict, item: Dict) -> float:
        """חישוב ניקוד חשיבות לחדשה"""
        # משקולות לסוגי הצבעות
        weights = {
            'positive': 2.0,
            'negative': -1.5,
            'important': 3.0,
            'liked': 1.5,
            'disliked': -1.0,
            'saved': 2.5,
            'toxic': -2.0,
            'comments': 0.5
        }
        
        score = 0
        for vote_type, weight in weights.items():
            score += votes.get(vote_type, 0) * weight
        
        # בונוס לחדשות מסוג 'important'
        if item.get('kind') == 'important':
            score *= 1.5
        
        # נרמול לטווח 0-100
        return max(0, min(100, score))
    
    def _analyze_sentiment(self, title: str, body: str) -> Dict:
        """ניתוח סנטימנט של טקסט"""
        # בדיקת cache
        cache_key = f"{title[:50]}_{body[:50]}"
        if cache_key in self.sentiment_cache:
            return self.sentiment_cache[cache_key]
        
        try:
            # שילוב כותרת וגוף
            full_text = f"{title}. {body}"
            
            # ניקוי טקסט
            clean_text = self._clean_text(full_text)
            
            # ניתוח עם TextBlob
            blob = TextBlob(clean_text)
            polarity = blob.sentiment.polarity
            subjectivity = blob.sentiment.subjectivity
            
            # הוספת משקל למילים ספציפיות לקריפטו
            crypto_keywords = {
                # חיוביות
                'bullish': 0.5, 'moon': 0.3, 'pump': 0.3, 'surge': 0.4,
                'rally': 0.4, 'breakthrough': 0.5, 'adoption': 0.4,
                'partnership': 0.3, 'upgrade': 0.3, 'growth': 0.3,
                
                # שליליות
                'bearish': -0.5, 'crash': -0.5, 'dump': -0.4, 'plunge': -0.4,
                'hack': -0.6, 'scam': -0.7, 'fraud': -0.7, 'regulation': -0.2,
                'ban': -0.5, 'lawsuit': -0.4, 'sec': -0.3
            }
            
            # התאמת פולריות על סמך מילות מפתח
            lower_text = clean_text.lower()
            keyword_adjustment = 0
            
            for keyword, weight in crypto_keywords.items():
                if keyword in lower_text:
                    keyword_adjustment += weight
            
            # פולריות סופית
            final_polarity = polarity + (keyword_adjustment * 0.3)
            final_polarity = max(-1, min(1, final_polarity))
            
            # קביעת סנטימנט
            if final_polarity > 0.1:
                sentiment = 'positive'
            elif final_polarity < -0.1:
                sentiment = 'negative'
            else:
                sentiment = 'neutral'
            
            result = {
                'sentiment': sentiment,
                'polarity': round(final_polarity, 4),
                'subjectivity': round(subjectivity, 4)
            }
            
            # שמירה ב-cache
            self.sentiment_cache[cache_key] = result
            self.stats['total_analyzed'] += 1
            
            return result
            
        except Exception as e:
            logger.error(f"Sentiment analysis error: {e}")
            return {'sentiment': 'neutral', 'polarity': 0, 'subjectivity': 0.5}
    
    def _clean_text(self, text: str) -> str:
        """ניקוי טקסט לניתוח"""
        # הסרת URLs
        text = re.sub(r'http\S+|www.\S+', '', text)
        
        # הסרת תגי HTML
        text = re.sub(r'<.*?>', '', text)
        
        # הסרת תווים מיוחדים מיותרים
        text = re.sub(r'[^\w\s\.\,\!\?\-]', '', text)
        
        # הסרת רווחים מיותרים
        text = ' '.join(text.split())
        
        return text.strip()
    
    def save_news(self, df: pd.DataFrame):
        """שמירת חדשות לקובץ"""
        if df.empty:
            logger.warning("No news to save")
            return
        
        try:
            # שמירה לקובץ ראשי (דריסה)
            df.to_csv(self.news_file, index=False, encoding='utf-8')
            logger.info(f"Saved {len(df)} news items to {self.news_file}")
            
            # הוספה לארכיון
            if os.path.exists(self.archive_file):
                # טעינת ארכיון קיים
                archive_df = pd.read_csv(self.archive_file)
                
                # הוספת חדשות חדשות
                combined_df = pd.concat([archive_df, df], ignore_index=True)
                
                # הסרת כפילויות
                combined_df = combined_df.drop_duplicates(subset=['url'], keep='last')
                
                # שמירה רק של X הימים האחרונים
                cutoff_date = datetime.now() - timedelta(days=30)
                combined_df['published_at'] = pd.to_datetime(combined_df['published_at'])
                combined_df = combined_df[combined_df['published_at'] > cutoff_date]
                
                combined_df.to_csv(self.archive_file, index=False, encoding='utf-8')
                logger.info(f"Archive updated: {len(combined_df)} total items")
            else:
                # יצירת ארכיון חדש
                df.to_csv(self.archive_file, index=False, encoding='utf-8')
                logger.info("Created new news archive")
                
        except Exception as e:
            logger.error(f"Error saving news: {e}")
    
    def fetch_and_save(self) -> pd.DataFrame:
        """פונקציה ראשית - איסוף ושמירה"""
        logger.info("Starting news collection cycle")
        
        # איסוף חדשות
        df = self.fetch_multiple_sources()
        
        if not df.empty:
            # שמירה
            self.save_news(df)
            
            # הדפסת סיכום
            self._print_summary(df)
        
        return df
    
    def _print_summary(self, df: pd.DataFrame):
        """הדפסת סיכום איסוף"""
        if df.empty:
            return
        
        # סנטימנט כללי
        sentiment_counts = df['sentiment'].value_counts()
        
        logger.info(f"Collection summary:")
        logger.info(f"  Total items: {len(df)}")
        logger.info(f"  Sentiment: Positive={sentiment_counts.get('positive', 0)}, "
                   f"Negative={sentiment_counts.get('negative', 0)}, "
                   f"Neutral={sentiment_counts.get('neutral', 0)}")
        
        # מטבעות מובילים
        currency_mentions = {}
        for currencies in df['currencies']:
            if currencies != 'General':
                for currency in currencies.split(','):
                    currency_mentions[currency] = currency_mentions.get(currency, 0) + 1
        
        if currency_mentions:
            top_currencies = sorted(currency_mentions.items(), key=lambda x: x[1], reverse=True)[:5]
            logger.info(f"  Top mentioned: {', '.join([f'{c[0]}({c[1]})' for c in top_currencies])}")
        
        # חדשות חשובות
        top_news = df.nlargest(3, 'importance_score')[['title', 'importance_score']]
        logger.info("  Top important news:")
        for _, news in top_news.iterrows():
            logger.info(f"    - {news['title'][:80]}... (score: {news['importance_score']:.1f})")
    
    def get_market_sentiment(self, currency: Optional[str] = None) -> Dict:
        """ניתוח סנטימנט שוק כללי או למטבע ספציפי"""
        try:
            if os.path.exists(self.news_file):
                df = pd.read_csv(self.news_file)
                
                # סינון לפי מטבע אם נדרש
                if currency:
                    df = df[df['currencies'].str.contains(currency, na=False)]
                
                if df.empty:
                    return {'sentiment': 'neutral', 'confidence': 0}
                
                # חישוב סנטימנט משוקלל
                df['weight'] = df['importance_score'] / 100
                weighted_polarity = (df['sentiment_polarity'] * df['weight']).sum() / df['weight'].sum()
                
                # קביעת סנטימנט
                if weighted_polarity > 0.1:
                    sentiment = 'bullish'
                elif weighted_polarity < -0.1:
                    sentiment = 'bearish'
                else:
                    sentiment = 'neutral'
                
                # רמת ביטחון
                confidence = min(abs(weighted_polarity) * 100, 100)
                
                return {
                    'sentiment': sentiment,
                    'polarity': round(weighted_polarity, 4),
                    'confidence': round(confidence, 2),
                    'sample_size': len(df),
                    'currency': currency or 'Market'
                }
            
            return {'sentiment': 'neutral', 'confidence': 0}
            
        except Exception as e:
            logger.error(f"Error calculating market sentiment: {e}")
            return {'sentiment': 'neutral', 'confidence': 0}


def run_news_monitor(interval: int = 300):
    """הפעלת מוניטור חדשות רציף"""
    collector = NewsCollector(
        currencies=Config.DEFAULT_COINS[:15],
        max_posts=100,
        analyze_sentiment=True
    )
    
    logger.info(f"News monitor started - interval: {interval}s")
    
    while True:
        try:
            # איסוף חדשות
            df = collector.fetch_and_save()
            
            # ניתוח סנטימנט שוק
            market_sentiment = collector.get_market_sentiment()
            logger.info(f"Market sentiment: {market_sentiment['sentiment']} "
                       f"(confidence: {market_sentiment['confidence']}%)")
            
            # סנטימנט למטבעות מובילים
            for currency in ['BTC', 'ETH', 'SOL']:
                sentiment = collector.get_market_sentiment(currency)
                if sentiment['sample_size'] > 0:
                    logger.info(f"{currency} sentiment: {sentiment['sentiment']} "
                               f"(confidence: {sentiment['confidence']}%)")
            
            # המתנה
            time.sleep(interval)
            
        except KeyboardInterrupt:
            logger.info("News monitor stopped by user")
            break
        except Exception as e:
            logger.error(f"Monitor error: {e}", exc_info=True)
            time.sleep(interval)


def test_news_collector():
    """בדיקת איסוף חדשות"""
    print("\n📰 Testing News Collector")
    print("="*50)
    
    collector = NewsCollector(
        currencies=['BTC', 'ETH', 'SOL'],
        max_posts=10,
        analyze_sentiment=True
    )
    
    print("\n🔍 Fetching news...")
    df = collector.fetch_and_save()
    
    if not df.empty:
        print(f"\n✅ Collected {len(df)} news items")
        
        # הצגת כותרות
        print("\n📋 Latest headlines:")
        for _, news in df.head(5).iterrows():
            sentiment_emoji = {'positive': '🟢', 'negative': '🔴', 'neutral': '🟡'}
            emoji = sentiment_emoji.get(news['sentiment'], '⚪')
            print(f"{emoji} {news['title'][:80]}...")
            print(f"   Source: {news['source']} | Currencies: {news['currencies']}")
            print(f"   Importance: {news['importance_score']:.1f} | Polarity: {news['sentiment_polarity']:.3f}")
            print()
        
        # סיכום סנטימנט
        sentiment_summary = collector.get_market_sentiment()
        print(f"\n📊 Market Sentiment: {sentiment_summary['sentiment'].upper()}")
        print(f"   Confidence: {sentiment_summary['confidence']}%")
        print(f"   Based on: {sentiment_summary['sample_size']} articles")
        
    else:
        print("\n❌ No news collected")
    
    # הצגת סטטיסטיקות
    print(f"\n📈 Statistics:")
    print(f"   Total fetched: {collector.stats['total_fetched']}")
    print(f"   Total analyzed: {collector.stats['total_analyzed']}")
    print(f"   Errors: {collector.stats['errors']}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Crypto News Collector')
    parser.add_argument('--test', action='store_true', help='Run test mode')
    parser.add_argument('--monitor', action='store_true', help='Run continuous monitor')
    parser.add_argument('--interval', type=int, default=300, help='Update interval in seconds')
    parser.add_argument('--currencies', nargs='+', help='Specific currencies to track')
    
    args = parser.parse_args()
    
    if args.test:
        test_news_collector()
    elif args.monitor:
        run_news_monitor(interval=args.interval)
    else:
        # הרצה בודדת
        collector = NewsCollector(
            currencies=args.currencies or Config.DEFAULT_COINS[:10]
        )
        collector.fetch_and_save()