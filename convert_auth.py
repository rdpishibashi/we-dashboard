#!/usr/bin/env python3
"""
Authentication File Conversion Script

Converts auth_users.json to auth_users.dat (Base64-encoded pickle format)
for deployment to Streamlit Cloud.

Usage:
    python convert_auth.py                       # Convert JSON to DAT
    python convert_auth.py -a/--add-user         # Add a new user interactively
    python convert_auth.py -c/--change-password  # Change password for existing user
    python convert_auth.py -p/--change-privilege # Change privilege for existing user
    python convert_auth.py -s/--show             # Show current users with privileges
    python convert_auth.py -d/--decode           # Decode DAT back to readable format

Workflow for Deployment
    1. Edit auth_users.json or use --add-user to add users
    2. Run python convert_auth.py to create auth_users.dat
    3. Commit auth_users.dat (not .json) to repository
    4. Deploy to Streamlit Cloud
"""

import json
import base64
import pickle
import hashlib
import argparse
from pathlib import Path

AUTH_FILE_JSON = Path('auth_users.json')
AUTH_FILE_DAT = Path('auth_users.dat')


def hash_password(password: str) -> str:
    """Hash a password using SHA-256."""
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


def load_json() -> dict:
    """Load auth data from JSON file."""
    if AUTH_FILE_JSON.exists():
        with open(AUTH_FILE_JSON, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"users": []}


