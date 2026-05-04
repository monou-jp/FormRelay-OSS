import datetime
import urllib.request
import urllib.parse
import json
from ..models.schema import RateLimit
import config

def check_rate_limit(ip):
    # (既存のコードと同じ)
    now = datetime.datetime.now()
    limit_time = now - datetime.timedelta(seconds=config.RATE_LIMIT_SECONDS)
    
    entry, created = RateLimit.get_or_create(ip_address=ip)
    
    if created:
        return True
    
    if entry.last_request_at < limit_time:
        # リセット
        entry.request_count = 1
        entry.last_request_at = now
        entry.save()
        return True
    else:
        if entry.request_count >= config.RATE_LIMIT_COUNT:
            return False
        else:
            entry.request_count += 1
            entry.last_request_at = now
            entry.save()
            return True

def validate_origin(origin, allowed_domains):
    if not allowed_domains or allowed_domains == '*':
        return True
    
    allowed_list = [d.strip() for d in allowed_domains.split(',')]
    if origin in allowed_list:
        return True
    
    # プロトコルを除去して比較なども考慮が必要な場合があるが、基本は一致確認
    return False

def verify_recaptcha(response_token, remote_ip):
    if not config.RECAPTCHA_ENABLED:
        return True
    
    if not response_token:
        return False
        
    url = "https://www.google.com/recaptcha/api/siteverify"
    params = urllib.parse.urlencode({
        'secret': config.RECAPTCHA_SECRET_KEY,
        'response': response_token,
        'remoteip': remote_ip
    }).encode('utf-8')
    
    try:
        req = urllib.request.Request(url, data=params)
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode('utf-8'))
            return result.get('success', False)
    except Exception as e:
        print(f"reCAPTCHA verification error: {e}")
        return False

def is_blacklisted_ip(ip):
    # ブラックリストIPチェック (簡易実装、将来的にDB管理可能)
    blacklist = getattr(config, 'IP_BLACKLIST', [])
    return ip in blacklist

def check_user_agent(ua):
    if not ua:
        return False
    # 簡易的なボットチェック (要件に合わせて拡張)
    bot_keywords = ['bot', 'crawler', 'spider', 'slurp', 'googlebot', 'yandex', 'bingbot']
    ua_lower = ua.lower()
    for kw in bot_keywords:
        if kw in ua_lower:
            return False
    return True

def is_spam_content(form_data, cfg=None):
    """
    コンテンツの内容からスパムかどうかを判定する
    """
    import re
    
    # 判定に使用するテキストを抽出（システムフィールド以外）
    all_text = " ".join([str(v) for k, v in form_data.items() if not k.startswith('_')])
    
    # 1. 日本語含有チェック (設定が有効な場合)
    require_japanese = cfg.require_japanese if cfg else False
    if require_japanese:
        # ひらがな、カタカナ、漢字の範囲
        jp_chars = re.findall(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]', all_text)
        min_jp = getattr(config, 'SPAM_CHECK_MIN_JP_CHARS', 3)
        if len(jp_chars) < min_jp:
            return True, f"Too few Japanese characters ({len(jp_chars)} < {min_jp})"
            
    # 2. URL数のチェック
    urls = re.findall(r'https?://[^\s<>"]+|www\.[^\s<>"]+', all_text)
    max_urls = getattr(config, 'SPAM_CHECK_MAX_URLS', 3)
    if len(urls) > max_urls:
        return True, f"Too many URLs ({len(urls)} > {max_urls})"
        
    # 3. NGワードチェック
    ng_words = getattr(config, 'SPAM_CHECK_NG_WORDS', [])
    all_text_lower = all_text.lower()
    for word in ng_words:
        if word.lower() in all_text_lower:
            return True, f"Contains NG word: {word}"
            
    return False, ""
