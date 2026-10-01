---
title: "Lite Mode — Build Order"
last_updated: 2026-09-29
status: Active
owner: "TODO — assign a Product Owner"
---

# Lite mode: build order

Each session leaves `main` shippable. Lite sits behind the user preference, so partial work never changes the full app. There are no prerequisites any more: audit H3 is done and the assistant has shipped.

The branches this once waited on (`player-invitations`, PR #9, `username-login-premier-league`) are all merged.

**Decisions (2026-09-29):** Lite is off by default until L4; four position groups; Buy results picked by rules; email money actions need sign-in; text size in Lite only. See README.md.

| # | Session | Backend | Frontend | Done when |
|---|---|---|---|---|
| L1 | Preferences and shell | §1, with `LITE_ROLE_DEFAULT_ON=false` | `/lite` route, Lite top bar, profile menu (Lite switch and text size), "Switch to Lite mode" in the full app's menu, login redirect | Toggling works both ways; text size persists across devices |
| L2 | Home | §2 | Screens 1 and 2, resume card, Answer offers as a list linking to the existing offer pages | All three window states render; the count matches the Dashboard; anonymous buyers are masked; opening home costs no AI allowance |
| L3 | Buy flow | §2a `/lite/buy/candidates` | Screen 3, answers kept in the URL, resume writes | Three results in two taps |
| L4 | Action cards and money | §4 `offer-check` money block; `ai_assisted` on create, accept and reject | Screen 5, fed by `useOfferCheck`; Answer offers become action cards; "Make an offer" from results. Confirming calls the existing endpoints directly (no undo yet). Then turn `LITE_ROLE_DEFAULT_ON` on | The money panel and the over-budget warning always agree |
| L5 | Ask anything in Lite | §3 Lite pages, `proposal`, separate rate-limit bucket, logging | Screen 4 using `useAsk`: large layout, suggestions, voice button, a proposal opens the action card | Scripted questions (money, contracts, a left-back search, an open offer, "bid £8m for X") give the right link or proposal |
| L6 | Undo and progress | §5 plus ADR 0007 | Screen 6; the undo bar counts down from `execute_at`; action cards switch to `POST /lite/actions` | Undo before send leaves no trace for the other club |
| L7 | Team contact | §6 | "Ask {name}" and "Send to {name}" buttons | The question reaches the contact |
| L8 | Email decisions | §7 | `/lite/confirm/:token` | GET has no side effects; a one-tap counter from the digest works |

**Progress:**
- **L1 built (2026-09-29).** Preferences (`app/lite/`, migration `0085`, `LITE_ROLE_DEFAULT_ON=false`), the `/lite` shell with top bar and profile menu (Lite switch, text size, notifications, sign out), "Switch to Lite mode" in the full app's sidebar, and the sign-in redirect. The Lite home is interim: it says Lite is being built and links to the full app.
- **L2 built (2026-09-29).** `GET /lite/home` (window state, money from `_budget_facts`, the Dashboard's waiting list, tiles from `build_tiles`, resume, the cached briefing headline; never a model call), `PUT/DELETE /lite/resume` (Lite paths only, 14-day expiry). Frontend:
  - the Lite home, with the greeting, situation line, resume card and tiles;
  - the Answer offers list, each item opening its existing page;
  - a basic Ask anything page on `/ai/ask`, which L5 extends.
- **Deviations in L2:**
  - Until L3 and a Lite squad picker exist, the Buy and Sell tiles (and Renew and My squad when the window is closed) go to the full-app pages that do those jobs today. The server sets the hrefs, so each is a one-line change when its Lite screen ships.
  - The closed-window tile reads "Plan the next window", not "Plan January", because the next window isn't always January.
- **L3 built (2026-09-30).** `GET /lite/buy/squad` (players per position group, for the "You have 12" lines) and `GET /lite/buy/candidates` (§2a). Frontend: position, budget and results pages, the answers kept in the URL (`/lite/buy/results?position=DEF&budget=5-10`), so Back and the resume card both return to the same results. The results page writes the resume point; "Make an offer" clears it and opens the full offer form until L4's action card. The Buy tile now opens `/lite/buy`.
- **Deviations in L3:**
  - **Price** is a listing's asking price, else the fee model, 30% lower when the contract ends within a year (the pricing assistant's rule). Comparable transfers are not used: the guide price needs a model call per player, which would spend the user's allowance.
  - **Rank** is squad need, then listed before estimated, then age fit, then price. Form is not used, because there is no form data yet.
  - The club's own uncontracted players (created by its members) count towards its squad and never appear as free agents to it.
- **L4 built (2026-09-30).**
  - **Backend:**
    - `money` block on `POST /ai/offer-check`, from `assist.money_effect`. It uses the reservation arithmetic the offer endpoints refuse with (`offers.service._reservation`), and `check_terms`' `over_*` warnings now use it too.
    - `approvals.service.approval_required`, a read-only rule that `maybe_capture` now calls.
    - `ai_assisted` on offer create, accept and reject, audited as `AI_SUGGESTION_USED`.
    - `GET /lite/offer-draft` and `GET /lite/offers/{id}`, which describe a card and never act.
  - **Frontend:**
    - the action card (`components/lite/ActionCard.tsx`) and the new-bid card (`/lite/bid?player_id=`), reached from "Make an offer" in the Buy results;
    - the received-offer card (`/lite/offers/:offerId`): Accept, Counter (a £0.5m stepper), Say no. Each asks once more, then calls the existing endpoints.
    - The money panel debounces 250ms; confirm waits until the panel describes the amount on screen, and is disabled when over budget.
  - `LITE_ROLE_DEFAULT_ON` stays false. The product owner chose on 2026-09-30 to keep the full app as everyone's default for now, which supersedes decision 1's switch-on at L4.
- **Deviations in L4:**
  - **Over-budget check:** the old check looked at the fee and wage alone. It now counts add-ons and a loan's wage split, as the refusal does, so a bid whose add-ons take it over is now warned about.
  - **Seller side:** the panel shows the fee arriving "when the deal completes", which is when the seller's budget is credited.
  - **Loans:** countered in the full app ("Change the loan terms"). Lite counters permanent offers only.
  - **Free agents:** there is no club to make an offer to, so their Buy result links to their page ("See how to sign him").
  - **Approvals:** the button reads "Send for approval" rather than naming the approver. Approval requests go to the owner and every sporting director.
  - **Starting counter:** a seller starts at the higher of the listing price, the fee model and the offer plus 10%, rounded up to £0.5m. A buyer answering a counter starts 5% lower. Both come from code; the assistant's counter advice is not used here, so opening a card uses no AI allowance.
- **L5 built (2026-10-01).** `/ai/ask` with `lite: true`, as BACKEND.md §3: Lite pages and Buy-results links in the facts, `ASK_LITE_USER` (plain language, three sentences), a checked `proposal`, a separate rate-limit bucket (40/hour), and `assistant_queries` logging (`question`, `input`, `lite`, `had_proposal`, `links_count`, `fallback`, migration `0086`). `GET /lite/ask/suggestions` builds four questions from the club's state with no model call. Frontend: the Screen 4 Ask page (suggestions, voice, thread, proposal card, fallback); the bid and offer cards take `?fee=`, `?action=`, `?amount=` and `from=ask`, and confirm with `ai_assisted`. The admin AI page lists questions Ask couldn't answer.
- **Deviations in L5:**
  - **Proposal kinds:** bid, counter, accept and reject, the actions with Lite cards. List and approval proposals wait for Lite cards of their own; Ask links to the page instead.
  - **Answer text:** when a proposal is involved, the answer comes from code ("I've prepared a £6m bid for … for you to check", or why it couldn't be prepared). The model can't know the outcome of the check, and in testing it contradicted it.
  - **Plain bid requests** ("bid £6m for De Cuyper") are also read in code when the model gives no proposal (it sometimes declined because the player isn't in the club's own data). They are checked the same way.
  - **Fallback:** no "Send to {Sam}" (L7). Admin fallbacks are listed newest first, not grouped by similar text.
- **Still open:** users have no first name on record, so the greeting uses the club's name ("Good afternoon, Liverpool"). "Good morning, {first name}" needs a name field, on the user or the club staff record.

**Why this order:**
- **L4 before L5.** The assistant's proposals open the action card, so the card has to exist first.
- **L4 ships without undo.** Direct confirms through the existing endpoints are safe to release on their own. L6 then swaps the card over to held sends, which gives undo.
