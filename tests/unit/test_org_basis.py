"""apply_org_basis() が「切り替える6列だけ差し替え、*_current は一切触らない」ことを守る。

権限判定用の *_current 列まで巻き込んで書き換えると、当時ビューで異動者・昇進者の
過去データが権限外ユーザーに見えてしまう（docs/PRIVILEGE_SYSTEM.md 「権限は現在値固定」）。
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from modules.config import ORG_BASIS_CURRENT, ORG_BASIS_AT_SURVEY  # noqa: E402
from modules.org_basis import apply_org_basis  # noqa: E402


def _sample_df():
    return pd.DataFrame({
        'mail_address': ['a@example.com', 'b@example.com'],
        'division': ['設計部門', '半導体BU'],               # current
        'division_at': ['半導体BU', '半導体BU'],            # at-survey (a moved division)
        'division_current': ['設計部門', '半導体BU'],
        'department': ['機電設計部', '機電設計部'],          # current
        'department_at': ['半導体設計部', '機電設計部'],     # at-survey (a moved department)
        'department_current': ['機電設計部', '機電設計部'],
        'section': ['第一設計課', '第二設計課'],             # current
        'section_at': ['第二設計課', '第二設計課'],          # at-survey (a moved section)
        'section_current': ['第一設計課', '第二設計課'],
        'team': ['PVD', '未設定'],
        'team_at': ['未設定', '未設定'],
        'team_current': ['PVD', '未設定'],
        'project': ['ENTRON-X', '現行機'],
        'project_at': ['現行機', '現行機'],
        'project_current': ['ENTRON-X', '現行機'],
        'grade': ['主管', '一般職'],                         # current
        'grade_at': ['主事', '一般職'],                       # at-survey (a was promoted)
        'grade_current': ['主管', '一般職'],
    })


def test_current_basis_is_a_no_op():
    df = _sample_df()
    result = apply_org_basis(df, ORG_BASIS_CURRENT)
    pd.testing.assert_frame_equal(result, df)


def test_at_survey_basis_overwrites_all_six_toggled_columns():
    df = _sample_df()
    result = apply_org_basis(df, ORG_BASIS_AT_SURVEY)

    assert list(result['division']) == ['半導体BU', '半導体BU']
    assert list(result['department']) == ['半導体設計部', '機電設計部']
    assert list(result['section']) == ['第二設計課', '第二設計課']
    assert list(result['team']) == ['未設定', '未設定']
    assert list(result['project']) == ['現行機', '現行機']
    assert list(result['grade']) == ['主事', '一般職']

    # pinned *_current columns used for privilege scoping and the 個人 profile
    # must stay untouched
    for col in ('division_current', 'department_current', 'section_current',
                'team_current', 'project_current', 'grade_current'):
        assert list(result[col]) == list(df[col]), col


def test_missing_at_survey_columns_are_left_untouched():
    """comment_df/member_df のように *_at 列を持たない DataFrame は素通しする。"""
    df = pd.DataFrame({'mail_address': ['a@example.com'], 'section': ['第一設計課']})
    result = apply_org_basis(df, ORG_BASIS_AT_SURVEY)
    pd.testing.assert_frame_equal(result, df)


def test_does_not_mutate_the_input_dataframe():
    df = _sample_df()
    original_section = df['section'].copy()
    apply_org_basis(df, ORG_BASIS_AT_SURVEY)
    pd.testing.assert_series_equal(df['section'], original_section)
