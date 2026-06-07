"""
Sync files from WE-Dashboard (Mac) to WE-Dashboard-Windows.

Copies every file that exists in both projects, with an exclusion list
for files that intentionally differ between the two.

Usage:
    python tools/sync_from_mac.py
    python tools/sync_from_mac.py --dry-run   # Preview without copying
"""

import argparse
import shutil
from fnmatch import fnmatch
from pathlib import Path

# Both project dirs are siblings under the WorkEngagement parent, so anchor by
# name rather than by this script's own location. That way an identical copy
# placed in WE-Dashboard/tools syncs in the same direction (Mac -> Windows).
_PARENT = Path(__file__).resolve().parents[2]
MAC_DIR = _PARENT / 'WE-Dashboard'
WIN_DIR = _PARENT / 'WE-Dashboard-Windows'

# Exact relative paths that must NOT be synced
EXCLUDE_FILES = {
    '.streamlit/secrets.toml',   # Different secrets per deployment
}

# Filename patterns that must NOT be synced
EXCLUDE_PATTERNS = [
    '*.xlsx',       # Data files
    '*.pyc',
    '.DS_Store',
]

# Directory names whose contents must NOT be synced
EXCLUDE_DIRS = {
    '__pycache__',
    '.git',
}

# Data files copied explicitly despite the *.xlsx exclusion above.
# Maps a source path (relative to MAC_DIR) to a destination path (relative to WIN_DIR).
INCLUDE_DATA_FILES = {
    'EngagementData-設計部門.xlsx': 'WE-Dashboard/EngagementData-設計部門.xlsx',
}


def should_exclude(rel: Path) -> bool:
    if any(part in EXCLUDE_DIRS for part in rel.parts):
        return True
    if str(rel) in EXCLUDE_FILES:
        return True
    if any(fnmatch(rel.name, pat) for pat in EXCLUDE_PATTERNS):
        return True
    return False


def main():
    parser = argparse.ArgumentParser(description='Sync WE-Dashboard → WE-Dashboard-Windows')
    parser.add_argument('--dry-run', action='store_true', help='Preview without copying')
    args = parser.parse_args()

    copied = []

    for src in sorted(MAC_DIR.rglob('*')):
        if not src.is_file():
            continue

        rel = src.relative_to(MAC_DIR)

        if should_exclude(rel):
            continue

        dst = WIN_DIR / rel
        if not dst.exists():
            continue  # Only sync files that already exist in Windows

        if src.stat().st_mtime <= dst.stat().st_mtime:
            continue  # Windows copy is up to date

        if not args.dry_run:
            shutil.copy2(src, dst)
        copied.append(str(rel))

    # Explicit data-file copies (bypass the *.xlsx exclusion and the
    # "must already exist in Windows" rule; destination dir is created).
    for src_rel, dst_rel in INCLUDE_DATA_FILES.items():
        src = MAC_DIR / src_rel
        if not src.is_file():
            print(f'Warning: source not found, skipping: {src_rel}')
            continue

        dst = WIN_DIR / dst_rel
        if dst.exists() and src.stat().st_mtime <= dst.stat().st_mtime:
            continue  # Windows copy is up to date

        if not args.dry_run:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
        copied.append(f'{src_rel} -> {dst_rel}')

    prefix = 'Would copy' if args.dry_run else 'Copied'
    for f in copied:
        print(f'{prefix}: {f}')

    if args.dry_run:
        print(f'\nDry run — {len(copied)} file(s) would be copied, nothing changed.')
    else:
        print(f'\nDone. {len(copied)} file(s) copied.')


if __name__ == '__main__':
    main()
