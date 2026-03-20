import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
import config
import os
from ..models.schema import MailLog
from ..utils.logger import logger

def send_email(to_list, subject, body, attachments=None, is_html=True, submission=None):
    """
    to_list: カンマ区切り文字列またはリスト
    attachments: (filename, filepath, mime_type) のリスト
    """
    if isinstance(to_list, str):
        to_list = [email.strip() for email in to_list.split(',')]

    success = True
    error_msg = None

    try:
        if config.MAIL_BACKEND == 'smtp':
            msg = MIMEMultipart()
            msg['Subject'] = subject
            msg['From'] = config.FROM_EMAIL
            msg['To'] = ", ".join(to_list)

            part = MIMEText(body, 'html' if is_html else 'plain', 'utf-8')
            msg.attach(part)

            if attachments:
                for filename, filepath, mime in attachments:
                    if os.path.exists(filepath):
                        with open(filepath, "rb") as f:
                            part = MIMEApplication(f.read(), Name=filename)
                            part['Content-Disposition'] = f'attachment; filename="{filename}"'
                            msg.attach(part)

            server = smtplib.SMTP(config.SMTP_SERVER, config.SMTP_PORT)
            if config.SMTP_USE_TLS:
                server.starttls()
            if config.SMTP_USER:
                server.login(config.SMTP_USER, config.SMTP_PASSWORD)
            
            server.sendmail(config.FROM_EMAIL, to_list, msg.as_string())
            server.quit()
        else:
            # API (SendGrid etc) - 実装例（今回は要件にあるので枠組みだけ用意）
            # requests などが必要になるが標準ライブラリ中心のため SMTP を優先
            raise NotImplementedError("API backend is not implemented in this version. Please use SMTP.")

    except Exception as e:
        success = False
        error_msg = str(e)
        logger.error(f"Mail send error: {error_msg}")

    # ログ保存
    MailLog.create(
        submission=submission,
        recipient=", ".join(to_list),
        subject=subject,
        body=body,
        status='success' if success else 'failed',
        error_message=error_msg
    )

    return success, error_msg
