---
title: "Valuation: the fair-value model and its data"
last_updated: 2026-11-13
status: market-v2 live; market-v3 (last-fee anchor) built and switched off until its production backtest is reviewed
owner: "TODO — assign a Product Owner"
---

# Valuation

## Purpose

Everything about TransferX's fair value in one folder: the model, the signal it feeds, the data it could draw on, and the plan and log of the `market-v3` work.

## Where things stand

- **Live:** `market-v2`. Each player's last transfer fee is shown beside the value, with its source. Staff can record a fee by hand from Admin → player → Transfer fees.
- **Built, switched off:** the `market-v3` last-fee anchor, behind `VALUATION_FEE_ANCHOR_ENABLED` (default `false`). It stays off until the read-only backtest and outcome report have been run against production and reviewed ([how to turn it on](../../operations/environments-and-deployment.md#the-last-fee-anchor-switch)).
- **Not built:** licensed market values from a provider. PlayerElo is the recommended pilot.

## Documents

| Document | What it is |
|---|---|
| [`model.md`](./model.md) | The model: `market-v2` stage by stage, the `market-v3` last-fee anchor, calibration and backtests |
| [`fair-value-vs-asking-signal.md`](./fair-value-vs-asking-signal.md) | The signal the model feeds: endpoints, permissions and UI |
| [`market-data.md`](./market-data.md) | Licensed market data and the last-fee anchor: the design, and how what was built differs from it |
| [`report-sample.md`](./report-sample.md) | A sample "valuation stack" report with worked cases |
| [`brief.md`](./brief.md) | The product owner's request of 2026-11-10 |
| [`execution-plan.md`](./execution-plan.md) | The plan for `market-v3` and staff-entered fees, with its three addenda |
| [`execution-log.md`](./execution-log.md) | What was built and verified, round by round; §11 is current |

## Code

| Path | Role |
|---|---|
| `backend/app/valuation/` | Engine (`engine_v2.py`), constants, features, service, API |
| `backend/app/players/last_fee.py` | A player's last fee: vendor rows, staff rows and completed TransferX deals |
| `backend/scripts/valuation_backtest.py`, `valuation_outcome_report.py` | Read-only backtest and before/after report |
| `frontend/src/components/players/ValuationBreakdownPopover.tsx` | The value build-up shown to clubs |

## Related

- [Injury-availability risk profile](../injury-availability-risk-profile.md): availability terms the model shares
- [Scheduled data refresh](../scheduled-data-refresh.md): the daily recompute
