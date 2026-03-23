from peewee import CharField, DateTimeField, BooleanField, IntegerField, TextField, ForeignKeyField
from .base import BaseModel
import datetime

class User(BaseModel):
    username = CharField(unique=True)
    password = CharField()  # ハッシュ化して保存
    email = CharField(null=True)
    role = CharField(default='user')  # 'admin' or 'user'
    is_active = BooleanField(default=True)
    created_at = DateTimeField(default=datetime.datetime.now)

class FormConfig(BaseModel):
    form_id = CharField(unique=True)
    name = CharField()
    notify_email = CharField()  # カンマ区切りで複数可能
    allowed_domains = TextField(default='*')  # カンマ区切り、*は全て
    subject_template = CharField(default='New Submission: {form_name}')
    body_template = TextField(null=True)
    enable_email_notification = BooleanField(default=True)
    success_url = CharField(null=True)
    cancel_url = CharField(null=True)
    require_japanese = BooleanField(default=False)
    validation_rules = TextField(null=True)  # JSON形式で保存
    is_active = BooleanField(default=True)
    created_at = DateTimeField(default=datetime.datetime.now)

class Submission(BaseModel):
    form = ForeignKeyField(FormConfig, backref='submissions')
    data = TextField()  # JSONで保存
    status = CharField(default='new')  # 'new', 'in_progress', 'completed', 'spam'
    ip_address = CharField()
    user_agent = TextField()
    is_spam = BooleanField(default=False)
    is_deleted = BooleanField(default=False)
    created_at = DateTimeField(default=datetime.datetime.now)

class Attachment(BaseModel):
    submission = ForeignKeyField(Submission, backref='attachments')
    filename = CharField()
    original_name = CharField()
    mime_type = CharField()
    size = IntegerField()
    created_at = DateTimeField(default=datetime.datetime.now)

class StatusHistory(BaseModel):
    submission = ForeignKeyField(Submission, backref='history')
    old_status = CharField()
    new_status = CharField()
    note = TextField(null=True)
    created_by = ForeignKeyField(User, null=True)
    created_at = DateTimeField(default=datetime.datetime.now)

class MailLog(BaseModel):
    submission = ForeignKeyField(Submission, backref='mail_logs', null=True)
    recipient = CharField()
    subject = CharField()
    body = TextField()
    status = CharField()  # 'success', 'failed'
    error_message = TextField(null=True)
    sent_at = DateTimeField(default=datetime.datetime.now)

class RateLimit(BaseModel):
    ip_address = CharField()
    last_request_at = DateTimeField(default=datetime.datetime.now)
    request_count = IntegerField(default=1)
