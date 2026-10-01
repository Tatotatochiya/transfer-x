# Handoff: Player Profile v2 — Season Ledger

## Overview
Redesign of the player detail page (`frontend/src/pages/market/PlayerMarketDetailPage.tsx`). Replaces the current compact view, which stacks one chip per league/season (20+ once backfilled) with no way to compare seasons.

The new layout:
1. A compact header (identity + actions) and a single **facts strip** (value, contract, wage, release clause, form).
2. Three tabs: **Overview**, **Career**, **Medical**. Each one renders the **same season ledger table**: one row per season, a career-total footer, and expandable sub-rows.
3. A right-hand column whose panels change with the viewer type: buying club, own club, or agent.

The ledger is built to scale. New stats become another column set (a segmented tab), so they never add another layout block.

## About the design files
`TransferX - Player Profile v2 Ledger.dc.html` is a **design reference built in HTML**. It shows the intended look and behaviour and is not production code. Rebuild it in the existing TransferX frontend (React + Tailwind, dark theme) using the components and patterns already there (`Badge.tsx`, `Icon.tsx`, `AppShell`, `Sidebar`). Open the file in a browser to try it. Its Tweaks panel switches `viewer` (Buying club / Own player / Agent) and `showDealBanner`.

All data in the mock is invented.

## Fidelity
**High-fidelity.** Colours, type sizes, spacing and interactions are final. The values below map directly to the Tailwind slate/emerald palette the app already uses, so prefer the existing classes to raw hex.

## Existing code to change
| Area | Files |
|---|---|
| Page | `frontend/src/pages/market/PlayerMarketDetailPage.tsx` |
| Overview stats | `components/players/StatsPanel.tsx` → rewrite as `SeasonLedger` |
| Career | `components/players/CareerHistoryPanel.tsx` → ledger + transfer event rows |
| Medical | `components/players/InjuryHistoryPanel.tsx` → ledger + injury sub-rows |
| AI fit (buyer) | `components/ai/PlayerFitCard.tsx` (keep its logic, restyle it) |
| Player account (own) | `PlayerAccountCard.tsx` |

Suggested new shared component: `SeasonLedger` with props `{ columns, rows, footer, gridTemplate, expandable }`. All three tabs render through it.

---

## Page layout
- Page background `#020617` (slate-950). Base font Inter, 14px, text `#f8fafc`.
- App shell: the existing 60px icon sidebar (`#0f172a`, right border `rgba(255,255,255,0.08)`).
- Main: padding `20px 28px 48px`. Content `max-width: 1280px`, centred, vertical stack with `gap: 12px`.

Order from top to bottom:
1. Breadcrumb
2. Header
3. Deal banner (conditional)
4. Facts strip
5. Body grid: `grid-template-columns: minmax(0,1fr) 300px; gap: 16px; align-items: start; margin-top: 4px`

### 1. Breadcrumb
13px, `#64748b`, `gap: 8px`: `← Back · Market / {Player name}`. The last item is `#94a3b8`. "← Back" turns `#f8fafc` on hover.

### 2. Header (flex, `gap: 14px`, wraps)
- **Avatar:** 52px circle, bg `rgba(16,185,129,0.15)`, initial in `#34d399` at 22px/800, ring `0 0 0 2px rgba(255,255,255,0.08)`. Use the player photo when one exists.
- **Identity block** (`flex: 1; min-width: 280px`, column, `gap: 4px`):
  - Line 1: name at 22px/700, followed by pills (11px, padding `2px 7px`, radius 999):
    - Position: bg `rgba(52,211,153,0.15)`, text `#34d399`, weight 700 (e.g. `MID`)
    - Contract status: bg `rgba(96,165,250,0.15)`, text `#93c5fd`, weight 600 (e.g. `Contracted`)
    - **Own club only:** `Listed` (6px dot `#10b981`, bg `rgba(16,185,129,0.15)`, text `#34d399`) and `{n} active offers` (dot `#818cf8`, bg `rgba(129,140,248,0.15)`, text `#a5b4fc`, clickable, opens the offer inbox).
  - Line 2: 13px `#94a3b8`, items separated by `·`: **Club** (`#e2e8f0`, 500) · age · nationality · height · weight · `Born {date}, {city}`.
