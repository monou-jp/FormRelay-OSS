import unittest
import json
import os
from bottle import Bottle
from webtest import TestApp
from app.models.base import db
from app.models.schema import User, FormConfig, Submission, Attachment, MailLog, StatusHistory, RateLimit
from app.routes.admin import setup_admin_routes
from app.utils.auth import hash_password, generate_session_token
import config

class TestAdmin(unittest.TestCase):
    def setUp(self):
        # テスト用DB (メモリ上)
        db.init(':memory:')
        db.connect()
        db.create_tables([User, FormConfig, Submission, Attachment, MailLog, StatusHistory, RateLimit])
        
        # テスト用管理者の作成
        self.admin_user = User.create(
            username='admin',
            password=hash_password('password123'),
            role='admin',
            is_active=True
        )
        
        self.app = Bottle()
        setup_admin_routes(self.app)
        self.test_app = TestApp(self.app)
        
        # セッショントークンの生成
        self.token = generate_session_token(self.admin_user.id)
        self.cookie_name = config.SESSION_NAME

    def test_login_page_access(self):
        response = self.test_app.get('/login')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Login', response.body.decode('utf-8'))

    def test_login_success(self):
        params = {
            'username': 'admin',
            'password': 'password123'
        }
        response = self.test_app.post('/login', params=params)
        # ログイン成功時はリダイレクトされる
        self.assertEqual(response.status_code, 302)
        # クッキーがセットされているか
        self.assertIn(self.cookie_name, response.headers.get('Set-Cookie', ''))

    def test_login_fail(self):
        params = {
            'username': 'admin',
            'password': 'wrongpassword'
        }
        response = self.test_app.post('/login', params=params)
        self.assertEqual(response.status_code, 200)
        self.assertIn('Invalid username or password', response.body.decode('utf-8'))

    def test_dashboard_access_denied(self):
        # ログインなしでダッシュボードにアクセス
        response = self.test_app.get('/', expect_errors=True)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response.headers['Location'])

    def test_dashboard_access_success(self):
        # クッキーをセットしてダッシュボードにアクセス
        self.test_app.set_cookie(self.cookie_name, self.token)
        response = self.test_app.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Dashboard', response.body.decode('utf-8'))

    def test_form_list_access(self):
        self.test_app.set_cookie(self.cookie_name, self.token)
        # テスト用フォーム
        FormConfig.create(form_id='f1', name='Form 1', notify_email='a@b.com')
        
        response = self.test_app.get('/forms')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Form 1', response.body.decode('utf-8'))

    def test_create_form(self):
        self.test_app.set_cookie(self.cookie_name, self.token)
        payload = {
            'form_id': 'new-form',
            'name': 'New Form',
            'notify_email': 'notify@example.com',
            'allowed_domains': '*',
            'subject_template': 'Sub: {form_name}',
            'is_active': 'on'
        }
        response = self.test_app.post('/forms/save', params=payload)
        self.assertEqual(response.status_code, 302)
        
        # 保存されているか確認
        self.assertTrue(FormConfig.select().where(FormConfig.form_id == 'new-form').exists())

    def test_delete_form(self):
        self.test_app.set_cookie(self.cookie_name, self.token)
        f = FormConfig.create(form_id='to-delete', name='Delete Me', notify_email='a@b.com')
        
        response = self.test_app.post(f'/forms/{f.id}/delete')
        self.assertEqual(response.status_code, 302)
        
        self.assertFalse(FormConfig.select().where(FormConfig.form_id == 'to-delete').exists())

    def test_submission_detail(self):
        self.test_app.set_cookie(self.cookie_name, self.token)
        f = FormConfig.create(form_id='sub-test', name='Sub Test', notify_email='a@b.com')
        sub = Submission.create(form=f, data=json.dumps({"msg": "hello"}), ip_address='1.1.1.1', user_agent='test-ua')
        
        response = self.test_app.get(f'/submissions/{sub.id}')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Submission Details', response.body.decode('utf-8'))
        self.assertIn('hello', response.body.decode('utf-8'))

    def test_update_submission_status(self):
        self.test_app.set_cookie(self.cookie_name, self.token)
        f = FormConfig.create(form_id='stat-test', name='Stat Test', notify_email='a@b.com')
        sub = Submission.create(form=f, data='{}', ip_address='1.1.1.1', user_agent='test-ua')
        
        payload = {
            'status': 'processed',
            'comment': 'All good'
        }
        response = self.test_app.post(f'/submissions/{sub.id}/status', params=payload)
        self.assertEqual(response.status_code, 302)
        
        # ステータスが更新されているか
        updated_sub = Submission.get_by_id(sub.id)
        self.assertEqual(updated_sub.status, 'processed')
        # 履歴が作成されているか
        self.assertTrue(StatusHistory.select().where(StatusHistory.submission == updated_sub).exists())

    def test_user_management(self):
        self.test_app.set_cookie(self.cookie_name, self.token)
        
        # ユーザー一覧
        response = self.test_app.get('/users')
        self.assertEqual(response.status_code, 200)
        self.assertIn('admin', response.body.decode('utf-8'))
        
        # ユーザー追加
        payload = {
            'username': 'newuser',
            'password': 'password123',
            'role': 'editor'
        }
        response = self.test_app.post('/users/add', params=payload)
        self.assertEqual(response.status_code, 302)
        
        self.assertTrue(User.select().where(User.username == 'newuser').exists())

if __name__ == '__main__':
    unittest.main()
