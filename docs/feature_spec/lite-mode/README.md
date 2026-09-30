---
title: "Lite Mode — Screens and Rationale"
last_updated: 2026-09-29
status: Active
owner: "TODO — assign a Product Owner"
---

# Handoff: Lite mode for sporting directors

## Overview

Lite mode is a second, simpler home for TransferX, built for sporting directors and club owners who are not technical. It replaces the dashboard and sidebar with four large choices and one question per screen, and adds an assistant that answers questions in plain English and can prepare actions for the user to confirm.

Lite mode is a **preference**, not a separate app. Once it is complete (L4) it is on by default for Owner and Sporting Director accounts and off for everyone else; until then it is off for everyone (decision 1). Anyone can switch it in the profile menu. The full app stays exactly as it is.

What it adds:

1. **Lite home**: four tiles that change with the transfer window, a "Carry on where you left off" card, and a money line in the greeting.
2. **Buy a player, guided**: position → budget → three suggested players.
3. **Ask anything**: an assistant that returns an answer, a shortcut, or a ready-to-confirm action card. Type or speak.
4. **Action cards with money effect**: every money action shows "£22m → £14m" before you confirm.
5. **Undo for 10 seconds** after every action, then a plain-word deal progress view.
6. **Decide outside the app**: one-tap decisions from email (phase 1) and WhatsApp (phase 2).
7. **Text size** setting (three steps).

## Decisions taken with the product owner (2026-09-29)

These override anything below that disagrees.

