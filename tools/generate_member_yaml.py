#!/usr/bin/env python3
"""
Generate config/members.yaml from MemberSS.xlsx

Reads the member master spreadsheet exported from Google Sheets (MemberSS) and
writes a YAML file embedded in the project. Every member is written with a `leave`
status ('' / 'absence' / 'leave'); the dashboard filters on it at display time.
members.yaml is CUMULATIVE: sheet additions/changes are applied, but people already in
members.yaml are never deleted just because they left the 'members' sheet (operators remove
leavers from it). That retention — and the carry-over of leavers from 'members_history' —
applies only to divisions that get an EngagementData-<division>.xlsx (see
split_by_division.list_active_divisions), so abolished divisions do not pile up.
This YAML is the runtime data source for the 未記入者 feature and for the
転属・退職メンバー toggle.

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

import split_by_division as sbd  # single definition of "a division that gets a data file"

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


def _read_history(source_path: Path) -> pd.DataFrame:
    """
    'members_history' rows normalized to OUTPUT_COLUMNS ('Y' -> 'leave'; address and
    division stripped). Empty if the sheet is absent (legacy Member.xlsx files).
    """
    try:
        hist = pd.read_excel(source_path, sheet_name=HISTORY_SHEET_NAME, engine='openpyxl')
    except ValueError:  # sheet not found
        return pd.DataFrame(columns=OUTPUT_COLUMNS)

    missing = [c for c in OUTPUT_COLUMNS if c not in hist.columns]
    if missing:
        raise ValueError(
            f"missing columns in '{HISTORY_SHEET_NAME}' sheet of {source_path}: {missing}")

    hist = hist[OUTPUT_COLUMNS].fillna('').copy()
    hist['leave'] = hist['leave'].replace({'Y': 'leave'})
    for col in ('mail_address', 'division'):
        hist[col] = hist[col].astype(str).str.strip()
    return hist


def _history_leavers(hist: pd.DataFrame, exclude_addresses: set, target_divisions: set) -> pd.DataFrame:
    """
    Leavers in 'members_history' that members.yaml should carry. A row qualifies only
    when ALL of these hold:
      - leave is 'leave' (history's 'Y' was normalized; the dashboard checks == 'leave');
      - the address is not already covered (in the sheet or retained from the old yaml);
      - its division is a target division (one that gets an EngagementData file).
        Abolished divisions are skipped on purpose (split_by_division would otherwise
        have a division with nothing to write); rows with no division are skipped too —
        their division cannot be determined;
      - first occurrence per address only.
    """
    keep = (
        (hist['leave'] == 'leave')
        & (hist['mail_address'] != '')
        & ~hist['mail_address'].isin(exclude_addresses)
        & hist['division'].isin(target_divisions)
    )
    return hist[keep].drop_duplicates(subset='mail_address', keep='first').reset_index(drop=True)


def load_existing(path: Path = YAML_FILE):
    """The current members.yaml entries (list of dicts), or None if the file does not exist."""
    if not Path(path).exists():
        return None
    data = yaml.safe_load(Path(path).read_text(encoding='utf-8')) or {}
    return data.get('members') or []


def resolve_target_divisions(master_path: Path = sbd.SOURCE_FILE):
    """
    Divisions that get an EngagementData-<division>.xlsx, per split_by_division
    (rating2 rows inside its MONTHS_WINDOW). None when Engagement Master.xlsx is absent or
    unreadable — build() then falls back to the divisions of the sheet's current members.
    """
    master_path = Path(master_path)
    if not master_path.exists():
        print(f"  Note: {master_path.name} not found — target divisions are taken from the sheet's current members only.")
        return None
    try:
        return set(sbd.list_active_divisions(master_path))
    except Exception as e:  # noqa: BLE001 - never block member generation on the data file
        print(f"  Warning: could not read {master_path.name} ({e}) — "
              f"target divisions are taken from the sheet's current members only.")
        return None


def build(source_path: Path, existing=None, extra_target_divisions=None) -> tuple[str, dict]:
    """
    Build the members.yaml content in memory, without writing anything.

    Rows, in this order:
      1. every row of the 'members' sheet (any division) — the sheet's values win, so
         changes and re-hires are applied;
      2. `existing` entries (the current members.yaml) that are no longer in the sheet,
         if their division is a target division — retained, i.e. never deleted. If
         'members_history' marks one as a leaver it is set to 'leave'; an entry that is
         still not a leaver is kept as is and listed in `vanished_active` so the operator
         can fix the source (nothing is guessed);
      3. 'members_history' leavers not covered above, target divisions only.
    Existing entries of non-target divisions that left the sheet are dropped (`dropped`).

    Target divisions = divisions of the sheet's current (not-left) members, plus
    `extra_target_divisions` (the divisions split_by_division writes files for).

    Returns:
        (yaml_text, summary) — summary is {total, on_leave, active, from_history,
        retained, dropped, vanished_active (list of addresses), by_division}.
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

    sheet_addresses = set(result['mail_address'].astype(str).str.strip())
    target_divisions = (
        set(result.loc[result['leave'] != 'leave', 'division'].astype(str).str.strip())
        | {str(d).strip() for d in (extra_target_divisions or ())}
    )
    target_divisions.discard('')

    history = _read_history(source_path)
    history_leave_addresses = set(history.loc[history['leave'] == 'leave', 'mail_address'])

    # 2. retain existing entries that left the sheet (target divisions only)
    retained_rows, vanished_active, dropped = [], [], 0
    covered = set(sheet_addresses)
    for entry in existing or []:
        address = str(entry.get('mail_address') or '').strip()
        if not address or address in covered:
            continue  # blank, in the sheet (the sheet wins), or a duplicate of one handled
        covered.add(address)
        row = {c: ('' if entry.get(c) is None else entry.get(c)) for c in OUTPUT_COLUMNS}
        if row['leave'] == 'Y':
            row['leave'] = 'leave'
        if str(row['division']).strip() not in target_divisions:
            dropped += 1
            continue
        if row['leave'] != 'leave' and address in history_leave_addresses:
            row['leave'] = 'leave'
        if row['leave'] != 'leave':
            vanished_active.append(address)
        retained_rows.append(row)
    retained = pd.DataFrame(retained_rows, columns=OUTPUT_COLUMNS)

    # 3. leavers only 'members_history' still knows about
    additions = _history_leavers(history, covered, target_divisions)

    parts = [result] + [p for p in (retained, additions) if len(p)]
    result = pd.concat(parts, ignore_index=True) if len(parts) > 1 else result

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
        'from_history': len(additions),
        'retained': len(retained),
        'dropped': dropped,
        'vanished_active': vanished_active,
        'by_division': by_division,
    }
    return yaml_text, summary


