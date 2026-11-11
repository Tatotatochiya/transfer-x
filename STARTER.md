# Starter: TransferX running on your machine

This takes you from a fresh clone to a working app with real data and demo deals, in about 15
minutes. You don't need an API-Football key or an AI key. The restore, migrations, club onboarding,
demo seed and account scripts were checked against a fresh database on 2026-11-11.

Afterwards, read [`docs/PRODUCT_SPEC.md`](docs/PRODUCT_SPEC.md) for what TransferX is, and
[`docs/SESSION_HANDOVER.md`](docs/SESSION_HANDOVER.md) for what's in progress.

---

## 1. What you need

- **Docker** with Compose v2 (`docker compose version`). Docker runs the database, the API, the
  frontend and a local mailbox.
- **Git.**
- **Node 20** only if you want to run the frontend's tests or dev server outside Docker.
- **Python 3.12** only if you want to run the API outside Docker.

Ports 5173, 8001, 8025 and 5432 must be free.

## 2. Create `.env`

```bash
cp .env.example .env
```

Then edit `.env`:

| Setting | What to do |
|---|---|
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | Leave as they are for local work, or choose your own. |
| `JWT_SECRET_KEY` | **Set it.** Any long random string: `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `DATABASE_URL` | **Leave it unset.** It overrides the `POSTGRES_*` values. |
| `APISPORTS_KEY` | Optional. Only for the data refresh and the backfill scripts (step 6). |
| `LLM_MODEL` + one of `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `DEEPSEEK_API_KEY` | Optional. Switches on Ask TransferX, briefings and the ✦ advice. Without a key those features say they're unavailable. |
| `LITE_DEFAULT_ON` | `true` opens club accounts in Lite mode. Set `false` if you'll mostly work in the full app. |
| `DEMO_ENABLED` | `true` lets tester accounts start demo runs. |

Email needs no setup locally: every email the API sends lands in Mailpit at
http://localhost:8025. Every other setting is described in `.env.example`.

