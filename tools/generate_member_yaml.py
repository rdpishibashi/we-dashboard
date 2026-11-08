#!/usr/bin/env python3
"""
Generate config/members.yaml from MemberSS.xlsx

Reads the member master spreadsheet exported from Google Sheets (MemberSS) and
writes a YAML file embedded in the project. Every member is written with a `leave`
status ('' / 'absence' / 'leave'); the dashboard filters on it at display time.
Leavers that operators have removed from the 'members' sheet are carried over from
'members_history' (see _history_leavers). This YAML is the runtime data source for
the 未記入者 feature and for the 転属・退職メンバー toggle.

Usage:
    python tools/generate_member_yaml.py
    python tools/generate_member_yaml.py --source /path/to/MemberSS.xlsx

Run this tool whenever MemberSS.xlsx is updated (typically with each org change).
Then commit the updated config/members.yaml.

Source file resolution (highest priority first):
    1. --source argument, if given
    2. ../WorkEngagementSystem/SpreadSheet/MemberSS.xlsx (sibling project's
       source-of-truth snapshot — the normal case; no copy step required)
    3. ./Member.xlsx (legacy fallback, kept for environments where the
       WorkEngagementSystem sibling folder is not checked out)

MemberSS.xlsx always contains a 'members' sheet plus other sheets
(members_history, and per-fiscal-year snapshots 'members in FYxx'). The
sheet name is read explicitly — do NOT rely on "first sheet in the
workbook", since older FY snapshot sheets use a different column schema
(department is 'section', section is 'tech_group') and a silent schema
mix-up would put department names into the section column.
"""

import argparse
import sys
import yaml
import pandas as pd
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
YAML_FILE = PROJECT_ROOT / 'config' / 'members.yaml'
SHEET_NAME = 'members'
HISTORY_SHEET_NAME = 'members_history'

# Candidate source paths, in priority order (excluding an explicit --source).
DEFAULT_SOURCE_CANDIDATES = [
    PROJECT_ROOT.parent / 'WorkEngagementSystem' / 'SpreadSheet' / 'MemberSS.xlsx',
    PROJECT_ROOT / 'Member.xlsx',
]

OUTPUT_COLUMNS = ['mail_address', 'member_name', 'division', 'department', 'section', 'team', 'project', 'grade', 'leave']


def resolve_source(explicit: str = None) -> Path:
    """
    Resolve the MemberSS source path. Raises FileNotFoundError if none exist.
    """
    if explicit:
        path = Path(explicit)
        if not path.exists():
            raise FileNotFoundError(f"--source {path} not found")
        return path

    for candidate in DEFAULT_SOURCE_CANDIDATES:
        if candidate.exists():
            return candidate

    tried = "\n".join(f"  - {c}" for c in DEFAULT_SOURCE_CANDIDATES)
    raise FileNotFoundError(
        f"MemberSS.xlsx not found. Tried:\n{tried}\n"
        f"Pass --source to specify an explicit path."
    )


def _history_leavers(source_path: Path, members: pd.DataFrame) -> pd.DataFrame:
    """
    Retirees/transferees who are in 'members_history' but no longer in 'members'.

    Operators delete a leaver from 'members' once 'members_history' holds the row
    (Admin MAINTENANCE_GUIDE). members.yaml is built from 'members' only, so those
    people would vanish from it — and the dashboard's 転属・退職メンバー toggle, which
    keys off `leave: leave` in members.yaml, would lose them (or disappear entirely).

    A history row is carried over only when ALL of these hold:
      - leave is 'Y' or 'leave' (history uses 'Y'; the dashboard checks == 'leave', so
        the value is written as 'leave');
      - the address is not in 'members' (members' own row wins — no duplicates);
      - its division is one that currently has members who have NOT left. Abolished
        divisions are skipped on purpose: split_by_division.py would otherwise create
        an empty EngagementData-<division>.xlsx for them. Rows with no division are
        skipped too — their division cannot be determined;
      - first occurrence per address only.

    Returns a DataFrame with OUTPUT_COLUMNS (empty if the sheet is absent, as in
    legacy Member.xlsx files).
    """
    try:
        hist = pd.read_excel(source_path, sheet_name=HISTORY_SHEET_NAME, engine='openpyxl')
    except ValueError:  # sheet not found
        return members.iloc[0:0].copy()

    missing = [c for c in OUTPUT_COLUMNS if c not in hist.columns]
    if missing:
        raise ValueError(
            f"missing columns in '{HISTORY_SHEET_NAME}' sheet of {source_path}: {missing}")

    hist = hist[OUTPUT_COLUMNS].fillna('').copy()
    hist['leave'] = hist['leave'].replace({'Y': 'leave'})
    for col in ('mail_address', 'division'):
        hist[col] = hist[col].astype(str).str.strip()

    current_divisions = set(members.loc[members['leave'] != 'leave', 'division'].astype(str).str.strip())
    current_divisions.discard('')

    keep = (
        (hist['leave'] == 'leave')
        & (hist['mail_address'] != '')
        & ~hist['mail_address'].isin(set(members['mail_address'].astype(str).str.strip()))
        & hist['division'].isin(current_divisions)
    )
    return hist[keep].drop_duplicates(subset='mail_address', keep='first').reset_index(drop=True)


