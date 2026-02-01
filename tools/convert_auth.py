#!/usr/bin/env python3
"""
Authentication File Conversion Script

Converts auth_users.json to auth_users.dat (Base64-encoded pickle format)
for deployment to Streamlit Cloud.

Usage:
    python convert_auth.py                       # Interactive menu (recommended)
    python convert_auth.py -a/--add-user         # Add a new user directly
    python convert_auth.py -c/--change-password  # Change password directly
    python convert_auth.py -p/--change-privilege # Change privilege directly
    python convert_auth.py -s/--show             # Show current users
    python convert_auth.py -d/--decode           # Decode DAT back to readable format

Interactive Menu Options:
    1. Convert JSON to DAT (for deployment)
    2. Add a new user
    3. Change password for existing user
    4. Change privilege for existing user
    5. Show current users
    6. Decode DAT file (for debugging)
    0. Exit

Workflow for Deployment:
    1. Run python convert_auth.py (interactive menu)
    2. Select option 2 to add users, or edit auth_users.json manually
    3. Select option 1 to create auth_users.dat
    4. Commit auth_users.dat (not .json) to repository
    5. Deploy to Streamlit Cloud
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


def interactive_menu():
    """Show interactive menu and execute selected operation in a loop."""
    while True:
        print()
        print("Authentication File Management")
        print("=" * 40)
        print()
        print("Select an operation:")
        print("  1. Convert JSON to DAT (for deployment)")
        print("  2. Add a new user")
        print("  3. Change password for existing user")
        print("  4. Change privilege for existing user")
        print("  5. Show current users")
        print("  6. Decode DAT file (for debugging)")
        print("  0. Exit")
        print()

        choice = input("Enter choice [0-6]: ").strip()

        if choice == '1':
            print()
            convert_to_dat()
        elif choice == '2':
            print()
            add_user()
        elif choice == '3':
            print()
            change_password()
        elif choice == '4':
            print()
            change_privilege()
        elif choice == '5':
            print()
            show_users()
        elif choice == '6':
            print()
            decode_dat()
        elif choice == '0':
            print("Exiting.")
            break
        else:
            print(f"Invalid choice: '{choice}'")


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

    # If any specific option is given, execute it directly
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
        # No options given - show interactive menu
        interactive_menu()


if __name__ == "__main__":
    main()
