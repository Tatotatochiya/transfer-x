---
title: "Type and colour: one scale, one meaning per colour"
last_updated: 2026-11-11
status: Implemented 2026-11-11
owner: "TODO — assign a Product Owner"
---

# Type and colour: one scale, one meaning per colour

Written against `Tatotatochiya/transfer-x` `main` at `e7e2453` (11 Nov 2026). Applies to `frontend/src/**` (217 `.tsx` files) and `frontend/src/index.css`.

**The problem.** TransferX has no shared type scale. Each page picks its own sizes, and there are now three styles in one app:
- the offer, deal and transfer-header work (13/15/16/19–20px)
- the older pages (`text-xs`/`text-sm`, 12/14px, with 11px uppercase labels)
- Lite (rem sizes, 15–40px)

The code uses **41 different font-size classes**. Pages show **up to 11 sizes** at once. Up to **77% of a page's text is under 13px**.

Colour comes entirely from tokens, which is good, but several colours carry more than one meaning:
- red means "your move", errors, delete and the FWD position
- the four position colours are the four status colours
- blue marks things you can't tap
- the AI shares the Agent badge's purple
- tints are mixed by hand with opacity

**Goal.**
- Seven named text sizes, nothing under 13px, 15px body text everywhere.
- Each colour means one thing.
- Reached through shared-component defaults and a guarded, page-by-page sweep, not a rewrite.
- **No behaviour changes.** This is visual only.

**Design reference.** `TransferX - Type and Colour.dc.html` in this folder (needs `support.js` and `typography-2026-11-11/` beside it):
- §1: measurements and captures
- §2: the scale
- §3: before and after
- §4: colour roles
- §5: rules

`measure-type.mjs` in this folder is the script that produced the measurements. Reuse it to check the result (§11).

Where this README and the mock disagree, **this README wins** (§14).

---

## 0. Before you start

