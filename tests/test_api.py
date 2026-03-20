from app.utils.logger import setup_logging
from unittest.mock import patch
import unittest
import json
import os
import sqlite3
import logging
from bottle import Bottle
from webtest import TestApp
from app.models.base import db
from app.models.schema import User, FormConfig, Submission, Attachment, MailLog, StatusHistory, RateLimit
from app.routes.api import setup_api_routes
from app.utils.auth import hash_password
import config

class TestAPI(unittest.TestCase):
    def setUp(self):
        # ログファイルをクリア
        if os.path.exists(config.LOG_FILE):
            with open(config.LOG_FILE, 'w') as f:
                f.write('')
        
        # ロギングを再セットアップ
        setup_logging()
        
        # テスト用DB (メモリ上)
        db.init(':memory:')
        db.connect()
        db.create_tables([User, FormConfig, Submission, Attachment, MailLog, StatusHistory, RateLimit])
        
        # テスト用データの作成
        self.form_cfg = FormConfig.create(
            form_id='test-form',
            name='Test Form',
            notify_email='test@example.com',
            allowed_domains='*',
            validation_rules=json.dumps({"required": ["name"]}),
            is_active=True,
            subject_template='New submission: {form_name}'
        )
        
        self.app = Bottle()
        self.app.catchall = False # 詳細なスタックトレースを表示
        setup_api_routes(self.app)
        self.test_app = TestApp(self.app)
        
        # レート制限をテスト用に緩める、またはRateLimitテーブルをクリア
        RateLimit.delete().execute()

    @patch('app.routes.api.send_email')
    def test_submission_success(self, mock_send_email):
        # 正常系
        mock_send_email.return_value = (True, None)
        payload = {
            'form_id': 'test-form',
            'name': 'John Doe',
            'email': 'john@example.com',
            'message': 'Hello'
        }
        
        response = self.test_app.post('/api/form', params=payload, extra_environ={'REMOTE_ADDR': '127.0.0.1'})
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('success', response.json['status'])
        
        # DBに保存されているか確認
        self.assertEqual(Submission.select().count(), 1)
        sub = Submission.get()
        data = json.loads(sub.data)
        self.assertEqual(data['name'], 'John Doe')
        
        # メール送信が呼ばれたか確認
        self.assertTrue(mock_send_email.called)

    def test_validation_fail(self):
        # 必須項目(name)が欠けている場合
        payload = {
            'form_id': 'test-form',
            'email': 'john@example.com'
        }
        
        response = self.test_app.post('/api/form', params=payload, extra_environ={'REMOTE_ADDR': '127.0.0.1'}, expect_errors=True)
        
        self.assertEqual(response.status_code, 400)
        self.assertIn('required', response.json['error'])

    def test_honeypot_detection(self):
        # honeypotが入力されている場合
        payload = {
            'form_id': 'test-form',
            'name': 'Spammer',
            '_honeypot': 'im-a-bot'
        }
        
        response = self.test_app.post('/api/form', params=payload, extra_environ={'REMOTE_ADDR': '127.0.0.1'})
        
        # 表向きは成功を返すが、DBに保存される(is_spam=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Submission.select().count(), 1)
        sub = Submission.get()
        self.assertTrue(sub.is_spam)
        self.assertEqual(sub.status, 'spam')

    def test_invalid_form_id(self):
        # 存在しないform_id
        payload = {
            'form_id': 'non-existent',
            'name': 'Ghost'
        }
        
        response = self.test_app.post('/api/form', params=payload, extra_environ={'REMOTE_ADDR': '127.0.0.1'}, expect_errors=True)
        self.assertEqual(response.status_code, 404)
        
        # ログファイルを確認
        log_file = config.LOG_FILE
        if os.path.exists(log_file):
            with open(log_file, 'r', encoding='utf-8') as f:
                logs = f.read()
                self.assertIn('non-existent', logs)
                self.assertIn('Ghost', logs)

if __name__ == '__main__':
    unittest.main()
