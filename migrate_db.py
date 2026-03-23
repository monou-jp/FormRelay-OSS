import os
import sqlite3
from peewee import SqliteDatabase, BooleanField
from playhouse.migrate import SqliteMigrator, migrate
import config
from app.models.base import db
from app.models.schema import FormConfig, Submission, Attachment, MailLog, StatusHistory, RateLimit, User

def run_migrations():
    db_path = config.DATABASE_PATH
    if not os.path.exists(db_path):
        print(f"Database file not found at {db_path}. No migration needed.")
        return

    # 1. require_japanese カラムの追加 (FormConfig)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(formconfig)")
    columns = [row[1] for row in cursor.fetchall()]
    
    # 2. is_deleted カラムの追加 (Submission)
    cursor.execute("PRAGMA table_info(submission)")
    submission_columns = [row[1] for row in cursor.fetchall()]
    conn.close()

    if 'require_japanese' not in columns:
        print("Migrating: Adding 'require_japanese' to 'FormConfig' table...")
        migrator = SqliteMigrator(db)
        require_japanese_field = BooleanField(default=False)
        
        try:
            migrate(
                migrator.add_column('formconfig', 'require_japanese', require_japanese_field),
            )
            print("Successfully added 'require_japanese' column.")
        except Exception as e:
            print(f"Error during migration: {e}")
    else:
        print("'require_japanese' column already exists in 'FormConfig' table.")

    if 'is_deleted' not in submission_columns:
        print("Migrating: Adding 'is_deleted' to 'Submission' table...")
        migrator = SqliteMigrator(db)
        is_deleted_field = BooleanField(default=False)
        
        try:
            migrate(
                migrator.add_column('submission', 'is_deleted', is_deleted_field),
            )
            print("Successfully added 'is_deleted' column.")
        except Exception as e:
            print(f"Error during migration: {e}")
    else:
        print("'is_deleted' column already exists in 'Submission' table.")

if __name__ == '__main__':
    run_migrations()