- **Actions** (flex, `gap: 8px`, wraps). Buttons are 13px, padding `8px 12px`, radius 8.
  - Secondary: bg `#1e293b`, text `#cbd5e1`, weight 500, ring `0 0 0 1px #334155`.
  - Danger: bg `rgba(239,68,68,0.12)`, text `#fca5a5`, 600, ring `rgba(239,68,68,0.3)`.
  - Primary: bg `#10b981`, text `#022c22`, 700, padding `8px 14px`.
  - Buttons by viewer:
    - **Buying club:** Compare · Shortlist · Ask about him · `Trigger clause £30m` (danger; shown only when a release clause exists) · **Make offer** (primary)
    - **Own club:** Compare · **View listing** (secondary style, text `#f8fafc`, 600)
    - **Agent:** Compare · Shortlist

### 3. Deal banner (only while a transfer is in progress)
Flex, `gap: 10px`, padding `9px 14px`, radius 10, bg `rgba(245,158,11,0.1)`, ring `0 0 0 1px rgba(245,158,11,0.25)`, 13px.
- `Transfer in progress` (700, `#fbbf24`)
- `{From} → {To} · Stage: {stage}` (`#cbd5e1`)
- Right-aligned: `New offers and listings are paused while a deal is active` (`#94a3b8`)

While the banner shows, disable Make offer, Trigger clause and listing actions.

### 4. Facts strip
- Container: `display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr))`, bg `#0f172a`, radius 10, ring `0 0 0 1px rgba(255,255,255,0.08)`, `overflow: hidden`.
- Cell: padding `10px 14px`, column, `gap: 2px`. Divider is a left inset `box-shadow: -1px 0 0 rgba(255,255,255,0.06)`.
  - Label: 11px/700, uppercase, letter-spacing 0.06em, `#64748b`
  - Value: 15px/700, tabular-nums
  - Sub: 12px `#64748b`

| # | Label | Value | Sub | Notes |
|---|---|---|---|---|
| 1 | Model value | `£15.8m` | `Range £13.9–18.1m` | |
| 2 | Market value | `€18m` | `Transfermarkt · Sep 2026` | |
| 3 | Contract | `Jun 2028` | Buyer/agent: `1 yr 9 mo left`. Own club: `Started Jul 2022` | |
| 4 | Wage | `£45k/wk` (`#34d399`) | Buyer/agent: `Capology est.`. Own club: `Contract` | |
| 5 | Release clause **or** Club valuation | Buyer/agent: `£30m` with sub `Can be triggered`. Own club: `£22m ✎` with sub `Only your club sees this` | | Own-club valuation is editable inline |
| 6 | Form | `72 ▲` (`#34d399`) | `Last 5 games` | Arrow ▲/▼ shows the trend |

---

## 5. Body — left column

### Tab bar
Flex, `gap: 4px`, bottom border `1px solid rgba(255,255,255,0.08)`. Each tab: padding `8px 12px`, weight 500, `gap: 6px`.
- Active tab: text `#f8fafc` with underline `box-shadow: inset 0 -2px 0 #10b981`.
- Inactive tab: text `#64748b`.
- Count suffix: 11px/600 `#64748b`.

Tabs: `Overview` (no count) · `Career` (`4 moves`) · `Medical` (`{injury count}`).

### Ledger card
bg `#0f172a`, radius 14, ring `0 0 0 1px rgba(255,255,255,0.08)`, padding 16, column, `gap: 14px`. Inside, in order:

**a) Toolbar (Overview only).** `space-between`, wraps.
- Segmented control: bg `#020617`, padding 3, radius 8, `gap: 2px`. Items are 12px/600, padding `5px 10px`, radius 6. Active item: bg `#1e293b`, text `#f8fafc`. Inactive: transparent, `#64748b`.
  - Options: **Output · Passing · Defending**. Future stat categories are added here.
