#!/usr/bin/env python3
"""
כלי למיפוי וזיהוי סמלי מטבעות ב-Kraken
מטפל בסיומות מיוחדות כמו .S (Staked), .F (Futures), .M (Multi-collateral)
"""

import krakenex
import pandas as pd
from collections import defaultdict

class KrakenSymbolMapper:
    """ממפה סמלי Kraken לשמות סטנדרטיים"""
    
    # מיפוי ידני של סמלים מיוחדים
    SYMBOL_MAP = {
        # מטבעות רגילים עם prefix
        'XBT': 'BTC', 'XXBT': 'BTC',
        'XETH': 'ETH', 'XXETH': 'ETH',
        'XXRP': 'XRP', 'XXXRP': 'XRP',
        'XLTC': 'LTC', 'XXLTC': 'LTC',
        'XXLM': 'XLM', 'XXXLM': 'XLM',
        'XDOGE': 'DOGE', 'XXDOGE': 'DOGE',
        'XETC': 'ETC', 'XXETC': 'ETC',
        'XMLN': 'MLN', 'XXML': 'MLN',
        'XREP': 'REP', 'XXREP': 'REP',
        'XXMR': 'XMR', 'XXXMR': 'XMR',
        'XXTZ': 'XTZ', 'XXXTZ': 'XTZ',
        'XZEC': 'ZEC', 'XXZEC': 'ZEC',
        
        # Staking variants (.S suffix)
        'ADA.S': 'ADA', 'ADAXS': 'ADA',
        'ATOM.S': 'ATOM', 'ATOMXS': 'ATOM',
        'DOT.S': 'DOT', 'DOTXS': 'DOT',
        'FLOW.S': 'FLOW', 'FLOWHS': 'FLOW',
        'KSM.S': 'KSM', 'KSMXS': 'KSM',
        'MATIC.S': 'MATIC', 'MATICXS': 'MATIC',
        'SCRT.S': 'SCRT', 'SCRTBS': 'SCRT',
        'SOL.S': 'SOL', 'SOLXS': 'SOL',
        'TRX.S': 'TRX', 'TRXXS': 'TRX',
        'XTZ.S': 'XTZ', 'XTZXS': 'XTZ',
        
        # Multi-collateral variants (.M suffix)
        'USDC.M': 'USDC', 'USDCM': 'USDC',
        'USDT.M': 'USDT', 'USDTM': 'USDT',
        'DAI.M': 'DAI', 'DAIM': 'DAI',
        'PAX.M': 'PAX', 'PAXM': 'PAX',
        
        # Futures variants (.F suffix)
        'BTC.F': 'BTC', 'XBTF': 'BTC',
        'ETH.F': 'ETH', 'ETHF': 'ETH',
        
        # Special cases
        'ETHW': 'ETH',  # ETH PoW fork
        'LUNA2': 'LUNA',  # New LUNA
        'LUNA': 'LUNC',  # Luna Classic
        'EUROC': 'EURC',  # Euro Coin
        
        # Fiat currencies
        'ZUSD': 'USD', 'ZEUR': 'EUR',
        'ZGBP': 'GBP', 'ZCAD': 'CAD',
        'ZJPY': 'JPY', 'ZAUD': 'AUD',
        'ZCHF': 'CHF'
    }
    
    # סיומות מיוחדות וההסבר שלהן
    SUFFIXES = {
        '.S': 'Staked (סטייקינג)',
        '.F': 'Futures (חוזים עתידיים)',
        '.M': 'Multi-collateral (רב-צדדי)',
        '.B': 'Bond (אג״ח)',
        '.P': 'Perpetual (נצחי)',
        'XS': 'Staked variant',
        'HS': 'Staked variant',
        'BS': 'Staked variant'
    }
    
    @classmethod
    def normalize_symbol(cls, symbol: str) -> str:
        """נרמל סמל Kraken לשם סטנדרטי"""
        symbol = symbol.upper()
        
        # בדוק במיפוי הישיר
        if symbol in cls.SYMBOL_MAP:
            return cls.SYMBOL_MAP[symbol]
        
        # הסר סיומות
        base_symbol = symbol
        for suffix in ['.S', '.F', '.M', '.B', '.P']:
            if symbol.endswith(suffix):
                base_symbol = symbol[:-2]
                break
        
        # בדוק שוב במיפוי
        if base_symbol in cls.SYMBOL_MAP:
            return cls.SYMBOL_MAP[base_symbol]
        
        # הסר USD/ZUSD מהסוף
        if base_symbol.endswith('USD'):
            base_symbol = base_symbol[:-3]
        elif base_symbol.endswith('ZUSD'):
            base_symbol = base_symbol[:-4]
        
        # הסר X/Z prefix
        if base_symbol.startswith('X') and len(base_symbol) > 3:
            base_symbol = base_symbol[1:]
        elif base_symbol.startswith('Z') and len(base_symbol) > 3:
            base_symbol = base_symbol[1:]
        
        # בדוק שוב במיפוי
        if base_symbol in cls.SYMBOL_MAP:
            return cls.SYMBOL_MAP[base_symbol]
        
        return base_symbol
    
    @classmethod
    def get_all_pairs_info(cls):
        """קבל מידע על כל הזוגות ב-Kraken"""
        api = krakenex.API()
        
        print("🔍 מושך רשימת כל הזוגות מ-Kraken...")
        
        try:
            # שליפת כל הזוגות
            resp = api.query_public('AssetPairs')
            if resp.get('error'):
                print(f"❌ שגיאה: {resp['error']}")
                return pd.DataFrame()
            
            pairs_data = []
            
            # עיבוד כל זוג
            for pair_name, pair_info in resp.get('result', {}).items():
                # רק זוגות עם USD
                if 'USD' not in pair_name:
                    continue
                
                base = pair_info.get('base', '')
                quote = pair_info.get('quote', '')
                status = pair_info.get('status', '')
                
                # נרמל את שם המטבע
                normalized_base = cls.normalize_symbol(base)
                
                # זהה סוג מיוחד
                special_type = 'Regular'
                for suffix, desc in cls.SUFFIXES.items():
                    if suffix in base or suffix in pair_name:
                        special_type = desc
                        break
                
                pairs_data.append({
                    'Pair': pair_name,
                    'Base': base,
                    'Quote': quote,
                    'Normalized': normalized_base,
                    'Type': special_type,
                    'Status': status,
                    'Original != Normalized': base != normalized_base
                })
            
            df = pd.DataFrame(pairs_data)
            return df.sort_values(['Normalized', 'Type'])
            
        except Exception as e:
            print(f"❌ שגיאה: {e}")
            return pd.DataFrame()
    
    @classmethod
    def print_mapping_report(cls):
        """הדפס דוח מיפוי מלא"""
        df = cls.get_all_pairs_info()
        
        if df.empty:
            return
        
        print("\n📊 דוח מיפוי סמלי Kraken")
        print("="*80)
        
        # סטטיסטיקות כלליות
        print(f"\n📈 סטטיסטיקות:")
        print(f"  • סה״כ זוגות USD: {len(df)}")
        print(f"  • זוגות רגילים: {len(df[df['Type'] == 'Regular'])}")
        print(f"  • זוגות מיוחדים: {len(df[df['Type'] != 'Regular'])}")
        print(f"  • מטבעות ייחודיים: {df['Normalized'].nunique()}")
        
        # זוגות מיוחדים
        special_df = df[df['Type'] != 'Regular']
        if not special_df.empty:
            print(f"\n🌟 זוגות מיוחדים ({len(special_df)}):")
            print(special_df[['Pair', 'Base', 'Normalized', 'Type']].to_string(index=False))
        
        # מטבעות עם מספר וריאנטים
        print("\n🔄 מטבעות עם מספר וריאנטים:")
        variants = df.groupby('Normalized')['Base'].unique()
        for norm, bases in variants.items():
            if len(bases) > 1:
                print(f"  • {norm}: {', '.join(bases)}")
        
        # מיפויים שדורשים תיקון
        needs_mapping = df[df['Original != Normalized']]
        if not needs_mapping.empty:
            print(f"\n🔧 סמלים שעברו נרמול ({len(needs_mapping)}):")
            for _, row in needs_mapping.iterrows():
                print(f"  • {row['Base']} → {row['Normalized']} ({row['Type']})")
    
    @classmethod
    def test_symbol(cls, symbol: str):
        """בדוק נרמול של סמל ספציפי"""
        normalized = cls.normalize_symbol(symbol)
        print(f"\n🔍 בדיקת סמל: {symbol}")
        print(f"  • נרמול: {normalized}")
        print(f"  • שונה: {'כן' if symbol != normalized else 'לא'}")
        
        # בדוק אם קיים ב-Kraken
        api = krakenex.API()
        
        # נסה וריאציות
        variations = [
            f"{symbol}USD",
            f"X{symbol}USD",
            f"{symbol}ZUSD",
            f"X{symbol}ZUSD"
        ]
        
        print(f"\n  בודק וריאציות:")
        for var in variations:
            try:
                resp = api.query_public('Ticker', {'pair': var})
                if not resp.get('error') and resp.get('result'):
                    print(f"    ✅ {var} - נמצא!")
                    return
            except:
                pass
        
        print(f"    ❌ לא נמצא ב-Kraken")

def main():
    """תוכנית ראשית"""
    print("🗺️  Kraken Symbol Mapper")
    print("="*50)
    
    while True:
        print("\n1. הצג דוח מיפוי מלא")
        print("2. בדוק סמל ספציפי")
        print("3. הצג רשימת כל הזוגות")
        print("q. יציאה")
        
        choice = input("\nבחירה: ").strip()
        
        if choice == '1':
            KrakenSymbolMapper.print_mapping_report()
        
        elif choice == '2':
            symbol = input("הכנס סמל (לדוגמה: ADA.S): ").strip()
            if symbol:
                KrakenSymbolMapper.test_symbol(symbol)
        
        elif choice == '3':
            df = KrakenSymbolMapper.get_all_pairs_info()
            if not df.empty:
                print("\n📋 כל זוגות ה-USD:")
                print(df[['Pair', 'Base', 'Normalized', 'Type']].to_string(index=False))
        
        elif choice.lower() == 'q':
            break

if __name__ == "__main__":
    main()