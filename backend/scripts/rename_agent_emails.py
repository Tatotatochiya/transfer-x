#!/usr/bin/env python
"""
Development / demo: give every agent a short sign-in name.

Sign-in accepts the part of the email before the "@" as a username, so an
agent at `jorge.mendes.gestifute.consulting@example.com` had to type all of
that. This renames each agent's email to `<name>@transferx.com`, where
<name> is their display name, lower-case and joined ("Jorge Mendes" →
`jorgemendes`), as the clubs' accounts are. A name already taken by another
account gets a number (`jorgemendes2`). Passwords are unchanged.

The email is also where TransferX sends the agent's mail, so after this,
mail for these agents goes to @transferx.com addresses (Mailpit locally).

Idempotent: an agent already on @transferx.com is skipped. One transaction;
--dry-run prints the renames and writes nothing.

Usage (inside Docker, or a shell on the Railway API service):
    python scripts/rename_agent_emails.py --dry-run
    python scripts/rename_agent_emails.py
"""

import argparse
import asyncio
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import backfill_demo_squad_contracts  # noqa: F401,E402  (registers every model)
from app.auth.models import AgentProfile, User, UserType  # noqa: E402
from app.config import settings  # noqa: E402

DOMAIN = "transferx.com"


def short_name(display_name: str, fallback: str) -> str:
    name = re.sub(r"[^a-z0-9]", "", display_name.lower())
    return name or re.sub(r"[^a-z0-9]", "", fallback.lower()) or "agent"


async def main(dry_run: bool) -> None:
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as db:
        taken = {e.split("@")[0] for e in (await db.execute(select(func.lower(User.email)))).scalars()}
        rows = (await db.execute(
            select(User, AgentProfile).join(AgentProfile, AgentProfile.user_id == User.id)
            .where(User.user_type == UserType.AGENT).order_by(User.created_at)
        )).all()
        renamed = 0
        for user, profile in rows:
            if user.email.lower().endswith(f"@{DOMAIN}"):
                print(f"  {user.email}: already short — skipped")
                continue
            base = short_name(profile.display_name, user.email.split("@")[0])
            name, n = base, 2
            while name in taken:
                name, n = f"{base}{n}", n + 1
            taken.add(name)
            new_email = f"{name}@{DOMAIN}"
            print(f"  {profile.display_name} ({profile.agency_name}): {user.email} → {new_email}  (sign in as '{name}')")
            user.email = new_email
            renamed += 1
        print(f"Agents renamed: {renamed} of {len(rows)}")
        if dry_run:
            await db.rollback()
            print("Dry run — nothing written.")
        else:
            await db.commit()
            print("Written.")
    await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("--dry-run", action="store_true")
    asyncio.run(main(parser.parse_args().dry_run))
