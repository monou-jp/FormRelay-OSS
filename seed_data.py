import os
import json
import datetime
import random
from app.models.base import db
from app.models.schema import User, FormConfig, Submission, Attachment, MailLog, StatusHistory, RateLimit
from app.utils.auth import hash_password

def seed_data():
    # 1. データベース接続
    db.connect()
    print("Database connected.")

    # 2. テーブル作成（存在しない場合）
    db.create_tables([User, FormConfig, Submission, Attachment, MailLog, StatusHistory, RateLimit])
    print("Tables ensured.")

    # 3. 初期管理者の作成
    admin_user, created = User.get_or_create(
        username='admin',
        defaults={
            'password': hash_password('admin123'),
            'role': 'admin',
            'email': 'admin@example.com'
        }
    )
    if created:
        print("Admin user created: admin / admin123")
    else:
        print("Admin user already exists.")

    # 4. FormConfigの作成
    forms_data = [
        {
            'form_id': 'contact-form',
            'name': 'ウェブサイトお問い合わせ',
            'notify_email': 'sales@example.com, support@example.com',
            'subject_template': '【お問い合わせ】{form_name} - {company_name}',
            'allowed_domains': '*',
            'success_url': '/thanks.html'
        },
        {
            'form_id': 'recruit-form',
            'name': '採用応募フォーム',
            'notify_email': 'hr@example.com',
            'subject_template': '【採用応募】{form_name} - {name}様',
            'allowed_domains': 'recruit.example.com',
            'success_url': '/recruit/thanks.html'
        },
        {
            'form_id': 'download-form',
            'name': 'ホワイトペーパー資料請求',
            'notify_email': 'marketing@example.com',
            'subject_template': '【資料請求】{form_name} - {email}',
            'allowed_domains': '*',
            'success_url': '/download/complete.html'
        }
    ]

    forms = []
    for f_data in forms_data:
        form, created = FormConfig.get_or_create(
            form_id=f_data['form_id'],
            defaults=f_data
        )
        forms.append(form)
        if created:
            print(f"FormConfig created: {form.name}")
        else:
            print(f"FormConfig already exists: {form.name}")

    # 5. Submissionデータの投入 (各フォームに数件ずつ)
    submission_templates = {
        'contact-form': [
            {'name': '田中 太郎', 'company_name': '株式会社サンプル', 'email': 'tanaka@example.jp', 'message': '製品の導入を検討しています。見積もりをお願いします。'},
            {'name': '佐藤 花子', 'company_name': 'Sample Inc.', 'email': 'sato@example.com', 'message': 'APIの仕様について詳しく教えてください。'},
            {'name': '鈴木 一郎', 'company_name': 'テスト株式会社', 'email': 'suzuki@test.co.jp', 'message': 'デモ環境の貸し出しは可能でしょうか？'}
        ],
        'recruit-form': [
            {'name': '山田 健一', 'email': 'yamada.ken@example.net', 'position': 'Backend Engineer', 'experience': '5 years', 'github': 'https://github.com/yamada'},
            {'name': '伊藤 美咲', 'email': 'misaki.ito@example.org', 'position': 'Product Designer', 'experience': '3 years', 'portfolio': 'https://behance.net/ito'}
        ],
        'download-form': [
            {'email': 'lead1@example.biz', 'company': 'Enterprise Ltd.', 'industry': 'Manufacturing'},
            {'email': 'lead2@example.co.jp', 'company': 'IT Solution Co.', 'industry': 'Technology'},
            {'email': 'lead3@example.com', 'company': 'Global Trade', 'industry': 'Finance'}
        ]
    }

    statuses = ['new', 'in_progress', 'completed']
    ips = ['192.168.1.10', '203.0.113.5', '198.51.100.22', '127.0.0.1']
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Mozilla/5.0 (iPhone; CPU iPhone OS 17_3_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3.1 Mobile/15E148 Safari/604.1'
    ]

    now = datetime.datetime.now()
    
    for form in forms:
        templates = submission_templates.get(form.form_id, [])
        for i, data in enumerate(templates):
            # 重複作成を避けるためにデータ内容でチェック
            data_json = json.dumps(data, ensure_ascii=False)
            exists = Submission.select().where(Submission.form == form, Submission.data == data_json).exists()
            if exists:
                continue

            status = random.choice(statuses)
            created_at = now - datetime.timedelta(days=random.randint(0, 10), hours=random.randint(0, 23))
            
            sub = Submission.create(
                form=form,
                data=data_json,
                status=status,
                ip_address=random.choice(ips),
                user_agent=random.choice(user_agents),
                created_at=created_at
            )
            print(f"Submission created for {form.name} (Status: {status})")

            # StatusHistory の作成
            if status != 'new':
                StatusHistory.create(
                    submission=sub,
                    old_status='new',
                    new_status='in_progress',
                    note='自動受付確認',
                    created_at=created_at + datetime.timedelta(minutes=30)
                )
                if status == 'completed':
                    StatusHistory.create(
                        submission=sub,
                        old_status='in_progress',
                        new_status='completed',
                        note='対応完了しました。',
                        created_by=admin_user,
                        created_at=created_at + datetime.timedelta(hours=5)
                    )

            # MailLog の作成
            MailLog.create(
                submission=sub,
                recipient=form.notify_email.split(',')[0].strip(),
                subject=form.subject_template.format(form_name=form.name, **data),
                body=f"新しい送信がありました。\n\nデータ: {data_json}",
                status='success',
                sent_at=created_at + datetime.timedelta(seconds=5)
            )

    print("\nSeeding completed successfully!")

if __name__ == '__main__':
    seed_data()
