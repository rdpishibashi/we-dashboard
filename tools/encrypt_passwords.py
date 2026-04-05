"""
Developer tool: encrypt passwords for windows_config.py
========================================================
Run this whenever you need to update the passwords stored in
modules/windows_config.py.

Usage:
    python tools/encrypt_passwords.py

The script prints the encrypted byte literals. Paste them into
modules/windows_config.py to replace _EXCEL_PASSWORD_ENC and
_RESPONSE_PASSWORD_ENC.

The encryption key (_KEY) in this file MUST match the one in
modules/windows_config.py. Never change the key without re-encrypting
all passwords.
"""

import getpass
from cryptography.fernet import Fernet

# Must match _KEY in modules/windows_config.py
_KEY = b'Q9M_yglxr3SeM6tuHOf31-m4xHLKxGXvFmJBht0H5_I='


def encrypt(plaintext: str) -> bytes:
    return Fernet(_KEY).encrypt(plaintext.encode())


def main():
    print("=== WE-Dashboard password encryptor ===")
    print("Enter the passwords to encrypt. Input is hidden.\n")

    excel_pw = getpass.getpass("EXCEL_PASSWORD (EngagementData.xlsx): ")
    response_pw = getpass.getpass("RESPONSE_PASSWORD (responses.xlsx): ")

    excel_enc = encrypt(excel_pw)
    response_enc = encrypt(response_pw)

    print("\n--- Paste the following into modules/windows_config.py ---\n")
    print(f"_EXCEL_PASSWORD_ENC = {repr(excel_enc)}")
    print(f"_RESPONSE_PASSWORD_ENC = {repr(response_enc)}")
    print("\n----------------------------------------------------------")
    print("Done. Do NOT commit windows_config.py to git.")


if __name__ == "__main__":
    main()
