# Screen specifications

Layout and component detail per screen. Values not stated here are in `TOKENS.md`; responsive
behaviour not stated here is in `RESPONSIVE.md`.

Copy given in quotes is the exact wording to use.

---

## Shell (every screen)

**Desktop sidebar** — 232px, white, `1px solid #e4e7ec` right border, sticky full height.

- Header: 60px tall, `0 20px`, bottom border. 28px accent tile with a 16px lightning glyph, then
  "TransferX" at 15px/700.
- Nav: `16px 12px`, groups separated by 20px. Group label 11px/600 uppercase, `0.04em`, muted,
  `0 10px`, 6px below.
- Nav item: `8px 10px`, radius 8, 14px. Inactive `#475467`/500. Active `#eaf2ff` background,
  `#1050ac` text, 600.
- Count badge: 11px/700, radius 9, `1px 7px`. Neutral `#f0f1f3` on `#667085`. Alert (items
  needing this user) `#ffdcd7` on `#9e151e`. **No background and no padding when the count is
  absent** — a common bug in the first implementation.
- Footer: 30px avatar tile, club name 13px/600, role 11px muted.

**Page container** — max-width 1280px, centred, padding `28px 32px 64px`.

**Page header** — title 24px/700 `-0.01em`; subtitle 13px muted, 3px below. Any header action
sits right, baseline-aligned.

---

## Dashboard

Route: `/dashboard`. The reference implementation of the four tiers.
Reference file: `TransferX - Board v2.dc.html`.

Subtitle format: `"{Club} · {Division} · Summer window closes in {countdown}"`.
Right of the header, 13px muted: `"Updated {n} minutes ago"` (see `DECISIONS.md` item 8).

### Tier 1 — "Waiting on you"

Card: radius 12, `0 1px 2px rgba(16,24,40,0.06), 0 0 0 1px #f7ccc7`. 18px below.

Band header: `12px 20px`, background `#ffeeeb`, bottom border `1px solid #fedbd7`.
8px round dot `#c53637`, then `"Waiting on you — {count}"` at 13px/700 `#970818`.
Right, 12px muted: `"Sorted by deadline"`.

Row: `14px 20px`, bottom rule `#f0f1f3`, flex with 16px gap, wrapping.

| Element | Width | Content |
|---|---|---|
| Label block | `flex: 1 1 300px` | Title 15px/600; description 13px `#667085` |
| Amount | `flex: 0 1 130px` | Label 11px muted; value 16px/700 |
| Deadline | `flex: 0 1 130px` | Label 11px muted `"Deadline"`; value 14px/700, coloured |
| Action | auto | Primary button, `nowrap` |

Deadline colour: under 24h `#ac1922`; waiting on this user with no hard deadline `#006925`;
otherwise `#475467`.

Sort by deadline ascending, items with no deadline last. Cap at 5 with a
`"View all {n} →"` link; do not paginate.

Empty state: replace the whole card with one line of 14px `#475467` — `"Nothing is waiting on
you."` Keep the rest of the page unchanged.

### Tier 2 — Standing figures

`repeat(auto-fit, minmax(180px, 1fr))`, 14px gap, 18px below.

Card: white, radius 12, ring, `16px 20px`. Label 12px/600 `#475467`; value 28px/700 `-0.01em`,
6px below; note 12px muted, 3px below; optional 6px bar 10px below.

The four: Transfer budget free (bar, `#007b2a`) · Wage room per week (bar, `#215fbc`) · Window
closes in (no bar) · Squad (no bar, note carries gaps and expiries).

### Tier 3 — Working panels

`repeat(auto-fit, minmax(320px, 1fr))`, 16px gap, 18px below. Three panels: "My open listings",
"Active offers", "Active deals".

Card header `15px 18px`, bottom rule: title 14px/700, right `"View all →"` 12px/600 accent.
Body `6px 18px 14px`.

Row: `11px 0`, bottom rule `#f5f6f7`, flex 12px gap.
Left (`flex: 1 1 130px`): name 14px/600; sub 12px `#667085`.
Right, aligned right: value 14px/700; **whose-move label** 12px/600 in its state colour.

Three rows per panel, then the header link carries the rest.

### Tier 4 — Reference panels

`repeat(auto-fit, minmax(280px, 1fr))`, 16px gap. Background `#fbfbfc`, ring `#eaecf0`.
Header `13px 18px`: title 13px/600 `#475467`, right link 12px muted.
Row `9px 0`: left 13px `#344054` + 11px muted sub; right 13px/600 coloured.

Three panels: "Squad needs" · "Shortlist on market" · "Expiring contracts".

### Completed transfers

