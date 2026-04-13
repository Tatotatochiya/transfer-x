# Transfer-X

A football (soccer) player transfer marketplace — auctions, direct offers, deal rooms, squad finance, scouting, analytics, and notifications.

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
| Clubs | `/clubs` | Club profiles, squad, finance, expiring contracts |
| Players | `/players` | Player market, contracts, career history, injuries |
| Sales | `/sales` | Listings, auctions, bids |
| Offers | `/offers` | Direct negotiation, counters, message thread |
| Deals | `/deals` | Deal stage workflow, notes, execute transfer |
| Scouting | `/scouting` | Shortlists, player interests, market hits |
| Notifications | `/notifications` | In-app alerts, preferences, system broadcast |
| Stats | `/stats` | Vendor stats sync (api-sports.io) |
| World | `/world` | Real-world teams and players |
| Vendor | `/vendor` | API-Football client, sync triggers, form computation |
| Fixtures | `/fixtures` | Fixture cache from API-Football, auto-bootstraps WorldTeam |
| Transfer Window | `/transfers/window` | Window open/close management, enforcement on sales/offers |
| Analytics | `/analytics` | Page view/click event ingestion, admin overview + trend |
| Admin | `/admin` | Superuser management: users, clubs, players, sales, deals, offers, health report, broadcast |
| Search | `/search` | Global cross-entity search (players, clubs, sales) |
| WebSocket | `/ws` | Real-time bid and notification updates |

### Background jobs (APScheduler)

Runs in-process on startup:

| Job | Interval | Description |
|---|---|---|
| `close_expired_sales` | 1 min | Closes auction/fixed listings past their end date |
| `expire_stale_offers` | 5 min | Expires offers past their deadline |
| `notify_upcoming_events` | 1 hr | Sends reminders for expiring contracts and upcoming deadlines |

### Alembic migration chain

```
0001 → 0002 → 0003 → 0004 → 0005 → 0006 → 0007 → 0008
     → merge(17e5dc6d) → c1aef17f
     → 0009 → 0010 → 0011 → 0012 → 0013 → 0014 → 0015 → 0016
     → 0017 → 0018 → 0019 → 0020 → 0021 → 0022 → 0023 → 0024
```

| Migration | Description |
|---|---|
| 0017 | Analytics events table |
| 0018 | Contract club valuation field |
| 0019 | Player bio fields |
| 0020 | Fixtures cache table |
| 0021 | Player stats extra fields |
| 0022 | Player career + injury tables |
| 0023 | Transfer windows table |
| 0024 | SYSTEM_BROADCAST notification type |

Latest migration: `0024_system_broadcast_notification`

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
| `/players/market/:id` | Player profile + career/injury history | Public |
| `/compare` | Player comparison tool | Public |
| `/sales` | Listings browser | Public |
| `/sales/:id` | Sale / auction detail + order book | Public |
| `/clubs` | Club browser | Public |
| `/clubs/:id` | Club profile | Public |
| `/world/teams/:id` | World team detail + fixtures | Public |
| `/transfers` | Transfer activity (feed + analytics) | Public |
| `/offers/received` | Offer inbox | Protected |
| `/offers/sent` | Sent offers | Protected |
| `/offers/:id` | Offer detail + thread | Protected |
| `/offers/new` | Create offer | Protected |
| `/deals` | Deal list | Protected |
| `/deals/:id` | Deal detail + stage tracker + timeline | Protected |
| `/club` | My Club (squad + sales + fixtures) | Protected |
| `/club/finance` | Budget & finance | Protected |
| `/scouting/shortlists` | Shortlist manager | Protected |
| `/scouting/shortlists/:id` | Shortlist detail | Protected |
| `/notifications` | Notification centre | Protected |
| `/account` | Account settings + notification preferences | Protected |
| `/admin` | Admin dashboard | Superuser |
| `/admin/users` | User management | Superuser |
| `/admin/clubs` | Club management | Superuser |
| `/admin/clubs/:id` | Club detail | Superuser |
| `/admin/players` | Player management | Superuser |
| `/admin/players/:id` | Player detail | Superuser |
| `/admin/sales` | Sales oversight | Superuser |
| `/admin/deals` | Deals oversight + force advance | Superuser |
| `/admin/offers` | Offers oversight | Superuser |
| `/admin/vendor` | Vendor sync controls | Superuser |
| `/admin/analytics` | Page view + user activity analytics | Superuser |
| `/admin/windows` | Transfer window create/delete | Superuser |
| `/admin/health` | System health report (stale deals, orphaned contracts) | Superuser |

---

## Environment variables

| Var | Purpose |
|---|---|
| `POSTGRES_*` | Database connection |
| `JWT_SECRET_KEY` | JWT signing |
| `APISPORTS_KEY` | Vendor stats sync (api-sports.io) |
| `TRANSFERX_ENABLE_ANTI_SNIPING` | Extend auction deadline on late bids (config present, not yet implemented) |

---

## Feature highlights

- **War Room dashboard** — transfer window countdown banner, urgent actions (deals at CONFIRMED, counters needing response), budget bars (transfer + wage with spent/committed/free split), shortlist pulse (shortlisted players with open sales), expiring contracts panel
- **Live auctions** — bid ladder updates in real-time via WebSocket; seller accepts winning bid → deal auto-created
- **Offer negotiation** — counter-offer thread with interleaved messages and event timeline
- **Deal stage workflow** — AGREEMENT → PAPERWORK → CONFIRMED ("Ready to Execute") → COMPLETED; contract created on completion; execute transfer button on CONFIRMED stage
- **Transfer windows** — admin-managed open/close periods; sale and offer creation blocked when window is closed
- **Scouting** — shortlists with priority tiers; player interest tracking (WATCHING / INTERESTED / PRIORITY); market-hits endpoint surfaces shortlisted players with live sales
- **Fixtures** — fixture cache from API-Football; team names link to WorldTeam detail page; bootstraps WorldTeam records automatically if missing
- **Player career & injury history** — transfer history panel and injury/sidelined timeline on player detail
- **Analytics** — page view / click event ingestion from frontend; admin overview with top pages, user activity, daily trend
- **System broadcast** — admin can push a SYSTEM_BROADCAST notification to all active users
- **System health report** — admin health page surfaces stale deals, orphaned contracts, and other data integrity issues with severity badges
- **Notification preferences** — per-type opt-out stored server-side, checked before delivery
- **Club browser** — filter by country/league; club detail includes squad stats, top performers, finance summary
- **Player comparison** — side-by-side stat comparison via floating CompareBar
- **Global search** — cross-entity search across players, clubs, and sales
- **Admin panel** — 15 superuser pages covering all entities plus vendor sync, analytics, transfer windows, and health

---

## Development notes

- Login page is login-only — no self-registration UI. Create users via CLI or `POST /auth/register` from the API docs.
- Vendor players have `status=FREE_AGENT` in the DB but display as "Contracted" when `team_name`, `world_team_id`, or `current_club_id` is set (display-layer override applied consistently across all views).
- `select_for_update(of=("self",))` — never bare `select_for_update()` when nullable FK joins are present.
- All monetary values use `formatCurrency()` on the frontend — never render raw numbers from the API.
- Page tracking is wired via `usePageTracking` hook in the root layout — fires PAGE_VIEW on route change and PAGE_LEAVE on unmount.

---

*Last updated: 2026-04-13*
*Status: Backend complete (24 migrations, 17 modules, 12 test files); Frontend complete (33 routes, 15 admin pages, Vitest + MSW testing infra)*
