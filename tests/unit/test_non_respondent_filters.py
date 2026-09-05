"""未記入者リストがサイドバーの全組織軸で絞られることを守る。

2026-09 以前は division/department/section と individual しか適用しておらず、
チーム=Management を選んでも members.yaml の全員が候補に残っていた
（=Management 以外の全メンバーが未記入者として並ぶ）。team/project/grade の
いずれか1軸でも落とすと、例外は出ずリストが黙って広がる。
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from modules.components import apply_member_filters  # noqa: E402


@pytest.fixture
def members():
    """members.yaml 相当。未所属は空文字で入る（generate_member_yaml.py の出力形式）。"""
    return pd.DataFrame(
        [
            {"member_name": "管理職A", "division": "設計部門", "department": "機電設計部",
             "section": "第一設計課", "team": "Management", "project": "現行機", "grade": "主管"},
            {"member_name": "管理職B", "division": "設計部門", "department": "システム開発部",
             "section": "ソフトウェア開発課", "team": "Management", "project": "", "grade": "主事"},
            {"member_name": "一般C", "division": "設計部門", "department": "機電設計部",
             "section": "第一設計課", "team": "", "project": "現行機", "grade": "一般職"},
            {"member_name": "一般D", "division": "設計部門", "department": "機電設計部",
             "section": "第二設計課", "team": "", "project": "ENTRON-X", "grade": "主任"},
            {"member_name": "課未所属E", "division": "品質保証部門", "department": "品質保証部",
             "section": "", "team": "", "project": "", "grade": "主事補"},
        ]
    )


def _names(df):
    return sorted(df["member_name"])


def test_team_selection_narrows_to_that_team(members):
    """本件の受入条件: チーム=Management で Management の2名だけになる。"""
    got = apply_member_filters(members, {"team": "Management"})
    assert _names(got) == ["管理職A", "管理職B"]


def test_team_selection_does_not_leak_non_members(members):
    """回帰: 修正前はここが5名（=Management 以外の全員が残る）だった。"""
    got = apply_member_filters(members, {"team": "Management"})
    assert "一般C" not in set(got["member_name"])
    assert len(got) != len(members)


def test_project_selection_is_applied(members):
    got = apply_member_filters(members, {"project": "ENTRON-X"})
    assert _names(got) == ["一般D"]


def test_grade_selection_is_applied(members):
    got = apply_member_filters(members, {"grade": "一般職"})
    assert _names(got) == ["一般C"]


@pytest.mark.parametrize(
    "key,expected",
    [
        ("team", ["一般C", "一般D", "課未所属E"]),
        ("project", ["管理職B", "課未所属E"]),
        ("section", ["課未所属E"]),
    ],
)
def test_unset_option_matches_members_with_an_empty_value(members, key, expected):
    """サイドバーは section/team/project/grade に '未設定' を残す
    (filter_helpers.get_filter_options) が members.yaml 側は空文字。
    正規化を外すとこれらは 0 件になる。"""
    assert _names(apply_member_filters(members, {key: "未設定"})) == expected


def test_axes_combine_as_an_intersection(members):
    got = apply_member_filters(
        members, {"department": "機電設計部", "section": "第一設計課", "team": "未設定"}
    )
    assert _names(got) == ["一般C"]


def test_subete_and_missing_keys_do_not_filter(members):
    assert len(apply_member_filters(members, {"team": "すべて"})) == len(members)
    assert len(apply_member_filters(members, {})) == len(members)
    assert len(apply_member_filters(members, None)) == len(members)


def test_individual_selection_still_applies(members):
    got = apply_member_filters(members, {"individual": "一般D"})
    assert _names(got) == ["一般D"]


def test_individual_combines_with_team(members):
    assert apply_member_filters(
        members, {"team": "Management", "individual": "一般C"}
    ).empty


def test_absent_column_is_skipped_rather_than_raising(members):
    """members.yaml に project 列が無い環境でも落ちない。"""
    got = apply_member_filters(members.drop(columns=["project"]), {"project": "現行機"})
    assert len(got) == len(members)


def test_every_sidebar_axis_is_covered():
    """filter_helpers が selected_filters に入れる組織軸を落としていないこと。"""
    from modules.components import _MEMBER_FILTER_COLUMNS

    covered = {key for key, _ in _MEMBER_FILTER_COLUMNS}
    assert {"division", "department", "section", "team", "project", "grade"} <= covered
