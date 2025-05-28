import subprocess
import os
import logging
from datetime import datetime
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

class GitManager:
    """מנהל Git אוטומטי לגיבוי ועדכון קוד"""
    
    def __init__(self, repo_path: Optional[str] = None):
        self.repo_path = repo_path or os.getcwd()
        self.git_exists = os.path.exists(os.path.join(self.repo_path, '.git'))
        
    def is_git_installed(self) -> bool:
        """בדיקה אם Git מותקן במערכת"""
        try:
            subprocess.run(['git', '--version'], capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    def init_repo(self) -> bool:
        """אתחול repository חדש אם לא קיים"""
        if self.git_exists:
            return True
            
        try:
            subprocess.run(['git', 'init'], cwd=self.repo_path, check=True)
            logger.info("Initialized new Git repository")
            self.git_exists = True
            
            # יצירת .gitignore בסיסי
            self._create_gitignore()
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to initialize Git repo: {e}")
            return False
    
    def _create_gitignore(self):
        """יצירת קובץ .gitignore בסיסי"""
        gitignore_content = """# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
ENV/
.venv

# IDE
.idea/
.vscode/
*.swp
*.swo

# Logs
logs/
*.log

# Environment variables
.env
.env.local
.env.*.local

# Data files (optional - uncomment if needed)
# data/*.csv
# data/*.json

# Temporary files
*.tmp
*.temp
.DS_Store
Thumbs.db

# Jupyter
.ipynb_checkpoints/

# Testing
.pytest_cache/
.coverage
htmlcov/

# Distribution
dist/
build/
*.egg-info/
"""
        
        gitignore_path = os.path.join(self.repo_path, '.gitignore')
        if not os.path.exists(gitignore_path):
            with open(gitignore_path, 'w') as f:
                f.write(gitignore_content)
            logger.info("Created .gitignore file")
    
    def has_changes(self) -> bool:
        """בדיקה אם יש שינויים לא מחויבים"""
        if not self.git_exists:
            return False
            
        try:
            result = subprocess.run(
                ['git', 'status', '--porcelain'],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            return bool(result.stdout.strip())
        except subprocess.CalledProcessError:
            return False
    
    def add_all(self) -> bool:
        """הוספת כל הקבצים לאזור הבמה"""
        try:
            subprocess.run(['git', 'add', '.'], cwd=self.repo_path, check=True)
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to add files: {e}")
            return False
    
    def commit(self, message: Optional[str] = None) -> bool:
        """ביצוע commit"""
        if message is None:
            message = f"Auto-update {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            
        try:
            subprocess.run(
                ['git', 'commit', '-m', message],
                cwd=self.repo_path,
                check=True
            )
            logger.info(f"Committed changes: {message}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to commit: {e}")
            return False
    
    def push(self, remote: str = 'origin', branch: str = 'main') -> bool:
        """דחיפת שינויים ל-remote"""
        try:
            subprocess.run(
                ['git', 'push', remote, branch],
                cwd=self.repo_path,
                check=True
            )
            logger.info(f"Pushed to {remote}/{branch}")
            return True
        except subprocess.CalledProcessError as e:
            # נסיון עם master אם main נכשל
            if branch == 'main':
                try:
                    subprocess.run(
                        ['git', 'push', remote, 'master'],
                        cwd=self.repo_path,
                        check=True
                    )
                    logger.info(f"Pushed to {remote}/master")
                    return True
                except subprocess.CalledProcessError:
                    pass
                    
            logger.warning(f"Failed to push: {e}")
            return False
    
    def pull(self, remote: str = 'origin', branch: str = 'main') -> bool:
        """משיכת עדכונים מ-remote"""
        try:
            subprocess.run(
                ['git', 'pull', remote, branch],
                cwd=self.repo_path,
                check=True
            )
            logger.info(f"Pulled from {remote}/{branch}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to pull: {e}")
            return False
    
    def get_current_branch(self) -> Optional[str]:
        """קבלת הענף הנוכחי"""
        try:
            result = subprocess.run(
                ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            return None
    
    def get_remote_url(self, remote: str = 'origin') -> Optional[str]:
        """קבלת כתובת ה-remote"""
        try:
            result = subprocess.run(
                ['git', 'config', '--get', f'remote.{remote}.url'],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            return None
    
    def has_remote(self) -> bool:
        """בדיקה אם יש remote מוגדר"""
        return self.get_remote_url() is not None
    
    def auto_update(self, 
                   commit_message: Optional[str] = None,
                   push_to_remote: bool = True) -> Tuple[bool, str]:
        """עדכון אוטומטי מלא"""
        
        # בדיקות ראשוניות
        if not self.is_git_installed():
            return False, "Git is not installed"
            
        if not self.git_exists:
            logger.info("No Git repository found. Skipping auto-update.")
            return False, "No Git repository"
        
        # בדיקת שינויים
        if not self.has_changes():
            logger.info("No changes to commit")
            return True, "No changes"
        
        # הוספה וחיוב
        if not self.add_all():
            return False, "Failed to add files"
            
        if not self.commit(commit_message):
            return False, "Failed to commit"
        
        # דחיפה ל-remote אם נדרש ואפשרי
        if push_to_remote and self.has_remote():
            branch = self.get_current_branch()
            if branch and self.push(branch=branch):
                return True, f"Committed and pushed to {branch}"
            else:
                return True, "Committed locally (push failed)"
        
        return True, "Committed locally"
    
    def status_report(self) -> dict:
        """דוח מצב מלא"""
        return {
            'git_installed': self.is_git_installed(),
            'repo_exists': self.git_exists,
            'has_changes': self.has_changes() if self.git_exists else False,
            'current_branch': self.get_current_branch(),
            'remote_url': self.get_remote_url(),
            'repo_path': self.repo_path
        }


# פונקציות עזר לשימוש מהיר
def quick_backup(message: Optional[str] = None) -> bool:
    """גיבוי מהיר של השינויים"""
    manager = GitManager()
    success, status = manager.auto_update(
        commit_message=message,
        push_to_remote=True
    )
    
    if success:
        print(f"✅ Git backup: {status}")
    else:
        print(f"❌ Git backup failed: {status}")
        
    return success


if __name__ == '__main__':
    # דוגמה לשימוש
    manager = GitManager()
    
    # הדפסת דוח מצב
    print("Git Status Report:")
    print("-" * 40)
    for key, value in manager.status_report().items():
        print(f"{key}: {value}")
    
    # ביצוע עדכון אוטומטי
    if input("\nPerform auto-update? (y/n): ").lower() == 'y':
        success, message = manager.auto_update()
        print(f"\nResult: {message}")