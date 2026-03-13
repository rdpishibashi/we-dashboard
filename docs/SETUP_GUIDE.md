# セットアップガイド

WE-Dashboard のローカル開発環境構築から Streamlit Cloud へのデプロイまでを網羅したガイドです。

---

## 1. 前提条件

### Python バージョン

Python 3.9 以上が必要です。バージョンを確認するには:

```bash
python3 --version
```

### 必要パッケージ（requirements.txt）

| パッケージ | 最低バージョン | 用途 |
|---|---|---|
| streamlit | 1.28.0 | Webアプリフレームワーク |
| pandas | 2.0.0 | データ処理 |
| plotly | 5.18.0 | グラフ描画 |
| openpyxl | 3.1.0 | Excel ファイル読み込み |
| numpy | 1.24.0 | 数値計算 |
| statsmodels | 0.14.0 | 統計モデル |
| msoffcrypto-tool | 5.0.0 | パスワード付き Excel の復号 |
| cryptography | 41.0.0 | 暗号化処理 |
| pyyaml | 6.0.0 | YAML 設定ファイル読み込み |
| gspread | - | Google Sheets 連携 |
| google-auth | 2.0.0 | Google 認証 |

---

## 2. ローカル開発環境構築

### Step 1: パッケージのインストール

```bash
pip install -r requirements.txt
```

### Step 2: シークレットファイルの作成

`.streamlit/secrets.toml` を作成します。テンプレートからコピーするのが最も簡単です:

```bash
cp .streamlit/secrets.toml.template .streamlit/secrets.toml
```

次に `.streamlit/secrets.toml` を編集して必要な値を設定します:

```toml
# パスワード付き Excel ファイルを使用する場合
EXCEL_PASSWORD = "実際のパスワード"

# Excel 暗号化キー（必要な場合）
EXCEL_ENCRYPTION_KEY = "暗号化キー"

# Google Sheets 連携（アンケート回答データ取得に使用）
RESPONSE_SHEET_ID = "GoogleスプレッドシートのID"

[gcp_service_account]
type = "service_account"
project_id = "your-project-id"
private_key_id = "key-id"
private_key = "-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----\n"
client_email = "service-account@project.iam.gserviceaccount.com"
client_id = "client-id"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
```

**重要:** `.streamlit/secrets.toml` は `.gitignore` に登録済みです。絶対に Git にコミットしないでください。

ローカルでパスワードなしの Excel ファイルを使う場合、`EXCEL_PASSWORD` の設定は不要です（省略可能）。

### Step 3: データファイルの配置

`EngagementMasterSS.xlsx` をプロジェクトルートに配置します:

```bash
cp /path/to/EngagementMasterSS.xlsx .
```

ファイル読み込みの優先順位:
1. ユーザーがアップロードしたファイル
2. プロジェクトルートの `EngagementMasterSS.xlsx`（`modules/config.py` の `DEFAULT_FILE_PATH` で設定）

### Step 4: 認証ファイルの確認

| ファイル | 用途 |
|---|---|
| `auth_users.json` | 開発用ユーザー認証情報（人間が読める形式） |
| `auth_users.dat` | 本番用ユーザー認証情報（Base64エンコード済み） |

ローカル開発では `auth_users.json` をそのまま使用できます。本番デプロイ時は `auth_users.dat` が必要です（「6. ツール」を参照）。

---

## 3. アプリケーション起動

### 基本起動（推奨）

```bash
streamlit run app.py
```

起動すると、ブラウザが自動的に `http://localhost:8501` を開きます。

### 起動オプション

```bash
# 別ポートで起動（ポート競合時）
streamlit run app.py --server.port 8502

# ブラウザを自動で開かない（ヘッドレスモード）
streamlit run app.py --server.headless true

# デバッグログを有効化
streamlit run app.py --logger.level debug
```

### ホットリロード