1. Follow `session-lifecycle`. Read `docs/PRODUCT_SPEC.md`, `docs/SESSION_HANDOVER.md` and `docs/design-system/TOKENS.md` ("Typography" and the colour tables). This spec **replaces** TOKENS.md's typography table and its "minimum 11px" rule. Also read `RESPONSIVE.md` ("Typography on small screens", which this replaces) and `frontend/scripts/gen_color_mix_fallback.py` (opacity fallbacks for Safari < 16.2).
2. Apply `engineering-standards`: small, reviewable commits, one area per commit, no logic changes mixed in.
3. Branch `type-and-colour`. Build in the order in §10. Every commit must leave the app looking at least as good as before.
4. This is a large mechanical change. **Never change text content, behaviour or layout logic** while sweeping, except the casing fix in §7.3.
5. If anything in this spec contradicts the code (a token that doesn't exist, a component that already does something), say so in your summary rather than quietly picking one.

---

## 1. Why: what renders today

Measured on the running app (demo data, signed in as Arsenal) with `measure-type.mjs`, laptop 1280 × 790. Shares are of visible characters in the main content. Phone figures are within a few points, except Browse Players, where the phone list brings under-13px text down to 11%.

| Page | Sizes on screen | Most text is | Text < 13px | Text ≥ 15px |
|---|---|---|---|---|
| Dashboard | 9 | 14px | 28% | 8% |
| Browse Players | 7 | 12px | 43% | 4% |
| Player profile | 10 | 13px | 40% | 5% |
| **Offer** | 11 | 14px | **5%** | **20%** |
| **Deal room** | 11 | 14px | **10%** | **35%** |
| Transfers board | 4 | 12px | **56%** | 1% |
| My Club | 7 | 13px | 19% | 1% |
| Finance | 7 | 14px | 18% | 5% |
| Notifications | 6 | 14px | 19% | 1% |
| Account | 5 | 12px | **77%** | 0% |
| Make an offer | 5 | 13px | 16% | 2% |
| Lite home | 6 | 18px | 0% | 100% |

**Counts in code** (non-test `.tsx` files):

| Pattern | Count |
|---|---|
| `text-xs` (12px) | 740 |
| `text-[11px]` | 141 |
| `text-[10px]` / `[9px]` / `[8px]` | 13 |
| `uppercase` (with `tracking-wider` ×142) | 181 |
| Opacity tints such as `bg-success/15` and `ring-warning-fill/30` | a dozen shades per hue |

Some sizes are written two ways: `text-[15px]` and `text-[0.9375rem]`, `text-[17px]` and `text-[1.0625rem]`.

**Colour.** No raw hex in components, and one raw Tailwind colour (`bg-slate-800`). The tokens collide on meaning:

| Token or value | Means |
|---|---|
| `--pos-gk-text` `#7a4a00` | = `--warning-text` |
| `--pos-fwd-text` `#9b1e22` | = `--danger-text-alt` |
| `--pos-def-text` `#1050ac` | = `--accent-hover` |
| `--pos-mid-*` | a success green |
| AI (`AskAboutButton`, ✦ buttons) | uses `role-agent-text` |
| `Badge variant="info"` | is accent blue ("Contracted" reads as a link) |
| Player page `TabBar` active underline | `bg-success` (green) |
| `Button variant="primary-success"` | a green primary button (one use, `PlayerProfilePage`) |
| Finance "Committed" series | accent blue |
| Price track (offer page) | red for the other club, blue for you |
| Dark theme `--accent` | emerald `#10b981` (same family as success), with white button text at about 2.5:1 contrast |

---

## 2. Success criteria

- [ ] `index.css` defines the seven text roles (§4), the Lite roles (§8) and the colour tokens in §5, for **both** themes.
- [ ] **No text under 13px** on any non-admin page. `measure-type.mjs` reports `0%` under 13px on every route in its list, at 390 and 1280 wide.
- [ ] **At most six sizes on screen per page** (Caption, Small, Body, Section, Headline, Title, plus Display where a card has a hero figure). Lite counts against its own scale.
- [ ] Every main-app page's dominant text size is **15px** (Body) or 14px (Small) on table-heavy pages.
- [ ] No `text-xs`, `text-[Npx]`, `text-[Nrem]`, `text-sm|base|lg|xl|2xl|3xl…` and no opacity tints on colour tokens in `frontend/src` (outside the allowlist in §9), enforced by a test.
- [ ] Positions, contract state, account roles and deal types render in the **neutral** style. Blue appears only on things you can tap or select. Red appears only for "needs you", errors and destructive actions. Violet appears only for the AI.
- [ ] All the contrast pairs in §5.4 pass 4.5:1 in both themes, checked by a test.
- [ ] Money: lists, cards and headers use the one compact format ("£21.5M", "£450K", "£52M"); full figures appear only where terms are agreed (§6.6).
- [ ] Lint, typecheck and `vitest` pass. Dark theme checked by hand on every swept area.

---

## 3. Decisions

- **D1. Seven text roles** (§4): Caption 13, Small 14, Body 15, Section 17, Headline 20, Title 24 (phone 22), Display 32 (phone 28). Plus one composite, `eyebrow`, for status overlines and table column headers. Components use **role utilities only** (`text-body`, `text-caption`, …), never `text-sm` or `text-[15px]`.
- **D2. 13px is the floor.** That covers badges, counts, timestamps, column headers and chart labels. **This replaces TOKENS.md's "11px for overlines".** The new pages already follow it (13px floor, per the deal and offer specs).
- **D3. 15px body.** Reading text, list rows, buttons and tab labels are 15px. Secondary lines and table cells are 14px. Inputs are **16px below 1024px** (iOS zooms inputs under 16px) and 15px from 1024px.
- **D4. Sentence-case headings.** Card and section headings are Section (17px/700), sentence case. `uppercase` is allowed **only** through the `eyebrow` utility, for status overlines ("Your move · reply by …") and table column headers.
- **D5. Weights.** 400 for reading, 600 for labels, values and buttons, 700 for headings and figures. 500 is allowed only for navigation labels and inactive tab labels. 800 is Lite only. Every number uses `tabular-nums`.
- **D6. Colour roles** (§5): Ink, Interactive (blue), Needs you (red), Caution (amber), Done (green), AI (violet), Neutral (grey). Categories are always neutral.
- **D7. Tints come from tokens**, never from opacity on a solid colour (§5.3). Allowed exceptions: overlays and backdrops (`bg-ink/40`), progress-bar fills, and focus rings drawn from `accent`.
- **D8. Lite keeps its larger scale**, expressed as `lite-*` roles one step up (§8).

### Open questions (build the default unless told otherwise)

- **Q1. Dark theme accent.** Today it's emerald, which collides with "done" green, and white text on it fails contrast. **Default:** a blue accent in dark mode, plus a new `--on-accent` token for text on accent fills (§5.2). This visibly changes dark mode from green to blue. If you'd rather keep emerald, keep `--on-accent` anyway (it fixes the contrast) and skip the hue change.
- **Q2. Admin pages** (`pages/admin`, 22 files, 293 sub-13px uses). **Default:** swept last (§10, step 9), and allowed to finish in a follow-up PR. They're staff-only.

---

## 4. Type scale: tokens and utilities

In `frontend/src/index.css`, add a **plain `@theme` block** (static values, not `@theme inline`; these don't change with the theme). Tailwind v4 then generates `text-caption`, `text-small` and the rest, each with its line height:

```css
@theme {
  --text-caption: 13px;   --text-caption--line-height: 18px;
  --text-small: 14px;     --text-small--line-height: 20px;
  --text-body: 15px;      --text-body--line-height: 24px;
  --text-input: 16px;     --text-input--line-height: 24px;   /* inputs below 1024px only */
  --text-section: 17px;   --text-section--line-height: 24px;
  --text-headline: 20px;  --text-headline--line-height: 28px;
  --text-title-sm: 22px;  --text-title-sm--line-height: 28px;
  --text-title: 24px;     --text-title--line-height: 30px;
  --text-display-sm: 28px; --text-display-sm--line-height: 34px;
  --text-display: 32px;   --text-display--line-height: 38px;

  /* Lite, one step up (§8) */
  --text-lite-caption: 16px;  --text-lite-caption--line-height: 24px;
  --text-lite-body: 18px;     --text-lite-body--line-height: 28px;
  --text-lite-section: 20px;  --text-lite-section--line-height: 28px;
  --text-lite-headline: 24px; --text-lite-headline--line-height: 32px;
  --text-lite-title: 32px;    --text-lite-title--line-height: 40px;
  --text-lite-title-lg: 40px; --text-lite-title-lg--line-height: 48px;
  --text-lite-display: 36px;  --text-lite-display--line-height: 44px;
}

@utility eyebrow {
  font-size: var(--text-caption);
  line-height: var(--text-caption--line-height);
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
```

> Don't name the utility `overline`: Tailwind already has `overline` (text-decoration).

**Role usage:**

| Role | Utility | Weight | Use |
|---|---|---|---|
| Display | `text-display-sm sm:text-display` | 700, `tracking-[-0.01em]`, `tabular-nums` | One hero figure per card at most (Finance budgets, a deal's fee) |
| Title | `text-title-sm sm:text-title` | 700, `tracking-[-0.01em]` | The page `h1` |
| Headline | `text-headline` | 700 | The one sentence that matters: the status card headline, empty-state titles, dialog and sheet titles |
| Section | `text-section` | 700 | Every card and section heading, sentence case |
| Body | `text-body` | 400 (strong 600) | Reading text, list rows, buttons, tabs, segmented controls |
| Small | `text-small` | 400 (strong 600) | Secondary lines, meta under a name, table cells, `Metric` rows |
| Caption | `text-caption` | 400 (labels 600) | Field labels above values, timestamps, notes, badges, chart labels |
| Eyebrow | `eyebrow` | 700, caps | Status overlines and table column headers only |

**Figures inside cards and tiles** (not hero): Headline 20 (tiles on phones) or Title 24 (tiles from 640px), `tabular-nums`.

**Line length:** paragraphs of Body get `text-wrap: pretty` and `max-w-[68ch]` where they span a wide card.

---

## 5. Colour: tokens and roles

### 5.1 Roles

| Role | Tokens | Use for | Never for |
|---|---|---|---|
| **Ink** | `text`, `text-secondary`, `text-muted` | All reading text. `text-muted` (#667085) is the lightest text allowed | Text lighter than muted |
| **Interactive** | `accent`, `accent-hover`, `accent-active`, `accent-bg`, `accent-bg-strong`, `accent-ring` (new), `on-accent` (new) | Buttons, links, selected tabs, chips and segments, focus | Statuses, positions, chart series, "your side" of a comparison |
| **Needs you** | `danger`, `danger-text`, `danger-text-alt`, `danger-bg`, `danger-ring`, `danger-border` | Your move, overdue, errors, destructive confirms | Positions, the other club's figures, low form |
| **Caution** | `warning-*`, `warning-ring` (new) | Deadlines close, on hold, budget nearly used, low form | Goalkeepers |
| **Done** | `success`, `success-text`, `success-dot`, `success-bg` (new), `success-ring` (new) | Completed, passed, signed, good form | Midfielders, toggles being on |
| **AI** | `ai-text`, `ai-bg`, `ai-ring` (all new) | Everything TransferX's AI writes or suggests: ✦ buttons, advice panels, fit scores, AI search | The Agent account badge |
| **Neutral** | `surface-inset`, `text-secondary`, `border` | Categories and plain facts: positions, contract state, account roles, deal type, chart series | — |

### 5.2 New and changed tokens

Add to the `@theme inline` mapping (`--color-<name>: var(--<name>)`) and to both palettes:

| Token | Light | Dark |
|---|---|---|
| `--success-bg` | `#e7f4ec` | `#0f2a1a` |
| `--success-ring` | `#b7dfc4` | `#1f5132` |
| `--warning-ring` | `#efd9a8` | `#5a4413` |
| `--accent-ring` | `#c7dafa` | `#284a7a` |
| `--ai-text` | `#5b2d9e` | `#c4a5f5` |
| `--ai-bg` | `#f5f0fd` | `#241a3d` |
| `--ai-ring` | `#ddcdf5` | `#45316e` |
| `--on-accent` | `#ffffff` | `#0b1220` |

**Changed values** (call sites don't change):

| Token | Light | Dark | Why |
|---|---|---|---|
| `--pos-gk-bg`, `--pos-def-bg`, `--pos-mid-bg`, `--pos-fwd-bg` | `#eef0f3` | `#1e293b` | Positions are categories: neutral |
| `--pos-gk-text`, `--pos-def-text`, `--pos-mid-text`, `--pos-fwd-text` | `#344054` | `#cbd5e1` | Same |
| `--role-club-bg`, `--role-agent-bg` | `#eef0f3` | `#1e293b` | Roles are categories: neutral, with their icon |
| `--role-club-text`, `--role-agent-text` | `#344054` | `#cbd5e1` | Same; free purple for the AI |

**Dark accent, Q1 default:** `--accent #5b9bf8`, `--accent-hover #7db0fa`, `--accent-active #3d86f5`, `--accent-soft #93bdfb`, `--accent-bg #13243f`, `--accent-bg-strong #172d4f`, `--accent-avatar #1a3254`. `--on-accent` (dark) is `#0b1220`, so primary buttons in dark mode are light blue with dark text.

**Every `bg-accent … text-white`** (38 occurrences in 27 files, including `Button` `primary` and `EmptyState`) becomes `text-on-accent`. Light mode is unchanged (`#ffffff`).

**Remove** `Button` variant `primary-success`. Its one use (`PlayerProfilePage.tsx:245`) becomes `primary`.

**Replace** the one raw `bg-slate-800` with the matching token (`bg-ink` or `bg-surface-inset`, whichever the context needs). Report which.

After changing `index.css`, re-run `frontend/scripts/gen_color_mix_fallback.py` as its README says, so the Safari < 16.2 fallbacks pick up the new values. Fewer opacity tints (§5.3) means fewer fallbacks.

### 5.3 Tints: opacity to tokens

| Today (any opacity) | Becomes |
|---|---|
| `bg-success/10`, `/15`, `/20`, `bg-success-text/10` | `bg-success-bg` |
| `ring-success/20`, `/30`, `/40` | `ring-success-ring` |
| `bg-warning-fill/10`, `/15`, `/20`, `/25` | `bg-warning-bg` |
| `ring-warning-fill/20`, `/25`, `/30`, `/40` | `ring-warning-ring` |
| `bg-danger/10`, `/15`, `/20` | `bg-danger-bg` |
| `ring-danger/20`, `/30` | `ring-danger-ring` |
| `bg-accent/10`, `/15`, `/20` | `bg-accent-bg` |
| `ring-accent/20`, `/30`, `/40` | `ring-accent-ring` |
| `bg-text-muted/15`, `ring-text-muted/30` | `bg-surface-inset`, `ring-border` |
| `bg-role-agent-text/10`, `/20`, `ring-role-agent-text/30` (AI) | `bg-ai-bg`, `hover:bg-ai-ring/…` → `hover:brightness-95`, `ring-ai-ring` |

The D7 exceptions stay as they are.

### 5.4 Contrast pairs (tested, §9)

Each pair must reach 4.5:1 in **both** themes:

| Text | Background |
|---|---|
| `text` | `surface`, `page`, `surface-inset` |
| `text-secondary` | `surface`, `surface-inset` |
| `text-muted` | `surface` |
| `accent` | `surface` (links) |
| `on-accent` | `accent` |
| `danger-text` | `danger-bg`, `surface` |
| `warning-text` | `warning-bg` |
| `success-text` | `success-bg`, `surface` |
| `ai-text` | `ai-bg`, `surface` |
| `pos-*-text` | `pos-*-bg` |

If a dark value above fails, adjust the dark value (not the light one) and note it.

---

## 6. Shared components: the big lever

Change these first (§10, step 2). Most pages improve immediately. Keep every prop and API; change only classes.

### 6.1 Text

- **`PageHeader`:**
  - `h1` → `text-title-sm sm:text-title font-bold tracking-[-0.01em]`
  - subtitle → `text-small text-text-secondary`
- **`SectionHeader`:**
  - `h2` → `text-section font-bold text-text`; **remove** `uppercase tracking-wider text-text-muted`
  - Check every caller's `title` string reads correctly in sentence case (§7.3)
- **`Panel`:**
  - title → `text-section font-bold`
  - subtitle → `text-small text-text-secondary`
- **`Modal`:** title → `text-headline font-bold`
- **`Sheet`:**
  - title → `text-headline font-bold`
  - subtitle → `text-small text-text-secondary`
  - close × → `text-headline`
- **`StatCard`:**
  - label → `text-caption font-semibold text-text-secondary`, **no uppercase**
  - value → `text-headline sm:text-title font-bold tabular-nums`
  - subtext → `text-small`
- **`Metric`:**
  - row → `text-small`
  - value → `font-semibold tabular-nums`
- **`Badge`:**
  - base → `text-caption font-semibold`, pills `px-2 py-0.5 rounded-full ring-1`
  - variants:

    | Variant | Classes |
    |---|---|
    | `success` | `bg-success-bg text-success-text ring-success-ring` |
    | `warning` | `bg-warning-bg text-warning-text ring-warning-ring` |
    | `danger` | `bg-danger-bg text-danger-text ring-danger-ring` |
    | `neutral` | `bg-surface-inset text-text-secondary ring-border` |
    | `ai` (new) | `bg-ai-bg text-ai-text ring-ai-ring` |
    | `info` | **an alias of `neutral`**; mark it `@deprecated` in a comment and migrate its 5 callers to `neutral` |

  - The `move-*` text variants stay.
- **`Button`:**

  | Size | Classes |
  |---|---|
  | `sm` | `text-small` |
  | `md` | `text-body` |
  | `lg` | `text-body` (`min-h-12` stays) |

  - `primary` → `bg-accent hover:bg-accent-hover text-on-accent`
  - `secondary`, `danger` and `ghost` labels → `font-semibold`
- **`Input` / `Select`:**
  - label → `text-small font-semibold text-text-secondary`
  - field → `text-input lg:text-body`
  - error → `text-caption`
- **`Tabs`:**
  - label → `text-body`
  - active → `border-accent text-text font-semibold`
  - inactive → `text-text-secondary font-medium`
  - Underline in accent (selected = interactive), text in ink.
- **`SegmentedControl`:**
  - `md` → `text-body`, `sm` → `text-small`
  - count badge → `text-caption` with `bg-accent text-on-accent`
- **`EmptyState`:**
  - title → `text-section font-bold text-text`
  - body → `text-body text-text-secondary`
  - CTA → `text-on-accent`
- **`Alert`:**
  - `text-body`
  - variants → token tints (§5.3): `warning` `bg-warning-bg ring-warning-ring`, `success` `bg-success-bg ring-success-ring`
  - `info` → `bg-accent-bg text-text ring-accent-ring`; text in ink, so it isn't mistaken for a link
- **`Timeline`, `Tooltip`, `Pagination`, `ResponsiveTable`:**
  - all text ≥ `text-caption`
  - table header cells → `eyebrow text-text-secondary`
  - table cells → `text-small`

### 6.2 Shared header and cards from the redesigns

- **`TransferHeader`** (`components/transfer`):
  - name → `text-title-sm sm:text-title`
  - sub line → `text-small`
  - amount → **compact** money (§6.6) in `text-headline sm:text-title`
- **`StatusCardShell`:**
  - overline → `eyebrow` (13px)
  - headline → `text-headline`
  - body → `text-body`
- **`PlayerRow`, `PlayerCard`, `PlayerListRow`:**
  - name → `text-body font-semibold`
  - secondary line → `text-small`
  - chips → `Badge` / `text-caption`
- **`FallbackImage` initials:** at least `text-caption` at 28px+ boxes. Below 28px (crest dots), hide the initials and show a neutral circle (`bg-surface-inset`). Text under 13px is not allowed.

### 6.3 Colour meaning fixes

- **AI:** `AskAboutButton`, the ✦ buttons in `components/ai/*`, `MarketRecommendationsPanel`, AI fit score, `NLPlayerSearch` / `MarketSearch` Describe toggle → `ai-*` tokens (or `Badge variant="ai"`). Grep `role-agent-text` and move every **AI** use to `ai-*`. Account-type badges stay on `role-*` (now neutral).
- **Positions:** no call-site change; the tokens turn neutral (§5.2). Check `SquadTable`, `PlayerCard`, `PlayerRow`, `GlobalSearch`, `TransferHeader` and `LedgerTabs`, and report any position colour that doesn't come from `pos-*`.
- **Contract state ("Contracted"):** `Badge variant="neutral"`.
- **Player page `TabBar`** (`PlayerMarketDetailPage.tsx` ~l.115–140):
  - underline `bg-success` → `bg-accent`
  - labels → `text-body`
  - count → `text-caption`
  - Better: replace it with the shared `Tabs` if the props fit; otherwise match its classes.
- **Finance chart series** (Spent / Committed / Reserved dots and bars):
  - neutral series: `text` (Spent), `text-secondary` (Committed), `text-muted` (Reserved), or `ink` / `border` fills
  - a series turns `warning` only when the budget passes its warning threshold
  - Never `accent`.
- **Offer page price track** (`OfferStanding`):
  - markers in ink: the other club's in `text-secondary`, hollow, and yours in `text`, filled
  - the gap band → `bg-border`
  - labels → `text-caption`
  - The labels carry who's who. No red or blue.
- **Board column markers** (Buying / Selling left bars, `pages/board`): neutral (`bg-text-secondary`), not amber.

### 6.4 Dashboard and finance figures

- Dashboard figure tiles → `StatCard` (§6.1), `grid-cols-2` below 640px.
- Finance budget hero → Display, **compact** money (`£232.5M`), "left of £260M" in `text-small`. The breakdown rows (`Metric`) stay in full figures.

### 6.5 Lite

See §8.

### 6.6 Money (part of "looks consistent")

- **One compact format.** `formatCompactCurrency` returns the same as `formatCompact`: capital `M`/`K`/`B`, one decimal, and the trailing `.0` dropped. So "£52M", "£21.5M", "£450K", "£2.6B". Update `formatCompact` the same way (drop `.0`), then make `formatCompactCurrency` call it. Update their tests.
- **Where full figures stay** (`formatCurrency`, "£21,500,000"):
  - offer and deal **terms** cards, the counter, raise and new-offer forms, and the accept and complete confirmations
  - Finance ledger rows and history tables
  - CSV and exports
- **Compact everywhere else:** headers, status card headlines and bodies, tiles, list rows, cards, the board, notifications and Lite.
- If a compact figure would hide a difference that matters (two offers both "£21.5M" but £20K apart), the list shows full figures. Leave existing full-figure uses where that's the reason, and say so in a comment.

---

## 7. The sweep

### 7.1 Class map

| Today | Becomes |
|---|---|
| `text-[8px]` `[9px]` `[10px]` `[11px]` `[11.5px]` `[12px]` `text-xs` | `text-caption` |
| `text-[13px]` `[0.8125rem]` | `text-caption` |
| `text-sm` `[13.5px]` | `text-small` (14), **or** `text-body` where it's reading text (a sentence, a list row title, a button) |
| `text-[15px]` `[0.9375rem]` `text-base` (prose) | `text-body` |
| `text-[16px]` `text-base` (inputs) | `text-input lg:text-body` |
| `text-[17px]` `[1.0625rem]` `text-lg` `[1.125rem]` `[1.1875rem]` | `text-section` |
| `text-[19px]` `text-xl` `[1.25rem]` `[1.3125rem]` `[1.375rem]` | `text-headline` |
| `text-[22px]` `text-2xl` `[1.5rem]` (page titles) | `text-title-sm sm:text-title` |
| `text-2xl` (figures) | `text-headline sm:text-title` |
| `text-[28px]`–`[34px]` `text-3xl` `[1.75rem]`–`[2.5rem]` `text-4xl` `text-5xl` | `text-display-sm sm:text-display` (main app) |
| `uppercase tracking-wider text-[11px]`/`text-xs` (labels above values) | `text-caption font-semibold text-text-secondary`, sentence case |
| `uppercase` on section or card headings | `text-section font-bold`, sentence case |
| `uppercase` on table `<th>` and status overlines | `eyebrow` |
| `font-extrabold` / `font-black` outside Lite | `font-bold` |

**The rule for `text-sm`:** if the element is a sentence someone reads, a row's main label or a control's label, use `text-body`. If it's a secondary line, a table cell, metadata or a dense list, use `text-small`. When unsure, prefer `text-body`.

### 7.2 Order (one commit per area)

| # | Area | Files | < 13px uses | `uppercase` | Tints |
|---|---|---|---|---|---|
| 1 | `components/transfer`, `components/deals`, `pages/deals`, `components/offers`, `pages/offers` | 30 | 20 | 4 | 23 |
| 2 | `pages/market`, `components/market`, `components/players` | 34 | 140 | 23 | 69 |
| 3 | `pages/dashboard`, `pages/board`, `pages/club`, `pages/clubs`, `components/sales`, `pages/sales`, `pages/scouting`, `components/scouting` | ~20 | 105 | 13 | 30 |
| 4 | `components/ai`, `components/conversation`, `pages/notifications`, `pages/account`, `pages/auth`, `components/layout` | 23 | 99 | 17 | 50 |
| 5 | `pages/player`, `pages/agent` (player and agent accounts) | 6 | 84 | 25 | 44 |
| 6 | `pages/lite`, `components/lite` (§8) | 13 | 0 | 4 | 7 |
| 7 | `pages/admin`, `components/admin` (Q2) | 24 | 295 | 65 | 65 |

Counts are from `main` at `e7e2453`. The guard test (§9) prints the live numbers.

### 7.3 Casing

When you remove `uppercase`, look at the **source string**. Most are already sentence case ("Model value"). Fix any that were written in capitals or Title Case so they read as a sentence ("Transfer Budget" → "Transfer budget", "Wage Budget (weekly)" → "Wages a week"). Don't change wording otherwise. Tests that match on visible text may need the new casing; update them in the same commit.

### 7.4 Things not to change

- Layout, spacing, radii and component structure, except where a size change needs a min-height to keep 44px targets.
- Copy, except the casing in §7.3.
- Icons' pixel sizes (`h-4 w-4` etc.).
- Charts' internal SVG font sizes may stay as numbers, but ≥ 13.

---

## 8. Lite

Lite already reads well: there's nothing under 16px. Make it the same system one step up:

| Today | Becomes |
|---|---|
| `[0.9375rem]`, `[1rem]` | `text-lite-caption` (16) |
| `[1.0625rem]`, `[1.125rem]`, `text-base` (reading) | `text-lite-body` (18) |
| `[1.25rem]`, `[1.375rem]` | `text-lite-section` (20) |
| `[1.5rem]` | `text-lite-headline` (24) |
| `[1.75rem]`, `[2rem]` | `text-lite-title` (32) |
| `[2.25rem]`–`[2.5rem]` | `text-lite-title-lg` (40) at `lg`, or `text-lite-display` (36) for figures |

Colour rules (§5) apply to Lite unchanged. The "1 waiting" pill stays danger, because it means "needs you". `font-extrabold` stays allowed in Lite for the home greeting and tile titles only.

Check Lite at 390 and 1280: no visual change bigger than a 1–2px size snap.

---

## 9. Guard tests

**`frontend/src/test/designSystem.test.ts`** (new, runs in `vitest`):

1. **Banned classes.** Read every `frontend/src/**/*.tsx` except tests (`fs` + `fast-glob`, or `import.meta.glob` with `?raw`), strip comments, and fail on:
   - `\btext-(xs|sm|base|lg|xl|[2-9]xl)\b` and `\btext-\[[\d.]+(px|rem)\]`
   - `\buppercase\b` outside the `eyebrow` utility
   - `\b(bg|ring|border)-(success|warning-fill|danger|accent|text-muted|role-agent-text)/\d+` (tints), except the D7 list: `bg-ink/\d+`, and any class on an element marked `data-progress`
   - `font-(extrabold|black)` outside `pages/lite` and `components/lite`
   - `text-white` on the same element as `bg-accent`
2. **Ratchet.** `frontend/src/test/design-allowlist.json` maps file paths to their remaining count per rule. At step 1 (§10) it holds today's counts. Each commit may only **lower** them. The test fails if a file's count rises or a new file appears. Remove files from the list as they reach zero. **Done means the allowlist is empty** (or holds admin files only, under Q2).
3. **Contrast.** Parse `index.css` for both palettes (`:root` and `[data-theme="dark"]`, dark inheriting unset tokens), then check every pair in §5.4 is ≥ 4.5:1 (WCAG relative luminance). Fail with the pair, theme and ratio.

Also add `npm run check:design` (runs only this test file) to `package.json`, and call it in CI next to the existing checks. The `lint` script has no ESLint config in the repo, so don't rely on ESLint for this.

---

## 10. Build order (one commit each; the app looks right after every step)

1. **Tokens.**
   - Add the type roles (§4) and the colour tokens (§5.2: new tokens, neutral positions and roles, `--on-accent`; leave the dark accent hue for step 8) to `index.css`.
   - Re-run `gen_color_mix_fallback.py`.
   - Add the guard test with the allowlist **at today's counts**, plus the contrast test.
   - Nothing visible changes yet, apart from positions and roles turning neutral.
2. **Shared components** (§6.1, §6.2).
3. **Colour meaning** (§6.3, §6.4):
   - AI tokens
   - Badge variants and `info` callers
   - TabBar
   - Finance series, price track, board markers
   - `primary-success`
   - `text-on-accent`
   - the `bg-slate-800` replacement
4. **Money** (§6.6): the compact formatter and the call sites that should be compact.
5. **Sweep area 1:** transfer, deal, offer.
6. **Sweep areas 2, 3 and 4**, one commit each.
7. **Sweep areas 5 and 6** (player and agent accounts, Lite).
8. **Dark accent** (Q1 default), then re-check contrast.
9. **Sweep area 7, admin** (Q2: may be a follow-up PR).
10. **Finish:** re-measure (§11), docs (§12), changelog.

---

## 11. Checks

**Automated:** `vitest` (including `designSystem.test.ts`), typecheck, and the existing tests. Component tests that assert class names (e.g. `MarketActions.test.tsx`, which checks for no `bg-accent`) must still pass.

**Measurement.** Run `measure-type.mjs` (this folder; copy it to `frontend/scripts/`) against a local stack with the demo data:

```
node frontend/scripts/measure-type.mjs http://127.0.0.1:5173 club@example.com 'password'
```

It signs in, visits each route at 390 × 844 and 1280 × 790, and prints, per page: the h1 size, the dominant body size, the % of text under 13px, and the sizes on screen. **Target:**
- 0% under 13px everywhere except admin, under Q2
- ≤ 6 sizes per page
- body 15px (14px allowed on table-heavy pages: transfers, finance, admin)

Paste the before-and-after table into the PR description.

**By hand, at 390, 768 and 1280, light and dark:**
- Dashboard, Browse Players, a player (another club's, your own, a free agent), an offer (your move, waiting), a deal (Paperwork), Transfers board, My Club, Finance, Listings, Notifications, Account, Make an offer, Lite home and a Lite offer card.
- Look for clipped text from the size changes (badges in tight rows, table headers, the board's cards, tab bars on phones). Fix with wrapping or truncation, never by shrinking below 13px.
- 200% zoom at 1280.

---

## 12. Docs (`documentation-standards`)

- **`docs/design-system/TOKENS.md`:** replace "Typography" with §4 (roles, utilities, weights, the 13px floor, `eyebrow`), and remove the "11px is only for overlines" rule. Add the colour roles table (§5.1) and the new tokens (§5.2) to the colour section, with the "categories are neutral" rule.
- **`docs/design-system/RESPONSIVE.md`:** replace "Typography on small screens" with: Title 22 and Display 28 below 640px; inputs 16px below 1024px; everything else the same size on every device; body 15px (it said 14px).
- **`docs/design-system/SCREENS.md`:** remove any per-screen pixel sizes that now come from roles, or point them at the roles.
- **`docs/CHANGELOG.md`:** the type scale, the 13px floor, neutral positions and roles, the AI colour, dark mode accent (if Q1), and compact money.
- **`docs/feature_spec/README.md`:** add this spec.
- **This file:** set `status: Implemented {date}` and list deviations.

---

## 13. Risks

- **Size changes can wrap or clip** text in tight places (badges, board cards, table headers, segmented controls on phones). The manual pass in §11 is there for this. Prefer `truncate` with a `title`, or letting rows wrap, over smaller text.
- **Neutral positions** remove colour from squad lists that some users scan by colour. The position letters stay, in bold. If that's missed in testing, the fallback is **one** neutral tint per position (four greys or four quiet non-status hues). Never the status colours.
- **A dark accent change** (Q1) is visible to every dark-mode user. Mention it in the changelog.
- **Test churn:** snapshot or class-name tests will change. Keep each in the commit that changes its component.

---

## 14. Where the mock differs (this README wins)

- **Rule 6 on the mock says "three weights".** This spec allows 500 for navigation and inactive tab labels (D5), matching TOKENS.md's existing four weights. 800 stays Lite-only.
- **The mock shows the price track neutral only implicitly.** Follow §6.3.
- **The mock's "after" Finance and Dashboard cards use sample values** for the window and squad tiles.
- **The mock's chip colours are illustrations.** Use the tokens and values in §5.2.
- **The mock's 12px monospace token names on the colour roles card** are documentation inside the mock, not app UI. They don't break the 13px floor in the product.

---

## 15. As built (2026-11-11)

Built on branch `type-and-colour` in the order of §10, one commit per step and sweep area, admin
included (Q2 done in the same PR). Q1 took the default (blue dark accent). The allowlist is empty:
no raw size, uppercase outside `eyebrow`, opacity tint, extra-bold outside Lite or white-on-accent
remains in `frontend/src`.

### Measured (laptop 1280 × 790, signed in as Man City, local demo data)

| Page | Before: sizes / most text / < 13px | After: sizes / most text / < 13px |
|---|---|---|
| Dashboard | 9 / 14 / 28% | 5 / 14 / 0% |
| Browse Players | 7 / 12 / 43% | 4 / 14 / 0% |
| Player profile | 10 / 13 / 40% | 5 / 14 / 0% |
| Offer | 11 / 14 / 5% | 6 / 14 / 0% |
| Transfers | 4 / 12 / 56% | 5 / 15 / 0% |
| My Club | 7 / 13 / 19% | 5 / 14 / 0% |
| Finance | 7 / 14 / 18% | 5 / 15 / 0% |
| Notifications | 6 / 14 / 19% | 4 / 15 / 0% |
| Account | 5 / 12 / 77% | 5 / 14 / 0% |
| Make an offer | 5 / 13 / 16% | 4 / 14 / 0% |
| Lite home | 6 / 18 / 0% | 6 / 18 / 0% |

"Before" is §1. At 390 × 844 every page is also 0% under 13px with at most six sizes
(Lite counts against its own scale).

### Deviations

- **Caption is for labels only.** §7.1 maps every `text-[13px]` to Caption, which left sentences,
  meta lines and small buttons at 13px and most pages reading at 13px. A second pass moved
  unweighted 13px paragraphs, list items, muted spans and small links and buttons to Small (14);
  labels, badges, counts and timestamps stay Caption.
- **Most text is 14px, not 15px, on Dashboard, Player, Offer, Account and Make an offer** (14px is
  allowed only on table-heavy pages). Their dominant text is secondary lines and terms rows, which
  are Small by §4. Not tuned further: raising them would mean calling secondary lines Body.
- **`body` defaults to Body (15px)**, so text with no size class no longer inherits the browser's
  16px; Lite's layout sets Lite body.
- **Crest and photo boxes under 28px** show a `bg-border` dot, not `bg-surface-inset` (invisible
  on white).
- **More categories turned neutral than §6.3 lists**, by the same rule: StatsPanel stat groups,
  the compare page's section rows, the agent pipeline's stage columns (Completed stays green),
  Ask's chart series, the dashboard budget bars, admin chart bars. Switches that are on use accent,
  not success (§5.1). My offer-thread bubbles were green; they now match the deal room
  (`bg-accent-bg`).
- **Finance series** stay neutral always: `FinanceSection` has no warning threshold to turn one
  amber.
- **Badge `info`**: more than five callers. The mapping helpers in `lib/badges.ts`
  (`positionVariant` now returns `neutral`, contract state, sent offers, deals in progress) and
  four call sites moved too.
- **Money**: Lite's `liteMoney` and four local formatters (AI search chips, fair-value badge,
  ledger facts strip, shortlist market values) now use `formatCompact`/`formatCompactIn`.
  Commission text stays full (it is a term).
- **Agent commission status** showed the raw enum (`PENDING`, capitalised by CSS); it now reads
  Pending / Confirmed / Invoiced / Paid, with Paid as the done colour.
- **`bg-slate-800`**: the only occurrence is in a comment in `Input.tsx`; there was no raw use to
  replace.
- **Guard test**: scans `.ts` as well as `.tsx` (`lib/badges.ts` held tints); also catches
  `/[0.07]` opacities; checks white-on-accent per class string. The allowlist must match exactly,
  so a fix is recorded when it's made (`UPDATE_DESIGN_ALLOWLIST=1` regenerates it).
  `npm run check:design` exists; the repo has no CI config to add it to.
- **Measurement**: `measure-type.mjs` is in `frontend/scripts/`, but Playwright isn't installed
  here, so the same `measure()` ran through headless Chrome over CDP. `/offers/received` and
  `/deals` now redirect to the board, so the script's link-following finds nothing for Offer and
  Deal; Offer, Player and Club were measured by direct URL. **Deal was not measured**: no local
  deal has a signed-in party.
- **SCREENS.md** keeps its pixel values with a note mapping them to roles, rather than rewriting
  about 100 entries.
- **Lite**: its few 13px pills grow to 16px (more than a 1–2px snap). Sidebar count badges grow
  from 16 to 20px so 13px digits fit. Dashboard figure tiles were 28px; they are Headline/Title per
  §4, two per row below 640px on both the club and agent dashboards.
- **Not checked by hand**: 768px, 200% zoom, a real iPhone, the Deal room, Lite offer card.