Full-width table card. Columns: Player (with position suffix) · From · To · Fee (right) ·
Completed (right). Three rows.

Mobile card priority: Player + Fee, then From → To on one line, then date.

---

## Offer inbox

Route: `/offers`. Reference: `TransferX - Board v2 Screens.dc.html`, "Inbox".

Filter chips above everything: All · Your move · Their move · Accepted · Rejected.
Active chip `#14171f` background, white text. Inactive white, `#475467`, `1px solid #d0d5dd`.
Radius 8, `7px 14px`, 13px/600, 8px gap.

### Tier 1 — "Your move"

Same band treatment as the dashboard, heading `"Your move — {count}"`.

Row, `16px 20px`:
- Identity (`flex: 1 1 260px`): name 16px/700 with position 11px/700 in its position colour
  beside it; description 13px `#475467`.
- Their offer (`flex: 0 1 120px`): 11px label, 17px/700 value.
- Your valuation (`flex: 0 1 120px`): 11px label, 17px/700, red when their offer is below it.
- Deadline (`flex: 0 1 110px`): 11px label, 14px/700 coloured.
- Actions: "Counter" primary, "Accept" secondary.

Below, separated by a `#f5f6f7` rule at 12px: the negotiation history inline, as a 22px-gap flex
row of up to three entries — 11px muted timestamp above 13px text with the amount in `<strong>`.

### Everything else

Table card, header `"Everything else"` with right caption `"Waiting on the other club, or
closed"`. Columns: Player · Club · Fee (right) · State · Last activity (right).
State uses whose-move colours; terminal states use `#9b1e22` (rejected) and `#00601c` (accepted).

Mobile card priority: Player + Fee · Club · State + timestamp.

---

## Deals

Route: `/deals`. Reference: same file, "Deals".

Chips: All · In progress · Pending completion · Completed · Collapsed.

Deal card: white, radius 12, ring — `#f7ccc7` when it is your move, `#e4e7ec` otherwise.
Padding `16px 20px`, 12px between cards.

Top row (16px gap, wrapping): identity `flex: 1 1 240px` (name 16px/700, route 13px `#475467`) ·
Agreed fee `flex: 0 1 120px` (11px label, 17px/700) · Whose move `flex: 0 1 150px` (11px label
`"Whose move"`, 14px/700 coloured, with the reason — `"You — signature"`, `"Agent — 4 days
idle"`) · action button (primary when yours, secondary otherwise).

Stage tracker below, 14px down: six pills — Agreement, Agent negotiation, Personal terms,
Paperwork, Confirmed, Completed. Pill `5px 11px`, radius 20, 12px/600, with a 6px dot.
Past `#475467` text, dot `#008a39`. Current `#dbecff` background, `#0347a2` text, dot `#215fbc`.
Future `#98a2b3` text, dot `#d0d5dd`. 12px 1px `#e4e7ec` connector between pills.

On mobile the tracker collapses to `"Step 5 of 6 · Confirmed"` with a 6px progress bar.

Below: "Closed this window" table, `#fbfbfc`. Columns: Player · Route · Fee (right) · Outcome ·
Date (right).

---

## Finance

Route: `/finance`. Reference: same file, "Finance".

**Budget cards** — `repeat(auto-fit, minmax(300px, 1fr))`, 16px gap. Two cards: "Transfer budget",
"Wage budget (weekly)". Padding `20px 22px`.
Title 13px/600 `#475467` · remaining 34px/700 · `"remaining of {total}"` 13px muted ·
10px four-segment bar (spent `#475467`, committed `#407ede`, reserved `#d29923`, free = track) ·
rule · four legend rows, each a 9px radius-2 swatch + 13px label left, 14px/600 value right.

**Approval threshold card** — description left (14px/1.6 `#475467`, max 560px), threshold right:
11px label, 30px/700 value, then "Change" and "Turn off" secondary buttons.
Copy: `"A manager's bid, offer or acceptance at or above this amount waits for sign-off from you
or a sporting director instead of executing."`

**Commitments table** — header `"Where the money is committed"`, right caption
`"£{x} across {n} commitments"`. Columns: Commitment · Type · Amount (right) · Releases when.
The "Releases when" column is the point of the table; never drop it on mobile.

---

## Approvals

Route: `/approvals`. Reference: same file, "Approvals".

Intro line 13px `#475467`: `"Manager actions at or above £5.0M require your approval. Change this
on the Finance page."`

Tier-1 band, heading `"Waiting on your decision — {count}"`.
Row `18px 20px`: request title 16px/700 · requester, elapsed time and any auction deadline as
13px `#475467` · "Budget after" `flex: 0 1 150px` at 17px/700 green · Approve (success primary)
and Reject (destructive) buttons.

