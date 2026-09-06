"""「主な指標」から最新月に在籍ゼロのグループを落とすことを守る。

「組織・職位の基準＝測定当時」では、解散した課・終了したプロジェクトが過去の月の
当時値として残る（例: 機電設計部付は 2026-06 まで存在し 2026-07 に消滅）。
平均・傾きは期間全体から計算されるので値は入るが、人数（最新月の在籍者数）は 0 に
なり、データ不整合に見える。行ごと落とすのが仕様。

個人別（group_col='name'）は対象外——人数列は表示されないうえ、最新月にたまたま
未回答だっただけのメンバーが履歴ごと消えてしまうため。
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from modules.statistics import calculate_group_statistics  # noqa: E402

END_DT = pd.Timestamp('2026-08-01')


def _sample_df():
    """第一設計課は最新月まで在籍、機電設計部付は 2026-06 で消滅。"""
    rows = []
    for ym in ('2026-06', '2026-07', '2026-08'):
        rows.append({'name': '在籍 太郎', 'section': '第一設計課',
                     'year_month': ym, 'engagement_rating': 5.0})
    rows.append({'name': '解散 花子', 'section': '機電設計部付',
                 'year_month': '2026-06', 'engagement_rating': 4.0})

    df = pd.DataFrame(rows)
    df['year_month_dt'] = pd.to_datetime(df['year_month'], format='%Y-%m')
    return df


def test_group_with_no_members_in_latest_month_is_dropped():
    stats = calculate_group_statistics(
        _sample_df(), 'engagement_rating', 'section', end_dt=END_DT
    )

    assert list(stats['課']) == ['第一設計課']
    assert list(stats['人数']) == [1]


def test_individual_grouping_keeps_members_absent_from_latest_month():
    """個人別では最新月に回答が無いメンバーも履歴として残す。"""
    stats = calculate_group_statistics(
        _sample_df(), 'engagement_rating', 'name', end_dt=END_DT
    )

    assert set(stats['個人']) == {'在籍 太郎', '解散 花子'}
    assert '人数' not in stats.columns


def test_all_groups_kept_when_end_dt_is_not_given():
    """end_dt が無ければ人数は期間全体のユニーク数——0 にはならず何も落ちない。"""
    stats = calculate_group_statistics(_sample_df(), 'engagement_rating', 'section')

    assert set(stats['課']) == {'第一設計課', '機電設計部付'}
