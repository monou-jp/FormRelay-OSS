from app.utils.logger import setup_logging
from unittest.mock import patch
import unittest
import json
import os
from bottle import Bottle
from webtest import TestApp
from app.models.base import db
from app.models.schema import User, FormConfig, Submission, Attachment, MailLog, StatusHistory, RateLimit
from app.routes.api import setup_api_routes
import config

class TestNewFeatures(unittest.TestCase):
    def setUp(self):
        # テスト用DB (メモリ上)
        db.init(':memory:')
        db.connect()
        db.create_tables([User, FormConfig, Submission, Attachment, MailLog, StatusHistory, RateLimit])
        
        self.app = Bottle()
        self.app.catchall = False
        setup_api_routes(self.app)
        self.test_app = TestApp(self.app)

    @patch('app.routes.api.send_email')
    def test_form_id_in_query(self, mock_send_email):
        mock_send_email.return_value = (True, None)
        FormConfig.create(
            form_id='query-id',
            name='Query ID Form',
            notify_email='test@example.com',
            is_active=True
        )
        
        # POSTボディには form_id を含めず、クエリパラメータに含める
        payload = {'name': 'Tester'}
        response = self.test_app.post('/api/form?form_id=query-id', params=payload, extra_environ={'REMOTE_ADDR': '127.0.0.1'})
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Submission.select().count(), 1)
        sub = Submission.get()
        self.assertEqual(sub.form.form_id, 'query-id')

    @patch('app.routes.api.send_email')
    def test_require_japanese(self, mock_send_email):
        mock_send_email.return_value = (True, None)
        FormConfig.create(
            form_id='jp-only',
            name='Japanese Required',
            notify_email='test@example.com',
            require_japanese=True,
            is_active=True
        )
        
        # 1. 日本語を含まない送信 -> スパム判定
        payload = {'name': 'John Doe', 'message': 'Hello world'}
        response = self.test_app.post('/api/form?form_id=jp-only', params=payload, extra_environ={'REMOTE_ADDR': '127.0.0.1'})
        
        self.assertEqual(response.status_code, 200)
        sub = Submission.get(Submission.data.contains('John Doe'))
        self.assertTrue(sub.is_spam)
        self.assertEqual(sub.status, 'spam')
        
        # 2. 日本語を含む送信 -> 正常判定
        payload = {'name': '山田太郎', 'message': 'こんにちは'}
        response = self.test_app.post('/api/form?form_id=jp-only', params=payload, extra_environ={'REMOTE_ADDR': '127.0.0.1'})
        
        self.assertEqual(response.status_code, 200)
        sub = Submission.get(Submission.data.contains('山田太郎'))
        self.assertFalse(sub.is_spam)
        self.assertEqual(sub.status, 'new')

    @patch('app.routes.api.send_email')
    def test_path_based_form_id(self, mock_send_email):
        mock_send_email.return_value = (True, None)
        FormConfig.create(
            form_id='path-id',
            name='Path ID Form',
            notify_email='test@example.com',
            is_active=True
        )
        
        payload = {'name': 'PathTester'}
        
        # 1. /form/<form_id>
        response = self.test_app.post('/form/path-id', params=payload, extra_environ={'REMOTE_ADDR': '127.0.0.1'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Submission.select().join(FormConfig).where(FormConfig.form_id == 'path-id').count(), 1)
        
        # 2. /f/<form_id>
        response = self.test_app.post('/f/path-id', params=payload, extra_environ={'REMOTE_ADDR': '127.0.0.1'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Submission.select().join(FormConfig).where(FormConfig.form_id == 'path-id').count(), 2)

if __name__ == '__main__':
    unittest.main()