- Right side hint, 12px `#64748b`: `Apps (starts) · per 90 where noted · tap a season for competitions`

**b) Summary tiles (Medical only).** `grid-template-columns: repeat(4, minmax(0,1fr))`, `gap: 1px` on bg `rgba(255,255,255,0.06)` (hairline dividers), radius 10. Each tile: bg `#020617`, padding `10px 12px`. Label uses the facts-label style. Value 17px/700 tabular. Sub 12px `#64748b`.
- Injuries `5` / `Since 2019/20`
- Games missed `26` / `≈ 4 per season`
- Last injury `Jan 2025` / `Hamstring · 4 games`
- Longest `11 games` (`#fca5a5`) / `Knee ligament · 2022`

**c) Ledger table.** Uses CSS grid rows inside a horizontally scrollable wrapper (`overflow-x: auto`). Every row has `min-width: 640px`.
- Grid template:
  - Overview: `86px 1.4fr repeat(7, minmax(0,1fr))`
  - Career and Medical: `86px 1.4fr repeat(5, minmax(0,1fr))`
  - Column gap 8px.
- **Header row:** padding `0 10px 8px`, bottom border `rgba(255,255,255,0.08)`, 11px/700, uppercase, letter-spacing 0.05em, `#64748b`. `Season`, `Club`, then the stat headers, right-aligned.
- **Season row:** padding `9px 10px`, tabular-nums, bottom border `rgba(255,255,255,0.05)`, hover bg `rgba(255,255,255,0.03)`. An expanded row gets bg `rgba(255,255,255,0.025)`.
  - Season cell: caret `▸`/`▾` (10px `#64748b`, fixed 8px wide; blank if the row can't expand) followed by the season label at 600.
  - Club cell: 8×8 swatch (radius 2) in the club colour, club name in `#cbd5e1` (ellipsis), and a `LOAN` tag (10px/700 `#fbbf24`) when the season was on loan.
  - Stat cells: right-aligned, 500, `#f8fafc`. On Overview, the **last column** (Rating or YC) is highlighted `#fbbf24`.
- **Expanded sub-rows:** container padding `2px 0 6px`, bg `rgba(255,255,255,0.02)`, bottom border. Each sub-row uses the same grid template, padding `5px 10px`, 13px, `#94a3b8`. Season cell is indented 14px. Club cell shows the sub-row name.
- **Footer (career total):** same grid, padding 10, bg `#020617`, radius `0 0 8px 8px`, 700. Shows the label `Career` and a sub-label in `#64748b`.
- Rows are ordered newest season first.

**d) Form strip (Overview only).** Flex, `gap: 16px`, padding `10px 12px`, radius 10, bg `#020617`, ring `rgba(255,255,255,0.06)`.
- Left: label `Form score` with sub `Last 5 games`.
- Score: `72` at 20px/800 `#34d399`, followed by `▲ 4` at 13px.
- Right-aligned: 5 game chips (bg `#0f172a`, padding `4px 8px`, radius 6). Each chip shows the rating at 13px/700 and the opponent code at 10px `#64748b`. Rating colours: ≥7.5 `#34d399`, ≥7.0 `#f8fafc`, otherwise `#fbbf24`.

### Tab contents

#### Overview
- One row per season, aggregated across all competitions. Expanding a row shows one sub-row per competition (La Liga, Europa League, Copa del Rey…) with the same columns. Sub-row names are plain text.
- Default state: the current season is expanded and all others are collapsed.
- Column sets (the first two columns are always Season and Club):

| Set | Columns |
|---|---|
| Output | Apps `n (starts)` · Min · G · A · G+A/90 · Shots/90 · Rating |
| Passing | Apps · Min · Key p. · KP/90 · Pass % · Assists · Rating |
| Defending | Apps · Min · Tackles · Int. · Tkl+Int/90 · Duels % · YC |

