#!/usr/bin/env python
"""
Bootstrap a user + club for TransferX.

Usage (inside Docker):
    docker compose exec api python scripts/create_user.py EMAIL PASSWORD "Club Name"
    docker compose exec api python scripts/create_user.py EMAIL PASSWORD "Club Name" --superuser

Usage (local venv, from backend/ dir):
    python scripts/create_user.py EMAIL PASSWORD "Club Name"
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Allow running from the backend/ directory or the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.auth import service as auth_service
from app.clubs import service as clubs_service
from app.config import settings


async def main(email: str, password: str, club_name: str, superuser: bool) -> None:
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as db:
        async with db.begin():
            try:
                user = await auth_service.create_user(db, email, password)
            except ValueError as exc:
                print(f"Error: {exc}", file=sys.stderr)
                sys.exit(1)

            if superuser:
                user.is_superuser = True

            club = await clubs_service.create_club(db, user.id, club_name)
            await clubs_service.create_club_finance(db, club.id)

    await engine.dispose()

    role_label = "superuser" if superuser else "user"
    print(f"Created {role_label}: {email}")
    print(f"Club: {club_name}  (id={club.id})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create a TransferX user + club")
    parser.add_argument("email", help="User email address")
    parser.add_argument("password", help="User password")
    parser.add_argument("club_name", help="Club name")
    parser.add_argument(
        "--superuser",
        action="store_true",
        default=False,
        help="Grant superuser (admin) privileges",
    )
    args = parser.parse_args()

    asyncio.run(main(args.email, args.password, args.club_name, args.superuser))
