"""
tools/generate_member_yaml.py の build() が、MemberSS の `members` シートから
外された退職者を `members_history` から補うことを守る。合成データのみ
（実際の MemberSS.xlsx には依存しない）。

背景（2026-11）: Admin の運用で退職者を `members` から削除すると、`members.yaml`
から退職者が 1 人も居なくなる。アプリは `members.yaml` の `leave: leave` の人だけを
「転属・退職メンバー」とみなすため、①「転属・退職メンバーを含む」チェックボックスが
消え（`leave_addresses` が空）、②退職者の過去の行が常に通常メンバーとして表示される。
"""

import sys
from pathlib import Path

import pandas as pd
import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))

import generate_member_yaml as gmy  # noqa: E402

COLUMNS = ['mail_address', 'member_name', 'division', 'department',
           'section', 'team', 'project', 'grade', 'leave']


def _row(addr, division, leave='', department='機電設計部', section='第一設計課'):
    return {'mail_address': addr, 'member_name': addr.split('@')[0], 'division': division,
            'department': department, 'section': section, 'team': '', 'project': '',
            'grade': '一般職', 'leave': leave}


def _write(tmp_path, members, history=None, history_columns=None):
    """MemberSS.xlsx 相当を書く。history=None なら members_history シート自体を作らない。"""
    path = tmp_path / 'MemberSS.xlsx'
    with pd.ExcelWriter(path, engine='openpyxl') as writer:
        pd.DataFrame(members, columns=COLUMNS).to_excel(writer, sheet_name='members', index=False)
        if history is not None:
            pd.DataFrame(history, columns=history_columns or COLUMNS).to_excel(
                writer, sheet_name='members_history', index=False)
    return path


def _built(path):
    text, summary = gmy.build(path)
    return yaml.safe_load(text)['members'], summary


def _by_addr(members):
    return {m['mail_address']: m for m in members}


BASE_MEMBERS = [
    _row('a@x', '設計部門'),
    _row('q@x', '品質保証部門', department='品質保証部', section=''),
]


def test_history_leaver_of_current_division_is_appended_as_leave(tmp_path):
    """守る対象: members から外れた退職者が members.yaml に `leave: leave` で残る。

    修正前はここで退職者が 0 人になり、アプリの退職者トグルが消えていた。
    `members_history` の退職は `Y` だが、アプリは `== 'leave'` だけを退職扱いにする。
    """
    path = _write(tmp_path, BASE_MEMBERS, history=[_row('old@x', '設計部門', leave='Y')])
    members, _ = _built(path)
    got = _by_addr(members)
    assert got['old@x']['leave'] == 'leave'
    leave_addresses = {m['mail_address'] for m in members if m['leave'] == 'leave'}
    assert leave_addresses == {'old@x'}


def test_leaver_of_quality_assurance_division_is_also_appended(tmp_path):
    path = _write(tmp_path, BASE_MEMBERS, history=[_row('oldq@x', '品質保証部門', leave='Y')])
    got = _by_addr(_built(path)[0])
    assert got['oldq@x']['leave'] == 'leave'


def test_leaver_of_division_without_current_members_is_not_appended(tmp_path):
    """廃止された部門（現在 members に在籍者が居ない部門）の退職者は補わない。

    補うと split_by_division.py が、その部門の空の EngagementData-<部門>.xlsx を作る。
    """
    path = _write(tmp_path, BASE_MEMBERS, history=[_row('dev@x', '開発部門', leave='Y')])
    assert 'dev@x' not in _by_addr(_built(path)[0])


@pytest.mark.parametrize('blank', ['', None])
def test_leaver_without_division_is_not_appended(tmp_path, blank):
    """部門が空欄の退職者は所属を断定できないので補わない。"""
    path = _write(tmp_path, BASE_MEMBERS, history=[_row('nodiv@x', blank, leave='Y')])
    assert 'nodiv@x' not in _by_addr(_built(path)[0])


def test_non_leave_history_rows_are_not_appended(tmp_path):
    """members_history には在籍者の行（leave 空欄）も入っている。それらは補わない。"""
    path = _write(tmp_path, BASE_MEMBERS, history=[_row('a@x', '設計部門'), _row('h@x', '設計部門')])
    assert sorted(_by_addr(_built(path)[0])) == ['a@x', 'q@x']


def test_member_present_in_members_sheet_is_not_duplicated(tmp_path):
    """members に居る人は members の値を使い、履歴から二重に補わない。"""
    history = [_row('a@x', '設計部門', leave='Y', department='旧部署')]
    path = _write(tmp_path, BASE_MEMBERS, history=history)
    members, _ = _built(path)
    assert [m['mail_address'] for m in members].count('a@x') == 1
    assert _by_addr(members)['a@x']['department'] == '機電設計部'


def test_duplicate_history_rows_are_appended_once(tmp_path):
    history = [_row('old@x', '設計部門', leave='Y'), _row('old@x', '設計部門', leave='Y')]
    path = _write(tmp_path, BASE_MEMBERS, history=history)
    assert [m['mail_address'] for m in _built(path)[0]].count('old@x') == 1


def test_missing_history_sheet_keeps_previous_behavior(tmp_path):
    """members_history シートが無いファイル（旧形式・Member.xlsx）でも従来どおり動く。"""
    path = _write(tmp_path, BASE_MEMBERS, history=None)
    members, summary = _built(path)
    assert sorted(m['mail_address'] for m in members) == ['a@x', 'q@x']
    assert summary['from_history'] == 0


def test_history_without_required_columns_raises(tmp_path):
    path = _write(tmp_path, BASE_MEMBERS, history=[{'mail_address': 'old@x', 'leave': 'Y'}],
                  history_columns=['mail_address', 'leave'])
    with pytest.raises(ValueError, match='members_history'):
        gmy.build(path)


def test_y_in_members_sheet_is_normalized_to_leave(tmp_path):
    """members シートの `Y` も `leave` に揃える（集計は `Y` を退職として数えていた）。"""
    path = _write(tmp_path, BASE_MEMBERS + [_row('y@x', '設計部門', leave='Y')], history=[])
    members, summary = _built(path)
    assert _by_addr(members)['y@x']['leave'] == 'leave'
    assert summary['on_leave'] == 1


def test_absence_is_preserved(tmp_path):
    """`absence`（休職中）は退職ではない。値をそのまま残す。"""
    path = _write(tmp_path, BASE_MEMBERS + [_row('ab@x', '設計部門', leave='absence')], history=[])
    members, summary = _built(path)
    assert _by_addr(members)['ab@x']['leave'] == 'absence'
    assert summary['on_leave'] == 0


def test_summary_counts_include_history_leavers_but_by_division_is_active_only(tmp_path):
    history = [_row('old1@x', '設計部門', leave='Y'), _row('old2@x', '品質保証部門', leave='Y'),
               _row('dev@x', '開発部門', leave='Y')]
    path = _write(tmp_path, BASE_MEMBERS, history=history)
    _, summary = _built(path)
    assert summary == {'total': 4, 'on_leave': 2, 'active': 2, 'from_history': 2,
                       'by_division': {'設計部門': 1, '品質保証部門': 1}}


def test_leave_only_divisions_do_not_count_as_current_divisions(tmp_path):
    """現在の部門は『在籍者（leave でない人）が居る部門』。退職者しか居ない部門は含めない。"""
    members = BASE_MEMBERS + [_row('gone@x', '開発部門', leave='leave')]
    path = _write(tmp_path, members, history=[_row('dev2@x', '開発部門', leave='Y')])
    assert 'dev2@x' not in _by_addr(_built(path)[0])
