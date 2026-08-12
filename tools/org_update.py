#!/usr/bin/env python3
"""
org_update.py — one-command sync after an org change

After you hand-edit:
  - WorkEngagementSystem/SpreadSheet/MemberSS.xlsx (members / sections)
  - config/privileges_configuration.md (privilege definitions)
  - account.md (login accounts)

... this script regenerates every derived file so the dashboard reflects the
change, and reports what it did / what still needs a human. See
docs/MAINTENANCE_ORG_CHANGES.md for the full picture (why each step exists,
what a new section vs. a new division looks like, etc).

Usage:
    python tools/org_update.py            # apply all steps
    python tools/org_update.py --check    # report only, write nothing (exit 1 if changes are pending)

What this script does NOT do:
    - It does not touch WorkEngagementSystem/ (read-only upstream; source of
      MemberSS.xlsx).
    - It does not run Admin GAS's updateMaster() or tools/monthly_update.py.
      Those require the Admin GAS run to happen first and end in a `git push`
      to GitHub — run them yourself when you're ready (see the printed
      "次の手動作業" section and docs/MAINTENANCE_ORG_CHANGES.md).
    - It does not add a new grade to group_order_config.json's `grade` list
      (that list is a rank order, not a display order — inserting at the
      wrong rank silently mis-sorts people by seniority). It only warns.
"""

import argparse
import base64
import hashlib
import json
import pickle
import sys
from pathlib import Path

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))
import generate_member_yaml as gmy      # noqa: E402
import generate_privileges_yaml as gpy  # noqa: E402

ACCOUNT_MD = PROJECT_ROOT / 'account.md'
AUTH_JSON = PROJECT_ROOT / 'auth_users.json'
AUTH_DAT = PROJECT_ROOT / 'auth_users.dat'
GROUP_ORDER_JSON = PROJECT_ROOT / 'group_order_config.json'

MEMBER_SS_CANDIDATES = [
    PROJECT_ROOT.parent / 'WorkEngagementSystem' / 'SpreadSheet' / 'MemberSS.xlsx',
    PROJECT_ROOT / 'Member.xlsx',
]

# group_order_config.json keys that are pure display order and safe to
# auto-insert into. 'grade' is deliberately excluded — see module docstring.
GROUP_ORDER_KEYS_TO_SYNC = ['department', 'section', 'team', 'project']


# =====================================================================
# Model layer — pure functions, no file I/O. Unit-tested in
# tests/unit/test_org_update.py.
# =====================================================================

def parse_account_md(text: str) -> list:
    """
    Parse account.md's markdown tables into a flat list of account records.

    account.md has one or more '### <division>' headings, each followed by a
    '| position | login name | password | res-name |' table. Header and
    ':---:' separator rows are skipped. Cell values are whitespace-trimmed
    (account.md has at least one login name with trailing spaces in the wild).

    Returns:
        [{'division', 'position', 'login', 'password', 'res_name'}, ...] in
        file order (division order, then row order within each table).
    """
    records = []
    division = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith('### '):
            division = stripped[4:].strip()
            continue
        if not stripped.startswith('|'):
            continue
        cells = [c.strip() for c in stripped.strip('|').split('|')]
        if len(cells) != 4:
            continue
        position, login, password, res_name = cells
        if login in ('', 'login name') or set(login) <= {':', '-'}:
            continue  # header row or ':---:' separator row
        records.append({
            'division': division,
            'position': position,
            'login': login,
            'password': password,
            'res_name': res_name,
        })
    return records


def hash_password(password: str) -> str:
    """SHA-256 hex digest, matching modules/auth.py::hash_password."""
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


