"""Reset the password of every user account to the default value.

Usage:
    python reset_passwords.py

Connects to whichever database DATABASE_URL points at (local SQLite by default,
or set DATABASE_URL to your production Postgres before running to reset the
deployed site, e.g.:
    $env:DATABASE_URL="postgresql://user:pass@host/db" ; python reset_passwords.py
)
"""
from database import init_db, db_session
from models import User

DEFAULT_PASSWORD = "123"


def main():
    init_db()
    users = db_session.query(User).all()
    if not users:
        print("No user accounts found.")
        return
    for user in users:
        user.set_password(DEFAULT_PASSWORD)
    db_session.commit()
    print(f"Reset password for {len(users)} account(s) to: {DEFAULT_PASSWORD}")
    for user in db_session.query(User).all():
        print(f"  - {user.username} ({user.role})")
    print("\nReminder: change these to something secure where possible.")


if __name__ == "__main__":
    main()
