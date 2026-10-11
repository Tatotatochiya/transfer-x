# TransferX

A platform for professional football transfers. Selling clubs, buying clubs, agents and players run a transfer end to end: enquiries, listings, offers and counters, the deal room, personal terms, paperwork and completion. Around that sit squad finance, approvals, scouting, valuations, an AI assistant, Lite mode for directors, and phone notifications.

**Stack:** React 19 + Vite + TypeScript + Tailwind v4 · FastAPI + SQLAlchemy (async) + Alembic · PostgreSQL

**Documentation:** start at [`docs/PRODUCT_SPEC.md`](docs/PRODUCT_SPEC.md). Architecture, modules, jobs, operations and decisions all live under [`docs/`](docs/README.md). This file only covers getting it running.

---

## Repo layout

```
transfer-x/
├── backend/          FastAPI app (Python 3.12): app/, migrations/, tests/, scripts/
├── frontend/         React app (Vite, TypeScript, Tailwind v4)
├── docs/             Documentation
├── docker-compose.yml
└── .env.example
```

## Quick start (Docker)

```bash
cp .env.example .env
# set POSTGRES_PASSWORD and JWT_SECRET_KEY at minimum; APISPORTS_KEY and an LLM key are optional

docker compose up --build
```

| Service | URL |
|---|---|
| Frontend | http://localhost:5173 |
| API | http://localhost:8001 (Swagger at `/docs`) |
| Mailpit (every email sent locally) | http://localhost:8025 |
| PostgreSQL | localhost:5432 |

**What runs:**
- **The API** mounts `backend/` and applies migrations when it starts, so `docker compose restart api` picks up backend changes.
- **The frontend** is a built production image, so UI changes need `docker compose build frontend && docker compose up -d frontend`.

**First accounts.** Accounts normally come from invitations. Locally:

```bash
docker compose exec api python scripts/create_superuser.py admin@example.com password123
docker compose exec api python scripts/create_user.py owner@club.com password123 "My Club"
docker compose exec api python scripts/seed_demo.py            # demo deals at every stage (needs the demo clubs and players; see backend/seeds/)
```

## Everyday commands

```bash
# Backend tests (SQLite in memory)
docker compose exec -T api python -m pytest -q
# Migrations
docker compose exec -T api alembic upgrade head
docker compose exec -T api alembic revision -m "description"
# The data refresh, by hand
docker compose exec -T api python -m app.jobs.daily_refresh --force

# Frontend type check and tests
cd frontend && npx tsc -b && npx vitest run
```

More in [`docs/engineering/`](docs/engineering/README.md): testing, migrations, conventions.

## Environment

See [`.env.example`](.env.example).
- **Required:** `POSTGRES_*` (or `DATABASE_URL`) and `JWT_SECRET_KEY`.
- **Optional:**
  - `APISPORTS_KEY` for API-Football data;
  - `LLM_MODEL` with a provider key for the AI assistant;
  - `SMTP_*` for email;
  - `VAPID_*` for phone push;
  - `SLACK_WEBHOOK_URL` for job and monitoring messages;
  - `FRONTEND_BASE_URL` for links in emails and Slack.

Production runs on Railway: see [`docs/operations/environments-and-deployment.md`](docs/operations/environments-and-deployment.md).
