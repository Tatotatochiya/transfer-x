---
title: "ADR 0002: Contract-Cliff Value-at-Risk Prefers the Fair-Value Model Over Legacy Market Value"
last_updated: 2026-08-11
status: Accepted
owner: "TODO — assign a Technical Lead"
---

# ADR 0002: Contract-Cliff Value-at-Risk Prefers the Fair-Value Model Over Legacy Market Value

## Context

`Player` carries two independent "what is this player worth" signals: `market_value` (TRA-66, an external/vendor enrichment field, unverified) and the `valuation` module's fair-value model (TRA-91/TRA-92, a deterministic in-house model with append-only history and a documented confidence level — HIGH/MEDIUM/LOW). Coverage of the fair-value model is partial: roughly 30% of players have a computed valuation as of this decision, growing via a daily recompute job.

Building the backend track's B6 item (`SESSIONS.md`: "contract cliff aggregation by expiry window") surfaced that these two signals were already being used inconsistently for the same concept without anyone deciding between them: `frontend/src/components/clubs/SquadRail.tsx`'s existing client-side "value at risk" sum (an already-shipped, working feature, not a stub) uses `market_value`, while the newer, more actively-developed fair-value model was never wired into it. Neither field was silently "correct by default" — this was an undecided discrepancy, not a deliberate choice, discovered while scoping B6's new `GET /clubs/me/contract-cliff` endpoint.

## Decision

`GET /clubs/me/contract-cliff`'s `value_at_risk` per window sums, per player: the latest fair-value model valuation (`valuation_service.get_latest_valuations`, batched) where one exists, falling back to the legacy `market_value` field only for players the model doesn't yet cover.

This was confirmed with the user (not assumed) with the coverage gap stated explicitly as the deciding factor: a fair-value-only sum would silently understate risk for any squad with low model coverage, which — at ~30% platform-wide — would be most squads today.

## Alternatives considered

- **Legacy `market_value` only** — matches what `SquadRail.tsx` already ships today, zero behavior change. Rejected: keeps using the less-rigorous, externally-sourced, unverified figure by default even where the platform's own model has a real answer.
- **Fair-value model only, skip uncovered players** — the cleanest single-source signal. Rejected: given ~30% coverage, this would understate value-at-risk for most squads, which is worse than a slightly-inconsistent-source number for a figure whose whole purpose is flagging financial risk.

## Consequences

- `value_at_risk` is not a single-source number — a squad with mixed coverage sums two different valuation methodologies together. This is a known, accepted approximation, not a modeling flaw to fix later without cause.
- `frontend/src/components/clubs/SquadRail.tsx` still computes its own version client-side, `market_value`-only, independent of this endpoint — B6 was scoped as a new backend endpoint alongside the existing client behavior, not a frontend migration (see `IMPLEMENTATION_STATUS.md`'s backend-track row). Migrating `SquadRail.tsx` onto `GET /clubs/me/contract-cliff` is a natural follow-up and should carry this same fair-value-with-fallback rule, not silently revert to `market_value`-only.
- Any future feature that needs a single "what is this player worth" number should default to this same precedence (fair-value model, fall back to legacy `market_value`) rather than re-deciding per call site.

## Related documents

- [`../data-model.md`](../data-model.md) — `Player`, `PlayerValuation` entities
- [`../backend-architecture.md`](../backend-architecture.md) — the `valuation` module
- [`0001-vendor-data-never-overrides-transferx-contract.md`](./0001-vendor-data-never-overrides-transferx-contract.md) — the same TRA-66-vendor-field-vs-TransferX-native-signal shape, decided the other way (there, the TransferX-native signal always wins outright rather than filling a coverage gap) — worth reading together
- [`../../IMPLEMENTATION_STATUS.md`](../../IMPLEMENTATION_STATUS.md) — backend-track row this decision was made under
