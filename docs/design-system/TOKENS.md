---
title: "Design Tokens"
last_updated: 2026-11-11
status: Active
owner: "TODO — assign a Design Owner"
---

# Design tokens

The project uses **Tailwind CSS v4**, so tokens live in the `@theme` block in
`frontend/src/index.css` (there is no `tailwind.config.js`). This file specifies the light theme;
`index.css` also carries a dark set that overrides every token.

Several colours were authored in `oklch()`. The hex equivalents below are exact conversions.
**Use the hex values** — they are what the design renders as, and they avoid browser
inconsistency. The oklch values are recorded only so future colours can be derived on the same
perceptual scale.

## Colour

### Colour roles

Each colour means one thing. Categories (positions, contract state, account roles, deal type,
pipeline stages, chart series) are always neutral; their label carries the meaning.

| Role | Tokens | Use for | Never for |
|---|---|---|---|
| **Ink** | `text`, `text-secondary`, `text-muted` | All reading text. `text-muted` is the lightest text allowed | Text lighter than muted |
| **Interactive** | `accent`, `accent-hover`, `accent-active`, `accent-bg`, `accent-bg-strong`, `accent-ring`, `on-accent` | Buttons, links, selected tabs, chips and segments, switches that are on, focus | Statuses, positions, chart series, "your side" of a comparison |
| **Needs you** | `danger-*` | Your move, overdue, errors, destructive confirms | Positions, the other club's figures |
| **Caution** | `warning-*` | Deadlines close, on hold, budget nearly used, low form | Goalkeepers |
| **Done** | `success`, `success-text`, `success-dot`, `success-bg`, `success-ring` | Completed, passed, signed, good form | Midfielders, switches being on |
| **AI** | `ai-text`, `ai-bg`, `ai-ring` | Everything TransferX's AI writes or suggests (✦ buttons, advice, fit scores, AI search) | The Agent account badge |
| **Neutral** | `surface-inset`, `text-secondary`, `border` | Categories and plain facts | — |

**Tints come from tokens**, never opacity on a solid colour: `bg-success-bg`, `ring-warning-ring`,
`bg-accent-bg`, `ring-accent-ring`, `bg-danger-bg`, `ring-danger-ring`, `bg-ai-bg`. Opacity stays
only for overlays (`bg-ink/40`), progress fills and focus rings drawn from accent. Text on an
accent fill is `text-on-accent` (white in light mode, `#0b1220` in dark).

New tokens (light / dark): `--success-bg` `#e7f4ec`/`#0f2a1a`, `--success-ring` `#b7dfc4`/`#1f5132`,
`--warning-ring` `#efd9a8`/`#5a4413`, `--accent-ring` `#c7dafa`/`#284a7a`, `--ai-text`
`#5b2d9e`/`#c4a5f5`, `--ai-bg` `#f5f0fd`/`#241a3d`, `--ai-ring` `#ddcdf5`/`#45316e`, `--on-accent`
`#ffffff`/`#0b1220`. The dark accent is blue (`#5b9bf8`), like light mode's; it was emerald.

Contrast: `designSystem.test.ts` checks every text/background pair above (text on surfaces,
accent links, on-accent on accent, each status text on its tint, AI, positions) reaches 4.5:1 in
both themes.

### Surfaces

| Token | Hex | Used for |
|---|---|---|
| `--color-page` | `#f7f8fa` | Page background, everywhere |
| `--color-surface` | `#ffffff` | Cards, panels, sidebar, table bodies |
| `--color-surface-quiet` | `#fbfbfc` | Tier-4 reference cards only |
| `--color-surface-header` | `#fafbfc` | Table header rows |
| `--color-surface-inset` | `#f9fafb` | Stat tiles inside a card |

### Borders and rules

| Token | Hex | Used for |
|---|---|---|
| `--color-border` | `#e4e7ec` | Card ring, sidebar divider, primary borders |
| `--color-border-quiet` | `#eaecf0` | Tier-4 card ring, progress-bar track |
| `--color-rule` | `#f0f1f3` | Divider inside a card (header → body) |
| `--color-rule-faint` | `#f5f6f7` | Row separators in a list |
| `--color-input-border` | `#d0d5dd` | Inputs, secondary buttons |

Cards use a **ring, not a border**: `box-shadow: 0 0 0 1px #e4e7ec`. This keeps card widths on
the grid. Tier-1 cards add a drop shadow (see Shadows).

### Text

| Token | Hex | Used for |
|---|---|---|
| `--color-text` | `#14171f` | Headings, values, player names |
| `--color-text-secondary` | `#475467` | Body copy, descriptions, table cells |
| `--color-text-muted` | `#667085` | Labels, captions, metadata, timestamps |

