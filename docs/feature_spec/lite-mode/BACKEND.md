---
title: "Lite Mode — Backend Changes"
last_updated: 2026-09-29
status: Active
owner: "TODO — assign a Product Owner"
---

# Lite mode: backend changes

Written against `main` on 2026-09-29, after PR #7 (the workflow assistant, architecture ADR 0006), the row locks for audit H3, and migrations up to `0084`. This replaces the 2026-09-28 version of this file.

## What already exists and gets reused

| Need in Lite | Already on `main` | Reuse how |
|---|---|---|
| Ask anything | `ai/assist.py` `ask()` behind `POST /ai/ask`. It answers from `ask_facts` (budget, offers, deals, waiting_on_you, listings, enquiries, squad, pages), returns `{answer, links}`, and only keeps links whose paths appear in the facts | Extend it (§3). Don't build a second assistant |
| Money checks | `check_terms` / `POST /ai/offer-check`: rule-based, no model and no rate-limit slot. Already warns `over_transfer_budget` and `over_wage_budget`. Budget numbers come from `_budget_facts`, `clubs.service.get_commitments` and `reserve_budget` | Add a `money` block to its response (§4) |
| Deal progress | `deal_steps(deal, viewer_club_id)`: outstanding steps and who owns each, computed from the deal's stages (no model). Exposed at `GET /ai/deals/{id}/next-steps` | Map onto five plain steps (§5) |
| Morning summary | `club_briefing` / `GET /ai/briefing`, already in the digest email | Optional line on the Lite home (§2) |
| Counter from a suggestion | Offer counter body `ai_assisted: bool`, which writes an `AI_SUGGESTION_USED` audit event | Extend to create, accept and reject (§3) |
| Row locks on money paths | `offers.service` and `deals.service` lock rows with `with_for_update` (H3 done) | Nothing to add. It was a prerequisite, now met |
| Anonymous buyers | `_masked()` / "an undisclosed club" | **Every Lite string that names a club must go through it** |

## Rules from ADR 0006 that shape this plan

- **The assistant advises; the club acts through the normal confirmed form.** In Lite, the action card (README screen 5) *is* that confirmed form. It is pre-filled from the assistant's validated suggestion, and confirming calls the existing offer, bid or approval endpoints with `ai_assisted: true`. No assistant endpoint changes state.
- **TransferX computes the figures.** The money panel's before and after amounts come from code (§4), never from the model.
- **Model output is validated.** The new `proposal` field (§3) is checked the same way as `_validate_suggestion`: known kinds only, a player and offer the club can see, amounts within the existing bounds.

The earlier plan's `assistant_drafts` table and `POST /ai/assistant` endpoint are **dropped**. They duplicated `ask()` and conflicted with ADR 0006.

Use the next free Alembic revision after the current head (`0084` at the time of writing; check before adding).

---

## 1. User preferences

**Why:** Lite mode and text size must follow the user across devices, and the default by role must be decided once, on the server.

**Migration:** new table `user_preferences`

| Column | Type | Notes |
|---|---|---|
| `user_id` | UUID PK, FK users.id ON DELETE CASCADE | |
| `lite_mode` | bool, nullable | null means use the role default |
| `text_scale` | enum `NORMAL`/`LARGE`/`LARGER`, default `NORMAL` | |
| `lite_resume_json` | `JSON().with_variant(JSONB, "postgresql")`, nullable | §2 |
| `updated_at` | timestamptz | |

**Role default** (when `lite_mode` is null): on for OWNER and SPORTING_DIRECTOR, off for everyone else, including players and agents, **but only when the `LITE_ROLE_DEFAULT_ON` setting is true**. It stays false after L4: the product owner keeps the full app as the default for now (2026-09-30).

**Endpoints:** `GET /users/me/preferences` returns `{ lite_mode, lite_mode_is_default, text_scale }`. `PATCH /users/me/preferences` updates them and writes an `AuditEvent` (`action="lite_mode_changed"`) so adoption can be measured.

## 2. Lite home read model

**Why:** the tiles depend on the transfer window and on what's waiting. Deciding them on the server means the rules can change without a frontend release, and the home screen needs one request, not four.

**Endpoint:** `GET /lite/home` (new module `app/lite/`), club members only.

```jsonc
{
  "first_name": "Rob",
  "window": { "state": "open" | "closed" | "none", "closes_at": "...", "next_opens_at": "...", "days": 12 },
  "money": { "transfer_remaining": 22000000, "transfer_budget": 40000000, "wage_remaining_weekly": 140000, "as_of": "..." },
  "waiting": { "count": 2, "club_names": ["Chelsea", "an undisclosed club"] },
  "tiles": [ { "key": "buy", "style": "accent", "title": "...", "subtitle": "...", "href": "/lite/buy", "badge": null }, ... ],
  "resume": { "title": "...", "href": "..." } | null,
  "team_contact": { "user_id": "...", "first_name": "Sam" } | null,
  "briefing_headline": "..." | null
}
```

