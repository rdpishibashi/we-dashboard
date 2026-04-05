"""
Response File Manager
=====================
Save and load password-protected response Excel files.

Used by the Windows standalone app to store survey responses
in a format that is not trivially readable.

Password source:
- PyInstaller bundle: modules/windows_config.py (RESPONSE_PASSWORD)
- Streamlit Cloud / dev: st.secrets["RESPONSE_PASSWORD"]
"""

import io
import pandas as pd


def get_response_password():
    """
    Get password for response Excel files.

    When modules/windows_config.py exists (local standalone mode, git-ignored),
    reads from it. Otherwise reads from Streamlit secrets (Cloud deployment).

    Returns:
        Password string or None if not configured
    """
    try:
        from modules import windows_config
        return windows_config.RESPONSE_PASSWORD
    except ImportError:
        pass
    try:
        import streamlit as st
        return st.secrets.get("RESPONSE_PASSWORD")
    except (AttributeError, FileNotFoundError):
        return None


def save_responses(df: pd.DataFrame, path: str, sheet_name: str = 'responses') -> None:
    """
    Write DataFrame to a password-protected Excel file.

    Args:
        df: DataFrame to save
        path: Output file path (e.g. "responses.xlsx")
        sheet_name: Sheet name inside the workbook

    Raises:
        ValueError: If password is not configured
        IOError: If the file cannot be written
    """
    import msoffcrypto

    password = get_response_password()
    if not password:
        raise ValueError("レスポンスファイルのパスワードが設定されていません。管理者に連絡してください。")

    # Write plain xlsx to an in-memory buffer
    plain_buf = io.BytesIO()
    with pd.ExcelWriter(plain_buf, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name=sheet_name, index=False)
    plain_buf.seek(0)

    # Encrypt and write to disk
    encrypted_buf = io.BytesIO()
    office_file = msoffcrypto.OfficeFile(plain_buf)
    office_file.encrypt(password, encrypted_buf)

    with open(path, 'wb') as f:
        f.write(encrypted_buf.getvalue())


def load_responses(path: str, sheet_name: str = 'responses') -> pd.DataFrame:
    """
    Load a password-protected response Excel file.

    Args:
        path: Path to the encrypted Excel file
        sheet_name: Sheet name to read

    Returns:
        DataFrame with response data

    Raises:
        ValueError: If password is not configured or incorrect
        FileNotFoundError: If the file does not exist
    """
    import msoffcrypto

    password = get_response_password()
    if not password:
        raise ValueError("レスポンスファイルのパスワードが設定されていません。管理者に連絡してください。")

    with open(path, 'rb') as f:
        file_data = io.BytesIO(f.read())

    try:
        decrypted = io.BytesIO()
        office_file = msoffcrypto.OfficeFile(file_data)
        office_file.load_key(password=password)
        office_file.decrypt(decrypted)
        decrypted.seek(0)
    except Exception as e:
        raise ValueError(f"レスポンスファイルの復号化に失敗しました。({e})")

    return pd.read_excel(decrypted, sheet_name=sheet_name, engine='openpyxl')
