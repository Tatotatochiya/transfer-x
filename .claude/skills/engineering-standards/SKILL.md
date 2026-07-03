---
name: engineering-standards
description: Apply TransferX's engineering principles whenever writing or modifying backend or frontend code. Use this before any non-trivial code change, and always when a change touches money/finance logic, permissions, access control, or the deal/negotiation state machine. Covers small maintainable diffs, reusing existing patterns, loose coupling, readability over cleverness, and explicit consideration of permissions, security, auditability, scalability, testing, and maintainability. If the code you're touching differs from what the documentation says it does, surface the discrepancy explicitly rather than silently resolving it in either direction.
---

# TransferX Engineering Standards

TransferX is enterprise software handling real transfer fees, contracts, and confidential negotiations between clubs, agents, and players. Code quality here isn't a style preference — a sloppy permission check or an unreviewed shortcut in the finance logic is the kind of thing that ends a club's confidence in the platform. This skill sets the bar for any code change.

## When to use this skill

- Before writing or modifying backend (`backend/app/`) or frontend (`frontend/src/`) code of any real size.
- Always — not just "when convenient" — for changes touching money (fees, wages, budgets, instalments), permissions/authorization, or the deal stage machine.
- When you're about to introduce a new pattern, abstraction, or dependency.
- When something you're implementing isn't described anywhere in `/docs` and you're tempted to guess at the intended behaviour instead of checking.

## Instructions

### 1. Read before you write

Check [`docs/architecture/`](../../../docs/architecture/README.md) and [`docs/product/workflows/`](../../../docs/product/workflows/README.md) for how the area you're touching is supposed to work before writing code. If the documentation doesn't cover it, that's not licence to assume — read the actual code the same way you'd want a new hire to: trace the existing module's `models.py` → `schemas.py` → `service.py` → `router.py` layering rather than guessing at a contract from a function name.

**Never assume undocumented behaviour.** If you can't find where a rule is enforced, don't code as if it is. A missing check is a finding to report, not a behaviour to preserve by accident.

### 2. Prefer small, maintainable changes

- The smallest change that correctly solves the stated problem beats a larger "while I'm in here" rewrite.
- Avoid unnecessary complexity — no abstraction for something used once, no configurability nobody asked for.
- Reuse existing patterns rather than inventing a parallel one. TransferX already has established patterns worth following rather than reinventing: the reserve → commit → spend budget lifecycle in `clubs/service.py`, the `_require_party` / participant-scoping pattern used across `deals`, `offers`, and the deal room, and the module-per-domain `models.py`/`schemas.py`/`service.py`/`router.py` layering. Match them instead of introducing a second way to do the same thing.
- Keep modules loosely coupled — a change in one domain module shouldn't require reaching deep into another's internals. Cross-module needs go through that module's service layer, not its models directly.
- Readability over cleverness. Consistent naming with what's already in the surrounding module.

### 3. Consider these explicitly, every time

Before calling a change done, actually ask:

| Consideration | Ask yourself |
|---|---|
| **Permissions** | Who should be able to call this, and does the code actually enforce that — or just assume it? |
| **Security** | Does this expose data (financial figures, medical records, personal terms, confidential bids) to someone who shouldn't see it? |
| **Auditability** | If this action matters later (a dispute, a compliance question), is there a trail? Should this emit an audit event? |
| **Scalability** | Does this work the same at 5 deals and 5,000? Any assumption about "there's only ever one of these"? |
| **Testing** | Is there a test that would catch this breaking later, especially for money-affecting or permission-affecting logic? |
| **Maintainability** | Would a new engineer understand why this is here without asking you? |

Not every change needs a deep answer to all six — but skipping the question because a change "feels small" is exactly how the kind of bug that erodes enterprise trust gets shipped.

### 4. When documentation and code disagree

If you discover the implementation doesn't match what `/docs` says, **surface the discrepancy** — say explicitly which one you believe is correct and why, and route it to the [`documentation-standards`](../documentation-standards/SKILL.md) skill to reconcile. Do not silently change business behaviour to match a stale doc, and do not silently rewrite the doc to match code you haven't confirmed is intentional. Both are ways of quietly making a decision that should have been visible.

### 5. Explain trade-offs before significant design changes

Before introducing a meaningfully different design — a new module boundary, a schema change with migration implications, a different concurrency approach — explain the trade-off you're making and why, before writing the code. This is also the trigger to consider whether an ADR belongs in [`docs/architecture/decisions/`](../../../docs/architecture/decisions/README.md).

### 6. Think about enterprise scale

TransferX isn't a weekend project — it's aimed at professional football clubs managing real money and real negotiations (see [`product-principles`](../product-principles/SKILL.md) for the full framing). A shortcut that's fine for a demo with one club and one deal often isn't fine for a platform running an actual transfer window with dozens of simultaneous deals. Concurrency-safe money operations, consistent authorization checks across every entry point to a resource (not just the "main" one), and predictable behaviour under load aren't gold-plating here — they're the bar.

## Examples

**Reusing an existing pattern instead of inventing one.** Asked to add a new club-side budget category (e.g. a loan-fee reserve distinct from transfer-fee reserve), don't invent a new ad hoc field with custom increment/decrement logic scattered across call sites — extend the existing `reserve_budget` / `commit_budget` / `release_budget` lifecycle in `clubs/service.py` the same way `transfer_reserved` and `wage_reserved_weekly` already work side by side.

**Surfacing a docs/code mismatch instead of resolving it silently.** While implementing a change to medical checks, you notice the code only blocks deal progression on a `FAILED` medical, but the relevant documentation implies a `PENDING` medical should also block it. Don't quietly "fix" the code to match the doc (that's a business-behaviour change nobody asked for) and don't quietly edit the doc to match the code (that hides a possible bug). State the mismatch plainly and let the human or the `documentation-standards` skill decide which one is correct.

**A permissions check that's easy to skip.** Adding a new endpoint that reads deal data, it would be easy to copy an existing "any authenticated user" pattern from a public-market endpoint. Stop and ask the permissions question from the table above — deal data usually needs a participant check, not just a login check.

## Related skills

- [`documentation-standards`](../documentation-standards/SKILL.md) — where a docs/code discrepancy or a significant design decision gets recorded, once flagged here.
- [`product-principles`](../product-principles/SKILL.md) — the *why* behind the permissions/security/professionalism bar this skill enforces mechanically.
- [`linear-workflow`](../linear-workflow/SKILL.md) — if a code review surfaces a gap that's out of scope for the current change, that's a backlog candidate, not something to silently fix or silently ignore.
- [`session-lifecycle`](../session-lifecycle/SKILL.md) — outstanding engineering concerns (tech debt noticed but not addressed) belong in the end-of-session summary.