Below a `#f5f6f7` rule, the decision context as a 26px-gap flex row: reserve on the listing ·
current best bid · our valuation · squad effect. Each is an 11px muted label over a 14px/600
value. **This context is the reason the screen exists** — an approval with only an amount is not
a decision.

Decided table: Request · Requested by · Amount (right) · Outcome · Decided (right).

---

## Squad (My Club)

Route: `/my-club`. Reference: `TransferX - Radical Screens.dc.html`, "Squad" — content only, chrome
restyled to Board v2.

Tier-2 figures: Contracts under 12 months (amber when > 0) · Listed · Average age · Wage room.

Filter chips: All {n} · Contract risk {n} · Listed {n} · Open to offers {n} · Injured {n}.
Right of the chips, 13px muted: `"Sorted by contract risk"`.

**Position groups.** Each group: heading 15px/700 (Goalkeepers / Defenders / Midfielders /
Forwards) with a verdict beside it at 13px/600 — `"1 of 3 minimum — priority gap"` in `#ac1922`
when short, `"4 of 4 — covered"` in `#006925` when not. 22px between groups.

Player row inside a white ringed card, `14px 20px`, 18px gap, wrapping:

| Element | Basis | Content |
|---|---|---|
| Avatar | 38px circle | Initials 14px/700, position colours |
| Identity | `1 1 170px` | Name 15px/600; age + nationality 12px `#667085` |
| Contract | `0 1 120px` | 11px label `"Contract ends"`; date 14px/600, red under 6 months, amber under 12 |
| Wage | `0 1 90px` | 11px label `"Wage / wk"`; 14px/600 |
| Value | `1 1 190px` | 11px muted `"Market vs your valuation"` left, signed percentage right in its colour; 6px two-segment bar; 12px muted `"{market} market · {valuation} yours"` |
| Flag | `0 1 110px`, right | 12px/600 coloured — "Offer £4.2M", "42 days left", "Open to offers", "Rising value" |

Rail: "Contract cliff" (three expiry windows with the value at risk in each) · "Wage bill by
position" · "Age profile" (four bands as 16px horizontal bars).

Mobile: keep avatar, identity, contract and wage. Drop the value bar and flag into a second line.

---

## Browse players

Route: `/market`. Reference: same file, "Browse players". Chrome restyled.

Tier-2 figures: Budget free · Wage room · `"Under fair value"` count.
Header subtitle names the active saved view: `"Search view: {name} · {n} matches · budget allows
{n} signings"`.

**Filter rail** — 250px, white, ringed, sticky `top: 24px`. Fields as 14px boxed rows with a
`1px solid #d0d5dd` border, radius 8, `9px 11px`, the value left and an 11px muted hint right.
Position · Asking price · Wage per week · Age · Contract ends within · Form score. Below a rule,
"Saved views" as a 13px list, active one 600 `#14171f`.

**Sort chips**: Best value first · Form · Cheapest · Youngest. Right, 13px muted:
`"{n} players · {n} selected to compare"`.

**Result row** — white card, radius 14, ring; `#e4e7ec` normally, tinted when the player is under
fair value. Padding `16px 20px`, 20px gap, wrapping.

Avatar 44px · identity `0 1 200px` (name 16px/600 with position 11px/700 beside it; club, age,
nationality 13px `#667085`) · **value signal `1 1 200px`** (11px muted `"Asking vs fair value"`
left with the plain-language signal right in its colour; 8px bar; asking and fair values 12px
muted beneath) · Form `0 1 96px` · Wage `0 1 110px` with the wage-fit line 11px coloured ·
"Make offer" primary and "Shortlist" secondary.

Signal wording is always plain: `"15% under fair value"`, `"20% over fair value"`,
`"Free transfer"`. Never a bare number or a letter grade.

**Compare tray** — fixed to the bottom, `#14171f`, `14px 36px`. `"Comparing"` label, then a pill
per selected player, then a white `"Compare {n} players"` button right.

---

## Sale detail / bidding

Route: `/listings/:id`. Reference: `TransferX - Radical Bidding.dc.html`, "Bidding on a listing".
Chrome restyled. Two variants driven by whether the current club owns the listing.

Tier-2 figures: Closes in · Best bid · Reserve (`"Met"` in green or the amount in red) ·
Minimum next bid.

**Bid ladder** — white card radius 14, `20px 22px`.
Legend row, 12px muted, 22px gap: a 14×3 swatch plus label for Bid (`#14171f`), Reserve
(`#c53637`), Your valuation (`#215fbc`).

