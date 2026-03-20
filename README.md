# FormRelay

複数ドメインのWebサイトから送信されるフォームを、単一APIで受信・管理し、メール通知およびCRM的に管理できるシステムです。
Bottle + Peewee + SQLite を使用しており、軽量かつ自己完結型で動作します。

## 🌍 ウェブサイト / デモ
[GitHub Pages](https://live.github.io/FormRelay-OSS/) で製品概要と導入方法を公開しています。

## 🌟 主な機能

- **フォーム受信API**: JSONまたはフォーム形式でデータを受信。
- **セキュリティ**:
  - Honeypot検知によるスパム対策
  - IPベースのレート制限（Rate Limit）
  - CORS制御（許可ドメイン設定）
  - reCAPTCHA (v2) 対応
  - IPブラックリスト
- **通知**:
  - SMTP経由のメール送信
  - HTMLメール・添付ファイル対応
  - フォームごとの通知先・テンプレート設定
- **CRM管理画面**:
  - モダンなダッシュボード（統計グラフ）
  - 送信データのステータス管理（未対応 / 対応中 / 完了）
  - 添付ファイルの安全な管理（要認証）
  - 失敗したメールの再送機能
- **メンテナンス**:
  - 起動時の自動DBバックアップ（直近5件を保持）
  - 構造変更時の自動マイグレーション
- **ユーザー管理**: 権限管理（管理者 / 一般）およびログイン機能。

## 🛠 インストール

1. リポジトリをクローンまたはダウンロードします。
2. 依存関係をインストールします。

```bash
pip install bottle peewee jinja2 itsdangerous
```

## 🚀 起動方法

### 開発環境

```bash
python main.py
```

デフォルトで `http://localhost:8080` にアクセスできます。

### デモデータの投入

開発や動作確認のために、実務に即したサンプルデータを投入できます。

```bash
# Windows (PowerShell)
$env:PYTHONPATH="."; python seed_data.py

# Linux / macOS
PYTHONPATH=. python3 seed_data.py
```

### 本番環境 (WSGI)

`gunicorn` などのWSGIサーバーを使用して実行できます。

```bash
gunicorn main:app
```

### CGI環境

ApacheなどのCGI環境で動作させる場合は、`main.py` を以下のように指定してください。

```python
import bottle
from main import app
bottle.run(app, server='cgi')
```

## 🔐 初期設定

1. `config.py` を開き、以下の項目を環境に合わせて変更してください。
   - `SECRET_KEY`: セッション暗号化用のキー
   - `SMTP_*`: メール送信設定
   - `BASE_URL`: 管理画面のベースURL（通知メール内のリンクに使用）
2. 初回起動時に管理者ユーザーが作成されます。
   - **ユーザー名**: `admin`
   - **パスワード**: `admin123`
   - *ログイン後、必ずユーザー管理画面からパスワードを変更してください。*

## 📝 API仕様

### フォーム送信

- **Endpoint**: `POST /api/form`
- **Content-Type**: `application/x-www-form-urlencoded` または `multipart/form-data`

#### 必須パラメータ
- `form_id`: フォーム識別子（管理画面で作成）

#### オプションパラメータ
- `_next`: 送信後のリダイレクト先URL
- `_honeypot`: スパム対策用の隠しフィールド（値が入っていると無視されます）
- `g-recaptcha-response`: reCAPTCHAトークン（有効な場合）
- その他、任意のフィールド名はすべて保存されます。

## 🧪 テスト

システムには、API、管理画面、およびブラウザシミュレーション（Selenium）のテストが含まれています。

### 依存関係のインストール

テストの実行には、以下の追加パッケージが必要です。

```bash
pip install webtest selenium
```

### テストの実行方法

全てのテストを実行する前に、プロジェクトルートを `PYTHONPATH` に含める必要があります。

#### 1. API テスト (Unit/Integration)
バリデーション、Honeypot、CORS、エラーログ出力などのAPI挙動を確認します。

```bash
# Windows (PowerShell)
$env:PYTHONPATH="."; python -m unittest tests/test_api.py

# Linux / macOS
PYTHONPATH=. python3 -m unittest tests/test_api.py
```

#### 2. 管理画面テスト (Integration)
ログイン、フォーム管理（CRUD）、送信データのステータス管理、ユーザー管理などを確認します。

```bash
# Windows (PowerShell)
$env:PYTHONPATH="."; python -m unittest tests/test_admin.py
```

#### 3. Selenium テスト (E2E)
実際のブラウザ（Chrome ヘッドレス）を使用して、フォーム送信の境界値テストや、管理画面からのフォーム作成フローを確認します。
*※実行には Chrome ブラウザと対応する ChromeDriver が必要です。*

```bash
# Windows (PowerShell)
$env:PYTHONPATH="."; python tests/test_selenium.py
```

## 📄 ライセンス

GNU Affero General Public License v3 (AGPLv3)
