#!/bin/bash
# Quick start script for running WE-Dashboard locally

echo "🚀 Starting Work Engagement Dashboard..."
echo ""

# Check if .streamlit directory exists
if [ ! -d ".streamlit" ]; then
    echo "📁 Creating .streamlit directory..."
    mkdir -p .streamlit
fi

# Check if secrets.toml exists
if [ ! -f ".streamlit/secrets.toml" ]; then
    echo "⚠️  Warning: .streamlit/secrets.toml not found"
    echo ""
    echo "If you're using password-protected Excel files, you need to:"
    echo "  1. Copy .streamlit/secrets.toml.template to .streamlit/secrets.toml"
    echo "  2. Edit secrets.toml and add your EXCEL_PASSWORD"
    echo ""
    echo "For unprotected files, you can ignore this warning."
    echo ""
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Check if data file exists
if [ ! -f "EngagementMasterSS.xlsx" ]; then
    echo "⚠️  Warning: EngagementMasterSS.xlsx not found in current directory"
    echo "You'll need to upload a file through the dashboard."
    echo ""
fi

# Run Streamlit
echo "✅ Starting Streamlit..."
echo "📊 Dashboard will open in your browser at http://localhost:8501"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

streamlit run app.py
