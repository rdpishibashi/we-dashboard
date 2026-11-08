"""
split_by_division.py が「どの部門の EngagementData-*.xlsx を作るか」を決める部分を守る。

generate_member_yaml.py（members.yaml の累積対象の部門）は同じ関数 list_active_divisions() を
使うため、ここが変わると members.yaml の対象部門も一緒に変わる（意図した連動）。
また、行が 0 件の部門では空のファイルを作らない（members.yaml 経由で部門だけが残る場合の防止）。
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

import split_by_division as sbd  # noqa: E402


def _master(tmp_path, rating2, comment=None):
    path = tmp_path / "Engagement Master.xlsx"
    comment = comment if comment is not None else [
        {"year": r["year"], "month": r["month"], "current_division": r["current_division"],
         "mail_address": r["mail_address"]} for r in rating2]
    with pd.ExcelWriter(path, engine="openpyxl") as w:
        pd.DataFrame(rating2).to_excel(w, sheet_name="rating2", index=False)
        pd.DataFrame(comment).to_excel(w, sheet_name="comment", index=False)
    return path


def _r(y, m, div, addr):
    return {"year": y, "month": m, "current_division": div, "mail_address": addr}


def test_active_divisions_drops_blank_and_keeps_order():
    df = pd.DataFrame({"current_division": ["設計部門", None, pd.NA, "品質保証部門", "設計部門"]})
    assert sbd._active_divisions(df) == ["設計部門", "品質保証部門"]


def test_list_active_divisions_applies_window_and_normalizes(tmp_path):
    path = _master(tmp_path, [_r(2026, 10, "設計部門 ", "a@x"), _r(2026, 10, "品質保証部門", "q@x"),
                              _r(2025, 9, "旧部門", "o@x")])  # 2025-09 は 12 か月の窓（2025-11〜）の外
    assert sbd.list_active_divisions(path) == ["設計部門", "品質保証部門"]


def test_split_does_not_create_file_for_leave_only_division(tmp_path, monkeypatch):
    """回帰防止: 退職者の部門だけが members.yaml に残っていても、行が無ければ空ファイルを作らない。"""
    path = _master(tmp_path, [_r(2026, 10, "設計部門", "a@x"), _r(2026, 9, "設計部門", "a@x")])
    monkeypatch.setattr(sbd, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(sbd, "_load_password", lambda: "pw")
    monkeypatch.setattr(sbd, "_load_leave_division_map", lambda: {"gone@x": "開発部門"})
    sbd.split_by_division(path)
    assert sorted(p.name for p in tmp_path.glob("EngagementData-*.xlsx")) == ["EngagementData-設計部門.xlsx"]


def test_split_creates_exactly_the_active_divisions(tmp_path, monkeypatch):
    path = _master(tmp_path, [_r(2026, 10, "設計部門", "a@x"), _r(2026, 10, "品質保証部門", "q@x")])
    monkeypatch.setattr(sbd, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(sbd, "_load_password", lambda: "pw")
    monkeypatch.setattr(sbd, "_load_leave_division_map", lambda: {})
    sbd.split_by_division(path)
    created = {p.name[len("EngagementData-"):-len(".xlsx")] for p in tmp_path.glob("EngagementData-*.xlsx")}
    assert created == set(sbd.list_active_divisions(path))


def test_split_still_includes_leave_member_rows_in_their_division(tmp_path, monkeypatch):
    """退職者の行（current_division が空）は members.yaml の部門のファイルに入る（従来どおり）。"""
    path = _master(tmp_path, [_r(2026, 10, "設計部門", "a@x"), _r(2026, 10, None, "gone@x")])
    monkeypatch.setattr(sbd, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(sbd, "_load_password", lambda: "pw")
    monkeypatch.setattr(sbd, "_load_leave_division_map", lambda: {"gone@x": "設計部門"})
    sbd.split_by_division(path)
    import io
    import msoffcrypto
    with open(tmp_path / "EngagementData-設計部門.xlsx", "rb") as fh:
        office = msoffcrypto.OfficeFile(fh)
        office.load_key(password="pw")
        buf = io.BytesIO()
        office.decrypt(buf)
    df = pd.read_excel(buf, sheet_name="rating2")
    assert sorted(df["mail_address"]) == ["a@x", "gone@x"]
