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
    # 元の 5 項目の期待値は変えない。累積型で足したキーは、既存 members.yaml を渡さない
    # 入力では 0 件／空であることを明示する（summary 全体の一致検査だと、キー追加のたびに壊れるため）。
    assert {k: summary[k] for k in ('total', 'on_leave', 'active', 'from_history', 'by_division')} == {
        'total': 4, 'on_leave': 2, 'active': 2, 'from_history': 2,
        'by_division': {'設計部門': 1, '品質保証部門': 1}}
    assert (summary['retained'], summary['dropped'], summary['vanished_active']) == (0, 0, [])


def test_leave_only_divisions_do_not_count_as_current_divisions(tmp_path):
    """現在の部門は『在籍者（leave でない人）が居る部門』。退職者しか居ない部門は含めない。"""
    members = BASE_MEMBERS + [_row('gone@x', '開発部門', leave='leave')]
    path = _write(tmp_path, members, history=[_row('dev2@x', '開発部門', leave='Y')])
    assert 'dev2@x' not in _by_addr(_built(path)[0])


# ---------------------------------------------------------------------------
# 累積型（既存の members.yaml から削除しない）
#
# 背景（2026-11）: members.yaml は「過去の退職者を含む累積の名簿」として扱う。
# MemberSS の members シートに追加・変更があれば反映するが、既存の members.yaml から
# 人を削除しない。ただし対象は EngagementData-*.xlsx を作成している部門に限る
# （旧部門の人が蓄積されないように）。
# ---------------------------------------------------------------------------

def _built_with(path, existing=None, targets=None):
    text, summary = gmy.build(path, existing=existing, extra_target_divisions=targets)
    return yaml.safe_load(text)['members'], summary


def test_existing_member_missing_from_sheet_is_retained(tmp_path):
    """守る対象: シートから消えても、作成対象の部門の既存メンバーは members.yaml に残る。

    履歴にも無い退職者でも消えない（members_history に依存しない）。
    """
    path = _write(tmp_path, BASE_MEMBERS, history=[])
    existing = [_row('gone@x', '設計部門', leave='leave')]
    members, summary = _built_with(path, existing)
    assert _by_addr(members)['gone@x']['leave'] == 'leave'
    assert summary['retained'] == 1


def test_retained_member_of_non_target_division_is_dropped(tmp_path):
    """作成対象でない部門の人は残さない（旧部門のメンバーが蓄積されないように）。"""
    path = _write(tmp_path, BASE_MEMBERS, history=[])
    existing = [_row('dev@x', '開発部門', leave='leave')]
    members, summary = _built_with(path, existing)
    assert 'dev@x' not in _by_addr(members)
    assert summary['dropped'] == 1 and summary['retained'] == 0


def test_sheet_values_win_over_existing_entry(tmp_path):
    """シートの変更（異動など）は反映される。"""
    path = _write(tmp_path, BASE_MEMBERS, history=[])
    existing = [_row('a@x', '設計部門', department='旧部署')]
    members, summary = _built_with(path, existing)
    assert [m['mail_address'] for m in members].count('a@x') == 1
    assert _by_addr(members)['a@x']['department'] == '機電設計部'
    assert summary['retained'] == 0


def test_rehired_member_is_active_again(tmp_path):
    """既存では leave でも、シートで復職（leave 空欄）していれば在籍者になる。"""
    path = _write(tmp_path, BASE_MEMBERS, history=[])
    existing = [_row('a@x', '設計部門', leave='leave')]
    assert _by_addr(_built_with(path, existing)[0])['a@x']['leave'] == ''


def test_extra_target_division_makes_its_members_retained(tmp_path):
    """作成対象の部門は、シートの在籍者だけでなく split_by_division が見る部門も含む。

    シートに在籍者が居なくなっても、データがまだ窓内にある部門の退職者は残す。
    """
    path = _write(tmp_path, BASE_MEMBERS, history=[])
    existing = [_row('old@x', '旧部門', leave='leave')]
    assert 'old@x' not in _by_addr(_built_with(path, existing)[0])
    members, _ = _built_with(path, existing, targets={'旧部門'})
    assert 'old@x' in _by_addr(members)


def test_vanished_active_member_becomes_leave_when_history_says_so(tmp_path):
    path = _write(tmp_path, BASE_MEMBERS, history=[_row('v@x', '設計部門', leave='Y')])
    existing = [_row('v@x', '設計部門', leave='')]
    members, summary = _built_with(path, existing)
    assert _by_addr(members)['v@x']['leave'] == 'leave'
    assert summary['vanished_active'] == []


