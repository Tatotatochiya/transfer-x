---
name: documentation-standards
description: Keep TransferX's /docs tree, docs/PRODUCT_SPEC.md, docs/CHANGELOG.md, and docs/IMPLEMENTATION_STATUS.md in sync with the actual implementation. Use this whenever product behaviour, business rules, architecture, permissions, or user-facing workflows change; whenever a feature is added, removed, or reworked; whenever a significant design decision is made; and always before ending a session that touched the product. Also consult it before writing any new documentation file, to check whether an existing document should be updated instead of a new one created. Trigger this even when the user only asked for a code change and didn't mention documentation — behaviour changes are exactly when docs go stale silently.
---

# TransferX Documentation Standards

Documentation is TransferX's source of truth, not an afterthought bolted onto code changes. This skill keeps `/docs` — and the two tracking files that ride alongside it, `docs/CHANGELOG.md` and `docs/IMPLEMENTATION_STATUS.md` — accurate, current, and free of duplication.

The full documentation system lives under [`/docs`](../../../docs/README.md), organized into six single-responsibility areas (business, product, architecture, engineering, operations, security-and-compliance) plus a small set of root-level tracking documents. Read [`docs/README.md`](../../../docs/README.md) if you haven't already — it explains the taxonomy and conventions (front matter, TODO markers, Mermaid placeholders) this skill assumes.

## When to use this skill

- Product behaviour, a business rule, a workflow, or the permissions model changes.
- A feature is added, removed, reworked, or its scope changes from what's documented.
- Architecture changes — a new module, a changed data model, a new integration.
- A significant design decision gets made, even in passing conversation.
- A session that touched the product is ending (the [`session-lifecycle`](../session-lifecycle/SKILL.md) skill invokes this one for that).
- Before creating any new documentation file — part of this skill's job is stopping unnecessary new files from being created.

## Instructions

### 1. Search before you write

Before creating a new document, search `/docs` for something that already covers the topic. A new file is the last resort, not the first move:

1. Check the relevant area's `README.md` (e.g. `docs/product/README.md` for a workflow question) — it has a table of contents for that area.
2. Grep for the concept across `/docs` — a term might already be defined in [`docs/business/glossary.md`](../../../docs/business/glossary.md) or covered in an existing workflow doc.
3. If something close exists, **update it**. Only create a new file when the topic genuinely doesn't fit any existing document's stated scope.

If you do create a new file, give it front matter (title, last_updated, status, owner), add it to its area's `README.md` index, and link it from anything related — see [`docs/README.md`](../../../docs/README.md) for the exact conventions.

### 2. Update PRODUCT_SPEC.md when it's no longer accurate

[`docs/PRODUCT_SPEC.md`](../../../docs/PRODUCT_SPEC.md) is the master index and the "Current State" snapshot of the product. Update it whenever:

- A workflow changes (also update the specific document under `docs/product/workflows/`).
- Permissions or the auth model change (also update `docs/architecture/authentication-and-permissions.md` and `docs/security-and-compliance/permissions-model.md`).
- A business rule changes.
- Architecture changes (also update the relevant `docs/architecture/` document).
- User experience changes materially.

Don't let `PRODUCT_SPEC.md` accumulate its own copy of the detail — it should stay a short, accurate index with a link to wherever the detail actually lives. If you find yourself writing more than a paragraph directly into `PRODUCT_SPEC.md`, that paragraph probably belongs in a linked document instead.

### 3. Keep the two tracking documents distinct

These answer different questions — don't let them collapse into duplicates of each other:

