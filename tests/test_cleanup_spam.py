import unittest
import json
from app.models.base import db
from app.models.schema import User, FormConfig, Submission, Attachment, MailLog, StatusHistory, RateLimit
from cleanup_spam import cleanup_spam

class TestCleanupSpam(unittest.TestCase):
    def setUp(self):
        db.init(':memory:')
        db.connect()
        db.create_tables([User, FormConfig, Submission, Attachment, MailLog, StatusHistory, RateLimit])
        
        # フォーム1: 日本語必須
        self.cfg_jp = FormConfig.create(
            form_id='jp-req',
            name='JP Required',
            notify_email='test@example.com',
            require_japanese=True
        )
        
        # フォーム2: 日本語必須ではない
        self.cfg_no_jp = FormConfig.create(
            form_id='no-jp-req',
            name='No JP Required',
            notify_email='test@example.com',
            require_japanese=False
        )
        
        # データ作成
        # JP Requiredフォームに日本語あり
        Submission.create(form=self.cfg_jp, data=json.dumps({'m': 'こんにちは'}), ip_address='1', user_agent='1')
        # JP Requiredフォームに日本語なし
        Submission.create(form=self.cfg_jp, data=json.dumps({'m': 'Hello'}), ip_address='2', user_agent='2')
        
        # No JP Requiredフォームに日本語なし
        Submission.create(form=self.cfg_no_jp, data=json.dumps({'m': 'Hello world'}), ip_address='3', user_agent='3')

    def test_cleanup_default(self):
        # デフォルトでは設定が有効なものだけ
        cleanup_spam(target_all=False)
        
        # jp-req の 'Hello' はスパムになるはず (ID 2)
        sub2 = Submission.get_by_id(2)
        self.assertEqual(sub2.status, 'spam')
        
        # no-jp-req の 'Hello world' はスパムにならないはず (ID 3)
        sub3 = Submission.get_by_id(3)
        self.assertNotEqual(sub3.status, 'spam')

    def test_cleanup_all(self):
        # --all 指定時は全件対象
        # ただし、現状のロジックでは require_japanese=False の場合は日本語チェックは行われない
        # (URL数やNGワードのチェックのみ行われる)
        # そのため、'Hello world' はスパムにならないのが正しい挙動
        cleanup_spam(target_all=True)
        
        # no-jp-req の 'Hello world' はURLもNGワードもないのでスパムにならない
        sub3 = Submission.get_by_id(3)
        self.assertNotEqual(sub3.status, 'spam')
        
        # NGワードを入れてみる
        Submission.create(form=self.cfg_no_jp, data=json.dumps({'m': 'Get cheap casino'}), ip_address='4', user_agent='4')
        cleanup_spam(target_all=True)
        sub4 = Submission.get_by_id(4)
        self.assertEqual(sub4.status, 'spam')

if __name__ == '__main__':
    unittest.main()