Each bid, 14px apart: rank 26px 13px/700 muted · club `0 1 190px` (name 15px/600, `"{when} ·
wage offer {amount}"` 12px muted) · **bar `1 1 260px`** · amount `0 1 120px` right (17px/700 with
a 12px/600 status beneath) · seller-only accept button.

The bar is the point of the screen: a 26px `#f2f3f5` track with the bid painted to scale, and two
absolutely-positioned 2px vertical lines at 55% opacity marking reserve and valuation as a
percentage of the scale maximum. Scale maximum = `max(highest bid, valuation) × 1.03`. Leading
bid `#14171f`; outbid `#98a2b3`; below reserve `#c4c9d2`.

**Seller — consequence card.** Header `"If you accept {club}'s {amount} now"`, right caption
`"Reserve met · {n} days early"`. Four cells: Fee received (with `"vs {valuation} valuation"`) ·
Budget after · Wage freed · Squad effect. Then "Accept {amount} and open deal" (success primary)
and "Hold until deadline" (secondary), with a 12px muted line beneath: `"Accepting closes the
auction to the other {n} bidders and creates a deal at the Agreement stage."`

**Buyer — composer.** Amount as a 26px/700 value in a `2px solid #215fbc` box, min-width 220px,
beside three secondary shortcuts: `"Min {amount}"`, `"+{increment}"`, `"Match valuation
{amount}"`. Below: a budget-after bar with `"Committed elsewhere {x} · this bid {y} · free after
{z}"`. Optional message field.

**The approval panel sits beside the composer, before the submit button** — `#faf6ec` background,
radius 12. Heading `"This bid needs approval before it is placed"` in `#7a4a00`, then a plain
explanation and the approver's name and typical response time. This is the ordering fix: the
current app reveals the approval requirement after submission.

Buttons: `"Send {amount} for approval"` primary, `"Withdraw current bid"` secondary.

Rail: "Accept now or wait" (two scenarios with the reasoning stated in words) · "Bidder history
with you" · "Listing terms".

---

## Deal room

Route: `/deals/:id`. Reference: same file, "Contract negotiation".

Header carries the blocker, not the stage: 11px overline `"Blocked on"`, then the blocker at
22px/700 amber, then `"{n} days without movement"`. The six-pill stage tracker sits beneath.

**Three lanes** — `repeat(auto-fit, minmax(230px, 1fr))`, 12px gap. Each: 4px accent strip on
top, status overline in the accent colour, title 15px/700, a two-line explanation, then a metric
row above a rule.
Club to club (green when agreed) · Agent commission (amber when blocking) · Personal terms (grey
when not started).

**Terms diff** — the spine of the screen. Header `"Terms — version {n} proposed by {club}"` with
`"{n} of {n} terms changed · sent {when}"` beneath, and the state right in amber.
Columns: Term · Agreed (v{n-1}) · Proposed (v{n}) · Effect on you (right).
Unchanged rows: white, old and new identical, effect `"No change"` muted.
Changed rows: `#fff8f7` tint, old value muted with `line-through`, new value 700, effect in red
or green.
Footer: Accept / Counter / Collapse buttons, then a 12px summary line —
`"Net change against version {n-1}: −£340K to {club} over the life of the deal."`

Mobile: one card per term. Unchanged terms collapse behind `"{n} unchanged terms"`.

**Message rail** — three channel buttons (Shared · {Club} only · Agent thread) filling the header
row. When a private channel is active, a full-width banner in `#fdf6e7` with `#7a4a00` text:
`"Private to {club} — {counterparty} and the agent cannot see this channel."` Not a small pill —
posting to the wrong channel is a real commercial risk.
Messages: author 12px/700 with timestamp right, body 13px/1.5, bubble radius 10, own messages
tinted `#f0f6ff`, others `#f7f8fa`. Composer placeholder names the channel.

**Documents** — name 13px/500 with 11px muted meta, status right 12px/600 (Signed / Passed /
Verified green, Pending amber).

---

## Archetypes for the remaining pages

**Admin table** (17 pages) — page header, optional filter chips, one `ResponsiveTable`. No tiers,
no rails. These should need no page-level work if the primitives are right.

**List + filter** — chip row, then either cards (when a row needs more than five fields) or a
table. Same chip styling everywhere.

**Form** — max-width 640px, single column, 20px between fields. Label 13px/600 `#344054` 6px
above the input. Input `10px 12px`, radius 8, `1px solid #d0d5dd`, 14px; focus swaps the border
to `#215fbc` and adds the focus ring. Error: border `#c53637`, message 12px `#9b1e22` beneath.
Actions bottom-left, primary first. 44px minimum height on touch.

**Auth** — centred card, max-width 400px, on the `#f7f8fa` page. Logo tile above the title.
Card white, radius 12, ring, 32px padding. Full-width primary button.
