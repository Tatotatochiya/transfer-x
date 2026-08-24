---
title: "Session Handover"
last_updated: 2026-08-14
status: Active
owner: "TODO — assign a Documentation Owner"
---

# Session Handover

## Purpose

The single, current handover note between one working session and the next — human or Claude. Read this at the start of every session, right after [`PRODUCT_SPEC.md`](./PRODUCT_SPEC.md).

## Scope

In scope: the most recent session's summary — what's in motion right now.
Out of scope: full project history (see [`CHANGELOG.md`](./CHANGELOG.md)); this file is not a log.

## How this file works

This file is **overwritten**, not appended to, at the end of each session — maintained by the [`session-lifecycle`](../.claude/skills/session-lifecycle/SKILL.md) skill. It should always contain exactly one thing: the latest session's summary. If you want history, `CHANGELOG.md` has it; this file only needs to answer "what does the next session need to know right now."

## Latest Session Summary

**Session date:** 2026-08-14

**The working tree is clean and pushed.** This session's work landed as five commits, split along the lines the work actually divides into: the type-floor sweep, the three responsive/Safari defects, the squad valuation cell, then the two valuation-signal fixes made after them. Full detail per commit in [`CHANGELOG.md`](./CHANGELOG.md). `main` is level with `origin/main`.

Not committed, deliberately: three `claude-*.bat` launcher scripts in the repo root. They are per-machine Claude Code wrappers (one sets `DEEPSEEK_API_KEY`), not project code — either add them to `.gitignore` or move them outside the repo.

**Completed work:**

Four device-reported UI defects, all pre-existing, all reproduced and verified in a headless browser against the running stack rather than by reading CSS. Full detail in [`CHANGELOG.md`](./CHANGELOG.md) and the two new [`IMPLEMENTATION_STATUS.md`](./IMPLEMENTATION_STATUS.md) rows.

- **Type below the design system's own floor in 88 places.** `design_handoff_transferx/CLAUDE.md` rule 5 sets an 11px minimum (uppercase overlines only) and a 13px body floor. 75 uses of `text-[10px]`, and 13 of `text-[9px]` that a first sweep missed because it grepped only for the former. Classified per site rather than swept: **52 → 11px** (non-prose tokens — overlines, `FT`/`NS` codes, position codes, avatar initials, `⌘K`, bare numerals in count pills), **36 → 13px** (anything read as words). Nothing renders below 11px now, verified by grepping every arbitrary size under 11.
- **Tier-2 figure grids overflowed on tablet only.** `auto-fit minmax(180px, 1fr)` inside a shell whose padding steps at `md:`/`lg:` packs a **4th column into a container narrower than desktop's** between roughly 820–900px, and `formatCurrency` emits unbreakable full-precision values (`£128,500,000`). Raised to `minmax(230px, 1fr)` — the largest floor still yielding 4 columns at 1280px, so desktop and mobile are unchanged. Four grids fixed; two were at `minmax(150px)` and overflowed on a 375px phone too.
- **Every tinted pill rendered solid on Safari < 16.2, hiding its own text.** Reported as two unrelated-looking symptoms — an empty grey `BOTH` badge on My Club, and Top Form as solid green blobs — which proved to be one root cause. Fixed once in `index.css`.
- **Compare/Shortlist escaped the player card on a phone** — a regression introduced by the type lift, on top of a `grid-cols-2` layout untenable at 166px regardless.
- Tier-1 mobile card built to `RESPONSIVE.md`'s spec (17px/700 name, 2-line clamp, 48px full-width button — the old 36px button also missed rule 6's 44px touch-target floor); Browse Players to 1 column below 640px.
- **Loans & free-agent capability review** — investigation only, no code changed. See *Outstanding work*.

**Important decisions:**