- `money`: use `_budget_facts` as it is. `transfer_remaining` is already net of reserved, committed and spent money, so it matches the Finance page; subtracting `get_commitments` again would count reservations twice.
- `waiting`: `dashboard.service.get_dashboard(...).waiting_on_you`. It is already the single source for the Dashboard, the digest and the briefing; keep it that way. Mask club names with `_masked()`.
- `tiles`: rules live in `lite.service.build_tiles`:
  - Window open: buy, sell, offers, ask.
  - Window closed: renew, plan, squad, ask. Swap squad for offers when `waiting.count > 0`.
  - Contracts use `_contract_ends` (active contract, else the player record). Contract end dates are **mock data** at the moment, so the renew tile's count is only as good as that data.
- `resume`: `PUT /lite/resume {title, href}` and `DELETE /lite/resume`, stored in `lite_resume_json`. Expires after 14 days.
- `briefing_headline`: only from the cache. **Never trigger a model call from the home screen**, because it would use up the user's AI allowance just by opening the app.

## 2a. Buy flow candidates

**Why:** the three suggestions must be players the club can actually make an offer for, and must appear without spending the user's AI allowance (decision 3).

`GET /lite/buy/candidates?position=GK|DEF|MID|FWD|ANY&band=0-5|5-10|10-20|free`:

