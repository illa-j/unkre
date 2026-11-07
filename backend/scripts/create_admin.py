"""Create an admin account for the /admins API and the admin panel.

Run from the backend directory:

    PYTHONPATH=src .venv/bin/python scripts/create_admin.py owner --owner
    PYTHONPATH=src .venv/bin/python scripts/create_admin.py operator

The password is read from the ADMIN_PASSWORD environment variable, or prompted
for interactively. The script is idempotent: an existing username is left
untouched and reported instead of overwritten.

Inside the Compose stack:

    docker compose run --rm web python scripts/create_admin.py owner --owner
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import os
import sys

from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from adapters.database import session_scope
from adapters.database.models import AdminModel


async def create(username: str, password: str, *, is_owner: bool) -> bool:
    async with session_scope() as session:
        existing = await session.scalar(
            select(AdminModel).where(AdminModel.username == username)
        )
        if existing is not None:
            print(f"admin '{username}' already exists; nothing changed")
            return False
        session.add(AdminModel.create(username, password, is_owner=is_owner))
    print(f"created admin '{username}'" + (" as owner" if is_owner else ""))
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Create an admin account")
    parser.add_argument("username")
    parser.add_argument("--owner", action="store_true", help="grant owner rights")
    args = parser.parse_args()

    password = os.environ.get("ADMIN_PASSWORD") or getpass.getpass("Password: ")
    if len(password) < 10:
        raise SystemExit("Password must be at least 10 characters long")
    try:
        asyncio.run(create(args.username.strip(), password, is_owner=args.owner))
    except (OSError, OperationalError) as exc:
        raise SystemExit(
            "Cannot connect to Postgres. The production Compose stack does not "
            "publish the database port; run the script inside the stack instead:\n"
            "  ADMIN_PASSWORD=... docker compose run --rm web python scripts/create_admin.py <username> --owner"
        ) from exc


if __name__ == "__main__":
    sys.exit(main())