- **The `color-mix()` fallback is fixed globally in CSS, not per component.** Tailwind v4 compiles `bg-success/20` as `background-color: var(--success)` **plus** an `@supports (color: color-mix(…))` block carrying the real tint. Without that support the fallback paints **fully opaque**, so any pill whose text comes from the same token disappears — `Badge` neutral is `#667085` on identical `#667085`, contrast **1.0:1**. A scan found **101 sites** with that pattern. The alternative considered and rejected was adding solid `-bg-badge` tokens and rewiring components: that is the design system's own pattern (`--danger-bg-badge` already exists), but it fixes 2 of 101 while leaving 99 on a different mechanism. One `@supports not (…)` block covering all 47 utilities in both themes was the better trade.
- **That block emits `rgba()`, and is generated rather than hand-written.** Tailwind cannot emit `rgba()` itself — it only has `var(--token)`, and CSS cannot decompose a custom property into channels; the generator knows the hex. `rgba()` also beats a pre-blended solid: no assumption about what sits behind the pill, and overlays like `bg-ink/40` stay see-through instead of turning a modal scrim opaque. Generator checked in at `frontend/scripts/gen_color_mix_fallback.py`.
- **Desktop and mobile were held byte-identical in every fix.** Each change is mobile- or tablet-scoped — `sm:` variants, or a grid floor chosen so 1280px still yields 4 columns. Verified by measurement at both ends, not assumed.
- **`RESPONSIVE.md` has two different card specs and they are easy to conflate.** Table cards are 14px/600 identifier + 12–13px supporting + 64px min height; `ResponsiveTable`'s `DefaultCard` already matches that exactly and was **not** changed. The 17px/700 + 13px figures belong to the **tier-1** card only. An earlier claim in this session that mobile table cards were built smaller than spec was wrong, and is corrected here.
- **The 720 `text-xs` (12px) uses were deliberately left alone.** 12px in a dense desktop table is defensible; a blanket lift needs a responsive step, not a find-and-replace. Note that `RESPONSIVE.md` line 150 explicitly says *"Do not scale type down"* and permits only three responsive roles — so a global mobile step would contradict the spec's letter and needs a real decision rather than a quiet change.

**Outstanding work:**

- **Loans cannot be proposed, only retrofitted.** Migration `0029` (TRA-56) gave `Deal` `deal_type`, `loan_start/end/fee`, `option_to_buy`, `obligation_to_buy`, `obligation_conditions` and `sell_on_pct`, and the deal room negotiates them (PERMANENT/LOAN toggle, `deal_type` in the terms-diff set). But `Offer` has **none** of it, and **no code path anywhere constructs a `DealType.LOAN`** — all five `Deal()` sites create `PERMANENT`, `FREE_TRANSFER` or `PRE_CONTRACT`. A loan is therefore sent as a fee-less *permanent* offer and restructured after acceptance. `CreateOfferPage.tsx:232` admits it in its own copy ("No fee — a free transfer, **loan**, or swap"). Three consequences:
  - **Money.** `offers/service.py:173` is `reserve = (fee_amount or 0) + add_ons_total`. A loan sent as "No fee" reserves **£0** and, being zero, sits below every approval threshold. The wage share — usually the entire cost of a loan — is never reserved at all. A season-long loan at £200k/wk is £8–10m of commitment with no reservation and no approval. Same root as the fee-less-offer bug fixed 2026-08-13, but structural rather than a crash.
  - **Seller's view.** The order book ranks by fee, so a loan, a swap and a free transfer are indistinguishable in the one screen where a seller chooses between them.
  - **Audit trail.** The deal's history shows it agreed as permanent, then mutated after acceptance.
