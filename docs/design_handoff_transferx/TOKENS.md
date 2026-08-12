# Design tokens

The project uses **Tailwind CSS v4**, so tokens belong in an `@theme` block in
`frontend/src/index.css`, not in a `tailwind.config.js`. The existing file already declares a
handful of CSS variables for the old dark theme — replace them wholesale.

Several colours were authored in `oklch()`. The hex equivalents below are exact conversions.
**Use the hex values** — they are what the design renders as, and they avoid browser
inconsistency. The oklch values are recorded only so future colours can be derived on the same
perceptual scale.

## Colour

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

| Position | Text | Avatar background |
|---|---|---|
| GK | `#7a4a00` | `#faf0dd` |
| DEF | `#1050ac` | `#e2ecfb` |
| MID | `#005a1c` | `#e0f0e6` |
| FWD | `#9b1e22` | `#fbe6e3` |

Position colour is decoration on an already-labelled element. Never the only carrier of meaning.

## Neutral dark

`#14171f` doubles as the ink colour and as the fill for the one dark element that survives — the
active filter chip. There is **no dark sidebar and no black header band** in Board v2.

## Typography

Inter, already loaded. Weights 400 / 500 / 600 / 700 only — no 800.

| Role | Size | Weight | Letter-spacing | Colour |
|---|---|---|---|---|
| Page title | 24px | 700 | -0.01em | text |
| Page subtitle | 13px | 400 | — | muted |
| Tier-2 figure value | 28px | 700 | -0.01em | text |
| Section heading | 18px | 700 | — | text |
| Card title | 14px | 700 | — | text |
| Tier-1 row title | 15–16px | 600–700 | — | text |
| Body / table cell | 14px | 400 | — | secondary |
| Row value (money) | 14–17px | 700 | — | text |
| Label above a value | 11px | 400 | — | muted |
| Overline (uppercase) | 11px | 600 | 0.04em | muted |
| Metadata / caption | 12–13px | 400 | — | muted |
| Button label | 14px | 600 | — | — |
| Chip / pill | 13px | 600 | — | — |

**Minimum text size anywhere is 11px, and 11px is only for uppercase overlines and labels sitting
directly above a large value.** Body copy never goes below 13px. This is a deliberate constraint
for the 35+ audience — do not shrink type to fit content; drop content instead.

Line-height: 1.5 for body copy and descriptions, 1.35 for multi-line headings, default for single
lines. Add `text-wrap: pretty` to any paragraph over one line.

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
| Primary | `#215fbc` | `#ffffff` | none |
| Primary success | `#007b2a` | `#ffffff` | none |
| Secondary | `#ffffff` | `#344054` | `1px solid #d0d5dd` |
| Destructive | `#ffffff` | `#9b1e22` | `1px solid #f0d3d3` |
| Ghost | transparent | `#667085` | none |

Padding `10px 18px`, radius 8px, 14px/600 label, `white-space: nowrap`.
Hover: primary → `#1050ac`; secondary → background `#f9fafb`.
Focus: `outline: 2px solid #215fbc; outline-offset: 2px`. Never remove the focus ring.

**Minimum touch target is 44×44px on touch devices** — see `RESPONSIVE.md`.

## Progress and comparison bars

Track `#eaecf0`, height 6px (inline) or 10px (finance), radius half the height.
Segments sit in a flex row and are painted in order, no gaps between them.
Finance bars use: spent `#475467`, committed `#407ede`, reserved `#d29923`, free = the track.

## Motion

Almost none, deliberately. Transitions only on `background-color`, `border-color`, `color` and
`box-shadow`, `150ms ease`. No layout animation, no entrance animation, no skeleton shimmer —
use a static grey block for loading. Respect `prefers-reduced-motion` by disabling the remaining
transitions entirely.
