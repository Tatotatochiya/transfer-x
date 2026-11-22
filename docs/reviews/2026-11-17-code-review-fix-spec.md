---
title: "Code review fix spec, 17 November 2026"
last_updated: 2026-11-21
status: In progress
owner: "TODO — assign"
---

# Code review fix spec

Reviewed on 17 November 2026 against `main` at `a74d563` (PR #84 merged). This spec covers the 23 findings and 4 smaller items from that review. It leaves out everything already listed in [`2026-11-15-product-and-readiness-review.md`](2026-11-15-product-and-readiness-review.md).

**How this was checked.** A static read of the backend (auth, permissions, offers, deals, approvals, loans, held sends, uploads, AI, deploy files) and a lighter pass over the frontend. No tests were run and nothing was reproduced against a running instance. Each item carries a confidence:

- **Confirmed in code**: the behaviour follows directly from the code as written.
- **Likely**: the code path exists, but the outcome depends on timing or on a caller that was not fully traced.

The race conditions (9, 14, 16, 17) are all **Likely**. The test suite cannot catch them today because it runs on SQLite, which ignores `FOR UPDATE`.

Line numbers are approximate and refer to `backend/` unless stated.

**Checked again on 21 November 2026.** Every item was traced in the code at `a74d563`, and all 23 hold. The corrections that came out of that check are written into the items themselves, each marked *Checked 21 November*:
- item 1 (no worker change needed);
- item 2 (a frontend caller exists);
- item 4 (bcrypt's limit is in bytes);
- item 6 (history is already trimmed; the real risk is forged figures);
- item 7 (a second upload);
- item 8 (uvicorn's `*` trusts a forged header);
- item 10 (CORS risk is low);
- item 11 (loans too);
- item 12 (instalments are already locked);
- item 13 (a broken link).

Items 15 and 8 moved up the order.

**Status.** Items 1, 2, 8 and 15 are fixed on branch `review-fixes-access-terms`.

## Contents

1. [Summary and order of work](#1-summary-and-order-of-work)
2. [Access control](#2-access-control) (items 1 to 3)
3. [Sign-in and sessions](#3-sign-in-and-sessions) (items 4 and 5)
4. [Cost and abuse](#4-cost-and-abuse) (items 6 to 8)
5. [Hardening](#5-hardening) (items 9 and 10)
6. [Deal pipeline: money and correctness](#6-deal-pipeline-money-and-correctness) (items 11 to 18)
7. [Deal pipeline: workflow](#7-deal-pipeline-workflow) (items 19 to 23)
8. [Smaller items](#8-smaller-items) (S1 to S4)
9. [Testing notes](#9-testing-notes)

---

## 1. Summary and order of work

| # | Finding | Area | Severity | Confidence | Size |
|---|---|---|---|---|---|
| 1 | Any signed-in user can overwrite player stats, form, snapshots, sync state and leagues | Access | High | Confirmed | S |
| 2 | Invitation-only club sign-up can be bypassed through `from-world-team` | Access | High | Confirmed | S |
| 3 | Agent registration has no email verification or throttle | Access | High | Confirmed | M |
| 4 | Password rules are inconsistent; password change keeps other sessions | Sign-in | Medium | Confirmed | S |
| 5 | WebSocket token in the URL; socket never re-checked | Sign-in | Medium | Confirmed | M |
| 6 | AI inputs are unbounded; no global spend cap | Cost | Medium | Confirmed | S |
| 7 | Uploads read fully into memory before the size check | Cost | Medium | Confirmed | S |
| 8 | Client IP handling wrong behind the proxy; limiter dicts never evict | Cost | Low | Likely | S |
| 9 | No database guard for one open deal per player | Hardening | Medium | Likely | S |
| 10 | No security headers; backend dependencies unpinned | Hardening | Medium | Confirmed | S |
| 11 | Instalment deals drop the buyer's hold at completion | Money | High | Confirmed | S |
| 12 | Marking instalments and clauses has no status or party guards | Money | High | Confirmed | S |
| 13 | Sell-on lookup picks the wrong prior deal | Money | Medium | Confirmed | S |
| 14 | Rival offers rejected without a lock; budget clamps hide drift | Money | Medium | Likely | S |
| 15 | Personal terms values are unvalidated | Money | High | Confirmed | S |
| 16 | Consent is not tied to the terms it answers | Money | Medium | Likely | M |
| 17 | Approvals can execute twice; no savepoint | Money | Medium | Likely | M |
| 18 | Collapsed deal leaves the agent commission PENDING | Money | Low | Confirmed | S |
| 19 | Either club can collapse alone at any stage, no reason needed | Workflow | Medium | Confirmed | M (needs a product decision) |
| 20 | Completion does not re-check ownership | Workflow | Medium | Likely | S |
| 21 | Offer expiry notifies no one | Workflow | Low | Confirmed | S |
| 22 | A seller retracting its counter withdraws the whole offer | Workflow | Low | Confirmed | M (needs a product decision) |
| 23 | Batch jobs run in one transaction | Workflow | Medium | Likely | S |

Size: S is under a day, M is one to three days.

**Suggested order**

1. **Items 1, 2, 3 and 15.** They are open to anyone who registers as an agent, or, for 15, to a buying club acting alone, and they are small. (Item 8 was done alongside, since it is small and touches the same limiters.)
2. **Items 11 and 12.** Wrong budget figures on paths a pilot club will use. Write the budget invariant test (section 9) first: it would catch 11, 12 and 14.
3. **Items 4, 5, 6, 7.** Before any outside user is onboarded.
4. **Items 9, 14, 16, 17.** Do these together with running the suite on Postgres (blocker 4 in the 15 November review), so the locks are actually tested.
5. **Items 13, 18, 20, 21, 23, 10** and the smaller items.
6. **Items 19 and 22** once the product decisions are made.

---

## 2. Access control

### 1. Any signed-in user can overwrite player data (High, Confirmed)

**Where**
- `app/stats/router.py`: `PUT /players/{id}/stats` (~85), `PUT /players/{id}/form` (~126), `POST /players/{id}/snapshots` (~158), `PUT /stats/sync-states/{vendor}` (~184)
- `app/world/router.py`: `POST /leagues` (~139)
- Related, found in the same pass: `app/vendor/router.py` `POST /sync/players/{id}` (~166) lets any signed-in user trigger an API-Football call, which spends the daily request quota.

**Problem.** These endpoints depend only on `get_current_user`. Any account, including a self-registered agent, can rewrite any player's stats and form, add snapshots, change the vendor sync state and upsert leagues. Stats and form appear to feed the valuation model, so this would also move fair-value figures.

**Fix**
- Change the dependency on all six endpoints to `get_current_superuser`.
- *Checked 21 November:* the `stats-worker` service runs `python -m app.jobs.daily_refresh` directly, not over HTTP, so it needs no change.

**Done when**
- A club, agent or player token gets 403 on each of the six endpoints.
- A staff token still succeeds.
- A test covers each endpoint for both cases.

### 2. Invitation-only club sign-up can be bypassed (High, Confirmed)

**Where.** `app/clubs/router.py:200`, `POST /clubs/from-world-team/{world_team_id}`.

**Problem.** `/auth/register` refuses club sign-up because "public club sign-up let anyone claim to be any club". This endpoint does the same thing by another route: any signed-in user without a club (an agent, a player) gets a club created with a real team's name, country, league and crest, with role `BOTH` and a finance record. It does not check `user_type`, and it does not check whether a club for that world team already exists.

**Fix**
- Make it superuser-only, or delete it if the club invitation flow has replaced it. Check the frontend for callers first.
- *Checked 21 November:* there is a caller. `frontend/src/pages/world/WorldTeamDetailPage.tsx` shows a "Register as my club" button to any signed-in user without a club. It goes in the same change.
- If kept for staff, refuse when a club already exists for that world team, and write an audit event.

**Done when**
- A non-staff token gets 403 (or the route returns 404 because it is gone).
- No frontend code calls the endpoint as a club or agent user.
- A test proves a self-registered agent cannot end up owning a club.

### 3. Agent registration has no email verification or throttle (High, Confirmed)

**Where.** `app/auth/router.py` `register`; `app/auth/schemas.py` `RegisterRequest`.

**Problem.** Agents can self-register with any email address and are signed in at once. There is no verification, no rate limit and no approval step. This is what makes items 1, 2 and 6 reachable by anyone, and it compounds the known issue that agent mandates need no player confirmation (TRA-144).

**Fix** (pick one; the first is the smallest)
- **Option A, invitation or approval.** Agents join by invitation, as clubs and players do, or register into a pending state that staff approve. Add an `ALLOW_AGENT_SELF_REGISTRATION` setting, off by default, to match the existing club and player settings.
- **Option B, verify and throttle.** Keep self-registration, but require a verified email before the account can do anything, and throttle `/auth/register` by address and by email domain.

Email is not configured on Railway yet (blocker 2 in the 15 November review), so Option A is the only one that works today.

**Done when**
- With the default settings, `POST /auth/register` with `user_type=AGENT` returns 403 with a message explaining how agents join.
- The test suite turns the setting on where its fixtures register agents directly.

---

## 3. Sign-in and sessions

### 4. Password rules are inconsistent (Medium, Confirmed)

**Where**
- `app/auth/schemas.py`: `RegisterRequest.password` and `ChangePasswordRequest.new_password` have no length rule.
- `app/clubs/schemas.py`: `InvitationAcceptRequest.password` has none; the club and player accept endpoints check `len < 8` by hand, the staff accept endpoint (`accept_invitation`) does not.
- `app/auth/router.py` `change_password`: other sessions stay signed in. `complete_password_reset` signs out everywhere.

**Problem.** A password can be set to one character, or changed to an empty string, on three of the six paths. Changing a password because a device was lost does not end that device's session.

**Fix**
- One shared type, used by every request model that sets a password: at least 8 characters, and at most 72 **bytes** once encoded as UTF-8.
  - *Checked 21 November:* `Field(max_length=72)` counts characters, so it would let through a 72-character password with accented or other non-ASCII characters.
  - The installed bcrypt is 5.0.0. It raises an error above 72 bytes instead of cutting the password short.
  - Check `len(v.encode())` in a validator.
  - Pin bcrypt (item 10).
- Remove the hand-written `len < 8` checks.
- On password change, delete the user's refresh tokens except the current session's.

**Done when**
- All six paths (register, change, reset, club invite, player invite, staff invite) refuse a 7-character password with 422.
- After a password change, a second session's next request gets 401; the session that made the change still works.

### 5. WebSocket token in the URL; socket never re-checked (Medium, Confirmed)

**Where.** `frontend/src/hooks/useWebSocket.ts`; `app/ws/router.py`; `entrypoint.sh` (uvicorn runs at `--log-level debug`).

**Problem**
- The access token is sent as `?token=<jwt>`. URLs are written to proxy and access logs, so tokens valid for 60 minutes can end up there.
- The session and token are checked once, at connect. A socket stays open after sign-out, after the token expires, and after the account is deactivated. `is_active` is not checked at all.

**Fix**
- Stop sending the access token in the URL. Either send it as the first message after connect and close the socket if it does not arrive within a few seconds, or issue a single-use ticket from an authenticated `POST /ws/ticket` (valid about 30 seconds) and pass that instead.
- Check `is_active` at connect.
- Close sockets when their session ends: have the manager track session id per socket and close on sign-out, sign-out-others, password reset and account deactivation. A periodic re-check (every few minutes) is an acceptable simpler version.

**Done when**
- No access token appears in any request URL.
- A socket opened by a session that is then signed out is closed within the agreed time.
- A deactivated user cannot connect.

---

## 4. Cost and abuse

### 6. AI inputs are unbounded (Medium, Confirmed)

**Where.** `app/ai/router.py`: `/ai/ask` (~468), `/ai/draft` (~511), `/ai/analyst` (~558) take `body: dict`. `app/ai/schemas.py` `NLSearchRequest.query` has no maximum. `app/ai/rate_limit.py` limits per user only.

**Problem**
- No cap on question length; only the logged copy is cut to 500 characters.
- `/ai/analyst` accepts a client-supplied `history` list of any size and content.
  - *Checked 21 November:* the model cost is already bounded. `ai/analyst/agent.py` sends only the last 4 turns, each question cut to 500 characters and each answer to 1,500. Only the request body is unbounded.
  - The sharper risk is at `agent.py:253`. Every client-supplied history answer, untrimmed, goes into `known`, the list that `keep_known_figures` checks the reply's figures against.
  - So a caller can forge an earlier "answer" containing a made-up figure, and that figure then passes the check meant to catch invented numbers.
- Limits are 20 or 40 calls an hour per user, with no overall cap. Together with item 3, spend is unbounded.
- Six endpoints across the app use `body: dict`, so they get no validation or API documentation.

**Fix**
- Replace `body: dict` with Pydantic models. Suggested limits: question 3 to 1,000 characters; `history` at most 10 turns, each field capped; `NLSearchRequest.query` at most 300 characters.
- Add a global daily ceiling (calls or estimated tokens) from settings. When reached, return 429 and post a Slack alert.
- Keep analyst history on the server, keyed by a conversation id, rather than trusting the client's copy. Build `known` only from answers the server stored. *Checked 21 November:* this is part of the fix, not a longer-term step, because of the forged-figures risk above.

**Done when**
- Oversized input gets 422 before any model call.
- The global ceiling is enforced and tested.
- No endpoint in `app/ai/router.py` takes `body: dict`.

### 7. Uploads are read fully into memory before the size check (Medium, Confirmed)

**Where.** `app/deals/room_router.py:210` (`content = await file.read()`, then `validate_attachment`).

**Problem.** The 10 MB limit is applied after the whole body is in memory. A participant in any deal can send a very large file and exhaust the single web process's memory. There is no request body limit anywhere in the app.

*Checked 21 November:* there is a second path. `app/agents/router.py:81`, the agent roster CSV preview, calls `file.read()` with no size limit at all. Agents can self-register (item 3), so anyone can reach it. Give it a small limit (for example 1 MB) in the same change.

**Fix**
- Reject early when the `Content-Length` header exceeds the limit (plus a small allowance for the multipart envelope).
- Read the file in chunks and stop with 413 as soon as the running total passes the limit.
- Do this in the same change as the move to object storage (blocker 1 in the 15 November review), since both touch `save_attachment_bytes`.

**Done when**
- An 11 MB upload is refused with 413 without being fully read.
- A 9 MB upload still succeeds.

### 8. Client IP handling behind the proxy; limiter dicts never evict (Low, Likely)

**Where.** `app/analytics/router.py` `_get_client_ip` (~24); `app/monitoring/router.py` `_client_hits` (~311, ~333); `app/ai/rate_limit.py` `_windows`.

**Problem**
- Analytics takes the first value of `X-Forwarded-For` as sent by the client, so the stored address can be forged.
- The client-error limiter keys on `request.client.host`. Behind Railway's proxy this is probably the proxy's address, so all anonymous callers would share one bucket of the per-minute allowance. Not verified against Railway.
- `_client_hits` and `_windows` never remove a key, so they grow for the life of the process.

**Fix**
- ~~Run uvicorn with `--proxy-headers` and `--forwarded-allow-ips` set to Railway's proxy.~~ *Checked 21 November:* Railway's proxy addresses aren't published or fixed. uvicorn 0.54 with `--forwarded-allow-ips="*"` takes the *leftmost* `X-Forwarded-For` entry, which is the one the client can forge.
- **Done instead:**
  - One helper, `app.common.client_ip.client_ip(request)`, takes the entry the trusted proxy appended: the `TRUSTED_PROXY_HOPS`-th from the right.
  - The setting defaults to 1 on Railway (detected by `RAILWAY_ENVIRONMENT`) and to 0 elsewhere, where the socket address is used.
  - Analytics and the client-error limiter both use the helper.
- Evict empty or stale keys on each call, or cap the dict size.
- These limiters move to Redis with the second instance, as the 15 November review already plans.

**Done when**
- The address recorded on Railway is the real client's (check one request by hand).
- A forged `X-Forwarded-For` does not change the recorded address.
- Both dicts shrink when keys go idle.

---

## 5. Hardening

### 9. No database guard for one open deal per player (Medium, Likely)

**Where.** `app/offers/service.py` `accept_offer` (~972); `app/deals/models.py`. Compare `migrations/versions/0070_one_open_sale_per_player.py`, which does this for sales.

**Problem.** `accept_offer` locks the offer being accepted, not the player. Nothing in the database stops two open deals for the same player. Two different offers for one player accepted at the same moment appear to end in a Postgres deadlock (one request fails with a 500) rather than two deals, but that depends on lock ordering. Other paths that create deals (direct signing, release clause, loan conversion) were not traced.

**Fix**
- Add a partial unique index on `deals(player_id)` where status is `IN_PROGRESS` or `PENDING_COMPLETION`. Check existing data for duplicates first.
- In `accept_offer`, lock the player row (`SELECT … FOR UPDATE`) before the ownership check, so the second request waits and is then refused with a clear message.
- Map a unique-index violation to a 409 with "This player already has a transfer in progress".

**Done when**
- A Postgres test runs two accepts for the same player concurrently: exactly one deal exists and the other caller gets a 409, not a 500.

### 10. No security headers; backend dependencies unpinned (Medium, Confirmed)

**Where.** `app/main.py` (no header middleware); `frontend/Dockerfile` (static files served by `serve` with defaults); `pyproject.toml` (every dependency is `>=` except litellm; no lockfile).

**Problem**
- Neither service sets `Content-Security-Policy`, `Strict-Transport-Security`, `X-Frame-Options` or `X-Content-Type-Options`. With refresh tokens in `localStorage`, any script injection takes the session, and a CSP is the main second line of defence.
- Each build can pull different dependency versions. The litellm breakage on 19 October came from this.
- The default `cors_origin_regex` allows any private-network origin on port 5173, in production too, unless it is set to an empty string. *Checked 21 November:* this is low risk, since the pattern matches only plain `http`, private addresses and port 5173. Worth fixing, but it does not raise the item's severity.
- *Checked 21 November:* `bcrypt>=4.0` is unpinned too, and 5.0 changed what happens with long passwords (item 4).

**Fix**
- Backend: a small middleware adding `X-Content-Type-Options: nosniff`, `Strict-Transport-Security`, and `Cache-Control: no-store` on authenticated JSON.
- Frontend: add a `serve.json` with a CSP (`default-src 'self'`, `connect-src` limited to the API and WebSocket hosts, `frame-ancestors 'none'`), plus `nosniff` and a referrer policy. Start with `Content-Security-Policy-Report-Only` for a week.
- Add a lockfile (`uv lock` or `pip-compile`) and install from it in the Dockerfile. Add a dependency audit to CI when CI exists.
- Default `cors_origin_regex` to `None` and set the private-network pattern only in local `.env` files.

**Done when**
- Both services return the headers (checked with `curl -I`).
- The backend image builds from the lockfile.
- A production-like configuration with no `CORS_ORIGIN_REGEX` set rejects a private-network origin.

---

## 6. Deal pipeline: money and correctness

Background for this section: a club's available transfer budget is `total − reserved − committed − spent` (`app/clubs/models.py`). An open offer reserves; acceptance moves reserved to committed; completion moves committed to spent.

### 11. Instalment deals drop the buyer's hold at completion (High, Confirmed)

**Where.** `app/deals/service.py` `_complete_deal` (~1170 to 1180).

**Problem.** At completion the fee is always subtracted from `transfer_committed`, but added to `transfer_spent` only when the deal has no instalment schedule. With a schedule, the whole fee leaves both columns, so the unpaid amount returns to the buyer's available budget and can be spent again. `mark_instalment_paid` later adds each payment to spent with no hold behind it.

**Fix**
- At completion, when a schedule exists, release from committed only what is not covered by unpaid instalments. Keep the sum of unpaid instalments in `transfer_committed`.
- In `mark_instalment_paid`, move the instalment amount from committed to spent (subtract from one, add to the other).
- If the schedule's total is less than the fee, treat the remainder as paid at completion (committed to spent). `validate_structure` may already force the two to match; check.
- Write a one-off repair script for completed deals with unpaid instalments, in the style of the existing `scripts/repair_*.py`.
- *Checked 21 November:* loan completion (`deals/service.py` ~1348 to 1352) has the same code (it subtracts from committed, then skips spent when there are instalments). It needs the same fix and test.

**Done when**
- Test: a £10m deal with a £4m and a £6m instalment. After completion the buyer has £10m committed and £0 spent. After the first payment, £6m committed and £4m spent. After the second, £0 and £10m. Available budget never rises above its level at acceptance.
- The seller is still credited per instalment, as now.

### 12. Marking instalments and clauses has no guards (High, Confirmed)

**Where.** `app/deals/service.py` `mark_instalment_paid` (~2055) and `update_clause_status` (~2005); `app/deals/router.py` (~1229).

**Problem**
- Neither function checks the deal's status. An instalment can be marked paid on a deal that is still in progress or has collapsed, which adds to the buyer's spent and to the seller's budget for a transfer that did not happen.
- If marked before completion, the amount is counted in both spent and committed. A later collapse releases the full fee from committed and leaves the payment in spent and in the seller's budget.
- One club alone can do it, including the buyer crediting itself as having paid or the seller declaring it has been paid.
- `update_clause_status` accepts any status from any status.

The 15 November review notes that these payments "aren't confirmed by both sides". The missing status checks are new.

**Fix**
- Require `deal.status == COMPLETED` in both functions.
- Instalments: the seller confirms receipt. Either only the seller (or staff) may mark paid, or the buyer marks "sent" and the seller confirms. This is a small product decision; the first is simpler.
- Clauses: define the allowed transitions (for example PENDING to TRIGGERED to PAID, PENDING to LAPSED) and refuse the rest.
- Lock the deal row in `update_clause_status`, as `advance_deal` does. *Checked 21 November:* `mark_instalment_paid` already locks the instalment row (`_lock(db, inst, "paid", "paid_at")`), so the same instalment cannot be paid twice. It needs only the status and party checks.

**Done when**
- Marking paid on an in-progress or collapsed deal returns 400.
- The buyer alone cannot mark an instalment paid (if seller-confirms is chosen).
- An invalid clause transition returns 400.

### 13. Sell-on lookup picks the wrong prior deal (Medium, Confirmed)

**Where.** `app/deals/service.py` `_complete_deal`, the TRA-57 block (~1213).

**Problem.** The query takes the most recent completed deal for the player that has any `sell_on_pct`. It does not require that deal's buyer to be the club now selling. After A sells to B with a sell-on, B sells to C without one, and C sells to D, club A is told it is owed a share of C's sale. A sell-on applies only to the next sale by the club that agreed it.

The result is also only a notification to the original seller's owner: nothing is recorded on the deal and no money is tracked. That part is covered by the review's existing "move no money" item.

**Fix**
- Add `Deal.buyer_club_id == deal.seller_club_id` to the query, and exclude loans.
- Record the obligation on the completing deal (a `DealClause` of a new type, or its own row) so both the current seller and the original seller can see it.
- Notify the original seller's club (`notify_club`), not only its owner.
- *Checked 21 November:* the notification links to `/deals/{deal.id}`, a deal the original seller is not a party to, so the link probably returns 403 for them. Point it at the recorded obligation instead.

**Done when**
- Test for the A, B, C, D chain: A is notified when B sells and not when C sells.

### 14. Rival offers rejected without a lock; budget clamps hide drift (Medium, Likely)

**Where.** `app/offers/service.py` `reject_offers_for_player` (~1143); `app/clubs/service.py` `release_budget` and `commit_budget`; the same `max(Decimal("0"), …)` pattern in `collapse_deal` and `_complete_deal`.

**Problem**
- When an offer is accepted, the other open offers for that player are loaded without a lock and their reservations released. If one of those buyers withdraws at the same moment, both transactions release the same reservation. The buyer's `transfer_reserved` falls by twice the amount, so its other open offers are under-reserved.
- Every release and commit clamps at zero. When the figures are wrong, the clamp hides it: nothing is logged and nothing fails.

**Fix**
- In `reject_offers_for_player`, select the siblings `FOR UPDATE` and re-check each one's status after the lock, as `expire_stale_offers` already does with `skip_locked`. Take the locks in a fixed order (by offer id).
- Replace the silent clamps with a helper that clamps, logs an error with the club id and the shortfall, and records an error event so it shows on the admin Errors page.
- Add a reconciliation check to the admin Health page: for each club, compare `transfer_reserved` and `transfer_committed` with the totals from `get_commitments`.

**Done when**
- A Postgres test runs accept and a rival's withdraw concurrently; the rival's reserved figure falls by the reservation once.
- A forced negative produces an error event.
- The Health page lists clubs whose totals disagree.

### 15. Personal terms values are unvalidated (High, Confirmed)

**Where.** `app/deals/schemas.py` `SetPersonalTermsRequest` (~184); `app/deals/service.py` `_apply_consented_terms` (~655).

**Problem.** Wage, signing bonus and contract length accept any value, including negatives. `_apply_consented_terms` applies a wage decrease straight to the buyer's `wage_committed_weekly`. A buying club can propose a large negative wage and, for a player with no account and no agent, record the consent itself with any uploaded document. That wipes the club's committed wage figure and frees budget. An absurd `length_years` reaches date arithmetic at completion.

**Fix**
- Schema: `wage_weekly > 0`, `signing_bonus >= 0`, `length_years` between 1 and 5 (FIFA's usual maximum; make it a setting if national rules differ).
- In `_apply_consented_terms`, never release more wage than this deal committed.
- Apply the same checks in the agent negotiation paths that carry terms.

**Done when**
- Negative or zero wage, negative bonus, and a length of 0 or 10 each return 422.
- A consented wage lower than the offer's reduces committed by the difference only.

### 16. Consent is not tied to the terms it answers (Medium, Likely)

**Where.** `app/deals/service.py` `set_personal_terms` (~1480), `club_respond_to_terms` (~1547), `player_consent_to_terms` (~1623); `app/deals/router.py` (~896).

**Problem**
- None of the three locks the deal or the terms row, and the consent request does not say which terms it is agreeing to. If one side sends new terms while the other sends "agree", the agreement can be saved against the new terms. Email decisions on offers already solve this with a version check (`lite/email_actions.py` `_version`); personal terms do not.
- `player_consent_to_terms` does not require the consent to be pending, so an answer already given can be changed. An "agree" can become a "decline", which collapses the deal.
- When the buying club records consent for an unrepresented player, the signed-terms upload is checked for who uploaded it and where, but not when. A document uploaded for earlier terms can be attached again after the terms change.

**Fix**
- Add a version to the terms (a counter, or the id of the latest `TermProposal` round). The consent and club-response requests carry it; a mismatch returns 409 with the current terms.
- Lock the deal row at the start of all three functions.
- Require the consent to be pending, except where a product decision says an answer may be changed.
- Require the evidence attachment to have been uploaded after the latest terms round.

**Done when**
- Consent carrying an old version returns 409.
- An attachment older than the latest round is refused.
- A second answer on already-agreed terms returns 400.

### 17. Approvals can execute twice; no savepoint (Medium, Likely)

**Where.** `app/approvals/service.py` `approve_and_execute` (~209) and `_execute` (~252); `app/offers/service.py` `create_offer`.

**Problem**
- `_require_pending` reads the approval without a lock. Two approvers acting at the same moment both pass the check and both execute.
- For a captured "create offer", the "already has an active offer" check is a plain read, and no database constraint enforces it, so both executions can create an offer and reserve budget twice. The same applies to two direct create-offer requests sent together (a double click).
- When `_execute` fails with a domain error, the approval is saved as `APPROVED_FAILED` in the same transaction. Anything the failed execution had already written is saved with it. No concrete leak path was found; the risk is structural.

**Fix**
- Load the approval `FOR UPDATE` in approve, reject and cancel, then re-check that it is pending.
- Add a partial unique index on `offers(player_id, from_club_id)` where status is `SENT` or `COUNTERED`. Check existing data first. Map a violation to a 409.
- Run `_execute` inside `db.begin_nested()` so a failure rolls back its writes before the failed status is saved.

**Done when**
- A Postgres test runs two approvals of the same request concurrently: one offer exists, and the second approver is told it was already decided.
- A test forces a failure halfway through `_execute` and finds no partial writes.

### 18. Collapsed deal leaves the agent commission PENDING (Low, Confirmed)

**Where.** `app/deals/service.py` `collapse_deal` (~908); `app/agents/models.py` `CommissionStatus` (~121); `app/agents/service.py` (~457, the agent's totals).

**Problem.** A commission record is created as `PENDING` when the deal leaves agent negotiation. Collapse does not touch it and there is no cancelled status, so it stays in the agent's pending total for good.

**Fix**
- Add `CommissionStatus.CANCELLED` (with a migration for the enum).
- In `collapse_deal`, set a pending commission for the deal to cancelled.
- Leave cancelled records out of the agent's totals.
- A data migration cancels pending commissions on deals that have already collapsed.

**Done when**
- After a collapse, the commission is cancelled and the agent's pending total falls by its amount.

---

## 7. Deal pipeline: workflow

### 19. Either club can collapse alone at any stage (Medium, Confirmed; needs a product decision)

**Where.** `app/deals/service.py` `collapse_deal` (~908).

**Problem.** Any party can collapse a deal on its own at any stage, including after every paperwork step is done and the deal is confirmed and waiting only for a window. The reason is optional. A confirmed deal "holds the player", and the other side may already have acted on that.

**Decision needed.** What should a club be able to do after confirmation?
- **Option A (recommended):** before confirmation, either club may end the transfer, with a reason required. After confirmation, ending it needs the other club's agreement or TransferX staff.
- **Option B:** keep the unilateral collapse at every stage, but require a reason and give the other club a short notice period.

**Fix (for Option A)**
- `reason` becomes required for club-initiated collapses.
- At `CONFIRMED` or `PENDING_COMPLETION`, a club's request creates a "proposed collapse" that the other club accepts or declines; staff can still collapse directly.
- Record the decision as a product decision document.

**Done when**
- A collapse without a reason returns 422.
- At the confirmed stage, one club alone cannot collapse.

### 20. Completion does not re-check ownership (Medium, Likely)

**Where.** `app/deals/service.py` `advance_deal`, the `CONFIRMED` branch (~790), and `_complete_deal`.

**Problem.** The check that the selling club owns the player runs when the offer is accepted (TRA-138) and not again at completion, which can be weeks later. If the seller no longer holds an active contract with him (released, a staff correction, a real-world move applied), completion still creates the buyer's contract and moves the money. The real-world hold covers only moves that API-Football reports. In the service layer either club can trigger completion; whether the router narrows this was not traced.

**Fix**
- In the `CONFIRMED` branch, lock the player row and require an active contract between the player and `deal.seller_club_id` (skip for free-agent signings, where there is no seller). On failure, refuse with a message that sends the clubs to TransferX staff.
- Decide who completes: the buying club registers the player, so the simplest rule is buyer or staff.

**Done when**
- Test: the seller's contract is deactivated after confirmation; completion returns 400 and no money moves.

### 21. Offer expiry notifies no one (Low, Confirmed)

**Where.** `app/offers/service.py` `expire_stale_offers` (~1505).

**Problem.** The job sets the offer to expired and releases the reservation. Neither club is told. There is a warning before expiry (`OFFER_EXPIRING`), but nothing when it happens, so the offer simply leaves "waiting on you".

**Fix**
- Notify both clubs when an offer expires. The buyer's message should say its budget has been released. Add an `OFFER_EXPIRED` notification type and place it in the notification tiers.
- Do not email or push for offers that were already past the point of interest (for example, the player has since signed elsewhere; those are rejected by another path already).

**Done when**
- After the job runs, both clubs have a notification linking to the offer.

### 22. A seller retracting its counter withdraws the whole offer (Low, Confirmed; needs a product decision)

**Where.** `app/offers/service.py` `withdraw_offer` (~1272).

**Problem.** The last club to act may retract its move. When that is the seller retracting a counter, the entire offer becomes `WITHDRAWN`, including the buyer's original proposal, and the buyer's reservation is released. The buyer has to start again, and the history reads as though the offer was withdrawn rather than the counter.

**Decision needed.** Should retracting a counter end the negotiation, or put the buyer's last terms back on the table?

**Fix (if restoring)**
- Counter events already store the terms they replaced (`SNAPSHOT_TERMS`). On a seller's retraction, restore those terms, hand the turn back to the seller, and record a `COUNTER_RETRACTED` event.
- Re-square the buyer's reservation to the restored terms.
- If the decision is to keep ending the negotiation, change the wording shown to the seller so the effect is clear before confirming.

**Done when**
- The chosen behaviour is written down as a product decision and covered by a test.

### 23. Batch jobs run in one transaction (Medium, Likely)

**Where.** `app/main.py` job wrappers; `app/loans/service.py` `process_due_loans`; `app/offers/service.py` `expire_stale_offers`; `app/deals/service.py` `check_deal_sla_breaches`; others with the same shape.

**Problem.** Each job processes every due row inside one transaction. If one row raises (for example, a loan conversion that the buying club cannot fund), the whole batch rolls back, and it does so again on every run. The other rows are never processed. The only trace is a log line, and Slack alerts are not configured.

**Fix**
- Process each row in its own savepoint (`async with db.begin_nested()`), catch and log the failure with the row's id, and carry on.
- Record failures as error events so they appear on the admin Errors page, and include a failed count in the job's run summary.
- Start with `process_due_loans`, where a stuck row has the most visible effect (a loan that never ends).

**Done when**
- Test: three due loans, the second raises. The first and third are processed and the failure is recorded.

---

## 8. Smaller items

| # | Item | Where | Fix |
|---|---|---|---|
| S1 | The public batch stats and form endpoints take no login and skip the player-visibility check that the player page applies | `app/stats/router.py` (~37, ~53) | Add `get_optional_user` and apply the same visibility rule as `players/router.py`; cap the number of ids per call |
| S2 | A GET without a login writes to the database (creates a world team from fixture data) | `app/world/router.py` (~46) | Require a login, or move the bootstrap into the data refresh |
| S3 | Several 502 responses return the raw exception text to the client | `app/vendor/router.py` (~201), `app/ai/router.py` (~223) | Return a fixed message; log the exception |
| S4 | `entrypoint.sh` prints "IMPORT FAILED" and carries on to start uvicorn | `entrypoint.sh` | Exit non-zero so the deploy fails at that step |

---

## 9. Testing notes

- **Run the lock tests on Postgres.** Items 9, 14, 16 and 17 need two real transactions. SQLite ignores `FOR UPDATE`, so these tests must be marked Postgres-only and run in CI against a Postgres service container (blocker 4 in the 15 November review). A small helper that runs two coroutines on separate sessions and waits at a chosen point would cover all four.
- **Add a permissions sweep test.** One test that walks the route list and asserts every write endpoint outside an allow-list depends on a capability, an ownership check or `get_current_superuser`. Items 1 and 2 were found by exactly this kind of sweep, and a test would stop the next one.
- **Add a budget invariant test.** After each money-path test, assert for every club that reserved and committed equal the totals from `get_commitments`. Items 11, 12 and 14 would each have failed it.

## Related documents

- [`2026-11-15-product-and-readiness-review.md`](2026-11-15-product-and-readiness-review.md): the earlier review; nothing here repeats it
- [`../architecture/authentication-and-permissions.md`](../architecture/authentication-and-permissions.md)
- [`../product/workflows/deal-completion.md`](../product/workflows/deal-completion.md)
- [`../product/workflows/negotiation-and-offers.md`](../product/workflows/negotiation-and-offers.md)