- **Pool:** buyable players only — at another TransferX club, or a free agent (the market's `buyable` filter). Never the club's own players, and never a player already in an active deal.
- **Price:** a listing's asking price, else the pricing assistant's guide price (`listing_advice`'s rule: fee model and comparable transfers), else the fee model. A player with no price at all only matches "free" if he is a free agent.
- **Rank:** by squad need at that position (the same signals as "Who might want him?", seen from the buyer), then form, then value against the model. Take the top three.
- **Reason:** one line each. If a model is available and the user's allowance allows, the model writes it from the computed facts; otherwise a plain reason ("You have 2 defenders; he's 24 and priced at £6m"). Cached, so going back and forth costs nothing.
- Anonymous buyers do not appear here (these are players, not offers), but a masked club name never leaks through any reason text.

> **As built (L3):** price is the asking price, else the fee model with the pricing assistant's 30% contract-ending discount; comparable transfers are left out, since they need a model call. Ranking uses need, listed-first, age fit and price; there is no form data yet. `GET /lite/buy/squad` returns the per-position counts shown on the first step. See `SESSIONS.md`, "Deviations in L3".

## 3. Ask anything: extend `ask()`

**Why:** `ask()` already answers and returns validated links. Lite needs two more things: links that go to Lite screens, and suggestions the user can act on.

**Changes to `ai/assist.py`:**

1. **Lite pages in the facts.** When the caller has Lite on, add these to `ask_facts["pages"]`: "Buy a player" `/lite/buy`, "Answer offers" `/lite/offers`, "Ask anything" `/lite/ask`. Also add Lite deep links such as `/lite/buy/results?position=LB&budget=5-10`. Path validation is unchanged: the model may only use paths from the facts.
2. **`proposal` in the answer.** Extend `ASK_USER` so the model can return:
   ```jsonc
   { "answer": "...", "links": [...],
     "proposal": { "kind": "bid" | "counter" | "accept" | "reject" | "list" | "approve" | "decline_approval",
                   "player": "Ellis Varga", "offer_path": "/offers/…"?, "amount": 8000000? } | null }
   ```
   Validate the proposal in code before returning it:
   - `kind` is in the list above.
   - The player or offer is resolved from `ask_facts` or the club's visible market. An ambiguous name returns `proposal: null`, with one link per candidate.
   - The amount passes the same bounds as `_validate_suggestion` (between half and double the known anchors).
   - The caller has the capability for that kind of action (`clubs/capabilities.py`).
   - The response carries the resolved ids and a `prefill` object shaped exactly like the existing endpoint's request body.
   - The server never sends it anywhere. The client opens the action card with it.
3. **The fallback** is the existing error path, plus `links` to two Lite tiles and "Send to {team contact}" (§6).
4. **`input: "voice" | "text"`** is accepted and only logged, to compare voice with typing. Speech-to-text runs in the browser.
5. **Logging:** add `question`, `input`, `had_proposal`, `links_count`, `fallback` to the existing AI usage log if there is one, or to a new `assistant_queries` table. An admin view groups fallbacks by similar text. **Why:** the questions it can't answer show what to build next.

**Plain language:** add to `ASK_USER` (or a Lite variant): British English, "£8m" and "£35k a week", at most three sentences, no internal terms. The shared `SYSTEM_ADVISOR` rule ("only the given figures") stays.

**Rate limit:** `ai/rate_limit.py` allows 20 requests per hour per user, shared across all AI features. Cache hits are free. For Lite:
- Home and money previews never call the model (§2, §4).
- Give `ask` its own bucket of 40 per hour, so a director asking questions doesn't lock out the offer advisor.
- The limiter is in memory. The handover already lists "Shared store for AI cache and rate limit" as a prerequisite for running several processes. Lite doesn't change that.

**Existing ⌘K:** `GlobalSearch.tsx` already calls `/ai/ask`. It keeps working unchanged, and can show `proposal` later as a separate improvement.

## 4. Money effect: extend `/ai/offer-check`

**Why:** the money panel has to use the same arithmetic as the real checks, or the card could say "£14m left" while the offer is refused as over budget.

- Add a `money` block to the `check_offer_terms` response:
  ```jsonc
  "money": { "transfer_before": 22000000, "transfer_after": 14000000, "transfer_budget": 40000000,
             "this_action": 8000000, "wage_before_weekly": 140000, "wage_after_weekly": 105000,
             "over_budget": false, "requires_approval": false, "approver_name": null }
  ```
- Compute it from the **same numbers** `check_terms` uses for `over_transfer_budget` and `over_wage_budget`, including the loan wage split and the `current` offset used for counters. Move that arithmetic into one pure helper that both call.
- The seller side (accept, list) increases `transfer_after` and has no wage line.
- `requires_approval`: extract the rule in `approvals.service.maybe_capture` (MANAGER role, club threshold set, amount at or above it; superusers, owners and sporting directors never) into a pure function, `approval_required(db, user, club, amount)`, that `maybe_capture` calls too. There is no read-only check today. `money` calls it without writing anything.
- `over_budget` means the existing checks will refuse the action. The card disables confirm; it is never an approval case.
- No model, so it's safe to call as the amount changes (debounce 250ms on the client). This matches how `useOfferCheck` already works.
- Tests: one table of cases (permanent bid, loan with split, counter raising the fee, accept, over budget) that asserts `money.over_budget` agrees with the `over_*` warnings.

> **As built (L4):** `assist.money_effect` returns `transfer_budget`, `transfer_before`, `transfer_after`, `this_action`, `wage_before_weekly`, `wage_after_weekly`, `wage_this_action`, `on_completion` (seller), `over_transfer`, `over_wage`, `over_budget` and `requires_approval`. It is built on `offers.service._reservation`, net of what a countered or accepted offer already holds, so "over" is exactly `reserve_budget`'s refusal. `approver_name` is left out; the card says "Send for approval". Tests: `tests/test_lite_actions.py`.

## 5. Undo and plain progress

### Undo

**Why:** withdrawing an offer after the other club has been notified is visible to them and embarrassing. Undo has to happen before anything is sent. That is a new state-changing mechanism, so record it in **architecture ADR 0007: "Held sends for undo"**. It does not touch the assistant: held actions are created by the user's confirm, not by the model.

**Migration:** `held_actions` (id, user_id, club_id, kind, `payload_json`, status `HELD`/`EXECUTED`/`CANCELLED`/`FAILED`, `execute_at`, `result_json`, `channel` `APP`/`EMAIL`, `ai_assisted`, created_at, executed_at).

**Endpoints** (in `app/lite/`):
- `POST /lite/actions {kind, payload, ai_assisted}`:
  - Runs the target service's validation **now**, so errors show on the card straight away.
  - Stores `HELD` with `execute_at = now + 10s`.
  - Returns `{id, execute_at}`.
- `POST /lite/actions/{id}/undo`: sets `CANCELLED` if the action is still held; returns 409 if it has already executed.
- `GET /lite/actions/{id}`: status, result, and progress.

**Executor:** an APScheduler job runs every 2 seconds:
- Picks up due rows with `with_for_update(skip_locked=True)`; the pattern is already used in `offers/service.py`.
- Calls the existing service function **as the original user**, with the H3 locks as they are.
- If the approval policy intercepts it, the result is a pending approval, and progress shows "Waiting for {owner} to approve".
- Passes `ai_assisted` through, so `AI_SUGGESTION_USED` is still written.
- Writes an `AuditEvent` when an action is held, cancelled or executed.

**No side effects while held:** no notification, email or websocket event for a `HELD` row.

### Progress

`GET /lite/actions/{id}` and `GET /lite/deals/{deal_id}/progress` return five plain steps. The **current step's label comes from `deal_steps()`** where there is one (e.g. "Record the player's answer, with the signed terms"), so Lite and the deal page never disagree.

| Source | Plain step |
|---|---|
| Held | "Sending in {n} seconds" |
| Approval pending | "Waiting for {owner} to approve" |
| Offer open, their move | "Waiting for {club} to reply" |
| Offer countered, your move | "{Club} replied with £{x}m — your turn" |
| Deal AGREEMENT | "Fee agreed" |
| AGENT_NEGOTIATION, PERSONAL_TERMS | "Medical and personal terms", with the current `deal_steps` label as the hint |
| PAPERWORK, CONFIRMED | "Paperwork", with the current `deal_steps` label as the hint |
| COMPLETED | "Signed" |
| Collapsed, rejected, withdrawn | Final step "Deal ended — {reason}" |

The "clubs usually reply in 1 to 2 days" hint is the platform median time to accept or counter. Hide it when there are fewer than 20 data points.

## 6. Team contact ("Ask Sam")

- **Migration:** add `is_lite_contact` to the club staff table, one per club, set on the team page by TEAM_MANAGE.
- **Fallback:** the first SPORTING_DIRECTOR or MANAGER who isn't the current user. If there is nobody, labels read "your team".
- `POST /lite/ask-team {subject_type, subject_id?, text}` creates a `LITE_QUESTION` notification (new `NotificationType`) with a link to the subject. The negotiation-message tables belong to offers and agents; don't reuse them for internal staff questions.

## 7. Decisions from email

**Why:** the digest (`notifications/digest.py`, `render_digest_html`) already sends waiting_on_you and the AI briefing every day. Adding one-tap decisions reaches directors who rarely open the app.

- **Migration:** `action_tokens`:
  - Columns: token_hash, user_id, subject_kind, subject_id, allowed_actions, subject_version, expires_at, used_at.
  - Only the hash is stored.
  - Each token is single-use and expires after 24 hours.
- `render_digest_html` and the OFFER_RECEIVED and APPROVAL_REQUESTED emails get up to three buttons per item. Each button links to `/lite/confirm/{token}?action=…&amount=…`.
- `GET /lite/confirm/{token}` has **no side effects** (mail scanners follow links). It returns the action card and runs the §4 money check.
- `POST /lite/confirm/{token}` creates a held action with `channel=EMAIL`. **For actions that move money (accept, counter, bid) the caller must also be signed in as the token's user** (decision 4); a decline needs only the token. If `subject_version` (the offer's `last_action_at`) has changed since the email was sent, return 409 "This has changed since we emailed you", with the current state.
- Masking applies: the email never names an anonymous buyer.
- Follows the existing per-type `email_enabled` and `DAILY_DIGEST` preferences.

**WhatsApp** stays phase 2 and out of this plan. It adds template approval, a webhook with signature checks, and number verification. Revisit it if email decisions get used.

## 8. Tests

- Preferences: role default; PATCH writes an audit event.
- `/lite/home`: tile sets for window open, closed and none; the waiting count equals `get_dashboard`; an anonymous buyer is masked; no model call.
- `ask` proposal:
  - an invalid kind, an out-of-range amount or a player the club can't see gives `proposal: null`;
  - a READONLY or SCOUT caller never gets a proposal;
  - Lite paths appear only for Lite users;
  - the LLM is mocked (tests never call a model today).
- `offer-check` money: the shared table from §4.
- Held actions:
  - undo before `execute_at` leaves no notification row for the other club;
  - undo after it returns 409;
  - the action executes exactly once under two workers;
  - a manager's action captured by the approval policy becomes a pending approval;
  - `ai_assisted` is carried through to `AI_SUGGESTION_USED`.
- Tokens: GET has no side effects; a reused or expired token fails; a changed offer returns 409; an anonymous buyer is masked in the email.

## 9. Summary

| Area | New | Changed |
|---|---|---|
| Tables | `user_preferences`, `held_actions`, `action_tokens`, optionally `assistant_queries` | staff `is_lite_contact` |
| Enum | `NotificationType.LITE_QUESTION` | |
| Endpoints | `/users/me/preferences`, `/lite/home`, `/lite/buy/candidates`, `/lite/resume`, `/lite/actions*`, `/lite/deals/{id}/progress`, `/lite/ask-team`, `/lite/confirm/{token}` | `/ai/ask` (Lite pages, `proposal`, `input`), `/ai/offer-check` (`money`), offer create/accept/reject accept `ai_assisted` |
| Code | `app/lite/`; `approvals.service.approval_required` (extracted) | `ai/assist.py` (`ask_facts`, `ask`, shared money helper), `ai/prompts.py` `ASK_USER`, `ai/rate_limit.py` (separate ask bucket), `notifications/email.py` and `digest.py` |
| Jobs | held-action executor (every 2s) | |
| Docs | architecture ADR 0007 "Held sends for undo" | ADR 0006: note that Lite's action card is the "normal confirmed form" |
| Dropped from the previous plan | `POST /ai/assistant`, `assistant_drafts`, `/lite/preview`, the L0 prerequisites (H3 done), WhatsApp | |
