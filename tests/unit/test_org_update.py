"""
Unit tests for tools/org_update.py's model layer (pure functions only —
no xlsx/yaml/json file I/O). Synthetic data throughout; no dependency on
MemberSS.xlsx or any other real project file.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))

import org_update as ou  # noqa: E402


# ---------------------------------------------------------------------
# parse_account_md
# ---------------------------------------------------------------------

ACCOUNT_MD_SAMPLE = """\
## WE-Dashboard Accounts

### 設計部門
| position | login name | password | res-name |
| :---: | :---: | :---: | :---: |
| システム開発部長 | sd | hope4827 | 田尻部長 |
| 第一設計課メンバー | mechele1  | value9360 | n/a |

### 品質保証部門
| position | login name | password | res-name |
| :---: | :---: | :---: | :---: |
| 品質保証課長 | qm | wisdom8194 | 細野課長 |
"""


def test_parse_account_md_skips_header_and_separator_rows():
    records = ou.parse_account_md(ACCOUNT_MD_SAMPLE)
    logins = [r['login'] for r in records]
    assert logins == ['sd', 'mechele1', 'qm']


def test_parse_account_md_trims_whitespace_in_login():
    """account.md has at least one real login with trailing spaces (mechele1)."""
    records = ou.parse_account_md(ACCOUNT_MD_SAMPLE)
    mechele1 = next(r for r in records if r['login'] == 'mechele1')
    assert mechele1['login'] == 'mechele1'  # trailing spaces stripped
    assert mechele1['res_name'] == 'n/a'


def test_parse_account_md_tracks_division_sections():
    records = ou.parse_account_md(ACCOUNT_MD_SAMPLE)
    assert next(r for r in records if r['login'] == 'sd')['division'] == '設計部門'
    assert next(r for r in records if r['login'] == 'qm')['division'] == '品質保証部門'


def test_parse_account_md_empty_input():
    assert ou.parse_account_md('') == []


# ---------------------------------------------------------------------
# merge_auth_users
# ---------------------------------------------------------------------

def test_merge_auth_users_adds_new_login():
    existing = []
    records = [{'division': 'X', 'position': '第四設計課メンバー', 'login': 'mechele4',
                'password': 'courage8032', 'res_name': 'n/a'}]
    new_users, changes = ou.merge_auth_users(existing, records)
    assert len(new_users) == 1
    assert new_users[0]['name'] == 'mechele4'
    assert new_users[0]['privilege'] == 'mechele4'
    # res_name 'n/a' -> derive from position, stripping trailing 'メンバー'
    assert new_users[0]['display_name'] == '第四設計課'
    assert new_users[0]['password_hash'] == ou.hash_password('courage8032')
    assert len(changes) == 1 and 'added' in changes[0]


def test_merge_auth_users_derives_display_name_with_real_res_name():
    existing = []
    records = [{'division': 'X', 'position': '第四設計課長', 'login': 'me4',
                'password': 'gratitude4859', 'res_name': '中津川課長'}]
    new_users, _ = ou.merge_auth_users(existing, records)
    assert new_users[0]['display_name'] == '中津川課長'


def test_merge_auth_users_preserves_user_not_in_account_md():
    """A user like 'admin' that account.md never lists must survive untouched."""
    existing = [{'name': 'admin', 'privilege': 'admin', 'display_name': '管理者',
                 'password_hash': 'deadbeef'}]
    new_users, changes = ou.merge_auth_users(existing, [])
    assert new_users == existing
    assert changes == []


def test_merge_auth_users_detects_password_change():
    existing = [{'name': 'qm', 'privilege': 'qm', 'display_name': '細野課長',
                 'password_hash': ou.hash_password('old_password')}]
    records = [{'division': 'X', 'position': '品質保証課長', 'login': 'qm',
                'password': 'new_password', 'res_name': '細野課長'}]
    new_users, changes = ou.merge_auth_users(existing, records)
    assert new_users[0]['password_hash'] == ou.hash_password('new_password')
    assert any('password changed' in c for c in changes)


def test_merge_auth_users_no_change_when_identical():
    existing = [{'name': 'qm', 'privilege': 'qm', 'display_name': '細野課長',
                 'password_hash': ou.hash_password('wisdom8194')}]
    records = [{'division': 'X', 'position': '品質保証課長', 'login': 'qm',
                'password': 'wisdom8194', 'res_name': '細野課長'}]
    new_users, changes = ou.merge_auth_users(existing, records)
    assert new_users == existing
    assert changes == []


def test_merge_auth_users_preserves_existing_order_and_appends_new():
    existing = [{'name': 'a', 'privilege': 'a', 'display_name': 'A', 'password_hash': 'x'},
                {'name': 'b', 'privilege': 'b', 'display_name': 'B', 'password_hash': 'y'}]
    records = [
        {'division': 'X', 'position': 'B長', 'login': 'b', 'password': 'pw', 'res_name': 'B'},
        {'division': 'X', 'position': 'C長', 'login': 'c', 'password': 'pw2', 'res_name': 'C'},
    ]
    new_users, _ = ou.merge_auth_users(existing, records)
    assert [u['name'] for u in new_users] == ['a', 'b', 'c']


# ---------------------------------------------------------------------
# insert_new_values
# ---------------------------------------------------------------------

def test_insert_new_values_inserts_after_nearest_preceding_reference_value():
    existing = ['A', 'B', 'C']
    reference = ['A', 'B', 'NEW', 'C']  # NEW comes right after B in the reference
    updated, insertions = ou.insert_new_values(existing, reference)
    assert updated == ['A', 'B', 'NEW', 'C']
    assert insertions == [('NEW', 'B')]


def test_insert_new_values_appends_when_no_preceding_match():
    existing = ['A', 'B']
    reference = ['NEW', 'A', 'B']  # nothing precedes NEW in the reference that's in `existing`
    updated, insertions = ou.insert_new_values(existing, reference)
    assert updated == ['A', 'B', 'NEW']
    assert insertions == [('NEW', None)]


def test_insert_new_values_never_removes_existing_values():
    """機電設計部付 must survive even though it has fewer members after the move.
    第四設計課 is inserted right after its nearest reference-preceding value
    (第三設計課), landing before 機電設計部付 — not appended past it."""
    existing = ['第三設計課', '機電設計部付']
    reference = ['第三設計課', '第四設計課']  # 機電設計部付 no longer appears in reference at all
    updated, insertions = ou.insert_new_values(existing, reference)
    assert '機電設計部付' in updated
    assert updated == ['第三設計課', '第四設計課', '機電設計部付']
    assert insertions == [('第四設計課', '第三設計課')]


def test_insert_new_values_no_op_when_nothing_new():
    existing = ['A', 'B']
    updated, insertions = ou.insert_new_values(existing, ['B', 'A'])
    assert updated == existing
    assert insertions == []


def test_insert_new_values_handles_multiple_new_values_in_reference_order():
    existing = ['A', 'D']
    reference = ['A', 'B', 'C', 'D']
    updated, insertions = ou.insert_new_values(existing, reference)
    assert updated == ['A', 'B', 'C', 'D']
    assert insertions == [('B', 'A'), ('C', 'B')]


def test_insert_new_values_ignores_falsy_reference_entries():
    existing = ['A']
    updated, insertions = ou.insert_new_values(existing, ['A', '', None, 'B'])
    assert updated == ['A', 'B']
    assert insertions == [('B', 'A')]


def test_insert_new_values_real_case_yondai_sekkeika():
    """The actual 2026-08 case: 第四設計課 must land right after 第三設計課,
    not at the end (which is what a naive alphabetical/append fallback gives)."""
    existing = ['ソフトウェア開発課', '製品技術課', '第一設計課', '第二設計課',
                '第三設計課', '機電設計部付']
    reference = ['機電設計部付', '第一設計課', '第二設計課', '第三設計課',
                 '第四設計課', 'ソフトウェア開発課', '製品技術課']
    updated, insertions = ou.insert_new_values(existing, reference)
    assert updated.index('第四設計課') == updated.index('第三設計課') + 1
    assert insertions == [('第四設計課', '第三設計課')]


# ---------------------------------------------------------------------
# check_consistency
# ---------------------------------------------------------------------

def test_check_consistency_detects_privilege_without_account():
    """This is the actual 2026-08 incident this check exists to catch:
    me4/mechele4 were added to privileges_configuration.md with no
    matching account.md login, so nobody could log in."""
    warnings = ou.check_consistency(
        account_logins=['me3'],
        privilege_user_names=['me3', 'me4'],
        member_sections=['第三設計課'],
        group_order_sections=['第三設計課'],
        member_grades=['主管'],
        group_order_grades=['主管'],
    )
    assert any('me4' in w and 'account.md' in w for w in warnings)


def test_check_consistency_detects_account_without_privilege():
    warnings = ou.check_consistency(
        account_logins=['me4'],
        privilege_user_names=[],
        member_sections=[],
        group_order_sections=[],
        member_grades=[],
        group_order_grades=[],
    )
    assert any('me4' in w and 'privileges_configuration.md' in w for w in warnings)


def test_check_consistency_detects_missing_section_in_group_order():
    warnings = ou.check_consistency(
        account_logins=[], privilege_user_names=[],
        member_sections=['第四設計課'], group_order_sections=[],
        member_grades=[], group_order_grades=[],
    )
    assert any('第四設計課' in w and 'section' in w for w in warnings)


def test_check_consistency_detects_missing_grade_and_does_not_auto_fix():
    warnings = ou.check_consistency(
        account_logins=[], privilege_user_names=[],
        member_sections=[], group_order_sections=[],
        member_grades=['新職位'], group_order_grades=['主管'],
    )
    assert any('新職位' in w and '自動追加はしません' in w for w in warnings)


def test_check_consistency_clean_state_has_no_warnings():
    warnings = ou.check_consistency(
        account_logins=['me4'],
        privilege_user_names=['me4'],
        member_sections=['第四設計課'],
        group_order_sections=['第四設計課'],
        member_grades=['主管'],
        group_order_grades=['主管'],
    )
    assert warnings == []


def test_check_consistency_ignores_empty_section_and_grade_values():
    """Members with no section (e.g. department heads) or blank grade must
    not trigger spurious 'missing' warnings."""
    warnings = ou.check_consistency(
        account_logins=[], privilege_user_names=[],
        member_sections=['', '第三設計課'], group_order_sections=['第三設計課'],
        member_grades=['', '主管'], group_order_grades=['主管'],
    )
    assert warnings == []