1. **Off by default until L4.** Lite is off for everyone while L1–L3 are built. Anyone can switch it on in the profile menu. The role default (on for OWNER and SPORTING_DIRECTOR) is switched on once action cards (L4) ship, by the `LITE_ROLE_DEFAULT_ON` setting. *(Superseded 2026-09-30: the product owner keeps the full app as everyone's default for now; Lite is opt-in.)*
2. **Four position groups.** The data holds only GK, DEF, MID and FWD, so the Buy flow asks Goalkeeper, Defender, Midfielder, Forward or Not sure.
3. **Buy results: rules first, the AI writes the reason.** TransferX picks the three players in code from buyable players only (a TransferX club or a free agent), by position, fee band and squad need. The model only writes the one-line reason. Without a model, results still show with a plain reason.
4. **Email decisions need sign-in to move money.** Opening the confirm page and saying no need no sign-in. Accepting, countering or bidding asks the user to sign in first.
5. **Text size applies inside Lite only.** The full app has many fixed pixel sizes that would not scale.
6. **Money figures:** see BACKEND.md §2 and §4. The remaining budget is `_budget_facts` as is (already net of reserved, committed and spent). An over-budget action is refused, not sent for approval.

Backend changes are in [`BACKEND.md`](./BACKEND.md). The build order is in [`SESSIONS.md`](./SESSIONS.md). The rules for any session doing this work are in [`CLAUDE.md`](./CLAUDE.md).

## About the design files

`TransferX - Director Home.dc.html` is a **design reference built in HTML**. It shows the intended layout, copy and behaviour. It is not production code. Recreate it in the existing frontend (React 19, TypeScript, Vite, Tailwind v4, TanStack Query, React Router) using the app's own components and tokens. Never copy its inline styles.

The file contains several design rounds. Only these are in scope:

| Id | What it is | Interactive in the mock? |
|---|---|---|
| **2a** | Lite home, Buy flow, Ask anything, Lite mode switch | Yes |
| **3a** | Assistant action card with money effect | No, static |
| **3b** | After confirming: undo bar and deal progress | No, static |
| **3c** | Phone notification and chat-app decision | No, static |
| **3d** | Home outside the window, resume card, profile menu | No, static |

Rounds 1a, 1b, 2b and 2c were rejected. Ignore them.

Where 2a and 3d disagree, **3d wins**: the Lite mode switch lives in the profile menu (3d), not in the top bar (2a).

## Fidelity

**High fidelity for layout, hierarchy, copy and sizing; token-mapped for colour.** Recreate the structure, type sizes, spacing and tap-target sizes exactly. Map the mock's colours onto the existing tokens in `src/index.css` (table under "Design tokens"). Lite mode must work in both light and dark themes, like the rest of the app.

All names, clubs and amounts in the mock (Northgate FC, Rob, Sam Price, Ellis Varga, Jordan Mitchell, £22m) are placeholders. Never commit them as fixtures or defaults.

---

## Why it is designed this way

These decisions came out of reviewing the earlier Lite mock and testing six directions with the product owner.

**1. Four big choices, not a nav.** The users think in jobs ("I need a left-back", "Chelsea want Mitchell"), not in pages. A sidebar with 13 items in four groups asks them to learn the software's structure first. Four tiles named after jobs need no learning. We tested a squad-on-a-pitch home (1a), a one-decision-at-a-time inbox (1b), a chat app (2b) and a morning letter (2c). The product owner picked the tiles.

**2. One question per screen.** Filter panels with ten controls are where non-technical users stall. Two questions with big buttons (position, then budget) reach the same result with no typing and no wrong answers. "Not sure" is always an option and hands the choice to the recruitment team.

**3. An assistant instead of search.** A search box needs the user to know what to search for. "Ask anything" accepts the question as they would say it to a colleague. It answers directly when it can ("You have £22m left"), gives a shortcut when the answer is a page, and prepares an action when the user asks for one. The backend already exists: "Ask TransferX" (`/ai/ask`, in the ⌘K search since PR #7). Lite gives it a home tile and a large, touch-first screen, because ⌘K suits neither this audience nor an iPad.

**4. The assistant suggests, the user confirms, the existing API executes.** This follows architecture ADR 0006 ("advises and never acts"). The model never places a bid or accepts an offer. It can return a validated `proposal`, which pre-fills the action card, and the action card is the normal confirmed form. Confirming calls the same endpoints the full app uses, marked `ai_assisted`, so permissions, spending approvals, budget checks, the transfer-window rule and the `AI_SUGGESTION_USED` audit all still apply. This keeps one path for money and removes the risk of acting on a misheard sentence.

**5. Always show the money effect before confirming.** Money is what directors worry about most. Seeing "£22m → £14m" and the wage change on the card answers the first question they would ask before they have to ask it.

**6. Undo instead of "Are you sure?".** Confirmation dialogs get clicked through. A 10-second undo lets people act quickly and still recover. The action is held on the server for those 10 seconds, so the other club never sees an offer that was taken back.

**7. Plain-word deal progress.** "Waiting for Brentwell to reply — clubs usually reply in 1 to 2 days" answers the phone call the director would otherwise make. It maps the existing deal stages onto five steps with no jargon.

**8. Decide outside the app.** Many directors live in email and WhatsApp and open a new app a few times a week at most. The daily digest already sends "waiting on you" by email. Adding one-tap decision links there reaches them where they already are. WhatsApp follows because its reply buttons (maximum three) match our three-option decisions exactly.

**9. Seasonal tiles.** "Buy a player" is the wrong first tile when the window is closed. Outside the window the home shows Renew contracts, Plan January, My squad and Ask anything.

**10. Lite mode in the profile menu, on by role.** A switch in the top bar is easy to hit by accident. The first-login question from the earlier mock was also dropped: it asked people to choose before they had seen either option. Instead the default is set by role and changing it is one tap in the profile menu. The full app gets a matching "Back to Lite mode" item so switching off never feels like a trap.

**11. Light theme, large type, text size setting.** Many directors are over 50 and use iPads in daylight. Body text starts at 17–18px, and headings at 30–40px. Tap targets are 52px or larger. A three-step text size setting covers the rest.

**12. Log the questions the assistant can't answer.** They show what directors actually want. Questions that come up often should become a tile or a shortcut.

---

## Screens

Design size is iPad landscape, 1194 × 834. See "Responsive" for other sizes.

### Shared: Lite top bar

- Height 72px, surface background, 1px bottom border.
- Left: logo mark (34px square, radius 9px, accent background), "TransferX" 18px/800, club name 16px muted.
- Right: **Home** button (only when not on home; 16px/700, padding 12×20, radius 12, subtle background, house icon), then the **avatar** (44px circle) which opens the profile menu.
- No sidebar, no search box, no notification bell. Waiting items appear on the home tiles.

### Screen 1 — Lite home, window open (2a)

**Purpose:** pick what to do.

**Layout:** padding 44px 56px 48px; vertical stack, gap 32px.

- **Greeting**: "Good morning, {first name}." 40px/800, letter-spacing −0.025em. Line below at 22px muted: "What would you like to do? You have {£22m} left to spend and {12} days until the window closes." Use "Good afternoon/evening" by local time.
- **Resume card** (optional, see 3d): full width, above the tiles, only when there is an unfinished flow.
- **Tile grid**: 2 × 2, fills the remaining height, gap 20px. Each tile: radius 24px, padding 30×32, icon 40px top-left, title 30px/800 bottom-left, subtitle 18px below.

| Tile | Style | Title | Subtitle | Goes to |
|---|---|---|---|---|
| 1 | Accent fill, white text | Buy a player | Tell us what you need. We'll find them. | Buy flow step 1 |
| 2 | Surface, 1px border | Sell or loan a player | Pick someone from your squad. | Squad picker (existing squad page filtered in Lite layout) |
| 3 | Surface, 2px danger-subtle border, count pill | Answer offers | "{Club A} and {Club B} are waiting for you." | Decision list (see below) |
| 4 | AI-subtle fill, 2px AI border | Ask anything | Ask a question in your own words. Get the answer or a shortcut. | Assistant |

- **Answer offers** shows a pill "{n} waiting" (18px/800, danger fill). The count and names come from the dashboard's `waiting_on_you`. An anonymous buyer is always written as "an undisclosed club". When the count is 0, the tile shows "Nothing waiting" in muted style and has no pill. It stays in place so the grid doesn't shift.
- **Answer offers destination**: a Lite list of the `waiting_on_you` items, each as an action card (screen 5 layout) with its three buttons. One card per item, stacked.

### Screen 2 — Lite home, window closed (3d)

Same layout. The greeting line reads "The window is closed. The next one opens on {1 January}, in {95} days." (from `get_next_window`). If no window is configured, the line is dropped.

| Tile | Title | Subtitle |
|---|---|---|
| 1 (accent) | Renew contracts | "{2} players' contracts end this season" |
| 2 | Plan January | Make a shortlist before the window opens |
| 3 | My squad | Who's playing, who's on loan |
| 4 (AI) | Ask anything | Type or speak a question |

If offers are waiting while the window is closed (e.g. loan recalls, enquiries), "Answer offers" replaces "My squad".

Tiles are chosen by the server (`/lite/home` returns them), so the rules can change without a frontend release.

**Resume card:** height about 84px, radius 18px, surface, 2px accent-subtle border. Clock icon in a 48px accent-subtle square. Overline "Carry on where you left off" 15px/600 accent. Title 20px/700, e.g. "Left-back search, £5m to £10m · 3 players found". Button "Continue" 54px high, accent fill. Hidden when there's nothing to resume. Dismissed automatically once the flow is finished.

### Screen 3 — Buy flow (2a)

**Step header:** Back button (outlined, chevron, 17px/600) on the left; step label on the right, 16px/600 muted ("Step 1 of 2", "Step 2 of 2", "Results").
**Question:** 38px/800. Hint 20px muted below.

- **Step 1 — "What position do you need?"** Hint: "Tap one. You can change it later." Grid of choice buttons (3 + 2, or one row on wide screens), gap 16, each 120px high, radius 20, 2px border, label 22px/700 and a 15px muted sublabel. Options: Goalkeeper, Defender, Midfielder, Forward, Not sure (decision 2: the data has only these four groups). The sublabel for a position with nobody in the squad reads "You have none" (from squad data). Hover/focus: 3px accent border.
- **Step 2 — "How much can you spend on the fee?"** Hint: "You have £{22}m left this window." Options: Up to £5m, £5m to £10m, £10m to £20m, Free or loan. Hide any band that is entirely above the remaining budget.
- **Results — "3 players who fit".** Hint: "{Left-backs} available now, chosen by {Head of Recruitment first name}'s team." Three cards in a row, gap 20. Each card: 56px initials avatar, name 22px/800, club 16px muted; rows Age / Price (accent, 800) / Wages; a reason box (16px, subtle background, radius 12); "Make an offer" (56px, accent) and "Ask {name} about him" (48px, outlined).
- Data: `GET /lite/buy/candidates?position=&band=` (BACKEND.md §2a). TransferX picks the three in code from buyable players; the model only writes each reason, and a plain reason shows without it (decision 3). Not `/ai/recommendations`, which can suggest players at clubs outside TransferX and needs a model call per search.
- "Make an offer" opens an action card (screen 5) prefilled with the listing's asking price, else the pricing assistant's guide price, else the fee model's value; not the full offer form.
- "Ask Sam about him" sends a message to the club's head of recruitment (see BACKEND.md §6). If the club has no such staff member, the button reads "Ask your team about him" and goes to all club members with MARKET_WRITE.

### Screen 4 — Ask anything (2a, 3a)

- **Input bar:** 68px high, radius 18, surface, 2px AI-border. Sparkle icon, input 20px, placeholder "Type or tap the microphone to speak". On the right a **Speak** button (52px, AI-subtle fill, mic icon) then **Ask** (52px, AI fill, white).
- **Suggestions** (only before the first question): "Or tap a question", then a 2 × 2 grid of 76px buttons, 20px/600 text. Suggestions come from the server so they can reflect the club's state, e.g. "What's happening with Mitchell?" only when there's an open offer for Mitchell.
- **Thread:** newest first. The user's question is a dark bubble aligned right (18px/600). The spoken version shows a small mic icon and quotes. The answer is a white card, radius 20, padding 22×24, text 21px/1.5.
- **Answer types** (from the existing `POST /ai/ask`, extended in BACKEND.md §3: `answer` + `links` is today's response; `proposal` is new. Map `links` onto shortcut buttons, `proposal` onto an action card, and the error path onto the fallback):
  - `answer`: text plus zero to three shortcut buttons (52px, radius 13, 17px/700, trailing "→"). The first shortcut is filled accent, the rest outlined.
  - `navigate`: text plus shortcut buttons only.
  - `action`: an action card (screen 5) inline in the thread.
  - `fallback`: "I don't have an answer for that yet. These might help, or I can pass the question to {Sam}." Shortcuts: two relevant tiles and "Send to {Sam}" (filled).
- **Source line** under every `answer` and `action`: check icon, "Based on your budget and squad data, updated today at 8:02" (15px muted), and "Ask {Sam} to check first →" (16px/700, indigo).
- **Loading:** show the question bubble immediately and a skeleton card with three shimmering lines. Stream the text if possible (the AI module already streams for squad analysis).
- **Errors:** rate limit returns "You've asked a lot of questions this hour. Try again at {time}, or ask {Sam}." LLM unavailable returns the fallback with shortcuts only.
- **Voice:** see BACKEND.md §4 and "Interactions".

### Screen 5 — Action card (3a)

Used by the assistant, by "Make an offer" in the Buy flow, and by Answer offers.

- Card radius 24, two columns: content (flexible) | money panel (400px, subtle background, 1px left border).
- **Content column** (padding 30×32, gap 20):
  - Pill overline "Ready to send · check before confirming" (13px/800 uppercase, AI-subtle). For received offers: "Offer for your player" (danger-subtle). For approvals: "Your approval" (info-subtle).
  - Title 30px/800: "Bid £8m for Ellis Varga".
  - Fact rows 18px, label muted left, value right, 1px separators: Player, Sent to, Fee, Wages offered (or whatever the action type needs; the server sends the rows).
  - Buttons, bottom, gap 12: primary (flex 1, 64px, accent) "Confirm and send bid"; secondary (64px, outlined) "Change amount"; tertiary text button "Cancel".
- **Money panel** (padding 30×28, gap 22):
  - "What this does to your money" 16px/700.
  - "Money left to spend": old value struck through 24px muted, then "→ £14m" 34px/800.
  - Bar 12px high: solid accent for what's left after the action, striped warning for this action's amount, track for what was already spent. Caption "Striped part is this bid, of your £40m budget".
  - "Spare for wages": "£140k → £105k a week".
  - If the action would go over budget: the new value turns danger colour, the primary button is disabled, and the card says "This is more than you have left to spend." An over-budget offer is refused by the existing checks; it is never sent for approval.
  - If the club's approval rule applies (a Manager's action at or above the club's approval threshold; owners and sporting directors are never escalated), the primary button reads "Send to {owner} for approval". The server says which, from the same rule the real endpoint uses.
  - Source line pinned to the bottom (as in screen 4).
- **Change amount:** the fee row becomes a large stepper (−/+ in £0.5m steps, with the number editable). The money panel updates live from `POST /ai/offer-check` (its new `money` block; no model involved), debounced 250ms, using the existing `useOfferCheck` hook.
- **Received offers** use three buttons instead: "Accept £18m" (accent), "Counter at £21m" (outlined; amount from the assistant's suggestion or the club's valuation), "Say no" (outlined danger).

### Screen 6 — Sent, with undo and progress (3b)

- Header: 64px success-subtle circle with a check, title 36px/800 "Bid sent to Brentwell Town", subline 19px "£8m for Ellis Varga. {Sam} has been told."
- **Where this deal is** card: vertical stepper, 32px nodes joined by 3px lines.
  - Done: filled accent with check; line accent.
  - Current: white node, 3px accent ring, accent dot; bold label; helper text below (e.g. "Clubs usually reply in 1 to 2 days. We'll message you.").
  - Future: white node, 2px border; label muted.
  - Steps for a bid: You approved it → Bid sent → Waiting for {club} to reply → Medical and personal terms → Signed. The server maps deal and offer states onto these (BACKEND.md §5).
- Right column (340px): money card ("£14m of £40m", bar, "£8m held for this bid until Brentwell reply"), then "Back to home" (60px, accent) and "Message {Sam} about this" (56px, outlined).
- **Undo bar:** fixed bottom-centre, 620px wide, dark background, radius 18. Text "Bid sent. Changed your mind?" 18px/600. Button "Undo · 8s" (52px, light fill, 800). A 5px progress bar under it counts down 10 seconds. After 10 seconds the bar slides away (200ms ease-out) and the action is final.
- Pressing Undo cancels the held action, shows "Cancelled. Nothing was sent." for 3 seconds, and returns to the previous screen with the card still filled in.
- During the undo window the progress shows "Bid sent" as current, with the helper text "Sending in {n} seconds". After that it advances.

### Screen 7 — Decide outside the app (3c)

**Phase 1, email.** Extend the existing daily digest and the per-event emails for OFFER_RECEIVED and APPROVAL_REQUESTED. Each item gets up to three buttons, e.g. "Ask for £21m", "Accept £18m", "Say no", plus "Open in TransferX". Each button links to a **confirm page** (a minimal Lite page) showing the action card with one "Confirm" button. Opening it and saying no need no sign-in; anything that moves money (accept, counter, bid) asks the user to sign in first (decision 4). Email links must never act on a GET request, because mail scanners follow links.

**Phase 2, WhatsApp.** Same decision as an interactive message with up to three reply buttons. After a reply, send a confirmation: "Done. Chelsea have been sent a counter-offer of £21m. Reply UNDO in the next minute to cancel." The undo window for messaging is 60 seconds, because people read replies more slowly.

**Web push** is optional and last. Action buttons in web push notifications don't work in Safari on iPad and iPhone, which is where most directors are.

### Screen 8 — Profile menu (3d)

Opens from the avatar. 380px wide, radius 20, anchored top-right under the bar.

- Name 18px/800, role and club 15px muted.
- **Lite mode** row: label 17px/700, helper "Simple home with big buttons", switch 52 × 30. Toggling it navigates immediately: on goes to `/lite`, off goes to `/dashboard`.
- **Text size**: three buttons "Aa" at 15, 19 and 24px. Selected has a 3px accent ring and accent-subtle fill. It sets a font-size multiplier (100%, 112.5%, 125%) on the Lite layout only (decision 5): the full app uses fixed pixel sizes that would not scale.
- "Notifications and messages" goes to the existing notification preferences page, which gains WhatsApp in phase 2.
- "Sign out".
- The full app's account menu gets a matching "Switch to Lite mode" item.

---

## Interactions and behaviour

- **Routing:** Lite lives at `/lite` with child routes `/lite/buy`, `/lite/buy/budget`, `/lite/buy/results`, `/lite/ask`, `/lite/offers`, `/lite/done/:actionId`, `/lite/confirm/:token`. After login, users with `lite_mode = true` land on `/lite`, not `/dashboard`.
- **Back:** browser back and the Back button behave the same. Buy flow answers are kept in the URL (`?position=DEF&budget=5-10`), so back and resume both work.
- **Home button** clears the assistant thread.
- **Voice:** the Speak button uses the browser's speech recognition where available, and is hidden where it isn't (Firefox). Recording state: the button turns AI fill with a pulsing dot and reads "Listening…". Tap again or 2s of silence stops recording. The recognised text appears in the input box. It is sent automatically after 1s unless the user edits it. On iPad the keyboard's dictation key already works in the text box, so voice is a convenience, not a dependency.
- **Transitions:** screen changes cross-fade 150ms. Tiles scale to 0.98 on press. No other animation. Respect `prefers-reduced-motion`.
- **Empty states:**
  - Answer offers with nothing waiting shows "Nothing needs you today."
  - Buy results with no matches show "No {left-backs} in that price range right now." with "Try a higher budget" and "Ask {Sam} to look".
- **Permissions:** tiles and buttons follow `GET /clubs/me/membership` capabilities. A READONLY or SCOUT user in Lite sees "Sell or loan" and the action buttons disabled with a text reason ("Your role can't send offers. Ask {owner}."). They are never hidden without a reason.
- **Whose move:** every received-offer card and deal row keeps the existing "Your move / Their move / Neither" badge from the API.

## State management

- **Server state (TanStack Query):** `lite-home`, `dashboard` (existing), `membership` (existing), `recommendations` (existing), `assistant-thread` (session-scoped), `pending-action/:id`, `deal-progress/:id`.
- **Client state:** Buy flow answers (URL params), assistant input text, recording state, undo countdown (derived from the server's `execute_at`, not a local timer alone).
- **Preferences:** `lite_mode`, `text_scale` from `GET /users/me/preferences`. Apply `text_scale` at the root on load, before first paint, to avoid a jump.
- **Resume:** the server stores the last unfinished Lite flow (BACKEND.md §2). The client writes it when a flow step changes and clears it on completion.

## Design tokens

Map the mock's literal colours to existing tokens. No new tokens are needed. The assistant's purple uses the `role-agent-text` token and the ✦ mark, as `AIPanel` in `components/ai/Assistant.tsx` already does.

| Mock value | Use | Token |
|---|---|---|
| `#faf8f5` | Page background | `--color-page` |
| `#ffffff` | Cards, top bar | `--color-surface` |
| `#1c1917` | Primary text | existing primary text token |
| `#57534e`, `#78716c` | Secondary text | existing secondary/muted text tokens (no lighter than `#667085` in light mode) |
| `#e7e5e4`, `#d6d3d1` | Borders | existing border tokens |
| `#047857` | Primary action, accent tile | `--color-accent` |
| `#ecfdf5`, `#d1fae5`, `#a7f3d0` | Accent-subtle fills and borders | existing accent-subtle token |
| `#be123c`, `#fda4af` | Offer waiting, "Say no" | existing danger and danger-subtle tokens |
| `#fbbf24` striped | This action's share of the budget | existing warning token |
| `#6d28d9` | Assistant: Ask button, icon | `role-agent-text` |
| `#f5f3ff` | Assistant tile fill | `role-agent-text` at 10% (as `AskButton`) |
| `#ddd6fe` | Assistant borders | `role-agent-text` at 25–30% (as `AIPanel`) |

Reuse the hooks in `hooks/useAssistant.ts` (`useAsk`, `useOfferCheck`, `useDealNextSteps`, `useAIStatus`). Don't reuse the compact panels: their 13px text is below Lite's size floor.

**Type:** the app font (Inter). Lite type scale: 40 / 38 / 36 / 34 / 30 / 28 / 22 / 21 / 20 / 19 / 18 / 17 / 16 / 15 / 13(overline only). Weights 500, 600, 700, 800. Headline letter-spacing −0.02 to −0.025em.

**Radius:** 9 (logo), 12–14 (buttons), 18 (inputs, resume card), 20 (choice buttons, menus, answer cards), 24 (tiles, action cards).

**Spacing:** 8, 10, 12, 14, 16, 18, 20, 22, 24, 28, 32, 44, 56.

**Tap targets:** 52px minimum for any Lite button, 44px absolute floor.

**Shadows:** cards `0 4px 12px rgba(28,25,23,0.05)` plus a 1px border. Action card `0 8px 24px rgba(28,25,23,0.07)`. Menu `0 20px 50px rgba(28,25,23,0.22)`. Use the existing shadow tokens where they're close.

## Responsive

- **≥1024px (iPad landscape, desktop):** as designed. On wider screens the content is capped at 1100px and centred.
- **768–1023px (iPad portrait):** tiles stay 2 × 2. Buy position grid becomes 2 × 4. Results become one column of horizontal cards. Action card money panel moves under the content.
- **<768px (phone):** tiles become one column, each 120px high. Titles drop to 24px, questions to 28px. Assistant input moves to the bottom of the screen. The undo bar goes full width minus 16px.

## Assets

No images. Icons are simple 24px stroke icons in the mock (lightning logo, house, user-plus, tag, inbox, sparkle, microphone, clock, check, undo arrow). Use the app's existing icon set and match by meaning.

## Files

- `TransferX - Director Home.dc.html`: the design reference. Open it in a browser. The rounds in scope are 2a, 3a, 3b, 3c and 3d.
- `support.js`: the runtime the reference file needs to open. Not part of the implementation.
- `BACKEND.md`: API, data model and job changes.
- `SESSIONS.md`: the build order.
- `CLAUDE.md`: rules for sessions working on this.
