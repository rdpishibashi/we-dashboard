# Excel Password Protection Setup Guide

## Overview

This guide explains how to password-protect your Excel files so users can upload them to the dashboard but cannot open them in Excel directly.

## How It Works

1. You password-protect the Excel file in Excel
2. Users receive the protected file but don't know the password
3. Users upload the file to the dashboard
4. Dashboard automatically opens it using the password stored in Streamlit secrets
5. Users can only view data through the dashboard

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

## Step 2: Configure Streamlit Cloud Secrets

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

## Step 3: Test the Configuration

### Local Testing (Optional):

Create a file `.streamlit/secrets.toml` in your project directory:

```toml
EXCEL_PASSWORD = "MySecurePassword123!"
```

⚠️ **Add this to .gitignore!** Never commit secrets to Git.

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
- Password is stored in Streamlit secrets (encrypted)
- Users cannot view password in code or browser
- File is password-protected at rest

❌ **Not Protected Against:**
- Users taking screenshots of dashboard
- Users with admin access to Streamlit Cloud
- Someone with physical access to your computer

For maximum security, also implement:
- Role-based access control (already implemented)
- Audit logging
- Regular password rotation
