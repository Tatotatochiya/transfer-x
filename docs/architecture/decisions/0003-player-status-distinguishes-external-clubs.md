---
title: "ADR 0003: Player Status Distinguishes External Clubs From Free Agency"
last_updated: 2026-08-11
status: Accepted
owner: "TODO — assign a Technical Lead"
---

# ADR 0003: Player Status Distinguishes External Clubs From Free Agency

## Context

`PlayerStatus` was a two-state enum: `CONTRACTED` | `FREE_AGENT`. `players_service.normalize_player_status` derived it solely from the presence of an active **TransferX** `Contract` — no contract meant `FREE_AGENT`, unconditionally.

That derivation is sound for players a TransferX club has actually signed. It is wrong for the ~7.9k players imported from the stats vendor (API-Football), who are under contract at real-world clubs that simply aren't on the platform. `vendor/sync.py` also created every imported player with an explicit `status=FREE_AGENT`.

Measured on the development database before this change:

| Status | Count |
|---|---|
| `FREE_AGENT` | 7,830 |
| `CONTRACTED` | 84 |
| …of the free agents, with a real-world club (`team_name` or `world_team_id`) | **7,825** |
| …genuinely unattached | **5** |

So 99.9% of "free agent" labels were wrong. Lamine Yamal displayed as *"MID · Free agent"* while also being browsable under Barcelona.

Two things made this more than a cosmetic defect:

1. **It was presented as an opportunity.** `playerStatusVariant` mapped `FREE_AGENT` to the `success` (green) badge, so the UI actively highlighted 7,825 contracted professionals as available.
2. **It was a signing exploit.** `create_free_agent_deal` gated only on `player.status != PlayerStatus.FREE_AGENT`. Its own docstring describes the pathway as *"no seller, no fee, no offer/bid negotiation pipeline."* No transfer windows are configured, so `is_transfer_allowed()` returns `True`. Any club user holding `MARKET_WRITE` could therefore sign Yamal — and ~7,824 other contracted professionals — for zero fee, with no selling club, no negotiation and no approval.

The problem was partially known. `scouting/service.py` carried a display-layer override with the comment *"Vendor players have status=FREE_AGENT in DB but are contracted when they have a team_name, world_team_id, or current_club_id."* Equivalent compensating checks existed in at least three frontend components. Every one of them patched a **read** path; none fixed the source, and none protected the **write** path that actually mattered.

## Decision

`PlayerStatus` gains a third value, `EXTERNAL`: under contract to a real-world club that is not on TransferX.

`normalize_player_status` now resolves in three ways when there is no active TransferX contract:
- a real-world club signal exists (`team_name` or `world_team_id`) → `EXTERNAL`
- no club signal anywhere → `FREE_AGENT`

`CONTRACTED` keeps its existing, narrower meaning: under contract to a club **on TransferX**. Vendor sync now creates players as `EXTERNAL`.

Supporting decisions:

- **Defence in depth on the signing path.** `create_free_agent_deal` rejects both `status == EXTERNAL` *and* any player with a live club signal, so a stale or hand-edited status row cannot reopen the hole. The status check alone is what failed here; it is not trusted alone again.
- **`EXTERNAL` displays to buyers as "Contracted", never green.** To a club browsing the market the actionable fact is identical — this player belongs to someone — and the club name shown alongside already says who. This matches the display collapse `scouting/service.py` had already chosen independently.
- **Admin surfaces show all three states distinctly.** Administrators are the people who need to spot data problems, so they see `External` as its own label rather than the buyer-facing collapse.
- **The compensating overrides are removed, not duplicated.** `scouting/service.py`'s override is deleted now the stored value is trustworthy. The remaining frontend guards (`PlayerMarketDetailPage`'s `status === "FREE_AGENT" && !team_name` checks) are left in place as deliberate defence in depth, consistent with the point above.

## Alternatives considered

- **Guard the signing endpoint only.** Closes the exploit in one line. Rejected as the whole fix: it leaves 7,825 players labelled "Free Agent" in green, which is the demo-facing half of the problem and would still read as a broken product to a sporting director.
- **Display-layer override everywhere, no schema change.** Cheapest, no migration. Rejected: this is precisely what had already been attempted — four separate copies of the same override, none of which protected the write path. Adding a fifth would repeat the failure mode. The stored value should be correct, so that every reader, filter, and future consumer is correct by default rather than by remembering to compensate.
- **Treat external players as `CONTRACTED`.** Simpler enum, no third state. Rejected: `CONTRACTED` implies a TransferX `Contract` row exists, which drives ownership checks (`get_owning_club_id`), squad membership, and finance. Overloading it would corrupt those.

## Consequences

- Migration `0063` adds the enum value and backfills existing rows by the same rule the service uses. It is a normal Alembic migration, so deployed environments (Railway) pick it up automatically — no manual repair step, unlike the listing repair in [`../../operations/environments-and-deployment.md`](../../operations/environments-and-deployment.md).
- `EXTERNAL` players are **not** signable, and correctly generate no `PLAYER_AVAILABLE` notifications (that fan-out remains gated on true `FREE_AGENT`).
- Downgrade collapses `EXTERNAL` back into `FREE_AGENT`, restoring pre-0063 meaning. The enum label itself is left in place — Postgres cannot drop an enum value without recreating the type, and an unused label is harmless.
- Any future status-like field derived from TransferX-internal state should ask the same question this one got wrong: *does absence of our record actually mean absence of the thing?* Here, no TransferX contract never meant "no contract".
- The admin health check for *"FREE_AGENT but has an active contract"* (`admin/service.py`) only ever caught TransferX contracts, so it never flagged any of these 7,825 rows. Worth extending to the external case — not done here.

## Related documents

- [`../data-model.md`](../data-model.md) — `Player`, `Contract` entities
- [`0001-vendor-data-never-overrides-transferx-contract.md`](./0001-vendor-data-never-overrides-transferx-contract.md) — the same vendor-data-vs-TransferX-truth boundary, decided for a different field
- [`../../DEMO_READINESS_AUDIT.md`](../../DEMO_READINESS_AUDIT.md) — finding C5, added from this work
- [`../../CHANGELOG.md`](../../CHANGELOG.md)