def merge_auth_users(existing_users: list, account_records: list) -> tuple:
    """
    Merge account.md records into the existing auth_users.json user list.

    account.md is the source of truth for accounts it lists. A user present
    in auth_users.json but absent from account.md (e.g. 'admin', which is
    intentionally not listed in account.md) is kept unchanged — never removed,
    never touched. New logins are appended in the order they appear in
    account.md. display_name comes from res_name unless res_name is 'n/a', in
    which case an existing display_name is preserved, or — for a brand-new
    user — derived from `position` (matching the existing convention, e.g.
    position "第四設計課メンバー" -> display_name "第四設計課").

    Args:
        existing_users: current auth_users.json['users'] list
        account_records: parse_account_md() output

    Returns:
        (new_users_list, change_log) — change_log is a list of human-readable
        one-line strings (additions / password changes / display_name
        changes), in encounter order. Empty list if nothing changed.
    """
    by_login = {u['name']: dict(u) for u in existing_users}
    order = [u['name'] for u in existing_users]
    changes = []

    for rec in account_records:
        login = rec['login']
        pw_hash = hash_password(rec['password'])
        res_name = rec['res_name']

        if login not in by_login:
            # Existing convention (soft/prod/mechele1-3): when res_name is
            # 'n/a', derive display_name from position with the trailing
            # role suffix 'メンバー' stripped (e.g. "第四設計課メンバー" ->
            # "第四設計課"). department_head/section_manager positions
            # ("...部長"/"...課長") always carry a real res_name instead, so
            # this suffix only ever applies to member-class rows.
            display_name = res_name if res_name and res_name != 'n/a' else rec['position'].removesuffix('メンバー')
            by_login[login] = {
                'name': login,
                'privilege': login,
                'display_name': display_name,
                'password_hash': pw_hash,
            }
            order.append(login)
            changes.append(f"added: {login} (privilege={login}, display_name={display_name})")
            continue

        user = by_login[login]
        if user.get('password_hash') != pw_hash:
            changes.append(f"password changed: {login}")
            user['password_hash'] = pw_hash
        if res_name and res_name != 'n/a' and user.get('display_name') != res_name:
            changes.append(f"display_name changed: {login} ({user.get('display_name')!r} -> {res_name!r})")
            user['display_name'] = res_name

    new_users = [by_login[name] for name in order]
    return new_users, changes


def insert_new_values(existing: list, reference_order: list) -> tuple:
    """
    Insert values present in reference_order but missing from existing,
    preserving existing's order for values it already has.

    Rule: for each new value (processed in reference_order's first-seen
    order), find the nearest preceding value in reference_order that is
    already present in the (possibly already-updated) result list, and
    insert the new value immediately after it. If no such preceding value
    exists, append the new value at the end.

    This exists because group_order_config.json's order is manually curated
    (it does not match MemberSS.xlsx's row order, e.g. system dev sections
    come first there but 機電設計部 comes first in MemberSS) — a full rebuild
    from reference_order would silently discard that curation. Only the
    delta is touched.

    Args:
        existing: current ordered list, e.g. group_order_config.json['section']
        reference_order: order to infer new-value placement from, e.g.
            first-seen order of values in MemberSS.xlsx. Need not be a
            superset or subset of existing.

    Returns:
        (updated_list, insertions) — insertions is
        [(value, after_value_or_None), ...] in insertion order, for reporting.
    """
    result = list(existing)
    insertions = []
    seen_reference = list(dict.fromkeys(v for v in reference_order if v))

    for i, value in enumerate(seen_reference):
        if value in result:
            continue
        after = None
        for prior in reversed(seen_reference[:i]):
            if prior in result:
                after = prior
                break
        if after is None:
            result.append(value)
            insertions.append((value, None))
        else:
            idx = result.index(after) + 1
            result.insert(idx, value)
            insertions.append((value, after))

    return result, insertions


def check_consistency(account_logins, privilege_user_names,
                       member_sections, group_order_sections,
                       member_grades, group_order_grades) -> list:
    """
    Cross-check the four config surfaces that must stay aligned after an org
    change: account.md, privileges_configuration.md (via privileges.yaml),
    MemberSS.xlsx, and group_order_config.json.

    This is the check that would have caught the actual 2026-08 incident:
    a new section_manager/member privilege (me4/mechele4) was added to
    privileges_configuration.md with no matching account.md login, so nobody
    could log in with it.

    Returns a list of human-readable warning strings (empty if consistent).
    Never raises — the caller decides whether warnings block anything.
    """
    warnings = []

    account_set = set(account_logins)
    privilege_set = set(privilege_user_names)

    for login in sorted(account_set - privilege_set):
        warnings.append(
            f"account.md にあるログイン '{login}' に対応する権限が "
            f"privileges_configuration.md にありません"
        )
    for priv in sorted(privilege_set - account_set):
        warnings.append(
            f"権限 '{priv}' に対応するアカウントが account.md にありません"
            f"（このままではログインできません）"
        )

    section_set = {s for s in member_sections if s}
    group_order_section_set = set(group_order_sections)
    for sec in sorted(section_set - group_order_section_set):
        warnings.append(f"課 '{sec}' が group_order_config.json の section に未登録です")

    grade_set = {g for g in member_grades if g}
    group_order_grade_set = set(group_order_grades)
    for grade in sorted(grade_set - group_order_grade_set):
        warnings.append(
            f"職位 '{grade}' が group_order_config.json の grade に未登録です"
            f"（表示順位を手動で決めて追加してください。自動追加はしません）"
        )

    return warnings


