from bottle import request, response, abort, HTTPResponse
import json
import os
import uuid
import datetime
from ..models.schema import FormConfig, Submission, Attachment
from ..utils.security import check_rate_limit, validate_origin, verify_recaptcha, is_blacklisted_ip, check_user_agent
from ..utils.email import send_email
from ..utils.logger import logger
import config

def setup_api_routes(app):
    @app.hook('after_request')
    def enable_cors():
        response.headers['Access-Control-Allow-Origin'] = '*' # 後で詳細制御
        response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Origin, Accept, Content-Type, X-Requested-With'

    @app.route('/api/form', method=['POST', 'OPTIONS'])
    @app.route('/form/<form_id_path>', method=['POST', 'OPTIONS'])
    @app.route('/f/<form_id_path>', method=['POST', 'OPTIONS'])
    def handle_form_submission(form_id_path=None):
        if request.method == 'OPTIONS':
            return {}

        ip = request.remote_addr
        ua = request.get_header('User-Agent', '')

        # 1. セキュリティチェック (IPブラックリスト)
        if is_blacklisted_ip(ip):
            logger.warning(f"Submission rejected: Blacklisted IP {ip}")
            return HTTPResponse(status=403, body=json.dumps({"error": "Forbidden IP"}), content_type='application/json')

        # 2. レート制限チェック
        if not check_rate_limit(ip):
            logger.warning(f"Submission rejected: Rate limit exceeded for IP {ip}")
            return HTTPResponse(status=429, body=json.dumps({"error": "Too many requests"}), content_type='application/json')

        # 3. User-Agentチェック (オプション設定があれば)
        if getattr(config, 'UA_CHECK_ENABLED', False):
            if not check_user_agent(ua):
                 return HTTPResponse(status=403, body=json.dumps({"error": "Bot detected or UA missing"}), content_type='application/json')

        # 4. データの取得 (UTF-8 decode対応)
        form_data = {}
        for key in request.forms.keys():
            form_data[key] = request.forms.getunicode(key)

        # form_id は パス、POSTボディ、またはクエリパラメータから取得可能にする
        form_id = form_id_path or form_data.get('form_id') or request.query.get('form_id')
        if not form_id:
            logger.warning(f"Submission rejected: Missing form_id from IP {ip}. Data: {json.dumps(form_data, ensure_ascii=False)}")
            return HTTPResponse(status=400, body=json.dumps({"error": "form_id is required"}), content_type='application/json')

        # 5. フォーム設定の取得
        try:
            cfg = FormConfig.get(FormConfig.form_id == form_id, FormConfig.is_active == True)
        except FormConfig.DoesNotExist:
            logger.warning(f"Submission rejected: Form configuration not found or inactive for form_id {form_id} from IP {ip}. Data: {json.dumps(form_data, ensure_ascii=False)}")
            return HTTPResponse(status=404, body=json.dumps({"error": "Form configuration not found or inactive"}), content_type='application/json')

        # 6. CORS/Origin検証
        origin = request.get_header('Origin')
        if not validate_origin(origin, cfg.allowed_domains):
             logger.warning(f"Submission rejected: Invalid origin {origin} for form_id {form_id} from IP {ip}. Data: {json.dumps(form_data, ensure_ascii=False)}")
             return HTTPResponse(status=403, body=json.dumps({"error": "Domain not allowed"}), content_type='application/json')
        
        # 7. reCAPTCHA検証
        if config.RECAPTCHA_ENABLED:
            recaptcha_token = form_data.get('g-recaptcha-response')
            if not verify_recaptcha(recaptcha_token, ip):
                logger.warning(f"Submission rejected: reCAPTCHA verification failed for form_id {form_id} from IP {ip}. Data: {json.dumps(form_data, ensure_ascii=False)}")
                return HTTPResponse(status=400, body=json.dumps({"error": "reCAPTCHA verification failed"}), content_type='application/json')

        # 7.5 日本語含有チェック (設定が有効な場合)
        if cfg.require_japanese:
            import re
            has_japanese = False
            # ひらがな、カタカナ、漢字が含まれているかチェック
            jp_pattern = re.compile(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]')
            for val in form_data.values():
                if val and isinstance(val, str) and jp_pattern.search(val):
                    has_japanese = True
                    break
            
            if not has_japanese:
                # データの整理
                cleaned_data = {k: v for k, v in form_data.items() if not k.startswith('_') and k != 'form_id' and k != 'g-recaptcha-response'}
                # DB保存 (スパムとして)
                submission = Submission.create(
                    form=cfg,
                    data=json.dumps(cleaned_data, ensure_ascii=False),
                    ip_address=ip,
                    user_agent=ua,
                    status='spam',
                    is_spam=True
                )
                logger.info(f"Spam detected (No Japanese) for form_id {form_id} from IP {ip}. Submission ID: {submission.id}")
                
                # リダイレクト
                redirect_url = form_data.get('_next') or cfg.success_url
                if redirect_url:
                    response.status = 303
                    response.set_header('Location', redirect_url)
                    return
                return {"status": "success", "message": "Thank you for your submission."}

        # 8. Honeypotチェック
        if form_data.get('_honeypot'):
            # データの整理 (システム用フィールドを除去)
            cleaned_data = {k: v for k, v in form_data.items() if not k.startswith('_') and k != 'form_id' and k != 'g-recaptcha-response'}

            # DB保存 (スパムとして)
            submission = Submission.create(
                form=cfg,
                data=json.dumps(cleaned_data, ensure_ascii=False),
                ip_address=ip,
                user_agent=ua,
                status='spam',
                is_spam=True
            )

            # スパムとして扱うが、表向きは200を返すか、静かに無視
            logger.info(f"Honeypot triggered for form_id {form_id} from IP {ip}. Submission ID: {submission.id}")
            
            # リダイレクト
            redirect_url = form_data.get('_next') or cfg.success_url
            if redirect_url:
                response.status = 303
                response.set_header('Location', redirect_url)
                return
            return {"status": "success", "message": "Thank you for your submission."}

        # 9. バリデーション (カスタム必須項目など)
        if cfg.validation_rules:
            try:
                rules = json.loads(cfg.validation_rules)
                required_fields = rules.get('required', [])
                for field in required_fields:
                    if not form_data.get(field):
                        logger.warning(f"Submission rejected: Field '{field}' is required for form_id {form_id} from IP {ip}. Data: {json.dumps(form_data, ensure_ascii=False)}")
                        return HTTPResponse(status=400, body=json.dumps({"error": f"Field '{field}' is required"}), content_type='application/json')
            except json.JSONDecodeError:
                logger.error(f"Invalid validation rules for form_id {form_id}: {cfg.validation_rules}")

        # 10. データの整理 (システム用フィールドを除去)
        cleaned_data = {k: v for k, v in form_data.items() if not k.startswith('_') and k != 'form_id' and k != 'g-recaptcha-response'}

        # 11. DB保存
        submission = Submission.create(
            form=cfg,
            data=json.dumps(cleaned_data, ensure_ascii=False),
            ip_address=ip,
            user_agent=ua
        )
        logger.info(f"Form submitted: form_id={form_id}, submission_id={submission.id}, ip={ip}")

        # 8. 添付ファイルの処理
        attachments_to_email = []
        files = request.files
        for key in files.keys():
            upfile = files.get(key)
            ext = os.path.splitext(upfile.filename)[1].lower()
            
            if ext not in config.ALLOWED_EXTENSIONS:
                continue
            
            # 保存
            save_name = f"{uuid.uuid4()}{ext}"
            save_path = os.path.join(config.UPLOAD_DIR, save_name)
            
            os.makedirs(config.UPLOAD_DIR, exist_ok=True)
            upfile.save(save_path)
            
            att = Attachment.create(
                submission=submission,
                filename=save_name,
                original_name=upfile.filename,
                mime_type=upfile.content_type,
                size=os.path.getsize(save_path)
            )
            attachments_to_email.append((upfile.filename, save_path, upfile.content_type))

        # 12. メール通知
        if cfg.enable_email_notification:
            try:
                subject = cfg.subject_template.format(form_name=cfg.name, **cleaned_data)
            except KeyError as e:
                logger.warning(f"KeyError in subject template: {e}. Using default.")
                subject = f"New Submission: {cfg.name}"
                
            # 本文テンプレートの構築 (簡易)
            try:
                if cfg.body_template:
                    body = cfg.body_template.format(**cleaned_data)
                else:
                    body = f"<h2>New Submission from {cfg.name}</h2><ul>"
                    for k, v in cleaned_data.items():
                        body += f"<li><strong>{k}:</strong> {v}</li>"
                    body += "</ul>"
            except KeyError as e:
                logger.warning(f"KeyError in body template: {e}. Using fallback.")
                body = f"<h2>New Submission from {cfg.name} (Fallback)</h2><ul>"
                for k, v in cleaned_data.items():
                    body += f"<li><strong>{k}:</strong> {v}</li>"
                body += "</ul>"

            send_email(
                to_list=cfg.notify_email,
                subject=subject,
                body=body,
                attachments=attachments_to_email,
                submission=submission
            )
        else:
            logger.info(f"Email notification skipped for form_id {form_id} as it is disabled.")

        # 13. レスポンス (リダイレクト)
        redirect_url = form_data.get('_next') or cfg.success_url
        if redirect_url:
            # 外部サイトへのリダイレクトを許可する場合
            response.status = 303
            response.set_header('Location', redirect_url)
            return
        
        return {"status": "success", "message": "Submission received"}