- **Free-agent signing is already shipped** — `POST /players/{id}/sign` → `create_free_agent_deal` (seller `NULL`, fee 0, `FREE_TRANSFER`), wired to Player Market Detail, alongside a Bosman `pre-contract` path with a 180-day legality window. A *represented* free agent already routes straight to `AGENT_NEGOTIATION` via `maybe_invite_agent_for_deal`. The only gap: an **unrepresented** free agent parks at `AGREEMENT` — a stage meaning "the two clubs agree a fee" when there is no seller and no fee — needing one meaningless click. Start those at `PERSONAL_TERMS` instead. **Do not skip `PERSONAL_TERMS` itself**: the comment at `deals/service.py:429` records that it used to jump straight to `PAPERWORK`, letting deals complete without the player ever consenting (TRA-60).
- **`DealType` enum drift — one-line fix.** `frontend/src/types/enums.ts:46` declares `"PERMANENT" | "LOAN"` while the backend has four values, and `DealDetailPage.tsx:1148` renders `deal_type === "LOAN" ? "Loan" : "Permanent"`. **Every free-agent signing and every Bosman pre-contract currently displays as "Permanent"** in the deal room.
- **81 of the 135 `text-[11px]` uses carry no `uppercase` class**, so they violate rule 5 exactly as the 10px ones did — including the "Amount" and "Deadline" labels inside the tier-1 card that was rebuilt this session. The natural next tranche.
- **`RESPONSIVE.md` also specifies a 2-column tablet tier-2 grid** (a tidier 2×2 than the 3+1 that auto-fit now produces) and a 28px→24px mobile figure size. Neither was causing the overflow; both are visible layout changes, so both were left as decisions rather than made quietly.
- **44 pre-existing TypeScript errors** (audit [H9](./DEMO_READINESS_AUDIT.md)) — 23 genuine mismatches in app code, 14 unused declarations, 5 test-fixture drift, 2 missing Node types. Untriaged. **This was recorded as 47 and that was a miscount**; corrected here, in the audit, and in `IMPLEMENTATION_STATUS.md`.
- Everything the previous handover listed that this session did not touch: **audit [H8](./DEMO_READINESS_AUDIT.md)** (`PublicRoute` does not wait for token bootstrap), anonymity not covering auction bids, offering for an `EXTERNAL` player creating an unacceptable `to_club_id = null` offer, **C3** (close self-registration — still the oldest open decision), H1, H2, H3, demo generator scenarios M1–M4/S1–S2, the orphaned £15,000,001 committed budget on Liverpool's W. Fofana deal, and the unverified `deal_sla`/`expire_mandates` job bodies.

**Risks:**

- **The `color-mix` diagnosis rests on an unconfirmed device version.** It requires the iPad to be on iPadOS ≤ 16.1. The simulated reproduction matched *both* reported symptoms exactly, so confidence is high — but the version was asked for and never confirmed. If that iPad is on 17+, a real bug was fixed but it was not *the* bug, and the original symptom will still be there.
- **The fallback block is generated and can go stale.** New `/opacity` utilities are not covered until `gen_color_mix_fallback.py` is re-run (`npx vite build` first — it reads the built CSS). A stale entry degrades to today's behaviour, not worse.
- **The Docker frontend service is a production build.** None of this session's work is visible on a device until `docker compose build frontend`. The running container currently serves a build predating the `color-mix` fix.
- **`npx tsc --noEmit` still checks nothing** — use `npx tsc -b --noEmit`. Still not in CI, so it can silently no-op again.
- **Work is going directly to `main`**, with no PR review step.
- Carried forward, all still true: **`commission_pct` is a fraction, not a percentage**; **`commissionpayer` is `BUYER`/`SELLER`/`PLAYER`**; **`app.clubs.service` must be imported explicitly in standalone scripts**; **every dev password is `password123`**, including on Railway; **deleting an offer row with raw SQL strands its budget reservation** — withdraw through the API instead.

**Recommended next task:**

1. **`docker compose build frontend`, then re-check the iPad.** The frontend container is a built image with no source mount, so it still serves the pre-fix bundle — none of this session's UI work is visible on `:5173` until it is rebuilt. That also settles the unconfirmed iPadOS version question in *Risks*.
2. **Then either** the **`DealType` enum drift** (one line, and free-agent deals are actively mislabelled in the deal room right now), **or scope loans onto the `Offer`** — `deal_type` plus loan fields on `Offer`, carried into the `Deal` on acceptance instead of defaulting to `PERMANENT`, with the reservation computing loan fee + wage share so approvals actually bite. The budget hole is the part that matters; the UI is the easy half.

## Related documents

- [`PRODUCT_SPEC.md`](./PRODUCT_SPEC.md) — read this first, then this file
- [`CHANGELOG.md`](./CHANGELOG.md) — full change history
- [`IMPLEMENTATION_STATUS.md`](./IMPLEMENTATION_STATUS.md) — current verified build status
