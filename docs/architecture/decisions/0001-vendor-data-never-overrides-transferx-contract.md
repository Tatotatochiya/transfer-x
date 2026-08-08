---
title: "ADR 0001: Vendor-Sourced Data Never Overrides an Active TransferX Contract"
last_updated: 2026-08-08
status: Accepted
owner: "TODO — assign a Technical Lead"
---

# ADR 0001: Vendor-Sourced Data Never Overrides an Active TransferX Contract

## Context

TransferX imports real-world player data from a third-party vendor (API-Football) via `vendor/sync.py`, which denormalizes a `team_name` string onto `Player` for display. Separately, TransferX's own transfer system moves a player between clubs *within the platform* by creating a `Contract`, which `players_service.normalize_player_status` uses to set `Player.current_club_id` — the actual ownership signal, used by `get_owning_club_id` to gate who may list or accept a transfer for that player.

These are two independent timelines that can legitimately disagree: a player can be under contract to a TransferX club while API-Football's real-world data still shows their actual real-world team, since TransferX's in-app deals aren't real-world transfers. A bug surfaced this directly — `_upsert_player_from_api_data` (used by `sync_league`/`sync_team`) unconditionally overwrote `player.team_name` on every sync, including for players with an active TransferX contract. It never touched `current_club_id` itself, and the frontend already resolves club display as `current_club?.name ?? world_team?.name ?? team_name` everywhere (`PlayerCard.tsx`, `PlayerListRow.tsx`, `SquadTable.tsx`), so this was never visible — but it left incorrect data sitting in `team_name`, which also feeds club-name text search (`players/service.py`), and which would resurface as the visible fallback the moment the contract lapsed and `current_club_id` went back to `None`.

## Decision

`current_club_id` (set only via an active `Contract`, through `normalize_player_status`) is the sole source of truth for a player's TransferX club, in every context — ownership checks, display, and search. Vendor-sourced fields — `team_name` today, and any denormalized vendor field added later — must never be written for a player who currently has `current_club_id is not None`. Vendor data is only authoritative for players TransferX doesn't currently have under contract.

Implemented as a guard at the point of write, not at the point of read: both `_upsert_player_from_api_data` and `sync_player_stats` (`backend/app/vendor/sync.py`) now skip the `team_name` write entirely when `player.current_club_id is not None`, rather than relying on display-layer precedence to mask a write that still happened.

## Alternatives considered

- **Do nothing — rely on the existing display precedence.** Rejected: the display was never actually wrong, but the stored data was, and "harmless until the contract lapses" is exactly the kind of bug that resurfaces silently, long after the sync that caused it is forgotten.
- **Stop syncing `team_name` after the first import.** Rejected: this would freeze a free-agent or not-yet-contracted player's displayed real-world team forever, defeating the actual purpose of periodic vendor sync for every player TransferX hasn't signed.

## Consequences

- Any future vendor-derived field on `Player` (or another entity with its own TransferX-native ownership concept) should follow the same rule: check the TransferX-native authoritative field before writing, don't lean on a downstream display precedence to paper over an incorrect write.
- `sync_player_stats`'s guard changed from "only backfill if `team_name` is currently empty" to "only write if not under a TransferX contract" — a deliberate behavior change, since the old guard would still overwrite a contracted player's `team_name` if it happened to be blank, and would also stop refreshing a genuinely free player's real-world team after the first sync.

## Related documents

- [`../data-model.md`](../data-model.md) — `Player`, `Contract`, `VendorSyncRun` entities
- [`../backend-architecture.md`](../backend-architecture.md) — the `vendor` and `stats` modules
- [`../../CHANGELOG.md`](../../CHANGELOG.md) — the fix this decision documents
