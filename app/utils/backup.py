import shutil
import datetime
import os
import config
from .logger import logger

def backup_db(force=False):
    """
    SQLite データベースファイルのバックアップを作成します。
    """
    db_path = config.DATABASE_PATH
    if not os.path.exists(db_path):
        logger.warning(f"Database file not found: {db_path}")
        return False
    
    # バックアップ先ディレクトリ
    backup_dir = os.path.join(config.BASE_DIR, 'data', 'backups')
    os.makedirs(backup_dir, exist_ok=True)

    # インターバルチェック (force=True の場合はスキップ)
    if not force:
        # 既存のバックアップファイルを取得 (更新日時順にソート)
        files = [os.path.join(backup_dir, f) for f in os.listdir(backup_dir) if f.endswith('.bak')]
        if files:
            last_backup_file = max(files, key=os.path.getmtime)
            mtime = os.path.getmtime(last_backup_file)
            last_backup_time = datetime.datetime.fromtimestamp(mtime)
            interval = datetime.timedelta(hours=getattr(config, 'BACKUP_INTERVAL_HOURS', 24))
            
            if datetime.datetime.now() < last_backup_time + interval:
                # まだバックアップのタイミングではない
                return True
    
    # タイムスタンプを付与したファイル名
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    backup_file = os.path.join(backup_dir, f'formrelay_{timestamp}.db.bak')
    
    try:
        shutil.copy2(db_path, backup_file)
        logger.info(f"Database backup created: {backup_file}")
        
        # 古いバックアップの削除 (最新の5件のみ残す)
        # 削除時にはもう一度リストを取得し直す (新しく作成した分も含まれる)
        backups = sorted([f for f in os.listdir(backup_dir) if f.endswith('.bak')])
        if len(backups) > 5:
            for b in backups[:-5]:
                os.remove(os.path.join(backup_dir, b))
                logger.info(f"Old backup removed: {b}")
        
        return True
    except Exception as e:
        logger.error(f"Database backup failed: {e}")
        return False

def cleanup_old_submissions(days=90):
    """
    古い送信データをクリーンアップするロジック (実装のみ、自動実行は別途)
    """
    from ..models.schema import Submission
    limit_date = datetime.datetime.now() - datetime.timedelta(days=days)
    count = Submission.delete().where(Submission.created_at < limit_date).execute()
    if count > 0:
        logger.info(f"Cleaned up {count} old submissions.")
    return count
