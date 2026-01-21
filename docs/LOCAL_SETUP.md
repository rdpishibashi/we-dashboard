# Local Development Setup

## Running the Dashboard Locally on Your Mac

### Prerequisites

- Python 3.9 or higher (you have Python 3.14.2 ✅)
- Streamlit installed

---

## Step 1: Install Dependencies

If you haven't already, install required packages:

```bash
pip install streamlit pandas plotly openpyxl numpy
```

---

## Step 2: Set Up Local Secrets

Create a secrets file for local development:

```bash
mkdir -p .streamlit
```

Create `.streamlit/secrets.toml` with your configuration:

```toml
# Excel password (if using password-protected files)
EXCEL_PASSWORD = "YourPasswordHere"

# Add any other secrets you need
# These secrets are for LOCAL DEVELOPMENT ONLY
# DO NOT commit this file to Git (already in .gitignore)
```

**Important:** This file is already in `.gitignore` and will NOT be committed to Git.

---

## Step 3: Place Your Data File

Put your Excel file in the project directory:

```bash
# If using password-protected file
cp /path/to/EngagementMasterSS.xlsx .

# Or if using default unprotected file for local testing
# Make sure DEFAULT_FILE_PATH in modules/config.py points to it
```

---

## Step 4: Run the App

```bash
streamlit run app.py
```

The dashboard will open in your default browser at `http://localhost:8501`

---

## For Development Without Password Protection

If you want to test locally with an unprotected Excel file:

1. Use an unprotected copy of the file for local development
2. The app will work fine without `EXCEL_PASSWORD` in secrets
3. Only use password-protected files for production (Streamlit Cloud)

**File Priority:**
1. User uploads a file → uses uploaded file
2. No upload → uses `DEFAULT_FILE_PATH` from `modules/config.py`

---

## Common Issues

### Error: "No module named 'streamlit'"

```bash
pip install streamlit
```

### Error: "EXCEL_PASSWORD not found"

- If using password-protected file: Add password to `.streamlit/secrets.toml`
- If using unprotected file: No action needed (password is optional)

### Error: "File not found"

- Check that `EngagementMasterSS.xlsx` exists in project directory
- Or update `DEFAULT_FILE_PATH` in `modules/config.py`

### Port already in use

```bash
streamlit run app.py --server.port 8502
```

---

## Development Workflow

### Recommended Setup:

```
WE-Dashboard/
├── .streamlit/
│   └── secrets.toml          # Local secrets (gitignored)
├── modules/
├── app.py
├── EngagementMasterSS.xlsx   # Local data file (gitignored)
└── ... other files
```

### Best Practices:

1. **Keep secrets local:** Never commit `.streamlit/secrets.toml`
2. **Use test data locally:** Consider using a smaller test dataset for faster development
3. **Sync with cloud:** Ensure Streamlit Cloud secrets match your production needs
4. **Branch for testing:** Use git branches for experimenting with changes

---

## Stopping the App

Press `Ctrl + C` in the terminal where Streamlit is running.

---

## Hot Reload

Streamlit automatically reloads when you save changes to:
- Python files (`.py`)
- Config files

The browser will show "Source file changed, rerunning..." and refresh automatically.

---

## Additional Options

### Run on different port:
```bash
streamlit run app.py --server.port 8502
```

### Run without opening browser:
```bash
streamlit run app.py --server.headless true
```

### Enable debug mode:
```bash
streamlit run app.py --logger.level debug
```

### Custom theme:
Create `.streamlit/config.toml`:
```toml
[theme]
primaryColor = "#F63366"
backgroundColor = "#FFFFFF"
secondaryBackgroundColor = "#F0F2F6"
textColor = "#262730"
font = "sans serif"
```

---

## Troubleshooting

### Check Python version:
```bash
python3 --version
```

Should show Python 3.9 or higher.

### Check installed packages:
```bash
pip list | grep streamlit
pip list | grep pandas
```

### Clear Streamlit cache:
```bash
streamlit cache clear
```

### View full logs:
Run with verbose logging:
```bash
streamlit run app.py --logger.level debug
```
