#!/usr/bin/env python3
"""
Debug tool for Kraken API connection
"""

import os
import sys
import krakenex
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config

def test_connection():
    """בדיקת חיבור בסיסית"""
    print("\n🔧 Kraken API Debug Tool")
    print("="*50)
    
    # בדיקת API keys
    print("\n1️⃣ Checking API Keys:")
    if Config.KRAKEN_API_KEY:
        print(f"   ✅ API Key: ...{Config.KRAKEN_API_KEY[-8:]}")
    else:
        print("   ❌ API Key: Missing")
        
    if Config.KRAKEN_API_SECRET:
        print(f"   ✅ API Secret: ...{Config.KRAKEN_API_SECRET[-8:]}")
    else:
        print("   ❌ API Secret: Missing")
    
    if not (Config.KRAKEN_API_KEY and Config.KRAKEN_API_SECRET):
        print("\n❌ API credentials missing. Please set them in .env file")
        return False
    
    # יצירת API object
    api = krakenex.API(Config.KRAKEN_API_KEY, Config.KRAKEN_API_SECRET)
    
    # בדיקת שעון מערכת
    print("\n2️⃣ Testing Public API (Server Time):")
    try:
        resp = api.query_public('Time')
        if resp.get('error'):
            print(f"   ❌ Error: {resp['error']}")
        else:
            server_time = resp['result']['unixtime']
            local_time = datetime.now().timestamp()
            diff = abs(server_time - local_time)
            print(f"   ✅ Server time: {datetime.fromtimestamp(server_time)}")
            print(f"   📍 Local time: {datetime.now()}")
            print(f"   ⏱️  Time diff: {diff:.1f} seconds")
            
            if diff > 5:
                print("   ⚠️  Warning: Time difference > 5 seconds")
    except Exception as e:
        print(f"   ❌ Connection error: {e}")
        return False
    
    # בדיקת Private API
    print("\n3️⃣ Testing Private API (Balance):")
    try:
        resp = api.query_private('Balance')
        if resp.get('error'):
            print(f"   ❌ Error: {resp['error']}")
            if 'EAPI:Invalid key' in str(resp['error']):
                print("   💡 Invalid API key - check your credentials")
            elif 'Permission denied' in str(resp['error']):
                print("   💡 API key exists but lacks permissions")
        else:
            balances = resp.get('result', {})
            print(f"   ✅ Connected! Found {len(balances)} assets")
            
            # הצגת יתרות
            if balances:
                print("\n   💰 Your balances:")
                for asset, amount in list(balances.items())[:5]:
                    if float(amount) > 0:
                        print(f"      • {asset}: {float(amount):.8f}")
                if len(balances) > 5:
                    print(f"      ... and {len(balances)-5} more")
    except Exception as e:
        print(f"   ❌ Private API error: {e}")
    
    # בדיקת זוגות מסחר
    print("\n4️⃣ Testing Trading Pairs:")
    try:
        resp = api.query_public('AssetPairs')
        if resp.get('error'):
            print(f"   ❌ Error: {resp['error']}")
        else:
            pairs = resp.get('result', {})
            usd_pairs = [p for p in pairs if 'USD' in p and pairs[p].get('status') == 'online']
            print(f"   ✅ Found {len(usd_pairs)} active USD pairs")
            print(f"   📊 Examples: {', '.join(usd_pairs[:5])}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    print("\n" + "="*50)
    print("✅ Debug complete!")
    
    return True

def main():
    """הפעלה ראשית"""
    success = test_connection()
    
    if success:
        print("\n💡 Tips:")
        print("   • Your connection is working properly")
        print("   • You can start trading (carefully!)")
        print("   • Use 'demo' mode first to test strategies")
    else:
        print("\n💡 Troubleshooting:")
        print("   • Check your internet connection")
        print("   • Verify API keys in .env file")
        print("   • Ensure API key has proper permissions")
        print("   • Check Kraken API status online")
    
    input("\nPress Enter to continue...")

if __name__ == "__main__":
    main()