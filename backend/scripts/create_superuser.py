#!/usr/bin/env python
"""
Create or promote a superuser account.

Usage (local venv, from backend/ dir):
    python scripts/create_superuser.py admin@example.com password123

Usage (inside Docker):
    docker compose exec api python scripts/create_superuser.py admin@example.com password123

If the email already exists the account is promoted to superuser and its
password is updated to the one provided.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.auth.models import User  # noqa: F401 — registers model with metadata
from app.auth.service import hash_password
from app.config import settings


async def main(email: str, password: str) -> None:
    engine = create_async_engine(settings.database_url, echo=False)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async with Session() as db:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if user is None:
            user = User(
                email=email,
                hashed_password=hash_password(password),
                is_active=True,
                is_superuser=True,
            )
            db.add(user)
            await db.commit()
            print(f"Created superuser: {email}")
        else:
            user.hashed_password = hash_password(password)
            user.is_superuser = True
            user.is_active = True
            await db.commit()
            print(f"Updated existing user to superuser: {email}")

    await engine.dispose()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python scripts/create_superuser.py <email> <password>")
        sys.exit(1)

    asyncio.run(main(email=sys.argv[1], password=sys.argv[2]))
