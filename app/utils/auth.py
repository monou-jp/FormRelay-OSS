import hashlib
from itsdangerous import URLSafeTimedSerializer
import config

# パスワードハッシュ化
def hash_password(password):
    # 標準ライブラリ hashlib を使用
    return hashlib.sha256(password.encode()).hexdigest()

def check_password(password, hashed):
    return hash_password(password) == hashed

# セッション管理
serializer = URLSafeTimedSerializer(config.SECRET_KEY, salt=config.SALT)

def generate_session_token(user_id):
    return serializer.dumps(user_id)

def verify_session_token(token, max_age=3600*24):
    try:
        return serializer.loads(token, max_age=max_age)
    except:
        return None

# Authデコレータなどは後ほど bottle と組み合わせて実装
