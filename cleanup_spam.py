import json
import re
from app.models.base import db
from app.models.schema import Submission, FormConfig

def cleanup_spam(target_all=False):
    """
    既存の送信データから日本語が含まれないものをスパムとしてマークします。
    
    :param target_all: Trueの場合、FormConfigの require_japanese 設定に関わらず全ての送信をチェックします。
                       Falseの場合、require_japanese が有効なフォームの送信のみチェックします。
    """
    if db.is_closed():
        db.connect()
    
    # ひらがな、カタカナ、漢字のパターン
    jp_pattern = re.compile(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]')
    
    if target_all:
        query = Submission.select().where(Submission.status != 'spam')
        print("Checking all submissions (excluding existing spam)...")
    else:
        query = Submission.select().join(FormConfig).where(
            (FormConfig.require_japanese == True) & 
            (Submission.status != 'spam')
        )
        print("Checking submissions for forms where 'Require Japanese' is enabled...")

    total_checked = 0
    updated_count = 0

    for sub in query:
        total_checked += 1
        try:
            data = json.loads(sub.data)
        except json.JSONDecodeError:
            continue

        has_japanese = False
        for val in data.values():
            if val and isinstance(val, str) and jp_pattern.search(val):
                has_japanese = True
                break
        
        if not has_japanese:
            sub.status = 'spam'
            sub.is_spam = True
            sub.save()
            updated_count += 1
            print(f"  [Marked as Spam] Submission ID: {sub.id} (Form: {sub.form.name})")

    print(f"\nScan completed.")
    print(f"Total checked: {total_checked}")
    print(f"Updated to spam: {updated_count}")

if __name__ == '__main__':
    import sys
    # --all 引数があれば全件対象にする
    use_all = '--all' in sys.argv
    cleanup_spam(target_all=use_all)
