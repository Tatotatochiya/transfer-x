---
name: session-lifecycle
description: Open and close every TransferX working session consistently, so work can be picked up by another engineer or another Claude session without re-deriving context. At the very start of a session, before making any suggestions or changes, read docs/PRODUCT_SPEC.md, docs/SESSION_HANDOVER.md, and any documentation relevant to the task at hand. At the end of a session — or whenever asked to wrap up, hand off, or summarize progress — invoke the documentation-standards skill to bring the docs current, then produce a session summary and update docs/SESSION_HANDOVER.md. Use this at the start and end of every session in this repository, not only when explicitly asked to.
---

# TransferX Session Lifecycle

Treat every session like handing off work to another senior engineer at the end of a shift — not a report to file and forget. This skill is what makes that handoff actually happen: read enough at the start to not repeat or contradict earlier work, and leave enough at the end that the next session (human or Claude) can continue immediately.

This skill is the **orchestrator** for session start/end, not a second copy of documentation or backlog rules. For the mechanics of updating docs, it invokes [`documentation-standards`](../documentation-standards/SKILL.md); for how to think about backlog changes, it defers to [`linear-workflow`](../linear-workflow/SKILL.md). Its own, non-duplicated job is the *reading-in* ritual, the *session summary*, and *`docs/SESSION_HANDOVER.md`*.

## When to use this skill

- At the start of every session in this repository, before making any suggestions or changes.
- At the end of every session that did real work — or whenever asked to wrap up, hand off, summarize progress, or "what did we do."
- Even for a session that only investigated or audited without changing code — a handover is still owed.

## Instructions

### 1. Session start — read before you act

Before making any suggestion or change, read, in this order:

1. [`docs/PRODUCT_SPEC.md`](../../../docs/PRODUCT_SPEC.md) — the current state of the product and the map of where everything else lives.
2. [`docs/SESSION_HANDOVER.md`](../../../docs/SESSION_HANDOVER.md) — what the last session left off with: outstanding work, risks, and the recommended next task.
3. Whatever documentation is specifically relevant to the task at hand (e.g. the exact workflow doc, the architecture doc for the module being touched).

Why this order matters: `PRODUCT_SPEC.md` gives orientation (what TransferX *is*, right now); `SESSION_HANDOVER.md` gives continuity (what was *in motion* when the last session ended). Skipping either risks either re-deriving context that already exists, or contradicting a decision that was already made and is sitting one file away.

Only after this should you form an opinion on the task or propose an approach.

### 2. Session end — bring the repo to a handoff-ready state

When a session is ending, or you're asked to wrap up:

1. **Invoke [`documentation-standards`](../documentation-standards/SKILL.md)** to bring `/docs`, `docs/PRODUCT_SPEC.md`, `docs/CHANGELOG.md`, and `docs/IMPLEMENTATION_STATUS.md` current, and to create any ADRs a significant decision this session warrants. This skill does not duplicate those mechanics — it triggers them.
2. **Write a Session Summary** (format below).
3. **Update [`docs/SESSION_HANDOVER.md`](../../../docs/SESSION_HANDOVER.md)** with that summary. This file holds the *current* handover, not a growing log — overwrite the "Latest Session Summary" section rather than appending to an ever-lengthening history. Full history lives in `docs/CHANGELOG.md`; this file only needs to answer "what does the next session need to know right now."
4. **Suggest** any Linear updates the session's work implies, using [`linear-workflow`](../linear-workflow/SKILL.md)'s principles for what a good suggestion looks like — but **do not create or modify Linear issues** unless the user explicitly asked for that in this session. A suggestion is a proposal in the summary, not an action taken.

### Session Summary format

Use exactly this structure — it's what makes summaries scannable across sessions instead of each one reinventing its own shape:

```markdown
## Session Summary — YYYY-MM-DD

**Completed work:**
- ...

**Important decisions:**
- ...

**Outstanding work:**
- ...

**Risks:**
- ...

**Recommended next task:**
- ...
```

- *Completed work* — what actually changed (code, docs, Linear), stated plainly enough that "did we do X" is answerable without re-reading the whole transcript.
- *Important decisions* — anything decided that a future session shouldn't accidentally reverse without knowing it was deliberate. Cross-reference an ADR if one was created.
- *Outstanding work* — what was identified but not done, distinct from things nobody has noticed yet.
- *Risks* — anything that could bite later if left unaddressed (a known gap, a fragile assumption, a temporary workaround).
- *Recommended next task* — a specific, concrete suggestion, not "keep improving things."

### 3. The repo should be immediately continuable

Before considering a session closed, check: could another engineer, or a fresh Claude session with no memory of this conversation, pick up `docs/SESSION_HANDOVER.md` and know exactly where to start? If the honest answer is "they'd have to ask you what you meant," the summary isn't done yet.

## Examples

**A session that shipped a feature.** After implementing a new deal stage, session end looks like: invoke `documentation-standards` (which updates `docs/product/workflows/transfer-lifecycle.md`'s stage table, `docs/CHANGELOG.md`'s `Added` section, and `docs/IMPLEMENTATION_STATUS.md`'s relevant row) → write the Session Summary noting the new stage, any trade-off made in how it was inserted into the stage machine, and whether tests were added → update `docs/SESSION_HANDOVER.md` → suggest (don't create) a Linear ticket for a follow-on UI surface that wasn't in scope this session.

**A session that only investigated.** A session spent entirely auditing a workflow for gaps, with no code or doc changes, still owes a handover: Session Summary's *Completed work* says "audit only, no changes," *Outstanding work* lists what the audit found, and *Recommended next task* points at the highest-priority finding. `SESSION_HANDOVER.md` still gets updated — "nothing changed" is not the same as "nothing to report."

## Related skills

- [`documentation-standards`](../documentation-standards/SKILL.md) — does the actual work of updating `/docs`, `CHANGELOG.md`, and `IMPLEMENTATION_STATUS.md` that this skill triggers at session end.
- [`linear-workflow`](../linear-workflow/SKILL.md) — owns how a Linear suggestion should be shaped; this skill only decides *that* a suggestion is owed, never executes it.
- [`engineering-standards`](../engineering-standards/SKILL.md) and [`product-principles`](../product-principles/SKILL.md) — concerns raised under either during the session and left unresolved belong in this summary's *Risks* or *Outstanding work*, not left to be rediscovered next time.
