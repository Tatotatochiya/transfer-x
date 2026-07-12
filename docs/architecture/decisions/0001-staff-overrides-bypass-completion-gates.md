---
title: "ADR 0001: Staff Override Endpoints Bypass the Ordinary Completion Gates"
last_updated: 2026-07-12
status: Accepted
owner: "TODO — assign a Technical Lead"
---

# ADR 0001: Staff Override Endpoints Bypass the Ordinary Completion Gates

## Context

The 2026-07-11 audit and its 2026-07-12 re-audit both flagged that a deal could complete with no medical ever recorded, and that transfer windows weren't enforced at completion. Fixing this for the ordinary `POST /deals/{id}/advance` path was straightforward: `PAPERWORK → CONFIRMED` now requires a recorded (`PASSED` or `WAIVED`) medical, and `CONFIRMED → COMPLETED` now checks the transfer window (with a deadline-day grace period — see [`../../product/workflows/deal-completion.md`](../../product/workflows/deal-completion.md)).

But `deals/service.py` also has `staff_complete` and `staff_collapse` — endpoints restricted to `is_superuser`, callable from *any* non-terminal stage, that force a deal straight to `COMPLETED` or `COLLAPSED`. These already skip `PAPERWORK`'s staff-only gate and `PERSONAL_TERMS` consent entirely; they exist for cases the ordinary stage machine can't handle (a stuck deal, an administrative correction, a demo reset). The question: should the new medical/window gates apply to these too?

## Decision

No. `staff_complete` keeps its existing, narrower check (`FAILED` medical still blocks; no medical at all does not) and gains no window check. `staff_collapse` is unaffected — it always required staff, so the M6 reason requirement (which only applies to non-staff actors) never applied to it either.

The principle: **the ordinary `/advance` path enforces every gate strictly, with no exceptions; the staff-only override endpoints are a deliberate full bypass, not a stricter version of the same path.** They already bypass stage sequencing and player consent — gating them on medical/window too would be inconsistent (why enforce *these* two gates on an endpoint whose entire purpose is to skip every other one?) without meaningfully improving safety, since a `FAILED` medical (the one signal actually worth respecting even in an override) still blocks.

## Alternatives considered

- **Apply the same medical/window gates to `staff_complete`.** Rejected: this would make the "administrative override" endpoint no longer able to override the thing it most needs to override — an admin using it to force-complete a deal that's stuck because a window closed mid-paperwork, for example. It also doesn't match how the existing `staff_complete` already treats consent and stage sequencing (both fully bypassed), so applying strictness selectively to only the two newest gates would be an arbitrary inconsistency, not a principled one.
- **Add a separate "staff force-complete with justification" flow** (reason required, extra confirmation) instead of the existing unconditional override. Deferred, not rejected outright — worth revisiting if `staff_complete`/`staff_collapse` usage grows beyond genuine edge cases; out of scope for this session, which was fixing the two specific audit findings, not redesigning the staff-override surface.

## Consequences

- `staff_complete`'s docstring now states the bypass explicitly, so a future change to the ordinary path's gates doesn't get silently assumed to also apply here.
- The re-audit's finding "a transfer can complete with no medical at all" is closed for the path every real transfer takes; staff force-completion remains, by design, an unaudited-by-medical escape hatch — this is the same trust model the platform already had for stage sequencing and consent, just made explicit for the two new gates.
- If `staff_complete`/`staff_collapse` usage in production ever needs its own audit trail beyond the existing `actor_user_id` attribution, that's a new decision, not a reversal of this one.

## Related documents

- [`../../product/workflows/deal-completion.md`](../../product/workflows/deal-completion.md) — the medical/window gates this ADR concerns, and where the staff-override behaviour is documented for product readers
- [`../../audits/2026-07-11-transfer-workflow-audit.md`](../../audits/2026-07-11-transfer-workflow-audit.md) — M7 (medical model), the finding that started this
- [`../../audits/2026-07-12-transfer-workflow-audit.md`](../../audits/2026-07-12-transfer-workflow-audit.md) — M4, M8 (deadline-day grace) — the re-audit findings this decision resolves
- [`../../CHANGELOG.md`](../../CHANGELOG.md) — the change entry