- Footer: the career aggregate for the same set. Sub-label `{n} clubs`.

#### Career
- Season rows without expansion. Columns: Apps · Starts · Min · G · A.
- **Transfer event rows** sit directly under the season they belong to:
  - Layout: flex, `gap: 10px`, padding `7px 10px 7px 30px`, 12px `#94a3b8`, bg `#020617`, bottom border.
  - Contents: date (700 `#cbd5e1`, 62px wide) · type pill (11px/600, padding `2px 8px`) · `From → To` (To in `#f8fafc` 600; arrow `#475569`) · fee right-aligned (600).
  - Type pill colours: Loan / End of loan use bg `rgba(245,158,11,0.12)` with `#fbbf24`. Transfer uses bg `rgba(96,165,250,0.12)` with `#93c5fd`.
  - Fee: shown in `#34d399` when known. If unknown and not a loan, show `Undisclosed` in `#64748b`. Loans show nothing.
- Footer sub-label: `{n} moves · €{sum} in fees`.

#### Medical
- Columns: Injuries · Missed · Avail. · Longest · Apps.
- Cell rules:
  - Zero values show `—` in `#475569`.
  - Missed: `n g`. Colour `#fca5a5` if ≥10, `#fbbf24` if >0.
  - Avail.: `%`. Colour `#34d399` if ≥90, `#f8fafc` if ≥75, otherwise `#fca5a5`.
  - Apps: `#94a3b8`.
- A row can expand only if it has injuries. Sub-rows show date (Season col) · injury pill (Club col) · games missed (Missed col) · league (Apps col).
  - Pill colours: severe injuries (knee, ankle, or a backend severity flag) use bg `rgba(239,68,68,0.12)` with `#fca5a5`. Others use bg `rgba(245,158,11,0.12)` with `#fbbf24`.
- Default state: the most recent season that had a significant injury is expanded (2022/23 in the mock).
- Footer: totals plus career availability. Sub-label `Since {first season}`.

> **Backend check needed — Availability.** Formula: `1 − (league games missed through injury ÷ league games that season)`. For the current season, use league games played so far. We need to confirm whether the API can provide (a) games missed per injury and (b) the number of league fixtures per competition-season. If it can't, hide the Avail. column and its footer value, and keep the rest of the tab.

---

## 6. Body — right column (300px, column, `gap: 12px`)
Card style: bg `#0f172a`, radius 12, ring `0 0 0 1px rgba(255,255,255,0.08)`, padding `12px 14px`. Card title 14px/600. List rows are 13px with a top border `rgba(255,255,255,0.05)`.

**Buying club**
- **✦ AI fit score** (`PlayerFitCard`)
  - Idle: `Analyse` button (12px/600, bg `rgba(167,139,250,0.15)`, text `#c4b5fd`, ring `rgba(167,139,250,0.3)`) and the copy `Check how well he fits your squad.`
  - Done: score `78` at 26px/800 `#34d399`, label `Good fit` / `Squad fit score / 100`, then reason lines: ✓ in `#34d399` for strengths, ⚠ in `#fbbf24` for concerns.
  - Add a loading state between idle and done.

**Own club**
- **Offers:** title row with `Open inbox →` (12px `#34d399`), then rows of club and fee (700 tabular).
- **Player account:** status copy (13px `#94a3b8`), e.g. `Invited 12 Sep · not joined yet. Until he joins, his agent answers personal terms.`, plus the link `Resend invitation`.
- **Potential buyers:** sub `Clubs short in central midfield`, then rows of club and reason (`#94a3b8`).

**Agent**
- **Representation:**
  - Label in the facts-label style.
  - `You don't represent him yet.`
  - `Exclusive mandate` checkbox (accent `#10b981`).
  - Start/End date inputs in a 2-column grid. Inputs: bg `#020617`, ring `#334155`, radius 6.
  - Full-width primary button `Represent this player`.

---

