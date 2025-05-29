#!/usr/bin/env python3
"""
סקריפט לתיקון Git conflicts
"""

import os
import re

def fix_git_conflicts(file_path):
    """מסיר סימני Git conflict מקובץ"""
    
    if not os.path.exists(file_path):
        print(f"❌ File not found: {file_path}")
        return False
    
    print(f"🔧 Fixing Git conflicts in: {file_path}")
    
    # קריאת הקובץ
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # חיפוש סימני conflict
    conflict_pattern = r'<<<<<<<.*?>>>>>>>'
    conflicts = re.findall(conflict_pattern, content, re.DOTALL)
    
    if conflicts:
        print(f"⚠️  Found {len(conflicts)} conflict(s)")
        
        # הסרת כל סימני ה-conflict
        # שומרים רק את הקוד מה-HEAD (הגרסה הנוכחית)
        cleaned_content = re.sub(
            r'<<<<<<< HEAD(.*?)=======(.*?)>>>>>>> .*?\n',
            r'\1',
            content,
            flags=re.DOTALL
        )
        
        # גיבוי
        backup_path = file_path + '.backup'
        with open(backup_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"📁 Backup saved to: {backup_path}")
        
        # שמירת הקובץ המתוקן
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(cleaned_content)
        
        print("✅ Git conflicts removed!")
        return True
    else:
        print("✅ No Git conflicts found")
        return False

def check_python_files():
    """בודק את כל קבצי Python ב-modules"""
    
    modules_dir = 'modules'
    if not os.path.exists(modules_dir):
        print(f"❌ Directory not found: {modules_dir}")
        return
    
    print(f"🔍 Checking Python files in {modules_dir}/...")
    print("="*50)
    
    for filename in os.listdir(modules_dir):
        if filename.endswith('.py'):
            file_path = os.path.join(modules_dir, filename)
            
            try:
                # ניסיון לקמפל את הקובץ
                with open(file_path, 'r', encoding='utf-8') as f:
                    compile(f.read(), file_path, 'exec')
                print(f"✅ {filename} - OK")
            except SyntaxError as e:
                print(f"❌ {filename} - Syntax Error: {e}")
                
                # בדיקה אם זה Git conflict
                with open(file_path, 'r', encoding='utf-8') as f:
                    if '<<<<<<< HEAD' in f.read():
                        print(f"   ⚠️  Git conflict detected!")
                        fix = input(f"   Fix {filename}? (y/n): ")
                        if fix.lower() == 'y':
                            fix_git_conflicts(file_path)

if __name__ == "__main__":
    print("🔧 Git Conflict Fixer")
    print("="*50)
    
    # בדיקת קובץ ספציפי
    problem_file = 'modules/hybrid_market_collector.py'
    
    if os.path.exists(problem_file):
        fix_git_conflicts(problem_file)
    else:
        print(f"Creating new {problem_file}...")
        
        # יצירת הקובץ מחדש
        wrapper_content = '''"""
Hybrid Market Collector Wrapper
==============================
This file imports the hybrid collector from market_collector.py
to maintain compatibility with main.py
"""

# Import everything from market_collector
from .market_collector import (
    HybridMarketCollector,
    RealTimePriceUpdate,
    WebSocketClient,
    OptimizedHTTPClient,
    run_hybrid_collector
)

# Re-export for compatibility
__all__ = [
    'HybridMarketCollector',
    'RealTimePriceUpdate',
    'WebSocketClient',
    'OptimizedHTTPClient',
    'run_hybrid_collector'
]
'''
        
        with open(problem_file, 'w', encoding='utf-8') as f:
            f.write(wrapper_content)
        
        print(f"✅ Created new {problem_file}")
    
    # בדיקת כל הקבצים
    print("\n" + "="*50)
    check_python_files()