def summary_notes(summary: dict) -> list[str]:
    """Human-readable lines about how the cumulative rules were applied (shared by CLIs)."""
    notes = [f"既存の members.yaml から残した人: {summary['retained']} 名 / "
             f"members_history から補った人: {summary['from_history']} 名"]
    if summary['dropped']:
        notes.append(f"EngagementData を作成していない部門のため残さなかった人: {summary['dropped']} 名")
    if summary['vanished_active']:
        notes.append(
            f"⚠ MemberSS の members シートに無いのに在籍扱い（leave でない）のまま残っている人: "
            f"{len(summary['vanished_active'])} 名 — 退職・転属なら MemberSS 側で leave を設定してください "
            f"（未記入者リストに残り続けます）: {', '.join(summary['vanished_active'])}")
    return notes


def generate(source_path: Path) -> dict:
    """
    Build members.yaml from source_path (cumulatively, see build) and write config/members.yaml.

    Returns the summary dict from build().
    """
    yaml_text, summary = build(
        source_path, existing=load_existing(), extra_target_divisions=resolve_target_divisions())
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
    print(f"  On leave       : {summary['on_leave']}")
    print(f"  Active+absence : {summary['active']}")
    for note in summary_notes(summary):
        print(f"  {note}")
    print()
    for division, count in summary['by_division'].items():
        print(f"  {division}: {count}")


if __name__ == '__main__':
    main()