# =====================================================================
# Driver layer — file I/O, CLI
# =====================================================================

def resolve_member_ss(explicit: str = None) -> Path:
    if explicit:
        path = Path(explicit)
        if not path.exists():
            print(f"Error: --member-ss {path} not found")
            sys.exit(1)
        return path
    for candidate in MEMBER_SS_CANDIDATES:
        if candidate.exists():
            return candidate
    tried = "\n".join(f"  - {c}" for c in MEMBER_SS_CANDIDATES)
    print(f"Error: MemberSS.xlsx not found. Tried:\n{tried}")
    sys.exit(1)


def step_privileges(write: bool) -> tuple:
    """Regenerate privileges.yaml from privileges_configuration.md.

    Returns (changed: bool, new_content: str) — new_content is what the file
    is/would-be, so callers can use it for the consistency check even under
    --check (where the file on disk is intentionally left stale).
    """
    print("\n[1/4] privileges.yaml")
    if not gpy.MD_FILE.exists():
        print(f"  Error: {gpy.MD_FILE} not found")
        sys.exit(1)
    md_content = gpy.MD_FILE.read_text(encoding='utf-8')
    new_content = gpy.generate_yaml_content(md_content)
    old_content = gpy.YAML_FILE.read_text(encoding='utf-8') if gpy.YAML_FILE.exists() else None
    changed = old_content is None or old_content.strip() != new_content.strip()

    if changed and write:
        gpy.YAML_FILE.parent.mkdir(parents=True, exist_ok=True)
        gpy.YAML_FILE.write_text(new_content, encoding='utf-8')
        print(f"  更新: {gpy.YAML_FILE}")
    elif changed:
        print(f"  [--check] 更新が必要です: {gpy.YAML_FILE}")
    else:
        print("  変更なし")
    return changed, new_content


def step_members(member_ss: Path, write: bool) -> tuple:
    """Regenerate members.yaml from MemberSS.xlsx.

    Returns (changed: bool, members: list[dict]) — members reflects the
    freshly-built content regardless of `write`.
    """
    print("\n[2/4] members.yaml")
    try:
        yaml_text, summary = gmy.build(member_ss)
    except ValueError as e:
        print(f"  Error: {e}")
        sys.exit(1)
    old_text = gmy.YAML_FILE.read_text(encoding='utf-8') if gmy.YAML_FILE.exists() else None
    changed = old_text is None or old_text.strip() != yaml_text.strip()

    if write:
        gmy.YAML_FILE.parent.mkdir(parents=True, exist_ok=True)
        gmy.YAML_FILE.write_text(yaml_text, encoding='utf-8')
        print(f"  更新: {gmy.YAML_FILE}  ({summary['total']} 名 / leave {summary['on_leave']} 名)")
    elif changed:
        print(f"  [--check] 更新が必要です: {gmy.YAML_FILE} ({summary['total']} 名)")
    else:
        print("  変更なし")

    members = yaml.safe_load(yaml_text)['members']
    return changed, members


def step_group_order(members: list, write: bool) -> tuple:
    """Insert new department/section/team/project values.

    Returns (insertions_by_key: dict, updated_config: dict) — updated_config
    reflects the computed result regardless of `write`, for the consistency
    check downstream.
    """
    print("\n[3/4] group_order_config.json")
    config = json.loads(GROUP_ORDER_JSON.read_text(encoding='utf-8'))
    insertions_by_key = {}

    for key in GROUP_ORDER_KEYS_TO_SYNC:
        reference_order = [m.get(key, '') for m in members]
        updated, insertions = insert_new_values(config.get(key, []), reference_order)
        if insertions:
            config[key] = updated
            insertions_by_key[key] = insertions

    if insertions_by_key:
        for key, insertions in insertions_by_key.items():
            for value, after in insertions:
                where = f"'{after}' の直後" if after else "末尾"
                prefix = "追加" if write else "[--check] 追加予定"
                print(f"  {prefix}: {key} に '{value}' を{where}")
        if write:
            GROUP_ORDER_JSON.write_text(
                json.dumps(config, ensure_ascii=False, indent=2) + '\n', encoding='utf-8'
            )
    else:
        print("  変更なし")

    return insertions_by_key, config