`.py` ファイルや設定ファイルを保存すると、Streamlit が自動的に再読み込みします。ブラウザには「Source file changed, rerunning...」と表示されます。

### アプリの停止

ターミナルで `Ctrl + C` を押します。

---

## 4. Streamlit Cloud デプロイ

### リポジトリの接続

1. [share.streamlit.io](https://share.streamlit.io/) にアクセス
2. 「New app」をクリック
3. GitHub リポジトリ、ブランチ（`main`）、メインファイル（`app.py`）を選択
4. 「Deploy!」をクリック

### シークレットの設定

デプロイ後、またはデプロイ前に Streamlit Cloud のシークレットを設定します:

1. Streamlit Cloud ダッシュボードでアプリを選択
2. 「⋮」（三点メニュー） → 「Settings」を選択
3. 左サイドバーの「Secrets」タブを開く
4. ローカルの `.streamlit/secrets.toml` と同じ内容を貼り付けて保存

シークレットを更新するとアプリが自動的に再デプロイされます。

### パスワード付き Excel の扱い

本番環境では Excel ファイルをパスワード保護することを推奨します:

- Excel で「ファイル」→「情報」→「ブックの保護」→「パスワードを使用して暗号化」で設定
- 設定したパスワードを `EXCEL_PASSWORD` としてStreamlit Cloud のシークレットに登録
- ユーザーには保護済みの Excel ファイルを配布し、ダッシュボードにアップロードしてもらう

---

## 5. 設定ファイル

### `.streamlit/config.toml` — テーマ・サーバー設定

```toml
[theme]
primaryColor = "#0365C0"
backgroundColor = "#ffffff"
secondaryBackgroundColor = "#f8f9fa"
textColor = "#1f4e79"
font = "sans serif"

[server]
maxUploadSize = 200      # アップロード可能な最大ファイルサイズ（MB）

[browser]
gatherUsageStats = false # 使用統計の送信を無効化
```

### `config/privileges.yaml` — 権限設定

`config/privileges_configuration.md` を「正」として管理されており、`tools/generate_privileges_yaml.py` で自動生成されます。直接編集せず、Markdown ファイルを編集してからスクリプトで再生成してください。

### `group_order_config.json` — グループ表示順序

ダッシュボード内のドロップダウンやフィルターでの部署・職級などの表示順を定義します:

```json
{
  "department": ["システム開発部", "機電設計部", "開発部", "品質保証部"],
  "section": ["ソフトウェア開発課", "製品技術課", "第一設計課", ...],
  "grade": ["一般職", "主任", "主事補", "主事", "主管", "課長", "部長"]
}
```

### `auth_users.json` / `auth_users.dat` — ユーザー認証情報

```json
// auth_users.json（開発用）
{
  "username": {
    "password": "hashed_password",
    "privilege": "admin"
  }
}
```

本番用の `auth_users.dat` は `tools/convert_auth.py` で生成します。

---

## 6. ツール

### `tools/generate_privileges_yaml.py` — 権限 YAML 生成

`config/privileges_configuration.md` から `config/privileges.yaml` を生成します:

```bash
# YAML を生成（上書き）
python tools/generate_privileges_yaml.py

# 差分チェックのみ（ファイルは更新しない）
python tools/generate_privileges_yaml.py --check
```

`privileges_configuration.md` を変更した後は必ず実行してください。

### `tools/convert_auth.py` — 認証ファイル変換

`auth_users.json` を本番用の `auth_users.dat`（Base64エンコード済みPickle形式）に変換します:

```bash
# インタラクティブメニューで起動（推奨）
python tools/convert_auth.py

# ユーザー追加
python tools/convert_auth.py --add-user

# パスワード変更
python tools/convert_auth.py --change-password

# 権限変更
python tools/convert_auth.py --change-privilege

# 現在のユーザー一覧表示
python tools/convert_auth.py --show

# DAT ファイルのデコード（内容確認）
python tools/convert_auth.py --decode
```

ユーザーを追加・変更した後は JSON → DAT 変換を行い、DAT ファイルをリポジトリにコミットしてデプロイしてください。

---

## 7. トラブルシューティング

### `No module named 'streamlit'`

```bash
pip install -r requirements.txt
```

### `EXCEL_PASSWORD not found` エラー

- パスワード付き Excel を使用している場合: `.streamlit/secrets.toml` に `EXCEL_PASSWORD` を追加する
- パスワードなし Excel を使用している場合: 対応不要（省略可能なシークレット）

### `File not found` エラー

- `EngagementMasterSS.xlsx` がプロジェクトルートに存在するか確認する
- または `modules/config.py` の `DEFAULT_FILE_PATH` を正しいパスに更新する

### ポート競合（`Port 8501 is already in use`）

```bash
streamlit run app.py --server.port 8502
```

または既存のプロセスを終了する:

```bash
lsof -i :8501 | grep LISTEN
kill -9 <PID>
```

### キャッシュのクリア

```bash
# コマンドラインから
streamlit cache clear

# ブラウザから
# 右上のハンバーガーメニュー（≡）→「Clear cache」
```

### ローカルでは動くが Streamlit Cloud で動かない

- Streamlit Cloud のシークレット設定が正しいか確認する（ローカルの `.streamlit/secrets.toml` と一致しているか）
- `requirements.txt` に必要なパッケージが全て記載されているか確認する
- Streamlit Cloud のログ（「Manage app」→「Logs」）でエラーの詳細を確認する

### Excel ファイルのパスワードエラー（`Excelファイルのパスワードが正しくありません`）

- シークレットの `EXCEL_PASSWORD` と Excel ファイルのパスワードが一致しているか確認する
- Streamlit Cloud 側と Excel ファイル側の両方を確認する

---

## 8. 開発ワークフロー

### ディレクトリ構成

```
WE-Dashboard/
├── .streamlit/
│   ├── config.toml              # テーマ・サーバー設定
│   ├── secrets.toml             # ローカル用シークレット（gitignore済み）
│   └── secrets.toml.template    # シークレットのテンプレート
├── config/
│   ├── privileges_configuration.md  # 権限定義（正）
│   └── privileges.yaml          # 自動生成された権限設定
├── docs/
│   ├── SETUP_GUIDE.md           # このファイル
│   ├── PASSWORD_PROTECTION_SETUP.md
│   └── TECHNICAL_ARCHITECTURE.md
├── modules/                     # アプリケーションモジュール
├── tests/                       # テストコード
├── tools/
│   ├── generate_privileges_yaml.py
│   └── convert_auth.py
├── app.py                       # アプリエントリーポイント
├── auth_users.json              # 開発用認証ファイル
├── auth_users.dat               # 本番用認証ファイル
├── EngagementMasterSS.xlsx      # データファイル（gitignore済み）
├── group_order_config.json      # グループ表示順序設定
└── requirements.txt
```

### ベストプラクティス

1. **シークレットは絶対にコミットしない:** `.streamlit/secrets.toml` は `.gitignore` に含まれているが、意図しない `git add .` に注意する

2. **データファイルはローカルのみ:** `EngagementMasterSS.xlsx` もコミット対象外。テスト用に小さいサンプルデータを用意すると開発が速い

3. **権限設定の変更手順:**
   ```
   config/privileges_configuration.md を編集
   → python tools/generate_privileges_yaml.py を実行
   → config/privileges.yaml の変更をコミット
   ```

4. **ユーザー追加の手順:**
   ```
   python tools/convert_auth.py --add-user を実行
   → auth_users.dat をコミット（auth_users.json も更新してコミット）
   ```

5. **機能開発はブランチで行う:** 変更が動作確認できてから `main` にマージする

6. **ローカルでテストを実行する:**
   ```bash
   python -m pytest tests/
   ```
