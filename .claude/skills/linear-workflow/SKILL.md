---
name: linear-workflow
description: Think like an experienced Product Manager refining the TransferX Linear backlog. Use this when reviewing completed or planned work, identifying missing functionality, proposing new tickets, deduplicating or restructuring the backlog, or when asked to create or update Linear issues. Always review existing projects, issues, and labels before proposing anything — prefer updating, merging, or splitting existing issues over creating new ones. Never create, edit, or archive a Linear issue unless the user has explicitly asked for it in the current conversation; producing a refinement plan is not the same as executing it.
---

# TransferX Linear Workflow

The goal of touching the backlog is a **clean, prioritised backlog** — not a large number of tickets. A well-run backlog has few, well-scoped, accurately-tracked issues; a poorly-run one accumulates duplicates, stale tickets nobody re-checks, and inconsistent labels until nobody trusts what's actually current. This skill is what keeps TransferX's Linear workspace in the first state.

## When to use this skill

- Reviewing work that's been done or planned.
- Identifying missing functionality that should become a ticket.
- Being asked to create Linear issues.
- Refining, deduplicating, or restructuring the backlog.
- Noticing a Linear ticket's status doesn't match reality (see [`documentation-standards`](../documentation-standards/SKILL.md) for the documentation side of this same problem).

## Instructions

### 1. Review before proposing anything

Before suggesting a single new issue, review what's already there:

- **Existing projects** — what's the current project/phase structure, and does new work already have a natural home?
- **Existing issues** — search by keyword, not just by title guess. A relevant ticket can be phrased very differently than you'd expect, or sitting in a project that's since been superseded.
- **Existing labels** — is there already a label taxonomy, or is it a grab-bag of leftover, unused, or foreign labels that needs cleanup before adding more?

This review is not optional overhead — it's the entire point. A refinement pass that skips it just adds noise to what's already there.

### 2. Prefer updating over creating

- **Merge duplicates** when you find two issues describing the same work.
- **Split oversized issues** when one ticket is actually several independent pieces of work bundled together (a classic sign: the description covers two unrelated concerns, or the acceptance criteria only partially maps to the title).
- **Improve titles and acceptance criteria** on existing issues rather than leaving a vague ticket in place and creating a clearer one next to it.
- **Apply consistent labels and priorities** across the existing set, not just on anything newly created.

### 3. Distinguish "duplicate" from "superseded"

These need different treatment:

- A **duplicate** is two open issues describing the same not-yet-done work — merge them.
- A **superseded** issue is an old, broad ticket that's since been replaced by several newer, more specific ones that actually shipped (or are actively tracked). This is common in a backlog that's gone through a rewrite or a major restructuring. Don't silently delete a superseded issue — cancel/archive it with a comment naming what replaced it, so the history stays traceable. A stale project holding open issues that were long since superseded elsewhere is a strong signal that project itself needs to be folded or retired.

### 4. Cross-check "Done" against reality before trusting it

A ticket marked Done in Linear is a claim, not a guarantee — especially on a fast-moving backlog where later work can silently break an earlier ticket's acceptance criteria. Before treating a Done ticket as settled:

- If you're reviewing an area where the code and the ticket's stated acceptance criteria might have drifted, check the code.
- If a "Done" ticket's AC is violated by the current implementation, that's a **regression**, and the right move is usually to reopen that ticket (labelled as a bug) rather than filing a fresh duplicate that loses the original ticket's context and history.
- If two tickets interact (a later one restructures something the earlier one shipped), check whether the interaction silently broke a guarantee neither ticket individually violates.

### 5. Structuring the backlog

- **Epics** should usually be existing Linear projects or milestones, not new containers invented for the occasion — check whether the work already has a natural home before creating a new grouping.
- **Identify dependencies** (blocked-by / relates-to) between issues, especially before recommending a build order — a critical-path item buried without its dependency noted will get picked up out of order.
- **Recommend project restructuring** when it's actually warranted: projects with no priority set, projects holding stale/superseded issues, or projects whose issues would more sensibly live under an existing milestone elsewhere. Don't restructure just to have done something — a good existing structure should be left alone, and that's a valid, worth-stating conclusion.

### 6. Never execute without explicit instruction

Producing a refinement plan — proposed merges, splits, new tickets, restructuring — is not the same as making those changes in Linear. **Do not create, edit, cancel, or otherwise modify a Linear issue unless the user has explicitly asked for it in the current conversation.** Present the plan, get a decision, then execute exactly what was approved — not a superset of it.

## Examples

**Superseded, not duplicate.** An old, broad ticket like "build the offer negotiation system" from early in the project has since been replaced by a dozen specific, shipped tickets covering counters, expiry, messaging, and turn-taking individually. Don't merge it with any one of those — cancel it with a comment listing the tickets that superseded it, since it's not really "the same work," it's obsolete framing for work that's since been done in finer detail.

**A regression, not a new feature request.** While reviewing the backlog, a Done ticket's acceptance criteria says "only the mandated agent can update negotiation terms," but the shipped code lets any agent do so on first write. This is a reopened bug against that ticket (with a comment explaining what's now failing), not a brand-new ticket proposing "add negotiation permission checks" — the new ticket framing would lose the fact that this was already promised and shipped incorrectly.

**Splitting an oversized ticket.** A ticket titled "squad import + club roles/permissions" bundles a CSV-upload data feature with an access-control feature that have nothing to do with each other beyond both touching clubs. Split it into two tickets, each with its own scope and acceptance criteria, and link them as related rather than leaving one bloated ticket that will inevitably get partially implemented and then stall.

## Related skills

- [`documentation-standards`](../documentation-standards/SKILL.md) — when a Linear ticket's status and `docs/IMPLEMENTATION_STATUS.md` disagree, both need reconciling; this skill handles the Linear side.
- [`engineering-standards`](../engineering-standards/SKILL.md) — a code review that surfaces an out-of-scope gap is exactly the kind of thing that becomes a backlog candidate for this skill, rather than being silently fixed or silently dropped.
- [`product-principles`](../product-principles/SKILL.md) — the lens for judging whether a proposed ticket is actually worth the backlog space, and how to prioritise it.
- [`session-lifecycle`](../session-lifecycle/SKILL.md) — at session end, Linear updates are *suggested*, using this skill's principles, never auto-created; that boundary is enforced there too, not just here.
