#!/usr/local/bin/python3.7
from bottle import Bottle, run, static_file
import config
import os
import logging
from app.models.base import db
from app.models.schema import User, FormConfig, Submission, Attachment, MailLog, StatusHistory, RateLimit
from app.routes.api import setup_api_routes
from app.routes.admin import setup_admin_routes
from app.utils.logger import setup_logging
from app.utils.backup import backup_db

# ログのセットアップ
setup_logging()
logger = logging.getLogger(__name__)

app = Bottle()

# データベースの初期化
def init_db():
    db.connect()
    db.create_tables([User, FormConfig, Submission, Attachment, MailLog, StatusHistory, RateLimit])
    
    # マイグレーションの実行
    try:
        from migrate_db import run_migrations
        run_migrations()
    except ImportError:
        logger.warning("Migration script not found.")
    except Exception as e:
        logger.error(f"Migration failed: {e}")

    # 初期管理者の作成 (存在しない場合)
    from app.utils.auth import hash_password
    if User.select().count() == 0:
        User.create(
            username='admin',
            password=hash_password('admin123'),
            role='admin'
        )
        logger.info("Default admin created: admin / admin123")

# 静的ファイルの配信
@app.route('/static/<filename:path>')
def send_static(filename):
    return static_file(filename, root=os.path.join(config.BASE_DIR, 'app', 'static'))

# 各ルートのセットアップ
setup_api_routes(app)
setup_admin_routes(app)

# サーバー起動 (CGIサーバー指定があるが、開発時は通常のサーバーで)
if __name__ == '__main__':
    init_db()
    
    # アップロードディレクトリの作成
    os.makedirs(config.UPLOAD_DIR, exist_ok=True)
    
    # バックアップの実行
    # CGI実行時はリクエストごとに走るため、前回のバックアップから一定時間経過している場合のみ実行するように修正
    backup_db()

    if os.path.exists("./dev.flag"):
        run(app, host='localhost', port=int(os.getenv('PORT', 8080)), debug=config.DEBUG, reloader=config.DEBUG)
    else:
        run(app, server="cgi")