## State
| State | Default | Notes |
|---|---|---|
| `tab` | `overview` | `overview` / `career` / `medical`. Mirror it in the URL (`?tab=`) |
| `statSet` | `output` | Overview column set. Persist per user (localStorage) |
| `expandedSeasons` | `{ [currentSeason]: true }` | Overview expansions |
| `expandedMedical` | latest injured season | Medical expansions; kept separate from Overview |
| `fitState` | `idle` | `idle` / `loading` / `done` / `error` |
| `viewer` | derived | From auth: is the viewer the player's club, an agent, or another club |

## Data requirements
Per player:
- Season list. Each season: `season`, `club`, `clubColor`, `isLoan`, and `competitions[]`.
- Per competition: `apps, starts, minutes, goals, assists, shots, keyPasses, passAccuracy, duelsWon, duelsTotal, tackles, interceptions, yellowCards, rating`.
- Aggregation rules (season and career totals are computed client-side or by the API):
  - Count stats are summed.
  - `passAccuracy` is weighted by minutes.
  - `rating` is weighted by apps.
  - Per-90 = `stat / minutes × 90`.
  - Duels % = `duelsWon / duelsTotal`.
- Transfers: `date, from, to, type, fee?`, linked to a season.
- Injuries: `date, type, gamesMissed, competition, season, severity?`.
- League fixtures per competition-season (for Availability, see the note above).

## Empty / edge states
- Season with no competitions (unattached or no data): show the row with `—` cells and make it non-expandable.
- No transfers: hide the Career count suffix.
- No injuries: show the Medical summary tiles as `0` / `—`, plus the ledger.
- Narrow widths: the table scrolls horizontally (the 640px minimum is kept). The right column stacks under the left column below about 1000px.

## Design tokens (already in Tailwind slate/emerald)
- **Backgrounds:**
  - page `#020617`
  - card `#0f172a`
  - raised/control `#1e293b`
  - border control `#334155`
  - hairlines `rgba(255,255,255,0.05 / 0.06 / 0.08)`
- **Text:** `#f8fafc` primary, `#e2e8f0`, `#cbd5e1`, `#94a3b8` secondary, `#64748b` muted, `#475569` disabled/empty.
- **Accent:** emerald `#10b981` / `#34d399` / `#6ee7b7` (hover), on-accent text `#022c22`.
- **Status:**
  - amber `#fbbf24` (tint `rgba(245,158,11,·)`)
  - red `#fca5a5` (tint `rgba(239,68,68,·)`)
  - blue `#93c5fd` (tint `rgba(96,165,250,·)`)
  - indigo `#a5b4fc`
  - violet `#c4b5fd`
- **Radii:** 2 (swatch), 6, 8, 10, 12, 14 (ledger card), 999 (pills).
- **Type:** Inter.
  - 22/700 (name)
  - 20/800 (form score)
  - 17/700 (medical values)
  - 15/700 (fact values)
  - 14 (base)
  - 13 (secondary)
  - 12 (meta)
  - 11/700 uppercase 0.05–0.06em (labels)
  - 10 (micro)
  - All numbers use `font-variant-numeric: tabular-nums`.
- **Borders:** use `box-shadow: 0 0 0 1px …` rings, not borders, so layout doesn't shift.

## Files
- `TransferX - Player Profile v2 Ledger.dc.html`: the design reference. Its logic block holds the full mock dataset and the aggregation and column-set definitions (`SETS`, `agg()`), which you can copy as a spec.
- `support.js`: the runtime needed to open the reference file in a browser.
- `screenshots/`: captured at 60% zoom. Minor text wrapping is a capture artefact; trust the spec values.
  - `01–03`: Buying club · Overview · Output / Passing / Defending
  - `04`: Buying club · Career (transfer event rows)
  - `05`: Buying club · Medical (summary tiles + injury sub-rows)
  - `06`: Own club (Listed/offers pills, Club valuation fact, Offers / Player account / Potential buyers panels)
  - `07`: Agent (Representation panel)
  - `08`: Deal-in-progress banner + AI fit score result state
