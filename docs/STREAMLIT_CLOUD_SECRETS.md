# Streamlit Cloud Secrets Configuration Guide

## Finding Secrets in Streamlit Cloud (Updated)

The Streamlit Cloud interface has changed. Here are **all possible ways** to access Secrets:

---

## Method 1: From Your App Dashboard (Most Common)

1. Go to **https://share.streamlit.io/** and log in
2. You'll see your list of apps in your workspace
3. Find your app (WE-Dashboard)
4. Click the **three-dot menu (⋮)** or **hamburger menu** next to your app name
5. Select **Settings** or **App settings**
6. In the left sidebar or tabs, look for:
   - **Secrets**
   - **Advanced settings**
   - **Environment variables**

---

## Method 2: From the Running App

1. Open your deployed app in the browser
2. Look in the **top-right corner** of the app for:
   - **⋮ menu** (three vertical dots)
   - **☰ menu** (hamburger menu)
   - **Manage app** button
3. Click it and select **Settings** or **App settings**
4. Navigate to the **Secrets** section

---

## Method 3: Direct from Workspace

1. Go to your Streamlit Cloud workspace
2. Click on your app name to open the app management page
3. Look for tabs at the top:
   - **Overview**
   - **Settings**
   - **Logs**
   - **Analytics**
4. Click **Settings**
5. Scroll down or look in sidebar for **Secrets** section

---

## Method 4: Via App Settings Page

If you see an app details/overview page:

1. Look for **Edit** or **Configure** button
2. Or look for navigation tabs/sections:
   - General settings
   - **Secrets** ← This is what you need
   - Resources
   - Python version
   - Advanced

---

## What the Secrets Section Looks Like

When you find it, you'll see:
- A text editor box (similar to code editor)
- Text saying "Secrets are encrypted" or similar security notice
- TOML format editor
- "Save" or "Deploy" button at the bottom

---

## Adding Your Secret

In the Secrets editor, type:

```toml
EXCEL_PASSWORD = "YourActualPasswordHere"
```

**Important:**
- Use straight quotes `"` not curly quotes `""`
- No spaces around the `=` sign (spaces are OK but not required)
- Password must be in quotes
- Save/Deploy after editing

---

## Still Can't Find It?

### Current Streamlit Cloud UI (as of 2024-2026):

The UI location varies based on:
- When your account was created
- Which version of the interface you're seeing
- Your workspace type (personal/organization)

### Try This:

1. **Search the page:** Press `Ctrl+F` (or `Cmd+F` on Mac) and search for "secret"
2. **Check the URL:** When viewing your app settings, the URL might be:
   - `https://share.streamlit.io/[workspace]/[app]/settings`
   - Look for a **Secrets** tab or section on this page

3. **Look for these keywords anywhere:**
   - Secrets
   - Environment
   - Configuration
   - Advanced
   - Security

### Screenshot Guide:

**What you're looking for:**
```
┌─────────────────────────────────┐
│ App Settings                     │
├─────────────────────────────────┤
│ ► General                        │
│ ► Secrets          ← HERE!       │
│ ► Resources                      │
│ ► Advanced                       │
└─────────────────────────────────┘
```

---

## Alternative: Use Environment Variables (If Secrets Not Found)

Some versions may call it "Environment Variables" instead:

```bash
EXCEL_PASSWORD=YourPasswordHere
```

(Same concept, different name)

---

## Verification

After adding the secret:

1. Click **Save** or **Deploy**
2. Your app will restart
3. Check the app logs for any errors
4. Try uploading a password-protected file

---

## Support

If you still can't find it:
- Check Streamlit's official docs: https://docs.streamlit.io/streamlit-community-cloud/deploy-your-app/secrets-management
- Or contact Streamlit support

The UI has changed several times, but the functionality is still there!
