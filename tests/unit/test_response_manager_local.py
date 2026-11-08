"""
modules/response_manager_local.py（返信ファイル response.xlsx）の
パスワード解決・旧ファイルの移行・読み込み失敗時のデータ保護を守る。
合成データのみ（実際の response.xlsx・secrets.toml・windows_config.py には触れない）。

背景（2026-11）: 返信ファイルのパスワードを EXCEL_PASSWORD から RESPONSE_PASSWORD へ
切り替えた。切り替え前の実装には「復号に失敗すると空の表を返し、post_response() が
その空の表へ 1 行足して上書きする＝過去の返信が全消去される」という潜在リスクがあり、
パスワードを変えると現実に起こりうるため、読めないファイルへは書かないことを守る。
"""

import sys
import types
from pathlib import Path

import msoffcrypto
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import modules  # noqa: E402
from modules import response_manager_local as rm  # noqa: E402


class FakeSt:
    """streamlit の最小代替。secrets は dict、警告・エラーは記録するだけ。"""

    def __init__(self):
        self.secrets = {}
        self.session_state = {}
        self.warnings = []
        self.errors = []

    def warning(self, msg):
        self.warnings.append(str(msg))

    def error(self, msg):
        self.errors.append(str(msg))


@pytest.fixture
def env(tmp_path, monkeypatch):
    fake = FakeSt()
    path = tmp_path / "response.xlsx"
    monkeypatch.setattr(rm, "st", fake)
    monkeypatch.setattr(rm, "_get_responses_path", lambda: path)
    # 既定では windows_config.py が無い環境（ImportError）にする
    monkeypatch.setitem(sys.modules, "modules.windows_config", None)
    monkeypatch.delattr(modules, "windows_config", raising=False)
    return types.SimpleNamespace(st=fake, path=path, mp=monkeypatch)


def set_passwords(env, windows=None, response=None, excel=None):
    env.st.secrets = {}
    if response is not None:
        env.st.secrets["RESPONSE_PASSWORD"] = response
    if excel is not None:
        env.st.secrets["EXCEL_PASSWORD"] = excel
    if windows is not None:
        fake = types.SimpleNamespace(RESPONSE_PASSWORD=windows)
        env.mp.setitem(sys.modules, "modules.windows_config", fake)
        env.mp.setattr(modules, "windows_config", fake, raising=False)


def sample_df(n=1):
    rows = [{c: f"{c}-{i}" for c in rm.RESPONSE_COLUMNS} for i in range(n)]
    return pd.DataFrame(rows, columns=rm.RESPONSE_COLUMNS)


def write_with(env, password, df):
    """指定パスワード（None なら暗号化なし）で response.xlsx を作る。"""
    with env.mp.context() as m:
        m.setattr(rm, "_get_password", lambda: password)
        rm._write_responses_file(env.path, df)


def is_encrypted(path):
    with open(path, "rb") as fh:
        return msoffcrypto.OfficeFile(fh).is_encrypted()


def opens_with(path, password):
    import io
    try:
        with open(path, "rb") as fh:
            office = msoffcrypto.OfficeFile(fh)
            office.load_key(password=password)
            office.decrypt(io.BytesIO())
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# パスワードの解決順
# ---------------------------------------------------------------------------

def test_windows_config_response_password_wins_over_secrets(env):
    set_passwords(env, windows="W", response="S", excel="E")
    assert rm._get_password() == "W"


def test_secrets_response_password_used_when_no_windows_config(env):
    set_passwords(env, response="S", excel="E")
    assert rm._get_password() == "S"


def test_falls_back_to_excel_password_when_response_password_unset(env):
    """RESPONSE_PASSWORD がどこにも無い環境では EXCEL_PASSWORD で暗号化する（暗号化を外さない）。"""
    set_passwords(env, excel="E")
    assert rm._get_password() == "E"


def test_no_password_anywhere_is_none(env):
    set_passwords(env)
    assert rm._get_password() is None


# ---------------------------------------------------------------------------
# 読み書きと移行
# ---------------------------------------------------------------------------

