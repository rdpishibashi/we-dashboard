"""
Split EngagementMasterSS.xlsx into per-division Excel files.

Each output file contains only the 'rating2' and 'comment' sheets,
filtered to rows where current_division matches the target division.
Rows with null current_division are skipped.
Each output file is encrypted with a password.

Output: EngagementMasterSS-{current_division}.xlsx
"""

import io
import sys
from pathlib import Path

import msoffcrypto
import pandas as pd

PASSWORD = "hachioji"

SOURCE_FILE = Path(__file__).parent.parent / "Engagement Master.xlsx"
OUTPUT_DIR = Path(__file__).parent.parent
SHEETS = ["rating2", "comment"]


def split_by_division(source: Path = SOURCE_FILE) -> None:
    # Load both sheets up front
    data: dict[str, pd.DataFrame] = {
        sheet: pd.read_excel(source, sheet_name=sheet) for sheet in SHEETS
    }

    # Derive division list from rating2 (drop nulls)
    divisions = (
        data["rating2"]["current_division"].dropna().unique().tolist()
    )
    print(f"Found {len(divisions)} division(s): {divisions}")

    for division in divisions:
        out_path = OUTPUT_DIR / f"EngagementData-{division}.xlsx"

        # Write to an in-memory buffer first, then encrypt to disk
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            for sheet in SHEETS:
                df = data[sheet]
                filtered = df[df["current_division"] == division].copy()
                filtered.to_excel(writer, sheet_name=sheet, index=False)

        buf.seek(0)
        with open(out_path, "wb") as f:
            office_file = msoffcrypto.OfficeFile(buf)
            office_file.encrypt(PASSWORD, f)

        print(f"  Written: {out_path.name}  "
              f"(rating2: {len(data['rating2'][data['rating2']['current_division'] == division])} rows, "
              f"comment: {len(data['comment'][data['comment']['current_division'] == division])} rows)")

    print("Done.")


if __name__ == "__main__":
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else SOURCE_FILE
    split_by_division(source)
