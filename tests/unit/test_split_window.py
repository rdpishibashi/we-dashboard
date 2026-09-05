"""split_by_division の12ヶ月窓が、年跨ぎ・欠測月・古い leave 行で正しく効くことを守る。

窓は「実行時刻」ではなく rating2 内の最大 (year, month) から決まる。ここが時刻依存に
戻ると、単独実行と monthly_update.py 経由で出力が食い違う。
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

from split_by_division import (  # noqa: E402
    MONTHS_WINDOW,
    _apply_window,
    _month_index,
    _recent_window,
    _ym_label,
)


def _df(pairs):
    return pd.DataFrame(
        {"year": [y for y, _ in pairs], "month": [m for _, m in pairs]}
    )


def test_month_index_is_monotonic_across_the_year_boundary():
    idx = _month_index(pd.Series([2025, 2025, 2026]), pd.Series([11, 12, 1]))
    assert list(idx) == [24311, 24312, 24313]


@pytest.mark.parametrize(
    "year,month",
    [(2025, 9), (2025, 12), (2026, 1), (2026, 8)],
)
def test_ym_label_round_trips_month_index(year, month):
    idx = int(_month_index(pd.Series([year]), pd.Series([month])).iloc[0])
    assert _ym_label(idx) == f"{year}-{month:02d}"


def test_window_spans_twelve_months_ending_at_the_newest_row():
    """2026-08 が最新なら 2025-09〜2026-08（ユーザー指定の受入条件そのもの）。"""
    first, last = _recent_window(_df([(2025, 7), (2026, 8), (2025, 12)]))
    assert (_ym_label(first), _ym_label(last)) == ("2025-09", "2026-08")


def test_window_is_derived_from_data_not_from_the_clock():
    """最新行が古くても、その行を末尾とする窓になる。"""
    first, last = _recent_window(_df([(2024, 3), (2024, 6)]))
    assert (_ym_label(first), _ym_label(last)) == ("2023-07", "2024-06")


def test_apply_window_drops_only_rows_older_than_the_window():
    df = _df([(2025, 7), (2025, 8), (2025, 9), (2026, 8)])
    kept = _apply_window(df, _recent_window(df))
    assert list(zip(kept["year"], kept["month"])) == [(2025, 9), (2026, 8)]


def test_shorter_history_than_the_window_passes_through_untouched():
    df = _df([(2026, 6), (2026, 7), (2026, 8)])
    assert len(_apply_window(df, _recent_window(df))) == 3


def test_missing_months_do_not_shift_the_window():
    """窓はカレンダー月で決まる。行数ベースに退化していないことを確かめる。"""
    df = _df([(2025, 8), (2025, 9), (2026, 8)])
    kept = _apply_window(df, _recent_window(df))
    assert list(zip(kept["year"], kept["month"])) == [(2025, 9), (2026, 8)]


def test_leave_member_whose_last_row_predates_the_window_is_dropped():
    """13ヶ月以上前で止まっている行は落ちる（=退職者が出力から消えうる）。"""
    df = pd.DataFrame(
        {
            "year": [2025, 2026],
            "month": [8, 8],
            "mail_address": ["left@example.com", "active@example.com"],
        }
    )
    kept = _apply_window(df, _recent_window(df))
    assert list(kept["mail_address"]) == ["active@example.com"]


def test_comment_sheet_uses_the_rating2_window_even_when_it_ends_earlier():
    """comment 側の最大月で窓を作り直すと2シートの期間がずれる。"""
    rating2 = _df([(2025, 7), (2026, 8)])
    comment = _df([(2025, 7), (2025, 9), (2026, 3)])
    kept = _apply_window(comment, _recent_window(rating2))
    assert list(zip(kept["year"], kept["month"])) == [(2025, 9), (2026, 3)]


def test_non_numeric_year_month_rows_are_excluded_not_crashing():
    df = pd.DataFrame({"year": [2026, "", None], "month": [8, 5, 5]})
    assert len(_apply_window(df, _recent_window(df))) == 1


def test_missing_year_month_columns_disable_filtering():
    df = pd.DataFrame({"mail_address": ["a@example.com"]})
    assert _recent_window(df) is None
    assert len(_apply_window(df, None)) == 1


def test_window_length_follows_the_constant():
    first, last = _recent_window(_df([(2026, 8)]))
    assert last - first + 1 == MONTHS_WINDOW
