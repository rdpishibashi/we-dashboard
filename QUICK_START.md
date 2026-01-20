# Quick Start Guide

## Running Locally on Mac

### Option 1: Simple Command (Recommended)

```bash
streamlit run app.py
```

The dashboard will open automatically in your browser at `http://localhost:8501`

### Option 2: Using the Start Script

```bash
./run_local.sh
```

This script checks your setup and provides helpful warnings.

---

## First Time Setup

### 1. Install Dependencies

```bash
pip install streamlit pandas plotly openpyxl numpy
```

### 2. Set Up Secrets (If Using Password-Protected Files)

```bash
# Copy template
cp .streamlit/secrets.toml.template .streamlit/secrets.toml

# Edit the file and add your password
nano .streamlit/secrets.toml
```

Add your password:
```toml
EXCEL_PASSWORD = "YourPasswordHere"
```

### 3. Add Your Data File (Optional)

Place `EngagementMasterSS.xlsx` in the project directory, or upload it through the dashboard UI.

---

## What You'll See

When you run the app:

1. ✅ Terminal shows: "You can now view your Streamlit app in your browser."
2. 🌐 Browser opens to `http://localhost:8501`
3. 📊 Dashboard interface loads
4. 📁 Upload your Excel file (or it loads the default if present)

---

## Stopping the App

Press **Ctrl + C** in the terminal

---

## Need Help?

- **Full setup guide:** See `LOCAL_SETUP.md`
- **Password protection:** See `PASSWORD_PROTECTION_SETUP.md`
- **Errors?** Check the terminal output for error messages

---

## Development Tips

### Hot Reload
Save any `.py` file → Streamlit automatically reloads

### Clear Cache
```bash
streamlit cache clear
```

### Different Port
```bash
streamlit run app.py --server.port 8502
```

### View Logs
```bash
streamlit run app.py --logger.level debug
```
