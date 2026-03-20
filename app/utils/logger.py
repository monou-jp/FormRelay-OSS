import logging
import sys
import os
import config

def setup_logging():
    """
    アプリケーションのロギング設定を初期化します。
    ファイルとコンソールの両方にログを出力します。
    """
    # ログレベルの取得
    level = getattr(logging, config.LOG_LEVEL.upper(), logging.INFO)
    
    # ログフォーマットの設定
    formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s in %(module)s: %(message)s'
    )
    
    # ルートロガーの設定
    logger = logging.getLogger()
    logger.setLevel(level)
    
    # コンソールハンドラ (CGIでの出力を考慮してstderrへ出力)
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # ファイルハンドラ (ログファイルパスが設定されている場合)
    if config.LOG_FILE:
        # ディレクトリが存在することを確認
        log_dir = os.path.dirname(config.LOG_FILE)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
            
        file_handler = logging.FileHandler(config.LOG_FILE, encoding='utf-8')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        # 即座に書き込むために
        file_handler.flush()
        
    return logger

logger = logging.getLogger(__name__)
