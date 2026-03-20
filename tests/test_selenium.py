import unittest
import time
import os
import random
import string
import threading
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from main import app as bottle_app, init_db
from app.models.schema import FormConfig, User, Submission
from bottle import run

class SeleniumTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # データベース初期化
        init_db()
        
        # メール送信をモック化
        import app.utils.email
        cls.original_send_email = app.utils.email.send_email
        cls.last_sent_email = None
        
        def mock_send_email(to_list, subject, body, attachments=None, is_html=True, submission=None):
            cls.last_sent_email = {
                'to': to_list,
                'subject': subject,
                'body': body,
                'attachments': attachments,
                'submission': submission
            }
            # ログ保存 (元の関数からロジックを借用、またはDBに直接作成)
            from app.models.schema import MailLog
            MailLog.create(
                submission=submission,
                recipient=", ".join(to_list) if isinstance(to_list, list) else to_list,
                subject=subject,
                body=body,
                status='success',
                error_message=None
            )
            return True, None
        
        app.utils.email.send_email = mock_send_email

        # テスト用フォーム設定の作成
        config_obj, created = FormConfig.get_or_create(
            form_id='test-form-id',
            defaults={
                'name': 'Test Form',
                'notify_email': 'test@example.com',
                'allowed_domains': '*',
                'is_active': True,
                'subject_template': 'Test Submission: {name}',
                'success_url': 'http://localhost:8081/static/success.html'
            }
        )
        if not created:
            config_obj.success_url = 'http://localhost:8081/static/success.html'
            config_obj.save()

        # サーバーを別スレッドで起動
        import config
        config.SMTP_SERVER = 'localhost' # ダミー
        config.BASE_URL = 'http://localhost:8081'
        
        # モジュールレベルの変数を直接書き換えてみる
        import app.routes.api
        app.routes.api.config.BASE_URL = 'http://localhost:8081'
        
        cls.server_thread = threading.Thread(target=run, kwargs={'app': bottle_app, 'host': 'localhost', 'port': 8081, 'quiet': True})
        cls.server_thread.daemon = True
        cls.server_thread.start()
        time.sleep(1) # 起動待ち

        # Selenium設定 (ヘッドレスモード)
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        
        try:
            cls.driver = webdriver.Chrome(options=chrome_options)
        except Exception as e:
            print(f"Skipping Selenium tests because ChromeDriver is not available: {e}")
            cls.driver = None

    @classmethod
    def tearDownClass(cls):
        if cls.driver:
            cls.driver.quit()
        # モックを元に戻す
        import app.utils.email
        app.utils.email.send_email = cls.original_send_email

    def setUp(self):
        if not self.driver:
            self.skipTest("Selenium driver not available")
        
        # レート制限をリセット
        from app.models.schema import RateLimit
        RateLimit.delete().execute()

        # テストフォームファイルのパス
        self.form_path = "file://" + os.path.abspath("tests/test_form.html")

    def test_normal_submission(self):
        driver = self.driver
        driver.get(self.form_path)
        
        # フォームのactionをテストサーバーに向ける (ローカルファイルから送信するため)
        driver.execute_script("document.forms[0].action = 'http://localhost:8081/api/form';")

        driver.find_element(By.ID, "name").send_keys("Test User")
        driver.find_element(By.ID, "email").send_keys("test@example.com")
        driver.find_element(By.ID, "message").send_keys("Hello World")
        
        driver.find_element(By.ID, "submit-btn").click()
        
        # 送信後の確認 (リダイレクト先や成功メッセージ)
        time.sleep(1)
        self.assertEqual(driver.current_url, 'http://localhost:8081/static/success.html')
        
        # メールの送信内容も検証
        self.assertIsNotNone(self.__class__.last_sent_email)
        self.assertEqual(self.__class__.last_sent_email['to'], ['test@example.com'])
        self.assertIn("Test User", self.__class__.last_sent_email['subject'])

    def test_boundary_values(self):
        """境界値テスト: 非常に長い文字列の入力"""
        driver = self.driver
        driver.get(self.form_path)
        driver.execute_script("document.forms[0].action = 'http://localhost:8081/api/form';")

        long_name = "A" * 1000
        long_message = "M" * 10000
        
        driver.find_element(By.ID, "name").send_keys(long_name)
        driver.find_element(By.ID, "email").send_keys("long@example.com")
        driver.find_element(By.ID, "message").send_keys(long_message)
        
        driver.find_element(By.ID, "submit-btn").click()
        time.sleep(1)
        self.assertIn("success", driver.current_url.lower() or driver.page_source.lower())

    def test_random_strings(self):
        """ランダム文字列テスト"""
        driver = self.driver
        for _ in range(3):
            driver.get(self.form_path)
            driver.execute_script("document.forms[0].action = 'http://localhost:8081/api/form';")
            
            # 制御文字や改行などはinput要素には適さない場合があるため、少しクリーンにする
            random_name = ''.join(random.choices(string.ascii_letters + string.digits + " !@#$%^&*()", k=50))
            random_email = ''.join(random.choices(string.ascii_letters, k=10)) + "@example.com"
            
            driver.find_element(By.ID, "name").clear()
            driver.find_element(By.ID, "name").send_keys(random_name)
            driver.find_element(By.ID, "email").clear()
            driver.find_element(By.ID, "email").send_keys(random_email)
            
            driver.find_element(By.ID, "submit-btn").click()
            time.sleep(2) # 送信完了を待機
            self.assertIn("success", driver.current_url.lower() or driver.page_source.lower())

    def test_error_logging(self):
        """エラー時のログ出力テスト (不正なform_id)"""
        driver = self.driver
        driver.get(self.form_path)
        driver.execute_script("document.forms[0].action = 'http://localhost:8081/api/form';")
        
        # form_idを書き換えてエラーを誘発
        driver.execute_script("document.getElementsByName('form_id')[0].value = 'invalid-id';")
        
        driver.find_element(By.ID, "name").send_keys("Error User")
        driver.find_element(By.ID, "email").send_keys("error@example.com")
        
        driver.find_element(By.ID, "submit-btn").click()
        time.sleep(1)
        
        # ログファイルに送信内容が含まれているか確認
        log_file = "data/app.log"
        if os.path.exists(log_file):
            with open(log_file, "r", encoding="utf-8") as f:
                logs = f.read()
                self.assertIn("invalid-id", logs)
                self.assertIn("Error User", logs)

    def test_admin_flow(self):
        """管理画面のログインからフォーム作成までのフロー"""
        driver = self.driver
        base_url = "http://localhost:8081"
        
        # 1. ログイン
        driver.get(f"{base_url}/login")
        driver.find_element(By.NAME, "username").send_keys("admin")
        driver.find_element(By.NAME, "password").send_keys("admin123")
        driver.find_element(By.TAG_NAME, "button").click()
        
        time.sleep(1)
        self.assertIn("Dashboard", driver.page_source)
        
        # 2. フォーム新規作成
        driver.get(f"{base_url}/forms/new")
        driver.find_element(By.NAME, "form_id").send_keys("sel-test-form")
        driver.find_element(By.NAME, "name").send_keys("Selenium Test Form")
        driver.find_element(By.NAME, "notify_email").send_keys("sel@example.com")
        
        # Saveボタンまでスクロールしてからクリック
        save_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Save')]")
        driver.execute_script("arguments[0].scrollIntoView();", save_btn)
        time.sleep(1)
        save_btn.click()
        
        time.sleep(1)
        self.assertIn("Selenium Test Form", driver.page_source)
        
        # 3. 作成したフォームで送信テスト
        driver.get(self.form_path)
        # form_idを今作ったものに書き換え
        driver.execute_script("document.getElementsByName('form_id')[0].value = 'sel-test-form';")
        driver.execute_script("document.forms[0].action = 'http://localhost:8081/api/form';")
        
        driver.find_element(By.ID, "name").send_keys("Selenium User")
        driver.find_element(By.ID, "email").send_keys("sel-user@example.com")
        driver.find_element(By.ID, "submit-btn").click()
        
        time.sleep(1)
        self.assertIn("success", driver.current_url.lower() or driver.page_source.lower())
        
        # 4. 送信内容が管理画面に反映されているか確認
        driver.get(f"{base_url}/submissions")
        self.assertIn("Selenium User", driver.page_source)

    def test_rate_limiting(self):
        """レート制限のテスト"""
        driver = self.driver
        # 制限を厳しく設定 (一時的に)
        import config
        original_limit = config.RATE_LIMIT_COUNT
        config.RATE_LIMIT_COUNT = 1
        
        try:
            # 1回目: 成功
            driver.get(self.form_path)
            driver.execute_script("document.forms[0].action = 'http://localhost:8081/api/form';")
            driver.find_element(By.ID, "name").send_keys("Rate User 1")
            driver.find_element(By.ID, "email").send_keys("rate1@example.com")
            driver.find_element(By.ID, "submit-btn").click()
            time.sleep(1)
            self.assertEqual(driver.current_url, 'http://localhost:8081/static/success.html')
            
            # 2回目: 失敗 (429 Too Many Requests)
            driver.get(self.form_path)
            driver.execute_script("document.forms[0].action = 'http://localhost:8081/api/form';")
            driver.find_element(By.ID, "name").send_keys("Rate User 2")
            driver.find_element(By.ID, "email").send_keys("rate2@example.com")
            driver.find_element(By.ID, "submit-btn").click()
            time.sleep(1)
            # エラーレスポンスがJSONで返るため、ブラウザにそのまま表示されるか、
            # サーバーエラーページが表示される
            self.assertIn("too many requests", driver.page_source.lower())
        finally:
            config.RATE_LIMIT_COUNT = original_limit

if __name__ == "__main__":
    unittest.main()
