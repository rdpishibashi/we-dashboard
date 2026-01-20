"""
Encrypt Excel file for secure storage in repository
Run this locally to encrypt your data file before deploying to Streamlit Cloud
"""

from cryptography.fernet import Fernet
import sys

def generate_key():
    """Generate a new encryption key."""
    key = Fernet.generate_key()
    print("\n=== ENCRYPTION KEY ===")
    print(key.decode())
    print("\n⚠️  IMPORTANT: Save this key securely!")
    print("Add it to Streamlit Cloud secrets as:")
    print("EXCEL_ENCRYPTION_KEY = \"" + key.decode() + "\"")
    print("\nNever commit this key to Git!\n")
    return key

def encrypt_file(input_file, output_file, key):
    """Encrypt a file using Fernet encryption."""
    fernet = Fernet(key)

    # Read the original file
    with open(input_file, 'rb') as f:
        data = f.read()

    # Encrypt the data
    encrypted_data = fernet.encrypt(data)

    # Write encrypted data
    with open(output_file, 'wb') as f:
        f.write(encrypted_data)

    print(f"✅ File encrypted successfully: {output_file}")
    print(f"Original size: {len(data):,} bytes")
    print(f"Encrypted size: {len(encrypted_data):,} bytes")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python encrypt_data.py <input_excel_file> [output_file] [encryption_key]")
        print("\nExample:")
        print("  python encrypt_data.py EngagementMasterSS.xlsx")
        print("  python encrypt_data.py data.xlsx encrypted_data.bin")
        print("  python encrypt_data.py data.xlsx encrypted_data.bin <existing_key>")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else input_file + ".encrypted"

    # Use existing key or generate new one
    if len(sys.argv) > 3:
        key = sys.argv[3].encode()
        print(f"Using provided encryption key")
    else:
        key = generate_key()

    encrypt_file(input_file, output_file, key)

    print("\n📋 Next steps:")
    print("1. Add the encryption key to Streamlit Cloud secrets")
    print("2. Commit the encrypted file to Git")
    print("3. Update DEFAULT_FILE_PATH in config.py to point to encrypted file")
    print("4. Delete or .gitignore the original unencrypted file")
