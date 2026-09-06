"""create_time_series_chart() が、カテゴリごとに実データ期間が重ならない場合でも
hovermode='x unified' で隣接月の値を誤表示しないことを守る。

組織・職位の基準トグルで「測定当時」を選ぶと、組織改編を境に新旧の課の実データ
期間が完全に分断されることがある（例: 旧課は2024-06まで、新課は2024-07から）。
このとき、データの無い月を暗黙に欠落させたままだと、Plotly の unified hover が
そのカテゴリの一番近いデータ点の値を誤ってその月の値として表示してしまう
（2026-09-06、実データで報告された不具合）。
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from modules.charts import create_time_series_chart  # noqa: E402


def _df():
    # 2024-06 は旧課のみ、2024-07 は新課のみ在籍（組織改編を模したデータ）
    return pd.DataFrame({
        'year_month': ['2024-06', '2024-06', '2024-07', '2024-07'],
        'section': ['旧課', '旧課', '新課', '新課'],
        'engagement_rating': [5.0, 6.0, 7.0, 8.0],
    })


def test_categories_get_explicit_nan_outside_their_actual_data_range():
    fig = create_time_series_chart(_df(), 'engagement_rating', 'test', 'section')

    traces = {t.name: t for t in fig.data}
    assert set(traces.keys()) == {'旧課', '新課'}

    # 新課の 2024-06 は明示的に NaN であるべき（行自体が欠落してはいけない）
    new_section = traces['新課']
    row = dict(zip([pd.Timestamp(x).strftime('%Y-%m') for x in new_section.x], new_section.y))
    assert '2024-06' in row, "データの無い月の行が欠落している（unified hoverが誤爆する）"
    assert pd.isna(row['2024-06'])
    assert row['2024-07'] == 7.5  # mean(7.0, 8.0)

    # 旧課の 2024-07 も同様に NaN
    old_section = traces['旧課']
    row_old = dict(zip([pd.Timestamp(x).strftime('%Y-%m') for x in old_section.x], old_section.y))
    assert '2024-07' in row_old
    assert pd.isna(row_old['2024-07'])


def test_actual_values_are_still_the_group_mean():
    fig = create_time_series_chart(_df(), 'engagement_rating', 'test', 'section')
    traces = {t.name: t for t in fig.data}

    old_section = traces['旧課']
    row_old = dict(zip([pd.Timestamp(x).strftime('%Y-%m') for x in old_section.x], old_section.y))
    assert row_old['2024-06'] == 5.5  # mean(5.0, 6.0)

    new_section = traces['新課']
    row_new = dict(zip([pd.Timestamp(x).strftime('%Y-%m') for x in new_section.x], new_section.y))
    assert row_new['2024-07'] == 7.5  # mean(7.0, 8.0)


def test_individual_name_grouping_is_not_reindexed():
    """name グルーピングは対象外 — latest_vals ソートが NaN で不安定にならないよう
    に、データの無い月の行を追加しない（従来どおり欠落させる）。"""
    df = pd.DataFrame({
        'year_month': ['2024-06', '2024-07'],
        'name': ['山田', '鈴木'],
        'engagement_rating': [5.0, 7.0],
    })
    fig = create_time_series_chart(df, 'engagement_rating', 'test', 'name')
    traces = {t.name: t for t in fig.data}
    assert len(traces['山田'].x) == 1
    assert len(traces['鈴木'].x) == 1
