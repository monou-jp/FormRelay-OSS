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

class TestSpamEnhancement(unittest.TestCase):
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
        self.form_cfg_jp = FormConfig.create(
            form_id='jp-form',
            name='Japanese Form',
            notify_email='test@example.com',
            allowed_domains='*',
            require_japanese=True,
            is_active=True
        )
        self.form_cfg_no_jp = FormConfig.create(
            form_id='no-jp-form',
            name='Normal Form',
            notify_email='test@example.com',
            allowed_domains='*',
            require_japanese=False,
            is_active=True
        )
        
        self.app = Bottle()
        self.app.catchall = False
        setup_api_routes(self.app)
        self.test_app = TestApp(self.app)
        
        # configの値を一時的に変更
        self.orig_min_jp = getattr(config, 'SPAM_CHECK_MIN_JP_CHARS', 3)
        self.orig_max_urls = getattr(config, 'SPAM_CHECK_MAX_URLS', 3)
        self.orig_ng_words = getattr(config, 'SPAM_CHECK_NG_WORDS', [])
        
        config.SPAM_CHECK_MIN_JP_CHARS = 3
        config.SPAM_CHECK_MAX_URLS = 2
        config.SPAM_CHECK_NG_WORDS = ['casino', 'viagra']
        
        RateLimit.delete().execute()

    def tearDown(self):
        config.SPAM_CHECK_MIN_JP_CHARS = self.orig_min_jp
        config.SPAM_CHECK_MAX_URLS = self.orig_max_urls
        config.SPAM_CHECK_NG_WORDS = self.orig_ng_words
        db.close()

    @patch('app.routes.api.send_email')
    def test_japanese_requirement_too_few(self, mock_send_email):
        # 日本語が必要だが1文字だけの場合 -> スパム
        payload = {'form_id': 'jp-form', 'message': 'Helloあ'}
        response = self.test_app.post('/api/form', params=payload, extra_environ={'REMOTE_ADDR': '127.0.0.1'})
        self.assertEqual(response.status_code, 200)
        sub = Submission.get(Submission.form == self.form_cfg_jp)
        self.assertTrue(sub.is_spam)
        self.assertEqual(sub.status, 'spam')

    @patch('app.routes.api.send_email')
    def test_japanese_requirement_enough(self, mock_send_email):
        # 日本語が必要で3文字ある場合 -> 正常
        payload = {'form_id': 'jp-form', 'message': 'Helloあいう'}
        response = self.test_app.post('/api/form', params=payload, extra_environ={'REMOTE_ADDR': '127.0.0.1'})
        self.assertEqual(response.status_code, 200)
        sub = Submission.get(Submission.form == self.form_cfg_jp)
        self.assertFalse(sub.is_spam)
        self.assertEqual(sub.status, 'new')

    @patch('app.routes.api.send_email')
    def test_too_many_urls(self, mock_send_email):
        # URLが多すぎる場合 -> スパム
        payload = {
            'form_id': 'no-jp-form', 
            'message': 'Check this: http://ex1.com, http://ex2.com, http://ex3.com'
        }
        response = self.test_app.post('/api/form', params=payload, extra_environ={'REMOTE_ADDR': '127.0.0.1'})
        self.assertEqual(response.status_code, 200)
        sub = Submission.get(Submission.form == self.form_cfg_no_jp)
        self.assertTrue(sub.is_spam)
        self.assertEqual(sub.status, 'spam')

    @patch('app.routes.api.send_email')
    def test_ng_word_detection(self, mock_send_email):
        # NGワードが含まれる場合 -> スパム
        payload = {'form_id': 'no-jp-form', 'message': 'Buy cheap viagra now'}
        response = self.test_app.post('/api/form', params=payload, extra_environ={'REMOTE_ADDR': '127.0.0.1'})
        self.assertEqual(response.status_code, 200)
        sub = Submission.get(Submission.form == self.form_cfg_no_jp)
        self.assertTrue(sub.is_spam)
        self.assertEqual(sub.status, 'spam')

if __name__ == '__main__':
    unittest.main()
