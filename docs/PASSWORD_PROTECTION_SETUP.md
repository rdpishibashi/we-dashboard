# Excel Password Protection Setup Guide

## Overview

This guide explains how to password-protect your Excel files so users can upload them to the dashboard but cannot open them in Excel directly.

## How It Works

1. You password-protect the Excel file in Excel
2. Users receive the protected file but don't know the password
3. Users upload the file to the dashboard
4. Dashboard automatically opens it using the configured password
5. Users can only view data through the dashboard

The password is configured in one of two ways depending on the runtime environment:

| 環境 | パスワード設定場所 |
|------|------------------|
| Streamlit Cloud | `.streamlit/secrets.toml` または Streamlit Cloud の Secrets 設定 |
| ローカル（Mac/Windows） | `modules/windows_config.py`（git-ignored） |

---

## Step 1: Password-Protect Your Excel File

### In Microsoft Excel:

1. Open your Excel file (`EngagementMasterSS.xlsx`)
2. Go to **File** → **Info** → **Protect Workbook** → **Encrypt with Password**
3. Enter a strong password (e.g., `MySecurePassword123!`)
4. Click **OK** and re-enter the password to confirm
5. Save the file

### In Excel for Mac:

1. Open your Excel file
2. Go to **File** → **Passwords**
3. Enter password in "Password to open"
4. Click **OK**
5. Save the file

**Important:** Remember this password! You'll need it for the next step.

---

## Step 2a: Configure Streamlit Cloud Secrets

### Finding the Secrets Section:

1. Go to your Streamlit Cloud dashboard: https://share.streamlit.io/
2. Go to your workspace and find your app in the list
3. Click the **three dots menu (⋮)** next to your app name
4. Select **Settings** from the dropdown
5. In the settings page, look for the **Secrets** section/tab on the left sidebar

**Alternative path:**
- From your app's page, look for the app menu (usually in the top-right corner)
- The exact location may vary, but look for: **App settings**, **Advanced settings**, or **⋮ menu**

### Add the Secret:

In the Secrets editor, add:

```toml
EXCEL_PASSWORD = "MySecurePassword123!"
```

Replace `MySecurePassword123!` with your actual password.

Click **Save** or **Deploy** (the button name varies)

**Note:** The secrets editor uses TOML format. Make sure there are no extra quotes or spaces.

---

## Step 2b: Configure Local Standalone (Mac/Windows)

ローカルで `streamlit run app.py` を実行する場合、`.streamlit/secrets.toml` はファイルシステム上に平文で存在するため推奨しません。代わりに `modules/windows_config.py` を使用します。

パスワードは AES（Fernet）で暗号化して保存します。平文はファイルに書かれません。

1. `tools/encrypt_passwords.py` を実行してパスワードを暗号化する:

```bash
python tools/encrypt_passwords.py
```

入力は非表示で求められます。出力として暗号化済みバイト列が表示されます。

2. 表示された `_EXCEL_PASSWORD_ENC` / `_RESPONSE_PASSWORD_ENC` の値を `modules/windows_config.py` に貼り付ける。

3. `windows_config.py` は `.gitignore` で除外済みのため、**Git にコミットされません**。

アプリは起動時に `windows_config.py` を自動検出し、AES 復号して `st.secrets` より優先して使用します。

---

## Step 3: Test the Configuration

### Local Testing (Streamlit Cloud approach):

Create a file `.streamlit/secrets.toml` in your project directory:

```toml
EXCEL_PASSWORD = "MySecurePassword123!"
```

⚠️ **Add this to .gitignore!** Never commit secrets to Git.

### Local Testing (Standalone approach):

`modules/windows_config.py` を Step 2b に従って作成します。`secrets.toml` は不要です。

### Deploy to Streamlit Cloud:

1. Commit and push your code changes
2. Streamlit Cloud will automatically redeploy
3. Test by uploading the password-protected Excel file

---

## For Users

### Instructions to provide to your users:

1. **Download** the Excel file we provide
2. **Do NOT try to open** the file in Excel (it's password-protected)
3. **Upload** the file directly to the dashboard using the file uploader
4. The dashboard will automatically process the file

---

## Troubleshooting

### Error: "Excelファイルのパスワードが正しくありません"

- The password in Streamlit secrets doesn't match the Excel file password
- Update the `EXCEL_PASSWORD` in Streamlit Cloud secrets

### Users can still open the file

- Make sure you saved the file after applying password protection
- Try opening the file yourself to verify it requires a password

### Dashboard works locally but not on Streamlit Cloud

- Verify the `EXCEL_PASSWORD` is set in Streamlit Cloud secrets (not just locally)

---

## Security Notes

✅ **Secure:**
- Streamlit Cloud: パスワードは Streamlit Secrets に暗号化して保存
- ローカル: パスワードは `windows_config.py` に AES（Fernet）暗号化して保存（git-ignored）。平文は記録されない
- PyInstaller ビルド時にバイトコードとして埋め込まれ、暗号化キーと暗号文の両方を抽出しないと復号不可
- Users cannot view password in code or browser
- File is password-protected at rest
- レスポンスファイルも同じパスワード管理で保護可能

❌ **Not Protected Against:**
- Users taking screenshots of dashboard
- Users with admin access to Streamlit Cloud
- 高度なリバースエンジニアリング（バイナリからキーと暗号文を抽出して復号）

For maximum security, also implement:
- Role-based access control (already implemented)
- Audit logging
- Regular password rotation
