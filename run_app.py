import sys
import os


def main():
    # Determine base directory
    if getattr(sys, 'frozen', False):
        # Running as PyInstaller bundle
        bundle_dir = sys._MEIPASS
    else:
        bundle_dir = os.path.dirname(os.path.abspath(__file__))

    # Streamlit needs to find app.py and its modules
    os.chdir(bundle_dir)

    from streamlit.web import cli as stcli

    sys.argv = [
        "streamlit", "run",
        os.path.join(bundle_dir, "app.py"),
        "--global.developmentMode=false",
        "--browser.gatherUsageStats=false",
    ]
    stcli.main()


if __name__ == "__main__":
    main()
