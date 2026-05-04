import json
from app.models.base import db
from app.models.schema import Submission, FormConfig
from app.utils.security import is_spam_content

def cleanup_spam(target_all=False):
    """
    既存の送信データからスパムと思われるものをマークします。
    """
    if db.is_closed():
        db.connect()
    
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

        is_spam, reason = is_spam_content(data, sub.form)
        
        if is_spam:
            sub.status = 'spam'
            sub.is_spam = True
            sub.save()
            updated_count += 1
            print(f"  [Marked as Spam] Submission ID: {sub.id} (Form: {sub.form.name}) - Reason: {reason}")

    print(f"\nScan completed.")
    print(f"Total checked: {total_checked}")
    print(f"Updated to spam: {updated_count}")

if __name__ == '__main__':
    import sys
    # --all 引数があれば全件対象にする
    use_all = '--all' in sys.argv
    cleanup_spam(target_all=use_all)