**Do not use `#98a2b3` or anything lighter for text.** An earlier draft did; it failed WCAG AA at
small sizes and read as "disabled" to older users. `#667085` is the floor. `#98a2b3` remains
acceptable for non-text elements only (an inactive dot, a disabled progress track).

### Accent — blue

| Token | Hex | oklch | Used for |
|---|---|---|---|
| `--color-accent` | `#215fbc` | `50% 0.16 259` | Primary buttons, links, active nav text |
| `--color-accent-hover` | `#1050ac` | `45% 0.16 259` | Primary button hover |
| `--color-accent-active` | `#0347a2` | `42% 0.16 259` | Primary button active, link hover |
| `--color-accent-soft` | `#407ede` | `60% 0.16 259` | Bar segments, secondary fills |
| `--color-accent-bg` | `#eaf2ff` | `96% 0.02 259` | Active nav item background |
| `--color-accent-bg-strong` | `#dbecff` | `94% 0.04 259` | Current stage pill |
| `--color-accent-avatar` | `#dce9fd` | `93% 0.03 259` | Avatar background |

### Semantic — red (urgent, your move, negative)

| Token | Hex | oklch | Used for |
|---|---|---|---|
| `--color-danger` | `#c53637` | `55% 0.18 25` | Status dot, bar fill |
| `--color-danger-text` | `#ac1922` | `48% 0.18 25` | "Your move", deadline under 24h |
| `--color-danger-text-alt` | `#9b1e22` | `45% 0.16 25` | Destructive button label, negative money |
| `--color-danger-heading` | `#970818` | `43% 0.17 25` | Tier-1 band heading |
| `--color-danger-bg` | `#ffeeeb` | `97% 0.03 25` | Tier-1 band background |
| `--color-danger-bg-badge` | `#ffdcd7` | `94% 0.06 25` | Sidebar alert count badge |
| `--color-danger-border` | `#fedbd7` | `92% 0.04 25` | Tier-1 band bottom rule |
| `--color-danger-ring` | `#f7ccc7` | `88% 0.05 25` | Tier-1 card ring |

### Semantic — green (agreed, completed, headroom)

| Token | Hex | oklch |
|---|---|---|
| `--color-success` | `#007b2a` | `50% 0.16 150` |
| `--color-success-text` | `#006925` | `45% 0.14 150` |
| `--color-success-text-alt` | `#00601c` | `42% 0.14 150` |
| `--color-success-dot` | `#008a39` | `55% 0.16 150` |

### Semantic — amber (blocked, expiring, caution)

| Token | Hex | oklch |
|---|---|---|
| `--color-warning-text` | `#7a4a00` | `45% 0.13 80` |
| `--color-warning-text-alt` | `#865100` | `48% 0.14 80` |
| `--color-warning-fill` | `#d29923` | `72% 0.14 80` |

### Position colours (squad and player rows)

Positions are categories: every position uses `--pos-*` tokens that are neutral (`#344054` on
`#eef0f3`; dark `#cbd5e1` on `#1e293b`). The letters (GK, DEF, MID, FWD) carry the meaning. Account
roles (`--role-club-*`, `--role-agent-*`) are neutral the same way.

## Neutral dark

`#14171f` doubles as the ink colour and as the fill for the one dark element that survives — the
active filter chip. There is **no dark sidebar and no black header band** in Board v2.

## Typography

Inter. Seven text roles, defined once in `index.css` (`@theme`, the same in both themes). Components
use the role utilities only, never `text-sm` or `text-[15px]`; `src/test/designSystem.test.ts` fails
on raw sizes.

| Role | Utility | Size / line | Weight | Use |
|---|---|---|---|---|
| Display | `text-display-sm sm:text-display` | 28 → 32 / 34–38 | 700, `-0.01em`, `tabular-nums` | One hero figure per card at most (Finance budgets) |
| Title | `text-title-sm sm:text-title` | 22 → 24 / 28–30 | 700, `-0.01em` | The page `h1` |
| Headline | `text-headline` | 20 / 28 | 700 | The one sentence that matters: status card headlines, empty-state titles, dialog and sheet titles |
| Section | `text-section` | 17 / 24 | 700 | Every card and section heading, sentence case |
| Body | `text-body` | 15 / 24 | 400 (strong 600) | Reading text, list rows, buttons, tabs, segmented controls |
| Small | `text-small` | 14 / 20 | 400 (strong 600) | Secondary lines, meta under a name, table cells, `Metric` rows |
| Caption | `text-caption` | 13 / 18 | 400 (labels 600) | Field labels above values, timestamps, badges, counts, chart labels |
| Eyebrow | `eyebrow` | 13, caps, `0.04em` | 700 | Status overlines and table column headers only |

