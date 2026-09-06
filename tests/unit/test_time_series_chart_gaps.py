"""create_time_series_chart() のカテゴリ別グルーピングが hovermode='closest' を
使うことを守る。

2026-09-06、組織・職位の基準トグルで「測定当時」を選ぶと、組織改編を境に新旧の
課の実データ期間が完全に分断されることがあり（例: 旧課は2024-06まで、新課は
2024-07から）、hovermode='x unified' がそのカテゴリの一番近いデータ点の値を
誤ってその月の値として表示する不具合が実データで報告された。

'x unified' は複数系列を1つのツールチップで比較するモードで、hoverdistance
（ホバーで反応する距離の上限）は 'closest' モードのときにしか効かない仕様の
ため、データ側に NaN を補完しても直らないことを確認済み（最初の修正案は
データ補完だったが実機で再現し、方針を hovermode の変更に切り替えた）。
'closest' はカーソルに実際に一番近い1点だけを正確に示すため、この誤表示は
原理的に起こらない。
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


def test_grouped_chart_uses_closest_hovermode():
    fig = create_time_series_chart(_df(), 'engagement_rating', 'test', 'section')
    assert fig.layout.hovermode == 'closest'


def test_ungrouped_chart_keeps_unified_hovermode():
    """単一系列のみの場合は 'x unified' のままで問題ない（比較対象が無いため）。"""
    df = pd.DataFrame({
        'year_month': ['2024-06', '2024-07'],
        'engagement_rating': [5.0, 7.0],
    })
    fig = create_time_series_chart(df, 'engagement_rating', 'test', None)
    assert fig.layout.hovermode == 'x unified'


def test_categories_with_non_overlapping_periods_keep_correct_x_ranges():
    """カテゴリごとの実データ期間（描画される線の位置）自体は正しいことを守る。"""
    fig = create_time_series_chart(_df(), 'engagement_rating', 'test', 'section')
    traces = {t.name: t for t in fig.data}

    old_section_months = {pd.Timestamp(x).strftime('%Y-%m') for x in traces['旧課'].x}
    new_section_months = {pd.Timestamp(x).strftime('%Y-%m') for x in traces['新課'].x}

    assert old_section_months == {'2024-06'}
    assert new_section_months == {'2024-07'}


def test_grouped_values_are_still_the_group_mean():
    fig = create_time_series_chart(_df(), 'engagement_rating', 'test', 'section')
    traces = {t.name: t for t in fig.data}
    assert list(traces['旧課'].y) == [5.5]  # mean(5.0, 6.0)
    assert list(traces['新課'].y) == [7.5]  # mean(7.0, 8.0)
