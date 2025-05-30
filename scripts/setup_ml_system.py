# scripts/setup_ml_system.py
#!/usr/bin/env python3
"""
הגדרת מערכת ML מלאה
"""
import os
import sys
import subprocess

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def main():
    print("🤖 Setting up ML Prediction System")
    print("="*50)
    
    # 1. בדיקת נתונים
    print("\n📊 Step 1: Checking data availability...")
    if not os.path.exists('data/market_history.csv'):
        print("❌ No historical data found!")
        print("💡 Run data collection first: python main.py --mode collect")
        return
    
    # 2. הכנת נתונים
    print("\n🔧 Step 2: Preparing ML data...")
    try:
        subprocess.run([sys.executable, 'scripts/prepare_ml_data.py'], check=True)
    except Exception as e:
        print(f"❌ Error preparing data: {e}")
        return
    
    # 3. אימון מודלים
    print("\n🚀 Step 3: Training ML models...")
    try:
        subprocess.run([sys.executable, 'scripts/train_ml_model.py'], check=True)
    except Exception as e:
        print(f"❌ Error training models: {e}")
        return
    
    # 4. בדיקת מודלים
    print("\n✅ Step 4: Verifying models...")
    from modules.ml_predictor import MLPredictor
    
    predictor = MLPredictor()
    info = predictor.get_model_info()
    
    print(f"\n📊 Available models: {len(info['available_models'])}")
    for model_key, details in info['model_details'].items():
        print(f"\n   {model_key}:")
        print(f"     - Model: {details['best_model']}")
        print(f"     - Accuracy: {details['accuracy']:.2%}")
        print(f"     - R² Score: {details['r2_score']:.4f}")
    
    print("\n✅ ML system setup complete!")
    print("\n🎯 Next steps:")
    print("   1. Test predictions in the dashboard")
    print("   2. Monitor model performance")
    print("   3. Retrain periodically with new data")

if __name__ == "__main__":
    main()