Inputs are `text-input lg:text-body`: 16px below 1024px (iOS zooms inputs under 16px), 15px from
1024px. Text with no size class inherits Body from `body`.

**13px is the floor, everywhere** (badges, counts, timestamps, column headers and chart labels
included). There is no 11px. Do not shrink type to fit content; drop content or let it wrap.

**Figures** inside cards and tiles (not a hero): Headline on phones, Title from 640px,
`tabular-nums`. A page shows at most six sizes (Display counts only where a card has a hero
figure).

**Case.** Headings and labels are sentence case ("Transfer budget", not "Transfer Budget").
`uppercase` is only ever the `eyebrow` utility.

**Weights.** 400 for reading, 600 for labels, values and buttons, 700 for headings and figures.
500 only for navigation and inactive tab labels. 800 is Lite only (home greeting, tile titles).

**Lite** has its own scale one step up: `text-lite-caption` 16, `text-lite-body` 18,
`text-lite-section` 20, `text-lite-headline` 24, `text-lite-title` 32, `text-lite-title-lg` 40
(titles from 640px), `text-lite-display` 36 (figures). Nothing in Lite is under 16px.

Paragraphs over one line get `text-wrap: pretty`; wide reading paragraphs `max-w-[68ch]`.

**Money.** One compact format (`formatCompact`): "£52M", "£21.5M", "£450K", "£2.6B" in headers,
status cards, tiles, list rows, the board, notifications and Lite. Full figures
(`formatCurrency`, "£21,500,000") only where terms are agreed: terms cards, the counter, raise and
new-offer forms, accept confirmations, order books (bids sit close together), the Finance
breakdown and ledger, exports.

## Spacing

4px base scale: 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 26, 28, 32, 36, 64.

Standing conventions:

- Page padding: `28px 32px 64px` desktop
- Card padding: `16–20px` horizontal, `14–20px` vertical
- Card header padding: `13–15px 18–20px`
- Gap between cards in a grid: `16px`
- Gap between stacked cards in a column: `12px`
- Gap between tiers: `18px`
- Row padding inside a list card: `11–14px 0`
- Sidebar width: `232px`; nav item padding `8px 10px`; group gap `20px`

Always lay out sibling groups with flex/grid + `gap`. No margin-based spacing between siblings.

## Radii

| Value | Used for |
|---|---|
| 6px | Progress bar segments, small swatches |
| 7px | Logo tile |
| 8px | Buttons, inputs, nav items, badges |
| 9px | Count badges (pill) |
| 10px | Stat tiles, message bubbles |
| 12px | Cards, panels |
| 14px | Large feature cards (bid ladder, decision cards) |
| 20px | Filter chips, stage pills |
| 50% | Avatars, status dots |

## Shadows

| Token | Value | Used for |
|---|---|---|
| Card ring | `0 0 0 1px #e4e7ec` | Every tier-3 card |
| Quiet ring | `0 0 0 1px #eaecf0` | Every tier-4 card |
| Raised | `0 1px 2px rgba(16,24,40,0.06), 0 0 0 1px #e4e7ec` | Tier-1 cards, cards with actions |
| Danger raised | `0 1px 2px rgba(16,24,40,0.06), 0 0 0 1px #f7ccc7` | The tier-1 "Waiting on you" card |

No blurs above 2px anywhere. No coloured glows.

## Buttons

| Variant | Background | Text | Border |
|---|---|---|---|
| Primary | `#215fbc` | `on-accent` (`#ffffff`) | none |
| Secondary | `#ffffff` | `#344054` | `1px solid #d0d5dd` |
| Destructive | `#ffffff` | `#9b1e22` | `1px solid #f0d3d3` |
| Ghost | transparent | `#667085` | none |

Padding `10px 18px`, radius 8px, Body (15px)/600 label (`sm`: Small), `white-space: nowrap`.
Hover: primary → `#1050ac`; secondary → background `#f9fafb`.
Focus: `outline: 2px solid #215fbc; outline-offset: 2px`. Never remove the focus ring.

**Minimum touch target is 44×44px on touch devices** — see `RESPONSIVE.md`.

## Progress and comparison bars

Track `#eaecf0`, height 6px (inline) or 10px (finance), radius half the height.
Segments sit in a flex row and are painted in order, no gaps between them.
Finance bars are ink: spent `text`, committed `text-secondary`, reserved `text-muted`, free = the track. Never accent.

## Motion

Almost none, deliberately. Transitions only on `background-color`, `border-color`, `color` and
`box-shadow`, `150ms ease`. No layout animation, no entrance animation, no skeleton shimmer —
use a static grey block for loading. Respect `prefers-reduced-motion` by disabling the remaining
transitions entirely.