def save_json(data: dict):
    """Save auth data to JSON file."""
    with open(AUTH_FILE_JSON, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Saved to {AUTH_FILE_JSON}")


def convert_to_dat():
    """Convert JSON file to encoded DAT file."""
    if not AUTH_FILE_JSON.exists():
        print(f"Error: {AUTH_FILE_JSON} not found.")
        print("Create the JSON file first or use --add-user to add users.")
        return False

    data = load_json()
    encoded = base64.b64encode(pickle.dumps(data))

    with open(AUTH_FILE_DAT, 'wb') as f:
        f.write(encoded)

    print(f"Converted {AUTH_FILE_JSON} -> {AUTH_FILE_DAT}")
    print(f"Users: {len(data.get('users', []))}")
    return True


def decode_dat():
    """Decode DAT file back to readable format (for debugging)."""
    if not AUTH_FILE_DAT.exists():
        print(f"Error: {AUTH_FILE_DAT} not found.")
        return

    with open(AUTH_FILE_DAT, 'rb') as f:
        data = pickle.loads(base64.b64decode(f.read()))

    print("Decoded content:")
    print(json.dumps(data, indent=2, ensure_ascii=False))


def add_user():
    """Interactively add a new user."""
    data = load_json()

    print("Add new user")
    print("-" * 30)

    username = input("Username: ").strip()
    if not username:
        print("Error: Username cannot be empty.")
        return

    # Check if user exists
    existing_names = [u.get("name") for u in data.get("users", [])]
    if username in existing_names:
        print(f"Error: User '{username}' already exists.")
        return

    privilege = input("Privilege (e.g., admin, manager, member): ").strip()
    if not privilege:
        print("Error: Privilege cannot be empty.")
        return

    password = input("Password: ").strip()
    if not password:
        print("Error: Password cannot be empty.")
        return

    confirm = input("Confirm password: ").strip()
    if password != confirm:
        print("Error: Passwords do not match.")
        return

    # Add user
    password_hash = hash_password(password)
    data["users"].append({
        "name": username,
        "privilege": privilege,
        "password_hash": password_hash
    })

    save_json(data)
    print(f"User '{username}' (privilege: {privilege}) added successfully.")
    print()
    print("Run 'python convert_auth.py' to create the .dat file for deployment.")


def show_users():
    """Show current users with privileges (no passwords)."""
    data = load_json()
    users = data.get("users", [])

    if not users:
        print("No users found.")
        return

    print("Current users:")
    print("-" * 40)
    print(f"  {'No.':<4} {'Username':<15} {'Privilege':<15}")
    print("-" * 40)
    for i, user in enumerate(users, 1):
        name = user.get('name', 'Unknown')
        privilege = user.get('privilege', '(none)')
        print(f"  {i:<4} {name:<15} {privilege:<15}")


def change_password():
    """Interactively change password for an existing user."""
    data = load_json()
    users = data.get("users", [])

    if not users:
        print("No users found.")
        return

    print("Change password")
    print("-" * 30)

    # Show existing users
    print("Existing users:")
    for i, user in enumerate(users, 1):
        print(f"  {i}. {user.get('name', 'Unknown')}")
    print()

    username = input("Username: ").strip()
    if not username:
        print("Error: Username cannot be empty.")
        return

    # Find user
    user_index = None
    for i, user in enumerate(users):
        if user.get("name") == username:
            user_index = i
            break

    if user_index is None:
        print(f"Error: User '{username}' not found.")
        return

    new_password = input("New password: ").strip()
    if not new_password:
        print("Error: Password cannot be empty.")
        return

    confirm = input("Confirm new password: ").strip()
    if new_password != confirm:
        print("Error: Passwords do not match.")
        return

    # Update password
    password_hash = hash_password(new_password)
    data["users"][user_index]["password_hash"] = password_hash

    save_json(data)
    print(f"Password for '{username}' changed successfully.")
    print()
    print("Run 'python convert_auth.py' to update the .dat file for deployment.")


def change_privilege():
    """Interactively change privilege for an existing user."""
    data = load_json()
    users = data.get("users", [])

    if not users:
        print("No users found.")
        return

    print("Change privilege")
    print("-" * 40)

    # Show existing users with current privileges
    print("Existing users:")
    print(f"  {'No.':<4} {'Username':<15} {'Privilege':<15}")
    print("-" * 40)
    for i, user in enumerate(users, 1):
        name = user.get('name', 'Unknown')
        privilege = user.get('privilege', '(none)')
        print(f"  {i:<4} {name:<15} {privilege:<15}")
    print()

    username = input("Username: ").strip()
    if not username:
        print("Error: Username cannot be empty.")
        return

    # Find user
    user_index = None
    for i, user in enumerate(users):
        if user.get("name") == username:
            user_index = i
            break

    if user_index is None:
        print(f"Error: User '{username}' not found.")
        return

    current_privilege = users[user_index].get('privilege', '(none)')
    print(f"Current privilege: {current_privilege}")

    new_privilege = input("New privilege: ").strip()
    if not new_privilege:
        print("Error: Privilege cannot be empty.")
        return

    # Update privilege
    data["users"][user_index]["privilege"] = new_privilege

    save_json(data)
    print(f"Privilege for '{username}' changed to '{new_privilege}'.")
    print()
    print("Run 'python convert_auth.py' to update the .dat file for deployment.")


def main():
    parser = argparse.ArgumentParser(
        description="Convert auth_users.json to auth_users.dat for Streamlit Cloud"
    )
    parser.add_argument(
        '-a', '--add-user',
        action='store_true',
        help='Add a new user interactively'
    )
    parser.add_argument(
        '-c', '--change-password',
        action='store_true',
        help='Change password for an existing user'
    )
    parser.add_argument(
        '-p', '--change-privilege',
        action='store_true',
        help='Change privilege for an existing user'
    )
    parser.add_argument(
        '-s', '--show',
        action='store_true',
        help='Show current users with privileges'
    )
    parser.add_argument(
        '-d', '--decode',
        action='store_true',
        help='Decode .dat file back to readable format'
    )

    args = parser.parse_args()

    if args.add_user:
        add_user()
    elif args.change_password:
        change_password()
    elif args.change_privilege:
        change_privilege()
    elif args.show:
        show_users()
    elif args.decode:
        decode_dat()
    else:
        convert_to_dat()


if __name__ == "__main__":
    main()
