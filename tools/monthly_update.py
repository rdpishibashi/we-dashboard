"""
Monthly update pipeline for WE-Dashboard.

Consolidates the four manual steps of the monthly data refresh into one script:

1. Export the "Engagement Master" Google Spreadsheet to Engagement Master.xlsx
   (Drive API export, using the service account credentials already configured
   in .streamlit/secrets.toml for the response-sheet feature).
2. Validate that the rating2/comment sheets contain rows for the expected
   month (the month before the one this script runs in, matching Admin's
   updateMaster() convention). Aborts before step 3 if the data is stale.
3. Run split_by_division() to regenerate the per-division EngagementData-*.xlsx
   files.
4. Commit and push only EngagementData-品質保証部門.xlsx to GitHub main.
   Engagement Master.xlsx (and every other division's file) is never staged —
   Engagement Master.xlsx also stays out of git entirely per .gitignore.

Requires .streamlit/secrets.toml to have ENGAGEMENT_MASTER_SHEET_ID set to the
"Engagement Master" spreadsheet ID, and that spreadsheet shared with the
service account email in [gcp_service_account].

Usage:
    python tools/monthly_update.py
"""

import subprocess
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

REPO_ROOT = Path(__file__).resolve().parent.parent
_SECRETS_FILE = REPO_ROOT / ".streamlit" / "secrets.toml"
OUTPUT_FILE = REPO_ROOT / "Engagement Master.xlsx"
PUSH_TARGET_FILE = "EngagementData-品質保証部門.xlsx"

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


def _git(*args: str, repo_root: Path = REPO_ROOT) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo_root), *args], capture_output=True, text=True
    )


def push_quality_assurance_division(repo_root: Path = REPO_ROOT) -> None:
    """Commit and push only PUSH_TARGET_FILE (EngagementData-品質保証部門.xlsx).

    No other file is ever staged here, so Engagement Master.xlsx and the other
    divisions' EngagementData-*.xlsx files are never pushed by this function.
    """
    target = repo_root / PUSH_TARGET_FILE
    if not target.exists():
        raise FileNotFoundError(
            f"{target} が見つかりません。split_by_division() が正しく実行されたか確認してください。"
        )

    branch = _git("branch", "--show-current", repo_root=repo_root).stdout.strip()
    if branch != "main":
        raise RuntimeError(
            f"現在のブランチは '{branch}' です。main ブランチで実行してください。"
        )

    fetch = _git("fetch", "origin", repo_root=repo_root)
    if fetch.returncode != 0:
        raise RuntimeError(f"git fetch に失敗しました: {fetch.stderr}")

    behind = _git(
        "rev-list", "--count", "main..origin/main", repo_root=repo_root
    ).stdout.strip()
    if behind != "0":
        raise RuntimeError(
            "ローカル main が origin/main より遅れています。"
            " 'git sync' 等で同期してから再実行してください。"
        )

    status = _git(
        "status", "--porcelain", "--", PUSH_TARGET_FILE, repo_root=repo_root
    ).stdout
    if not status.strip():
        print(f"  {PUSH_TARGET_FILE} に変更はありません。push をスキップします。")
        return

    add = _git("add", "--", PUSH_TARGET_FILE, repo_root=repo_root)
    if add.returncode != 0:
        raise RuntimeError(f"git add に失敗しました: {add.stderr}")

    commit_message = f"data: {PUSH_TARGET_FILE} を更新 ({date.today():%Y-%m-%d})"
    commit = _git("commit", "-m", commit_message, repo_root=repo_root)
    if commit.returncode != 0:
        raise RuntimeError(f"git commit に失敗しました: {commit.stderr}")

    push = _git("push", "origin", "main", repo_root=repo_root)
    if push.returncode != 0:
        raise RuntimeError(f"git push に失敗しました: {push.stderr}")

    print(f"  {PUSH_TARGET_FILE} を GitHub に push しました。")


def main() -> None:
    secrets = _load_secrets()
    spreadsheet_id = secrets.get("ENGAGEMENT_MASTER_SHEET_ID")
    if not spreadsheet_id:
        raise KeyError(
            "ENGAGEMENT_MASTER_SHEET_ID が .streamlit/secrets.toml に設定されていません。"
        )

    print("Step 1/4: Engagement Master を Google Sheets からエクスポート...")
    export_engagement_master(spreadsheet_id)

    print("Step 2/4: 最新月のデータを検証...")
    validate_latest_month()

    print("Step 3/4: 部門別データに分割...")
    split_by_division()

    print(f"Step 4/4: {PUSH_TARGET_FILE} を GitHub に push...")
    push_quality_assurance_division()

    print("完了しました。")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
