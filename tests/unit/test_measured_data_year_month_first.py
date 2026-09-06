"""format_measured_data() の year_month_first オプションを守る。

時系列タブの「計測値」テーブルは「年月」→「課」の順に列・並び替えを行う一方、
カテゴリ比較タブは既存どおり「課」→「年月」のまま（同じ関数を共有しているため、
呼び出し元ごとに挙動が変わることを明示的にテストする）。
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from modules.statistics import format_measured_data  # noqa: E402


def _df():
    return pd.DataFrame({
        'year_month': ['2025-08', '2025-08', '2025-07', '2025-07'],
        'section': ['課B', '課A', '課B', '課A'],
        'name': ['田中', '佐藤', '田中', '佐藤'],
        'engagement_rating': [6.0, 5.0, 7.0, 4.0],
    })


def test_default_orders_by_category_then_year_month():
    result = format_measured_data(_df(), 'engagement_rating', 'section')
    assert list(result.columns[:2]) == ['課', '年月']
    assert list(result['年月']) == ['2025-07', '2025-08', '2025-07', '2025-08']


def test_year_month_first_orders_by_month_then_category():
    result = format_measured_data(_df(), 'engagement_rating', 'section', year_month_first=True)
    assert list(result.columns[:2]) == ['年月', '課']
    assert list(result['年月']) == ['2025-07', '2025-07', '2025-08', '2025-08']
    # 各月内は課の並び順（category order）を維持する
    assert list(result['課']) == ['課A', '課B', '課A', '課B']
