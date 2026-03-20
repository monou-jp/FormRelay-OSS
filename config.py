import os
import uuid

# ベースディレクトリ
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# セキュリティ設定
def _get_secret_key():
    env_key = os.getenv('SECRET_KEY')
    if env_key:
        return env_key
    
    key_file = os.path.join(BASE_DIR, 'data', 'secret.key')
    if os.path.exists(key_file):
        with open(key_file, 'r') as f:
            return f.read().strip()
    
    # 新規生成して保存
    new_key = str(uuid.uuid4())
    try:
        os.makedirs(os.path.dirname(key_file), exist_ok=True)
        with open(key_file, 'w') as f:
            f.write(new_key)
    except Exception:
        # 書き込み失敗時はメモリ上のみ
        pass
    return new_key

SECRET_KEY = _get_secret_key()
SESSION_NAME = 'formrelay_session'
SALT = 'formrelay_salt_for_it_sd'

# データベース設定
DATABASE_PATH = os.path.join(BASE_DIR, 'data', 'formrelay.db')

# アップロード設定
UPLOAD_DIR = os.path.join(BASE_DIR, 'uploads')
MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_EXTENSIONS = {'.pdf', '.jpg', '.jpeg', '.png', '.gif', '.zip', '.txt', '.doc', '.docx'}

# メール設定
MAIL_BACKEND = 'smtp'  # 'smtp' or 'api'
SMTP_SERVER = 'localhost'
SMTP_PORT = 1025
SMTP_USER = ''
SMTP_PASSWORD = ''
SMTP_USE_TLS = False
FROM_EMAIL = 'noreply@example.com'

# SendGrid/Mailgun API設定 (API使用時)
MAIL_API_KEY = ''
MAIL_DOMAIN = ''

# レート制限
RATE_LIMIT_SECONDS = 60  # 同じIPからの送信間隔
RATE_LIMIT_COUNT = 5     # 指定時間内に許可する回数

# reCAPTCHA (オプション)
RECAPTCHA_ENABLED = False
RECAPTCHA_SITE_KEY = ''
RECAPTCHA_SECRET_KEY = ''

# ページング
PER_PAGE = 20

# サーバー設定
BASE_URL = 'http://localhost:8080'

# 開発モード
DEBUG = True

# ログ設定
LOG_LEVEL = 'INFO'
LOG_FILE = os.path.join(BASE_DIR, 'data', 'app.log')

# バックアップ設定
BACKUP_INTERVAL_HOURS = 24  # バックアップを実行する間隔 (時間)
