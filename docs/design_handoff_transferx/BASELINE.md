# Redesign baseline — recorded at Phase 0

Recorded 2026-08-10, branch `redesign/ui-light-theme`, before any redesign code changed. Every later phase's "no new failures" done-criterion is measured against this file, not against "fully green" — the frontend suite was not green before this work started.

## Backend

`cd backend && python -m pytest tests/ -q` → **403 passed**, 26 test files (`backend/tests/test_*.py`), 0 failed.

## Frontend

`cd frontend && npx vitest run` → **96 passed, 23 failed**, 9 test files (4 failing, 5 clean). All 23 failures are pre-existing and confirmed unrelated to product behavior (missing `CompareProvider` test wrapper, selectors stale from an earlier unrelated redesign of these components, one deliberate label rename never reflected in its test) — see `docs/DEMO_READINESS_AUDIT.md` finding M11 for the full root-cause breakdown.

The exact 23, so later phases can diff the *list*, not just the count — a failure disappearing because a phase happens to touch that selector is a bonus; a *new* name appearing here is a real regression:

- `src/lib/badges.test.ts` — `dealStageLabel > CONFIRMED → Confirmed` (1)
- `src/components/players/PlayerCard.test.tsx` — `PlayerCard >` (13): renders player name · shows team_name when current_club is null · prefers current_club.name over team_name when both present · shows Free Agent when both current_club and team_name are null · shows Contracted badge when team_name is set (vendor player) · shows Open badge when player is open to offers · does not show Open badge when player is not open to offers · shows position badge · shows age and nationality · shows initial letter avatar when no photo · renders photo img when photo_url is set · renders form badge when formScore provided · does not render form badge when formScore is null
- `src/components/players/PlayerFilters.test.tsx` — `PlayerFilters >` (7): renders search, position, status, sort controls · calls onChange with correct position when position selected · toggles open_to_offers on click · shows Clear all button only when filters are active · resets to defaults when Clear all clicked · calls onChange with min_age when age input changes · calls onChange with nationality when nationality input changes
- `src/components/players/StatsPanel.test.tsx` — `StatsPanel >` (2): shows team name and season header · shows multiple-seasons notice when more than 1 stats record

## Verification commands (repeat per phase)

```
cd backend && python -m pytest tests/ -q          # expect >= 403 passed
cd frontend && npx vitest run                      # expect >= 96 passed, failures <= the 23 above
cd frontend && npx tsc --noEmit                     # expect clean
```

Then manually drive the phase's touched routes at 375px / 768px / 1280px per `RESPONSIVE.md`'s own checklist.
