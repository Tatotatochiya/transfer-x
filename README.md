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

## Getting started

**New here? Follow [`STARTER.md`](STARTER.md).** It goes from a fresh clone to a running app with
real players, all 20 Premier League clubs and demo deals at every stage, with no API keys. It covers
`.env`, restoring the reference database snapshot, the setup scripts, demo sign-ins and common
problems.

The short version, once `.env` exists (`cp .env.example .env`, then set `JWT_SECRET_KEY`):

```bash
docker compose up -d db mailpit
docker compose cp backend/seeds/transferx_reference_20260808.dump db:/tmp/ref.dump
docker compose exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner /tmp/ref.dump'
docker compose up --build -d
docker compose exec api python scripts/onboard_premier_league_clubs.py
docker compose exec api python scripts/seed_demo.py
```

| Service | URL |
|---|---|
| Frontend | http://localhost:5173 (demo clubs sign in as `arsenal` … with `password123`) |
| API | http://localhost:8001 (Swagger at `/docs`) |
| Mailpit (every email sent locally) | http://localhost:8025 |
| PostgreSQL | localhost:5432 |

**What runs:**
- **The API** mounts `backend/` and applies migrations when it starts, so `docker compose restart api` picks up backend changes.
- **The frontend** is a built production image, so UI changes need `docker compose build frontend && docker compose up -d frontend`.

## Everyday commands

```bash
# Backend tests (SQLite in memory)
docker compose exec -T api python -m pytest -q
# Migrations
docker compose exec -T api alembic upgrade head
docker compose exec -T api alembic revision -m "description"
# The data refresh, by hand
docker compose exec -T api python -m app.jobs.daily_refresh --force

# Frontend type check and tests (includes the design guard; `npm run check:design` runs it alone)
cd frontend && npx tsc -b && npx vitest run
```

More in [`docs/engineering/`](docs/engineering/README.md): testing, migrations, conventions.

## Environment

Every setting is listed and explained in [`.env.example`](.env.example); `STARTER.md` step 2 says which to set.
- **Required:** `POSTGRES_*` and `JWT_SECRET_KEY`. Leave `DATABASE_URL` unset locally (Railway sets it).
- **Optional:** `APISPORTS_KEY` (data refresh and backfills), `LLM_MODEL` with a provider key (the AI assistant), `SMTP_*` (email; Mailpit locally), `VAPID_*` (phone push), `SLACK_WEBHOOK_URL`, `FRONTEND_BASE_URL`, `LITE_DEFAULT_ON`, `DEMO_ENABLED`.

Production runs on Railway: see [`docs/operations/environments-and-deployment.md`](docs/operations/environments-and-deployment.md).
