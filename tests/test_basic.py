import unittest
import os
import json
import sqlite3
import main
from app.models.base import db
from app.models.schema import User, FormConfig, Submission
from app.utils.auth import hash_password

class FormRelayTestCase(unittest.TestCase):
    def setUp(self):
        # テスト用DB (オンメモリ)
        db.init(':memory:')
        db.create_tables([User, FormConfig, Submission])
        
        # テストデータの作成
        self.user = User.create(username='testuser', password=hash_password('testpass'), role='admin')
        self.form_cfg = FormConfig.create(
            form_id='test-form',
            name='Test Form',
            notify_email='test@example.com',
            allowed_domains='*'
        )

    def test_db_setup(self):
        self.assertEqual(User.select().count(), 1)
        self.assertEqual(FormConfig.select().count(), 1)

    def test_form_config_retrieval(self):
        cfg = FormConfig.get(FormConfig.form_id == 'test-form')
        self.assertEqual(cfg.name, 'Test Form')

if __name__ == '__main__':
    unittest.main()
