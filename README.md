# TransferX

A football (soccer) player transfer marketplace — auctions, direct offers, deal rooms, squad finance, scouting, and notifications.

**Stack:** React + FastAPI + PostgreSQL

---

## Repo layout

```
transferx/
├── backend/          FastAPI app (Python 3.12, SQLAlchemy async, Alembic)
├── frontend/         React app (Vite, TypeScript, Tailwind v4)
├── docker-compose.yml
└── .env.example
```

---

## Quick start

```bash
cp .env.example .env
# edit .env — set POSTGRES_PASSWORD and JWT_SECRET_KEY at minimum

docker compose up --build
```

| Service | URL |
|---|---|
| React frontend | http://localhost:5173 |
| FastAPI backend | http://localhost:8001 |
| API docs (Swagger) | http://localhost:8001/docs |
| PostgreSQL | localhost:5432 |

---

## Backend (FastAPI)

```bash
cd backend

pip install -e ".[dev]"

# Dev server
uvicorn app.main:app --reload --port 8001

# Migrations
alembic upgrade head
alembic revision --autogenerate -m "description"

# Tests
pytest
```

### API modules

| Module | Prefix | Description |
|---|---|---|
| Auth | `/auth` | JWT login, refresh, logout, me |
| Clubs | `/clubs` | Club profiles, squad, finance |
| Players | `/players` | Player market, contracts |
| Sales | `/sales` | Listings, auctions, bids |
| Offers | `/offers` | Direct negotiation, counters |
| Deals | `/deals` | Deal stage workflow, notes |
| Scouting | `/scouting` | Shortlists, player interests, targets |
| Notifications | `/notifications` | In-app alerts, preferences |
| Stats | `/stats` | Vendor stats sync (api-sports.io) |
| World | `/world` | Real-world teams and players |
| Vendor | `/vendor` | API-Football client, sync triggers, form computation |
| Admin | `/admin` | Superuser user/club/player/sale management + system stats |
| Search | `/search` | Global cross-entity search |
| WebSocket | `/ws` | Real-time bid and notification updates |

### Alembic migration chain

```
0001 → 0002 → 0003 → 0004 → 0005 → 0006 → 0007 → 0008
     → merge(17e5dc6d) → c1aef17f
     → 0009 → 0010 → 0011 → 0012 → 0013 → 0014 → 0015 → 0016
```

Latest migration: `0016_player_search_views`

---

## Frontend (React)

```bash
cd frontend

npm install
npm run dev       # Vite dev server → http://localhost:5173
npm run build     # Production build → dist/
npm test          # Vitest unit tests
```

### Pages

| Route | Page | Auth |
|---|---|---|
| `/login` | Login | Public |
| `/dashboard` | War Room dashboard | Protected |
| `/players/market` | Player browser | Public |
| `/players/market/:id` | Player profile | Public |
| `/players/compare` | Player comparison tool | Protected |
| `/sales` | Listings browser | Public |
| `/sales/:id` | Sale / auction detail | Public |
| `/sales/mine` | My sales | Protected |
| `/sales/new` | Create listing | Protected (seller) |
| `/clubs` | Club browser | Public |
| `/clubs/:id` | Club profile | Public |
| `/offers/received` | Offer inbox | Protected |
| `/offers/sent` | Sent offers | Protected |
| `/offers/:id` | Offer detail | Protected |
| `/offers/new` | Create offer | Protected (buyer) |
| `/deals` | Deal list | Protected |
| `/deals/:id` | Deal detail + timeline | Protected |
| `/club` | My Club (squad + sales) | Protected |
| `/club/finance` | Budget & finance | Protected |
| `/scouting/shortlists` | Shortlist manager | Protected |
| `/scouting/shortlists/:id` | Shortlist detail | Protected |
| `/notifications` | Notification centre | Protected |
| `/notifications/preferences` | Notification preferences | Protected |
| `/account` | Account settings | Protected |
| `/transfers` | Transfer activity log | Protected |
| `/world/teams/:id` | World team detail | Protected |
| `/admin/*` | Admin panel (12 pages) | Superuser only |

---

## Environment variables

| Var | Purpose |
|---|---|
| `POSTGRES_*` | Database connection |
| `JWT_SECRET_KEY` | JWT signing |
| `APISPORTS_KEY` | Vendor stats sync (api-sports.io) |
| `TRANSFERX_ENABLE_ANTI_SNIPING` | Extend auction deadline on late bids |

---

## Feature highlights

- **Live auctions** — bid ladder updates in real-time via WebSocket (5 min fallback poll); seller accepts winning bid → deal auto-created; anti-sniping config flags present but not yet implemented
- **Offer negotiation** — counter-offer thread with message history and event timeline
- **Deal stage workflow** — AGREEMENT → PAPERWORK → CONFIRMED → COMPLETED; contract created on completion
- **Scouting** — shortlists with priority tiers; player interest tracking (WATCHING / INTERESTED / PRIORITY)
- **Notification preferences** — per-type opt-out; preferences stored server-side, checked before delivery
- **Bid activity history** — sellers see full bid timeline (active + historical) on auction detail
- **Club browser** — filter by country/league, sort by name/country/league/date
- **Open to offers toggle** — squad table toggle directly updates player availability flag
- **Deal activity timeline** — deal detail synthesises creation, notes, and completion into a chronological log
- **Player comparison** — side-by-side stat comparison for up to N players via CompareBar
- **Global search** — cross-entity search across players, clubs, and sales
- **WebSocket** — real-time bid and notification updates (replaces polling where applicable)
- **Admin panel** — 12 superuser pages covering users, clubs, players, sales, offers, deals, vendor sync, and world import
- **Vendor sync** — API-Football (api-sports.io v3) sync for player stats, form scores, and world team data

---

## Development notes

- Login page is login-only — no self-registration UI. Create users via CLI or `POST /auth/register` from the API docs.
- Vendor players have `status=FREE_AGENT` in the DB but display as "Contracted" when `team_name`, `world_team_id`, or `current_club_id` is set (display-layer override applied consistently across all views).
- `select_for_update(of=("self",))` — never bare `select_for_update()` when nullable FK joins are present.
- All monetary values use `formatCurrency()` on the frontend — never render raw numbers from the API.

---

*Last updated: 2026-03-29*
*Status: M0–M8 backend complete (18 migrations, 12 test files); F0–F6 frontend complete + admin panel, player comparison, global search, WebSocket, account settings, transfer activity log*