| Document | Answers | Update when |
|---|---|---|
| [`docs/CHANGELOG.md`](../../../docs/CHANGELOG.md) | What changed, in order, over time? | Every session that ships a user-visible or behaviour-affecting change. Follows [Keep a Changelog](https://keepachangelog.com) format: `Added` / `Changed` / `Fixed` / `Removed` under an `[Unreleased]` heading. |
| [`docs/IMPLEMENTATION_STATUS.md`](../../../docs/IMPLEMENTATION_STATUS.md) | What's actually built right now, verified against the code? | Whenever a feature moves between not-started / in-progress / done, or whenever the real implementation state turns out to differ from what this file currently claims. |

The important discipline for `IMPLEMENTATION_STATUS.md`: it must reflect **verified** reality, not "what the ticket status says." A ticket can be marked Done in Linear while its acceptance criteria are only partially met in the actual code — that exact mismatch has happened in this project before. Check the code before marking something done here; don't transcribe Linear's status as if it were ground truth.

### 4. Record significant decisions as ADRs

If a design decision was made — a trade-off, a "we chose X over Y and here's why" — capture it rather than letting the reasoning live only in conversation history that nobody can search later:

- Product-level decisions (what to build, what not to, scope calls) → [`docs/product/decisions/`](../../../docs/product/decisions/README.md)
- Architecture-level decisions (system design, module boundaries, schema choices) → [`docs/architecture/decisions/`](../../../docs/architecture/decisions/README.md)

Both folders explain the expected format in their own `README.md`. A short ADR now saves a much longer re-litigation later, and stops a future session (human or Claude) from accidentally reversing a decision it doesn't know was deliberate.

### 5. Writing quality bar

- **Concise.** A placeholder that says `> **TODO:** decide X` is more useful than three invented paragraphs pretending X is settled.
- **Cross-referenced.** Link to the canonical definition instead of restating it — especially terms in [`docs/business/glossary.md`](../../../docs/business/glossary.md) and entities in [`docs/architecture/data-model.md`](../../../docs/architecture/data-model.md).
- **Never invent functionality.** If you're not sure whether something exists, check the code — don't describe a feature because it would make the documentation feel more complete.
- **Unknown stays a TODO**, formatted as `> **TODO:** ...` (see [`docs/README.md`](../../../docs/README.md) conventions) — not a guess dressed up as fact.
- **Reflect the implementation, not the intention.** If the code and an existing doc disagree, the code is what actually happens — flag the doc as stale and fix it, don't just add a second, contradictory claim next to the first.
- **Quality over quantity.** One accurate paragraph beats five padded ones. Resist the urge to expand a document just because you're already editing it.

## Examples

**A workflow changes.** A deal's stage machine gains a new `RELEASE_CLAUSE_TRIGGERED` state. Update `docs/product/workflows/transfer-lifecycle.md`'s stage table, update the Mermaid diagram placeholder's TODO note to mention the new transition, and check whether `docs/business/glossary.md`'s "Deal stage" entry needs a line added. Don't create a new `docs/product/workflows/release-clauses.md` unless the existing workflow docs genuinely can't hold this in a paragraph.

**Asked to document something that's already documented.** A request comes in to "write up how club permissions work." Search first: `docs/architecture/authentication-and-permissions.md` and `docs/security-and-compliance/permissions-model.md` already exist and deliberately split this exact topic (mechanism vs. risk posture). Update those instead of creating `docs/permissions.md`, and explain the existing split so whoever asked knows which one to use going forward.

**A ticket says Done but the code says otherwise.** While updating `IMPLEMENTATION_STATUS.md` for the personal-terms consent flow, the code shows non-mandated players skip consent entirely — even though the corresponding Linear ticket is marked Done. Record the *verified* state here (partially implemented, gap named explicitly), not the ticket's claimed state, and flag the mismatch for the [`linear-workflow`](../linear-workflow/SKILL.md) skill to reconcile in Linear separately.

## Related skills

- [`session-lifecycle`](../session-lifecycle/SKILL.md) invokes this skill at the end of every session — it owns *when* documentation gets updated as part of wrapping up; this skill owns *how*.
- [`engineering-standards`](../engineering-standards/SKILL.md) flags when code and documentation disagree during a code change — this skill is where that flag gets resolved on the documentation side.
- [`linear-workflow`](../linear-workflow/SKILL.md) owns the backlog in Linear; this skill owns the docs. A ticket's status and an `IMPLEMENTATION_STATUS.md` entry can diverge — when they do, that's a signal for both skills, not a job for either one alone.
- [`product-principles`](../product-principles/SKILL.md) informs *what* a workflow document should say a feature does (the intended, professional-grade behaviour); this skill governs *how* that gets written down and kept current.