def step_auth(write: bool) -> tuple:
    """Regenerate auth_users.json / auth_users.dat from account.md.

    Returns (changes: list[str], account_records: list[dict]).
    """
    print("\n[4/4] auth_users.json / auth_users.dat")
    account_records = parse_account_md(ACCOUNT_MD.read_text(encoding='utf-8'))
    existing = json.loads(AUTH_JSON.read_text(encoding='utf-8')) if AUTH_JSON.exists() else {'users': []}
    new_users, changes = merge_auth_users(existing.get('users', []), account_records)

    if changes:
        for c in changes:
            prefix = "" if write else "[--check] "
            print(f"  {prefix}{c}")
        if write:
            AUTH_JSON.write_text(
                json.dumps({'users': new_users}, ensure_ascii=False, indent=2), encoding='utf-8'
            )
            encoded = base64.b64encode(pickle.dumps({'users': new_users}))
            AUTH_DAT.write_bytes(encoded)
    else:
        print("  変更なし")

    return changes, account_records


def main():
    parser = argparse.ArgumentParser(
        description='Sync WE-Dashboard config files after MemberSS.xlsx / '
                     'privileges_configuration.md / account.md are edited.'
    )
    parser.add_argument('--check', '--dry-run', dest='check', action='store_true',
                         help='変更内容を表示するだけで書き込まない（変更が保留中なら exit 1）')
    parser.add_argument('--member-ss', help='MemberSS.xlsx の明示パス（省略時は自動解決）')
    args = parser.parse_args()
    write = not args.check

    member_ss = resolve_member_ss(args.member_ss)
    print(f"MemberSS.xlsx: {member_ss}")
    if args.check:
        print("(--check モード: ファイルには書き込みません)")

    privileges_changed, privileges_content = step_privileges(write)
    members_changed, members = step_members(member_ss, write)
    group_order_insertions, group_order_config = step_group_order(members, write)
    auth_changes, account_records = step_auth(write)

    print("\n[整合性チェック]")
    privileges_data = yaml.safe_load(privileges_content) or {}
    privilege_names = list(privileges_data.get('user_privileges', {}).keys())
    account_logins = [r['login'] for r in account_records]
    warnings = check_consistency(
        account_logins=account_logins,
        privilege_user_names=privilege_names,
        member_sections=[m.get('section', '') for m in members],
        group_order_sections=group_order_config.get('section', []),
        member_grades=[m.get('grade', '') for m in members],
        group_order_grades=group_order_config.get('grade', []),
    )
    if warnings:
        for w in warnings:
            print(f"  ⚠ {w}")
    else:
        print("  問題なし")

    print("\n[group_order_config.json の確認]")
    if group_order_insertions:
        print("  表示順を自動更新しました。挿入位置は MemberSS.xlsx の行順からの推定です。")
        print("  グラフ・テーブルの並び順に反映されるため、意図どおりか目視で確認してください。")
        for key, insertions in group_order_insertions.items():
            print(f"    {key}: {[v for v, _ in insertions]}")
    else:
        print("  更新なし（確認不要）")

    print("\n[次の手動作業]")
    print("  1. 上記 group_order_config.json の並び順を確認する")
    print("  2. streamlit run app.py でローカル起動し、新しい権限のログインを確認する")
    print("  3. git diff で生成物を確認し、意図どおりならコミットする")
    print("  4. Admin GAS の updateMaster() を実行 → python tools/monthly_update.py を実行する")
    print("     （実行するまで Engagement Master 側のデータに新しい課・メンバーは反映されない）")

    pending = privileges_changed or members_changed or bool(group_order_insertions) or bool(auth_changes)
    if args.check and pending:
        sys.exit(1)
    sys.exit(0)


if __name__ == '__main__':
    main()
