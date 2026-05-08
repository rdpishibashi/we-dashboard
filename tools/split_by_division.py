"""
Split EngagementMasterSS.xlsx into per-division Excel files.

Each output file contains only the 'rating2' and 'comment' sheets,
filtered to rows where current_division matches the target division.

Leave members (leave == "leave") have their current_* fields cleared by
Admin GAS, so current_division is empty for them.  Their rows are included
in the division file that matches their division in members.yaml, so that
the WE-Dashboard checkbox "転属・退職メンバーを含む" can display them.

Rows with no division in either current_division or members.yaml are skipped.
Each output file is encrypted with a password read from .streamlit/secrets.toml.

Output: EngagementData-{division}.xlsx
"""

import io
import sys
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]

import msoffcrypto
import pandas as pd
import yaml

_SECRETS_FILE = Path(__file__).resolve().parent.parent / ".streamlit" / "secrets.toml"
_MEMBERS_YAML = Path(__file__).resolve().parent.parent / "config" / "members.yaml"

SOURCE_FILE = Path(__file__).parent.parent / "Engagement Master.xlsx"
OUTPUT_DIR = Path(__file__).parent.parent
SHEETS = ["rating2", "comment"]


def _load_password() -> str:
    if _SECRETS_FILE.exists():
        with open(_SECRETS_FILE, "rb") as f:
            secrets = tomllib.load(f)
        pwd = secrets.get("EXCEL_PASSWORD")
        if pwd:
            return pwd
    raise FileNotFoundError(
        f"EXCEL_PASSWORD not found in {_SECRETS_FILE}. "
        "Please set it in .streamlit/secrets.toml."
    )


def _load_leave_division_map() -> dict[str, str]:
    """
    Return {mail_address: division} for members with leave == "leave".

    Admin GAS clears current_division for leave members, so we use
    members.yaml as the source of truth for their division.
    """
    if not _MEMBERS_YAML.exists():
        print(f"  Warning: {_MEMBERS_YAML} not found — leave members will not be included.")
        return {}

    with open(_MEMBERS_YAML, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    result = {}
    for member in data.get("members", []):
        if member.get("leave") == "leave":
            addr = member.get("mail_address", "").strip()
            div = member.get("division", "").strip()
            if addr and div:
                result[addr] = div
    return result


def _normalize_str_col(series: pd.Series) -> pd.Series:
    """Strip leading/trailing whitespace and normalize empty strings to NaN."""
    return series.astype(str).str.strip().replace({"nan": pd.NA, "": pd.NA})


def split_by_division(source: Path = SOURCE_FILE) -> None:
    password = _load_password()

    # Load both sheets up front
    data: dict[str, pd.DataFrame] = {
        sheet: pd.read_excel(source, sheet_name=sheet) for sheet in SHEETS
    }

    # Normalize key string columns to eliminate whitespace mismatches that
    # silently exclude rows from the division filter (e.g. "設計部門 " != "設計部門").
    for sheet in SHEETS:
        for col in ["current_division", "mail_address"]:
            if col in data[sheet].columns:
                data[sheet][col] = _normalize_str_col(data[sheet][col])

    # Derive division list from active members in rating2 (drop nulls/empty)
    active_divisions = (
        data["rating2"]["current_division"]
        .dropna()
        .unique()
        .tolist()
    )

    # Load leave member → division mapping from members.yaml
    leave_div_map = _load_leave_division_map()
    leave_divisions = set(leave_div_map.values())
    leave_count = len(leave_div_map)
    print(f"Found {len(active_divisions)} active division(s): {active_divisions}")
    print(f"Found {leave_count} leave member(s) in members.yaml across "
          f"{len(leave_divisions)} division(s): {sorted(leave_divisions)}")

    # Union of all divisions (active + leave-member divisions)
    all_divisions = list(dict.fromkeys(active_divisions + sorted(leave_divisions)))

    for division in all_divisions:
        out_path = OUTPUT_DIR / f"EngagementData-{division}.xlsx"

        # Addresses of leave members belonging to this division
        leave_addrs = {addr for addr, div in leave_div_map.items() if div == division}

        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            for sheet in SHEETS:
                df = data[sheet]
                # Active members in this division
                active_mask = df["current_division"] == division
                # Leave members whose division (per members.yaml) is this division
                leave_mask = df["mail_address"].isin(leave_addrs) if "mail_address" in df.columns else pd.Series(False, index=df.index)
                filtered = df[active_mask | leave_mask].copy()
                # Sort chronologically so the latest row is always last
                sort_cols = [c for c in ["year", "month"] if c in filtered.columns]
                if sort_cols:
                    filtered = filtered.sort_values(sort_cols, kind="stable").reset_index(drop=True)
                filtered.to_excel(writer, sheet_name=sheet, index=False)

        buf.seek(0)
        with open(out_path, "wb") as f:
            office_file = msoffcrypto.OfficeFile(buf)
            office_file.encrypt(password, f)

        active_rows = int((data["rating2"]["current_division"] == division).sum())
        leave_rows = int(data["rating2"]["mail_address"].isin(leave_addrs).sum()) if "mail_address" in data["rating2"].columns else 0
        print(f"  Written: {out_path.name}  "
              f"(rating2: {active_rows} active + {leave_rows} leave rows)")

    print("Done.")


if __name__ == "__main__":
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else SOURCE_FILE
    split_by_division(source)
