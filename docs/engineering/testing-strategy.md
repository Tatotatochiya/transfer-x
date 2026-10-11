---
title: "Testing Strategy"
last_updated: 2026-10-11
status: Active
owner: "TODO — assign a Technical Owner"
---

# Testing Strategy

## Purpose

How TransferX is tested, how to run the tests, and where the suites stand.

## Scope

In scope: frameworks, conventions, commands, current totals.
Out of scope: CI (there is none yet).

## Table of Contents

- [Backend](#backend)
- [Frontend](#frontend)
- [Beyond the suites](#beyond-the-suites)
- [Current totals](#current-totals)
- [Related documents](#related-documents)

## Backend

**Framework.** Pytest with pytest-asyncio, in `backend/tests/` (70 files). Each test gets a fresh in-memory SQLite database built from the models (`tests/conftest.py`).

**Fixtures** register clubs through the API, and superusers are made by flagging a registered user. Self-registration is switched on for tests only.

**No outside calls.** Tests never call API-Football, a model, Slack, push or exchange rates: `conftest.py` blanks those settings, and tests that need them use fakes (e.g. a scripted `chat_with_tools`, a fake API client).

**Monitoring writes** (job runs, errors) are pointed at the test database, or at nothing, by an autouse fixture. They never reach a real database.

```bash
docker compose exec -T api python -m pytest -q -p no:warnings                 # full suite, about 14 minutes
docker compose exec -T api python -m pytest -q tests/test_offers.py -k accept # one file or test
```

**Not covered by SQLite:** row locks (verified against Postgres by hand) and migrations (see [database-migrations](./database-migrations.md#gotchas)).

## Frontend

**Framework.** Vitest with Testing Library, files beside the code as `*.test.ts(x)`. `src/test/utils.tsx` renders with the providers. Most tests mock `lib/api` directly; MSW is installed.

**Commands:**
- `npx tsc -b` is the type check, and part of the build. Use `-b`: plain `tsc --noEmit` checks nothing in this project.
- `npx vitest run` runs the tests.

## Beyond the suites

- **AI analyst evaluation:** `backend/scripts/analyst_eval.py`, 72 questions against the real model. It costs model calls, so it's not run in tests.
- **Browser checks:** changes to UI are checked in a real browser against the running stack before shipping.
- **Valuation calibration:** `scripts/valuation_archetypes.py` and `scripts/valuation_backtest.py`.

## Current totals

As of 2026-10-11:
- **Backend:** 877 passed.
- **Frontend:** vitest 250 passed.
- **Type check:** `tsc -b` has 0 errors.

## Related documents

- [`coding-standards.md`](./coding-standards.md)
- [`database-migrations.md`](./database-migrations.md)
