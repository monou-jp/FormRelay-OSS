from peewee import SqliteDatabase, Model
import config
import os

# データベースディレクトリの確認
os.makedirs(os.path.dirname(config.DATABASE_PATH), exist_ok=True)

db = SqliteDatabase(config.DATABASE_PATH)

class BaseModel(Model):
    class Meta:
        database = db