def test_vanished_active_member_without_history_is_kept_and_reported(tmp_path):
    """シートから消えた在籍者で履歴にも記録が無い人は、推測で leave にせず、そのまま残して警告対象にする。"""
    path = _write(tmp_path, BASE_MEMBERS, history=[])
    existing = [_row('v@x', '設計部門', leave='')]
    members, summary = _built_with(path, existing)
    assert _by_addr(members)['v@x']['leave'] == ''
    assert summary['vanished_active'] == ['v@x']


def test_absence_member_missing_from_sheet_is_also_reported(tmp_path):
    path = _write(tmp_path, BASE_MEMBERS, history=[])
    existing = [_row('ab@x', '設計部門', leave='absence')]
    assert _built_with(path, existing)[1]['vanished_active'] == ['ab@x']


def test_history_addition_is_not_counted_when_already_retained(tmp_path):
    """既存に居る人は retained であり、履歴由来（from_history）として二重に数えない。"""
    path = _write(tmp_path, BASE_MEMBERS, history=[_row('old@x', '設計部門', leave='Y'),
                                                   _row('new@x', '設計部門', leave='Y')])
    existing = [_row('old@x', '設計部門', leave='leave')]
    members, summary = _built_with(path, existing)
    assert [m['mail_address'] for m in members].count('old@x') == 1
    assert summary['retained'] == 1 and summary['from_history'] == 1


def test_output_order_is_sheet_then_retained_then_history(tmp_path):
    path = _write(tmp_path, BASE_MEMBERS, history=[_row('h@x', '設計部門', leave='Y')])
    existing = [_row('r@x', '設計部門', leave='leave')]
    members, _ = _built_with(path, existing)
    assert [m['mail_address'] for m in members] == ['a@x', 'q@x', 'r@x', 'h@x']


def test_summary_counts_with_cumulative_members(tmp_path):
    path = _write(tmp_path, BASE_MEMBERS, history=[_row('h@x', '設計部門', leave='Y')])
    existing = [_row('r@x', '設計部門', leave='leave'), _row('dev@x', '開発部門', leave='leave'),
                _row('v@x', '品質保証部門', leave='')]
    _, summary = _built_with(path, existing)
    assert summary == {'total': 5, 'on_leave': 2, 'active': 3, 'from_history': 1,
                       'retained': 2, 'dropped': 1, 'vanished_active': ['v@x'],
                       'by_division': {'設計部門': 1, '品質保証部門': 2}}


def test_existing_none_behaves_like_before(tmp_path):
    path = _write(tmp_path, BASE_MEMBERS, history=[])
    members, summary = _built_with(path, None)
    assert sorted(m['mail_address'] for m in members) == ['a@x', 'q@x']
    assert summary['retained'] == 0 and summary['dropped'] == 0


def test_load_existing_returns_none_when_file_missing_and_list_otherwise(tmp_path):
    assert gmy.load_existing(tmp_path / 'nope.yaml') is None
    p = tmp_path / 'members.yaml'
    p.write_text(yaml.dump({'members': [_row('a@x', '設計部門')]}, allow_unicode=True), encoding='utf-8')
    assert [m['mail_address'] for m in gmy.load_existing(p)] == ['a@x']


def test_resolve_target_divisions_matches_split_by_division(tmp_path):
    """作成対象の部門の定義は split_by_division と同一（同じ関数を使う）。"""
    import split_by_division as sbd
    master = tmp_path / 'Engagement Master.xlsx'
    rows = [{'year': 2026, 'month': 10, 'current_division': '設計部門 ', 'mail_address': 'a@x'},
            {'year': 2026, 'month': 10, 'current_division': '品質保証部門', 'mail_address': 'q@x'},
            {'year': 2025, 'month': 1, 'current_division': '旧部門', 'mail_address': 'o@x'}]
    with pd.ExcelWriter(master, engine='openpyxl') as w:
        pd.DataFrame(rows).to_excel(w, sheet_name='rating2', index=False)
    got = gmy.resolve_target_divisions(master)
    assert got == set(sbd.list_active_divisions(master)) == {'設計部門', '品質保証部門'}


def test_resolve_target_divisions_is_none_without_master(tmp_path):
    assert gmy.resolve_target_divisions(tmp_path / 'missing.xlsx') is None