**Never commit `.env`** (it's in `.gitignore`), and never put production credentials in it.

## 3. Start the database and load the reference data

The repo carries a snapshot of the development database:
`backend/seeds/transferx_reference_20260808.dump`. It holds 7,914 players, 11 leagues, 99 world
teams with crests, valuations, three clubs (Arsenal, Chelsea, Liverpool) and the demo accounts.
Restore it into the **empty** database before the API first starts:

```bash
docker compose up -d db mailpit

docker compose cp backend/seeds/transferx_reference_20260808.dump db:/tmp/ref.dump
docker compose exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner /tmp/ref.dump'
```

`pg_restore` prints nothing when it succeeds.

> **Already started the API before restoring?** The API created an empty schema, and the restore
> will collide with it. Start again with an empty database:
> `docker compose down -v && docker compose up -d db mailpit`, then restore.
> `down -v` deletes the local database volume.

## 4. Start everything

```bash
docker compose up --build -d
docker compose logs -f api      # wait for "Starting uvicorn", then Ctrl+C
```

When the API starts it migrates the database to the latest revision. The snapshot is at revision
0059, so the first start applies about 50 migrations.

| What | Where |
|---|---|
| The app | http://localhost:5173 |
| API and Swagger | http://localhost:8001/docs |
| Mailpit (local email) | http://localhost:8025 |
| PostgreSQL | `localhost:5432`, with the user and password from `.env` |

## 5. Fill in the clubs and demo deals

```bash
# All 20 Premier League clubs on TransferX: owner accounts, budgets, a contract for every player
docker compose exec api python scripts/onboard_premier_league_clubs.py

# Six demo deals, one at each stage, built through the real services
docker compose exec api python scripts/seed_demo.py

# A staff account for the admin pages (/admin)
docker compose exec api python scripts/create_superuser.py admin@example.com password123
```

The first two are safe to re-run: a club that's already on TransferX is skipped. `seed_demo.py
--refresh` removes the demo deals and builds them again (`--reset` only removes them). Both
have `--dry-run`.

### Signing in

Every demo account uses the password **`password123`**. You can sign in with the full email or
just the part before the `@`.

| Account | Sign in as |
|---|---|
| A Premier League club | `arsenal`, `chelsea`, `liverpool`, `manchestercity`, `tottenham`, … (`<club name, no spaces>@transferx.com`) |
| An agent | `james.mitchell@elitesports.com`, `marco.rossi@globalfootball.com`, `sofia.reyes@premiertalent.com` |
| Staff (admin pages) | `admin@example.com`, once you've run `create_superuser.py` |

Club accounts open in **Lite** mode by default. Use "Switch to full app" in the top bar (or set
`LITE_DEFAULT_ON=false`).

To make your own club:

```bash
docker compose exec api python scripts/create_user.py you@example.com a-password "My Club"
```

## 6. Optional: backfill and refresh real data

The snapshot is enough for development. The scripts below call API-Football, so they need
`APISPORTS_KEY` and use your daily request quota. Each one explains itself at the top of the file.

| Command (prefix with `docker compose exec api`) | What it does |
|---|---|
| `python -m app.jobs.daily_refresh --force` | The scheduled data refresh, run by hand: player stats, injuries, form, real-world transfers, valuations (`--steps stats,form` for some of them). |
| `python scripts/backfill_player_history.py` | Season stats, transfer history and injuries for the player profile ledger. |
| `python scripts/populate_world_teams.py` | World teams and crests, from player stats. |
| `python backfill_2025.py` | The 2025 season for the top five European leagues. Heavy on quota. |

These need no key. Each is a one-off that fixes up demo data, and each is safe to skip:

| Command | What it does |
|---|---|
| `python scripts/mock_contract_end_dates.py` | Contract end dates for contracted players, so expiring-contract features have data. |
| `python scripts/backfill_contract_wages.py` | Wages on contracts that have none, added to each club's wage bill. |
| `python scripts/allocate_players_to_agents.py` | An agent for every signable player. |
| `python scripts/rename_agent_emails.py` | Short sign-in names for agents (`<name>@transferx.com`). |
| `python scripts/repair_player_statuses.py` | Re-derives player statuses (free agent, contracted, external). |

## 7. Everyday work

```bash
# Backend: a code change needs a restart (the API mounts backend/)
docker compose restart api
docker compose exec -T api python -m pytest -q          # tests (SQLite in memory)
docker compose exec -T api alembic revision -m "what it does"
docker compose exec -T api alembic upgrade head

# Frontend: the container is a built image, so UI changes need a rebuild
docker compose build frontend && docker compose up -d frontend

# Frontend checks, outside Docker (Node 20)
cd frontend && npm ci
npx tsc -b && npx vitest run
npm run check:design            # type scale and colour rules only
npm run dev                     # Vite dev server on :5173 against the API on :8001
```

> `npm run dev` uses port 5173 too. Stop the frontend container first
> (`docker compose stop frontend`).

Before you change the UI, read [`docs/design-system/RULES.md`](docs/design-system/RULES.md) and
the typography and colour roles in [`docs/design-system/TOKENS.md`](docs/design-system/TOKENS.md).
The design guard test fails on raw Tailwind sizes (`text-sm`, `text-[13px]`), opacity tints and
stray `uppercase`.

## 8. When something's wrong

| Symptom | Fix |
|---|---|
| `pg_restore` errors with "already exists" | The API started first and created the schema. `docker compose down -v`, then step 3 again. |
| The API exits during migrations | `docker compose logs api` names the migration. Check `DATABASE_URL` isn't set in `.env`. |
| A UI change doesn't show | Rebuild the frontend image (step 7). |
| Sign-in fails for a demo account | You skipped step 3, so the database has no demo accounts. Make one with `create_user.py`. |
| Ask TransferX says it's unavailable | Set `LLM_MODEL` and its key in `.env`, then `docker compose up -d api`. |
| Port already in use | Another stack or a local Postgres is using it. Stop it, or change the left-hand port in `docker-compose.yml`. |
| You want a clean slate | `docker compose down -v` deletes the database. Then restart from step 3. |

## 9. Where to go next

- [`docs/README.md`](docs/README.md): how the documentation is organised.
- [`docs/architecture/system-overview.md`](docs/architecture/system-overview.md): the services and how they fit.
- [`docs/engineering/`](docs/engineering/README.md): coding standards, testing, migrations, API reference.
- [`docs/product/workflows/transfer-lifecycle.md`](docs/product/workflows/transfer-lifecycle.md): how a transfer runs, end to end.
- [`docs/operations/environments-and-deployment.md`](docs/operations/environments-and-deployment.md): staging and production (Railway).
