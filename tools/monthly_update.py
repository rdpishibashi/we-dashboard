"""
Monthly update pipeline for WE-Dashboard.

Consolidates the three manual steps of the monthly data refresh into one script:

1. Export the "Engagement Master" Google Spreadsheet to Engagement Master.xlsx
   (Drive API export, using the service account credentials already configured
   in .streamlit/secrets.toml for the response-sheet feature).
2. Validate that the rating2/comment sheets contain rows for the expected
   month (the month before the one this script runs in, matching Admin's
   updateMaster() convention). Aborts before step 3 if the data is stale.
3. Run split_by_division() to regenerate the per-division EngagementData-*.xlsx
   files.

Requires .streamlit/secrets.toml to have ENGAGEMENT_MASTER_SHEET_ID set to the
"Engagement Master" spreadsheet ID, and that spreadsheet shared with the
service account email in [gcp_service_account].

Usage:
    python tools/monthly_update.py
"""

import sys
from datetime import date
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]

import pandas as pd
from google.auth.transport.requests import AuthorizedSession
from google.oauth2 import service_account

from split_by_division import split_by_division

_SECRETS_FILE = Path(__file__).resolve().parent.parent / ".streamlit" / "secrets.toml"
OUTPUT_FILE = Path(__file__).resolve().parent.parent / "Engagement Master.xlsx"

_DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
_XLSX_MIME_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _load_secrets() -> dict:
    if not _SECRETS_FILE.exists():
        raise FileNotFoundError(f"{_SECRETS_FILE} not found.")
    with open(_SECRETS_FILE, "rb") as f:
        return tomllib.load(f)


def export_engagement_master(spreadsheet_id: str, out_path: Path = OUTPUT_FILE) -> None:
    """Export the Engagement Master Google Spreadsheet to an xlsx file."""
    secrets = _load_secrets()
    creds = service_account.Credentials.from_service_account_info(
        secrets["gcp_service_account"], scopes=_DRIVE_SCOPES
    )
    session = AuthorizedSession(creds)
    url = f"https://www.googleapis.com/drive/v3/files/{spreadsheet_id}/export"
    response = session.get(url, params={"mimeType": _XLSX_MIME_TYPE})
    response.raise_for_status()
    out_path.write_bytes(response.content)
    print(f"  Exported to {out_path}")


def _expected_year_month(today: date) -> tuple[int, int]:
    """Previous month relative to today, matching Admin's updateMaster()."""
    if today.month == 1:
        return today.year - 1, 12
    return today.year, today.month - 1


def validate_latest_month(source: Path = OUTPUT_FILE, today: date | None = None) -> None:
    """Raise ValueError if rating2/comment lack a row for the expected month."""
    year, month = _expected_year_month(today or date.today())
    for sheet in ["rating2", "comment"]:
        df = pd.read_excel(source, sheet_name=sheet)
        match = df[(df["year"] == year) & (df["month"] == month)]
        if match.empty:
            raise ValueError(
                f"{sheet} シートに {year}-{month:02d} のデータが見つかりません。"
                " Admin の updateMaster() が実行済みか確認してください。"
            )
    print(f"  {year}-{month:02d} のデータを rating2/comment 両方で確認しました。")


def main() -> None:
    secrets = _load_secrets()
    spreadsheet_id = secrets.get("ENGAGEMENT_MASTER_SHEET_ID")
    if not spreadsheet_id:
        raise KeyError(
            "ENGAGEMENT_MASTER_SHEET_ID が .streamlit/secrets.toml に設定されていません。"
        )

    print("Step 1/3: Engagement Master を Google Sheets からエクスポート...")
    export_engagement_master(spreadsheet_id)

    print("Step 2/3: 最新月のデータを検証...")
    validate_latest_month()

    print("Step 3/3: 部門別データに分割...")
    split_by_division()

    print("完了しました。")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
