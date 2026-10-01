---
title: "Player Profile v2: Season Ledger"
last_updated: 2026-10-01
status: Active
owner: "TODO — assign a Product Owner"
---

# Player Profile v2: Season Ledger

The design handoff is [`HANDOFF.md`](./HANDOFF.md), with the HTML reference and `screenshots/`. This file holds the build plan and the product owner's decisions, which override the handoff where they disagree.

## Decisions (product owner, 2026-10-01)

1. **Light mode.** Build on the app's colour tokens, so light is the default and dark follows the existing theme switch. The handoff's dark-only hex values map to tokens; they are not copied.
2. **Backfill three past seasons** (2022/23, 2023/24, 2024/25) alongside the current one, **for TransferX players only** (contracted at a TransferX club, or a free agent). Other players get no history yet. The season count is a script option.
3. **Run the backfill locally first**, check the data, then on Railway.
4. **The third tab is "Injuries", not "Medical"**, so it isn't confused with a deal's private medical results.
5. **P5 is in scope:** the private club valuation, the last-5-games chips, and Availability.

## Data from API-Football (plan: 75,000 requests a day)

| Data | Endpoint | Calls (693 players, 3 seasons) |
|---|---|---|
| Season stats by competition (every ledger column, league and team names and logos) | `/players?id=&season=` | ~2,100 |
| Transfer history (dates, fees, loans) | `/transfers?player=` | ~700 |
| Injury periods | `/sidelined?player=` | ~700 |
| Missed matches, for games missed per injury | `/injuries?league=&season=` | ~30 |
| League fixtures per club and season, for Availability | `/teams/statistics?team=&league=&season=` | ~300 |
| Last 5 games: ratings and opponents | `/fixtures?team=&last=5`, `/fixtures/players?fixture=` | ~120 |

About 4,000 calls in all. The script caps itself per minute and resumes where it stopped.

## Sessions

| # | Session | Done when |
|---|---|---|
| P0 | Contract confidentiality: the player API sends another club's contract (wage, signing date) to any signed-in user. Release clause stays public; wage and signing date only to the owning club (and staff); buyers see the estimate | A rival club's request has no contract wage; the owning club's does |
| P1 | Storage (migration 0087) and `scripts/backfill_player_history.py`: stats gain league/team names and logos and a loan flag; new tables for per-game ratings and club league fixture counts; staged, resumable, `--dry-run`, `--seasons`, `--limit`, a per-minute cap | Locally, TransferX players have three past seasons of stats, transfers, injuries, fixture counts and recent games |
| P2 | `GET /players/market/{id}/ledger`: seasons with competition sub-rows and career totals (handoff aggregation rules), transfers linked to seasons, injuries grouped with games missed and severity, Availability, last 5 games. All computed in code | Totals match the handoff's rules in tests |
| P3 | The page in light mode: header, facts strip, tabs (Overview / Career / Injuries) through one `SeasonLedger` component, URL tab, remembered stat set, horizontal scroll on narrow screens | Matches the screenshots' structure in light and dark |
| P4 | Side panels by viewer (buying club, own club, agent), plus the player, signed-out, read-only/scout staff (actions disabled with a reason), staff, and an agent seeing another agent's client. Deal banner pauses offers, clause trigger and listing. Anonymous bidders stay masked | Each viewer sees the right panels and actions |
| P5 | Last-5-games chips, Availability column and total, private club valuation (owning club only, editable, audited) | Each shows from real data; the valuation is invisible to other clubs |

## Progress

- **P0 done (2026-10-01).** `players.service.can_see_contract_terms` / `contract_for_viewer` mask wage, start date, club valuation and notes for anyone but the holding club, staff, the player and his agent. They apply on `GET /players/market/{id}` and `GET /clubs/{id}/players`. The AI's player facts (`assist._player_facts`, `context.build_player_context`) use the public estimate for a rival's player. Tests in `tests/test_contract_confidentiality.py`.
  - Finding: the private club valuation already exists (`contracts.club_valuation`, editable inline by the owner on the current page). So P5's valuation is a matter of showing it in the new facts strip; no new field is needed.
- **P1 built (2026-10-01).**
  - **Migration `0087`:** `player_stats` gains `league_name`, `league_logo`, `team_logo` and `is_loan`; `player_injuries` gains `end_date`. New tables: `player_injury_fixtures`, `player_fixture_ratings`, `team_season_fixtures` and `vendor_fetch_log`.
  - **Fetching** is in `app/vendor/history.py`. The profile's transfer and injury refresh now uses it too, and rolls back on a failed fetch instead of serving an empty history.
  - **`scripts/backfill_player_history.py`** runs in stages, resumes from `vendor_fetch_log`, and takes `--dry-run`, `--stages`, `--seasons`, `--limit`, `--per-minute` and `--max-calls`. A failed item is logged and retried on the next run.
  - **Seasons:** the current season is the latest in `player_stats` (2025, i.e. 2025/26), refetched so its rows gain labels and a per-club key. Past seasons are 2024, 2023 and 2022.
- **Deviations in P1:**
  - **Stats rows are keyed by club** as well as competition and season, so a mid-season move within one league stays as two spells.
  - **The history fetch never changes the player's own club, position or name**, unlike the league sync.
  - **National teams and youth sides come with the stats.** The ledger separates them (see P2).
- **P2 built.** `GET /players/market/{id}/ledger` (`app/players/ledger.py`):
  - club seasons, one row per season and club, with a sub-row per competition, a career total, and internationals kept apart;
  - transfers placed in seasons;
  - injury periods with games missed (missed matches inside each `/sidelined` period), plus each season's injuries, games missed, longest and availability;
  - form and the last 5 games.

  Injuries are only sent to signed-in users, as the old tab did. Tests in `tests/test_player_ledger.py`.
- **Deviations in P2:**
  - **National teams** (a team name that is a nationality or team country we hold, ignoring a U21-style suffix) go under "International" and are left out of club totals. Club youth sides (Arsenal U21) stay as club rows.
  - **Availability** counts the club's matches in every competition he played that season, not only the league. Where any match count is unknown, it shows "—".
  - **A severe injury** is a knee, ankle, ligament, Achilles, fracture or surgery type (keyword match). API-Football has no severity flag.
- **P3 built.**
  - **The page** has the breadcrumb, compact header and facts strip (model value, market value, contract, wage, and the release clause or the owner's editable club valuation, plus form).
  - **The tabs** are Overview / Career / Injuries over one `SeasonLedger` (`components/players/ledger/`). The tab is in the URL as `?tab=`, and the stat set is remembered on the device. The table scrolls sideways below 640px, and the side column stacks under 1024px.
  - **Light mode** comes from the app's tokens; dark follows the theme switch.
  - **Club crests** stand in for colour swatches, and opponents' codes are the first three letters of their name.
- **P4 built.**
  - **Own club:** an Offers panel (anonymous buyers arrive masked from the order book).
  - **Representation:** the endpoint names each mandate's agent and marks the caller's own, so the card says "You represent him" or "Represented by …". Revoke appears only on your own mandate, and the form is blocked behind another agent's exclusive mandate.
  - **Read-only and scout staff** see Make Offer disabled with a reason.
  - **The player** sees a note that his contract terms are private.
- **Still open:**
  - **Transfermarkt market values** are marked in the code as prototype-only, with no redistribution rights. The facts strip shows the source; whether to keep showing them is a licensing decision.
  - **Weekly refresh:** run `--stages recent --refresh` weekly for the last-5 chips (not scheduled yet).
