from bottle import Jinja2Template, request, response, redirect
import config
from ..models.schema import User
from ..utils.auth import verify_session_token
import os

# Jinja2の設定
template_path = os.path.join(config.BASE_DIR, 'app', 'templates')
jinja_view = Jinja2Template.settings.get('loader') # ダミー

def render_template(template_name, **kwargs):
    # 手動でJinja2環境を作るか、Bottleの機能をうまく使う
    # ここではカスタムのヘルパーを定義
    from jinja2 import Environment, FileSystemLoader
    env = Environment(loader=FileSystemLoader(template_path))
    template = env.get_template(template_name)
    
    # 共通変数を注入
    kwargs['request'] = request
    kwargs['config'] = config
    kwargs['user'] = getattr(request, 'user', None)
    
    return template.render(**kwargs)

def login_required(callback):
    def wrapper(*args, **kwargs):
        # request.get_cookie(..., secret=...) は Bottle の内部的な署名付きクッキー用
        # 今回は itsdangerous で自前シリアル化しているので、通常のクッキーとして取得
        token = request.get_cookie(config.SESSION_NAME)
        if not token:
            return redirect('/login')
        
        user_id = verify_session_token(token)
        if not user_id:
            return redirect('/login')
        
        user = None
        try:
            from ..models.schema import User
            user = User.get_by_id(user_id)
        except User.DoesNotExist:
            pass

        if not user or not user.is_active:
            return redirect('/login')
            
        request.user = user
        return callback(*args, **kwargs)
    return wrapper

def admin_required(callback):
    @login_required
    def wrapper(*args, **kwargs):
        if request.user.role != 'admin':
            return "Forbidden: Admin access required", 403
        return callback(*args, **kwargs)
    return wrapper