def test_write_then_read_roundtrip_is_encrypted_with_primary(env):
    set_passwords(env, response="R", excel="E")
    rm._write_responses_file(env.path, sample_df(2))
    assert is_encrypted(env.path) and opens_with(env.path, "R") and not opens_with(env.path, "E")
    assert len(rm._read_responses_file(env.path)) == 2


def test_file_readable_with_primary_is_not_rewritten(env):
    set_passwords(env, response="R", excel="E")
    write_with(env, "R", sample_df())
    before = env.path.read_bytes()
    rm._read_responses_file(env.path)
    assert env.path.read_bytes() == before  # 暗号化は毎回バイト列が変わるので、書き直せば必ず変わる


def test_legacy_excel_password_file_is_read_and_migrated_to_response_password(env):
    """守る対象: 旧パスワード（EXCEL_PASSWORD）で暗号化された既存ファイルを失わず、新パスワードへ移行する。"""
    set_passwords(env, response="R", excel="E")
    write_with(env, "E", sample_df(3))
    assert len(rm._read_responses_file(env.path)) == 3
    assert opens_with(env.path, "R") and not opens_with(env.path, "E")


def test_unencrypted_file_is_read_and_encrypted_with_primary(env):
    set_passwords(env, response="R")
    write_with(env, None, sample_df(2))
    assert not is_encrypted(env.path)
    assert len(rm._read_responses_file(env.path)) == 2
    assert opens_with(env.path, "R")


def test_no_password_configured_reads_unencrypted_file_without_rewriting(env):
    set_passwords(env)
    write_with(env, None, sample_df(2))
    before = env.path.read_bytes()
    assert len(rm._read_responses_file(env.path)) == 2
    assert env.path.read_bytes() == before


def test_missing_file_reads_as_empty_with_columns(env):
    set_passwords(env, response="R")
    df = rm._read_responses_file(env.path)
    assert df.empty and list(df.columns) == rm.RESPONSE_COLUMNS


# ---------------------------------------------------------------------------
# 読めないファイルを守る（全消去の回帰防止）
# ---------------------------------------------------------------------------

def test_unreadable_file_loads_as_empty_with_warning_and_is_untouched(env):
    set_passwords(env, response="R", excel="E")
    write_with(env, "SOMETHING-ELSE", sample_df(2))
    before = env.path.read_bytes()
    assert rm._read_responses_file(env.path).empty
    assert env.st.warnings
    assert env.path.read_bytes() == before


def test_post_response_refuses_to_overwrite_unreadable_file(env):
    """回帰: 修正前は空の表へ 1 行足して上書きし、過去の返信がすべて消えていた。"""
    set_passwords(env, response="R", excel="E")
    write_with(env, "SOMETHING-ELSE", sample_df(5))
    before = env.path.read_bytes()
    ok = rm.post_response("2026-10", "m@x", "c", "acct", "name", "text")
    assert ok is False
    assert env.st.errors
    assert env.path.read_bytes() == before


def test_post_response_refuses_when_encrypted_but_no_password_configured(env):
    set_passwords(env)
    write_with(env, "X", sample_df(2))
    before = env.path.read_bytes()
    assert rm.post_response("2026-10", "m@x", "c", "acct", "name", "text") is False
    assert env.path.read_bytes() == before


def test_post_response_appends_to_legacy_file_and_keeps_old_rows(env):
    set_passwords(env, response="R", excel="E")
    write_with(env, "E", sample_df(2))
    assert rm.post_response("2026-10", "m@x", "c", "acct", "name", "text") is True
    df = rm._read_responses_file(env.path)
    assert len(df) == 3 and df.iloc[-1]["response_text"] == "text"
    assert opens_with(env.path, "R")


def test_post_response_creates_file_when_absent(env):
    set_passwords(env, response="R")
    assert rm.post_response("2026-10", "m@x", "c", "acct", "name", "text") is True
    assert len(rm._read_responses_file(env.path)) == 1 and opens_with(env.path, "R")