def build(source_path: Path) -> tuple[str, dict]:
    """
    Read source_path's 'members' sheet (plus leavers from 'members_history', see
    _history_leavers) and build the members.yaml content in memory, without
    writing anything.

    Returns:
        (yaml_text, summary) — summary is
        {total, on_leave, active, from_history, by_division}; `from_history` is how
        many of `total` came from 'members_history'.
    """
    df = pd.read_excel(source_path, sheet_name=SHEET_NAME, engine='openpyxl')

    missing = [c for c in OUTPUT_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"missing columns in '{SHEET_NAME}' sheet of {source_path}: {missing}")

    # Include ALL members with their leave status.
    # leave values: NaN/''/active, 'absence' = long-term leave (still employed),
    #               'leave' = retired/transferred
    # Filtering is done at display time in the dashboard, not here.
    result = df[OUTPUT_COLUMNS].fillna('').copy()
    result['leave'] = result['leave'].replace({'Y': 'leave'})

    # Retirees whom operators have removed from the 'members' sheet live on only in
    # 'members_history'. Without them the dashboard has no leave members at all.
    history = _history_leavers(source_path, result)
    from_history = len(history)
    if from_history:
        result = pd.concat([result, history], ignore_index=True)

    members = result.to_dict(orient='records')
    leave_count = int((result['leave'] == 'leave').sum())

    header = (
        "# Member list for WE-Dashboard\n"
        "# Auto-generated by tools/generate_member_yaml.py\n"
        "# Do not edit this file directly.\n"
        f"# Source: {source_path} (sheet: {SHEET_NAME})\n\n"
    )
    body = yaml.dump({'members': members}, allow_unicode=True,
                      default_flow_style=False, sort_keys=False)
    yaml_text = header + body

    active_result = result[~result['leave'].isin(['leave', 'Y'])]
    by_division = active_result.groupby('division').size().to_dict()

    summary = {
        'total': len(members),
        'on_leave': leave_count,
        'active': len(members) - leave_count,
        'from_history': from_history,
        'by_division': by_division,
    }
    return yaml_text, summary


def generate(source_path: Path) -> dict:
    """
    Read source_path's 'members' sheet and write config/members.yaml.

    Returns a summary dict: {total, on_leave, active, by_division}.
    """
    yaml_text, summary = build(source_path)
    YAML_FILE.parent.mkdir(parents=True, exist_ok=True)
    YAML_FILE.write_text(yaml_text, encoding='utf-8')
    return summary


def main():
    parser = argparse.ArgumentParser(description='Generate config/members.yaml from MemberSS.xlsx')
    parser.add_argument('--source', help='Explicit path to MemberSS.xlsx (overrides default resolution)')
    args = parser.parse_args()

    try:
        source_path = resolve_source(args.source)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)

    print(f"Source: {source_path}")

    try:
        summary = generate(source_path)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)

    print(f"Generated {YAML_FILE}")
    print(f"  Total members  : {summary['total']}")
    print(f"  On leave       : {summary['on_leave']}  (from members_history: {summary['from_history']})")
    print(f"  Active+absence : {summary['active']}")
    print()
    for division, count in summary['by_division'].items():
        print(f"  {division}: {count}")


if __name__ == '__main__':
    main()
