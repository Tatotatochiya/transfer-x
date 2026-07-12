---
title: "Permissions Model — Risk Posture"
last_updated: 2026-07-12
status: Active
owner: "TODO — assign a Security Owner"
---

# Permissions Model — Risk Posture

## Purpose

Describes what is and isn't protected in TransferX today from a confidentiality/access standpoint — the risk-facing view. For how authentication and authorization are technically implemented, see [`../architecture/authentication-and-permissions.md`](../architecture/authentication-and-permissions.md); this document doesn't repeat that mechanism, only assesses it.

## Scope

In scope: confidentiality boundaries between parties (e.g. clubs, agents, players), and known gaps.
Out of scope: implementation mechanism (see [`../architecture/authentication-and-permissions.md`](../architecture/authentication-and-permissions.md)).

## Table of Contents

- [Confidentiality boundaries](#confidentiality-boundaries)
- [Known gaps](#known-gaps)
- [Related documents](#related-documents)

## Confidentiality boundaries

**Verified 2026-07-12** against the code (see [`CHANGELOG.md`](../CHANGELOG.md) for the fixes that closed the gaps this table used to list as open). Rows below carry their own verification date where they were touched more recently than 2026-07-04.

| Entity / field | Who can see it | Enforced in |
|---|---|---|
| Sale `reserve_price`, `best_bid`, `bid_count`, `minimum_next_bid` | Seller club, staff — all four fields, since `minimum_next_bid` equals `best_bid + increment` and so leaks the same information by arithmetic if shown to anyone else. | `GET /sales`, `GET /sales/{id}` |
| Deal medical check | **Buying club and staff only** (2026-07-12 — was buyer/seller/agent/player/staff). Special-category personal data (GDPR); the selling club can no longer read status, notes, or even whether a record exists — a real negotiation-leverage and privacy problem the previous, broader visibility created. | `GET /deals/{id}/medical-check`, and nulled out in `GET /deals/{id}`'s `medical_check` field for the selling club |
| Deal personal terms | Buyer club, seller club, mandated agent, the player, staff | `GET /deals/{id}/personal-terms` |
| Deal detail (stage, terms, notes, clauses, etc.) | Same participants as above | `GET /deals/{id}` |
| Deal commission terms (`agent_commission_pct`/`amount`, `commission_payer`, `commission_agent_id`) | Buyer club, seller club, mandated agent, staff — **not** the player, mirroring the same split already used for `AgentNegotiation` | `GET /deals/{id}` (field-scoped response) |
| Deal audit log (+ CSV export) | Same participants as the deal itself, with actor UUIDs resolved to display labels in both the JSON response and the CSV | `GET /deals/{id}/audit-log`, `GET /deals/{id}/audit-log/export.csv` |
| Player registration/ownership | A club can only list a player for sale, or accept a transfer naming them as seller, if that player is actually registered to them (active contract, or — before a contract exists — whichever club created the player record) | `POST /sales`, `POST /offers/{id}/accept` |
| Setting personal terms (`PUT /deals/{id}/personal-terms`) | The mandated agent for that specific deal (verified against `AgentNegotiation.agent_id`, not just "any agent"), or the buying club when there's no mandate, or staff | `backend/app/deals/router.py::set_personal_terms` |
| Consenting to personal terms / commission's player-side counterpart | The player themselves if they have a `PlayerProfile`; the mandated agent may act as proxy only if the player has none | `POST /deals/{id}/personal-terms/player-consent` |
| Advancing a deal's stage (`POST /deals/{id}/advance`) | The relevant party for that specific transition: club/staff generally, the mandated agent specifically for `AGENT_NEGOTIATION → PERSONAL_TERMS`, staff only for `PAPERWORK → CONFIRMED` — staff bypasses the club-profile check entirely, since a pure admin account has none | `backend/app/deals/router.py::advance_deal` |
| Staff deal access (deal detail, deal room, audit log + CSV, medical check, personal terms) | Staff of the buyer/seller club see exactly the club-side view their owner sees (commission fields included — they're club business). Staff of an *unrelated* club get 403 like any stranger. Every club-side **write** additionally requires the `DEAL_WRITE` capability — READONLY/SCOUT staff see everything, change nothing | `room_service.is_deal_participant` (owner-or-staff) + `app/clubs/capabilities.py` |
| Club write actions by role (market, deals, scouting, club admin) | Enforced by a single capability matrix — see the table in [`../architecture/authentication-and-permissions.md`](../architecture/authentication-and-permissions.md#club-roles). Every previously-ungated club write (offer negotiation messages, squad player edits, player/contract creation) now carries a capability gate | `require_club_capability` / `ensure_club_capability` at every club write route |
| Staff invitations | The raw invitation token is never stored (sha256 hash only), returned exactly once at creation, single-use, dead after expiry/revocation/acceptance — preview and accept return an identical 404 for every invalid state, so there is no oracle on *why* a token failed. Inviting an email that already has an account is refused (409); account-linking is deliberately out of scope | `clubs_service.create_staff_invitation` / `get_live_invitation_by_token` |
| Spending approvals | A pending approval stores the validated payload only — nothing is reserved or executed at capture. Deciding requires `APPROVE_ACTIONS` (owner/sporting director); the requester can only cancel their own. Execution re-validates budget/window/auction state from scratch, so an approver can never resurrect an action against stale state | `app/approvals/service.py` |
| Notification routing by role | Club-directed deal/offer/bid events reach OWNER + SPORTING_DIRECTOR + MANAGER; scouting/market events additionally reach SCOUT; account/administrative events (verification, staff joins) reach the owner only. READONLY staff receive none — they observe, they're not worked | `notifications/service.py::club_recipient_user_ids` |
| Writing a deal's medical check (`PUT /deals/{id}/medical-check`) | The **buying club** (their medical team conducted it) or staff. Not the selling club, not the mandated agent, not the player. | `deals_service.upsert_medical_check` |
| Deal fee disclosure (`fee_disclosed`) | Either deal party can set it (via `PATCH /deals/{id}`), controlling whether `agreed_fee` is nulled on the public `/transfers` feed and analytics top-deals for that deal. **Known gap:** currently a unilateral toggle — one club can flip disclosure a counterparty wanted kept private, with no agreement step. | `deals_service.update_deal`, `deals_router._to_transfer_item` |
| Transfer-window enforcement | Association-scoped (`TransferWindow.association`: null = global/matches all, set = that association plus global windows). Checked at sale creation, offer creation, direct signing, approval execution, bid placement, bid acceptance, offer acceptance, and deal completion (with a per-window `grace_period_hours` deadline-day grace for deals already `CONFIRMED` before the window closed). No applicable windows configured → controlled by `TRANSFERX_WINDOWS_FAIL_CLOSED` (default `false`/open, recommended `true` in production). | `transfer_window/service.py::is_transfer_allowed`, `::can_complete_deal` |
| Staff overrides / admin destructive actions (**2026-07-12**) | Force-completing a deal, force-collapsing a deal, force-withdrawing an offer, cancelling a sale, deleting a transfer window, and removing a staff account all now require a non-blank reason, rejected with 400 if missing. Force-complete requires one unconditionally (it was the one staff override with no reason field at all); force-collapse of a `CONFIRMED`+ deal now requires one for staff too — previously only non-staff actors were held to that bar, so the actor with the most bypass power was silently exempt from the audit trail. Reasons land in the deal audit log (complete/collapse), the offer's event payload (force-withdraw), the sale's event `notes` (cancel), or the generic `AuditEvent` table (window delete, staff removal) | `deals_service.staff_complete`/`collapse_deal`, `admin_service.admin_force_withdraw_offer`/`admin_cancel_sale`/`delete_staff`, `transfer_window_service.delete_window` |

## Known gaps

- **Player identity claims aren't attested** — a player self-registers a claim to a `Player` record with no verification step (Linear TRA-143).
- **Agent mandates don't require player confirmation** — a mandate can take effect without the player confirming it (Linear TRA-144). As of the 2026-07-11 audit remediation this has a *wider* blast radius than before: since the auction path now also invites the mandated agent (previously only the offer path did), every deal for a mandated player routes through whatever mandate exists, confirmed or not.
- **Unilateral financial actions** — a selling club can mark its own instalments paid (crediting itself); either party can unilaterally mark a clause `TRIGGERED`/`PAID`, edit deal structure at `AGREEMENT`, or toggle `fee_disclosed`; none of these require the counterparty's agreement, only a record in the version history. See [`audits/2026-07-12-transfer-workflow-audit.md`](../audits/2026-07-12-transfer-workflow-audit.md) M1.
- **The sealed order book can be probed via the bid-validation error.** `minimum_next_bid` is hidden from non-sellers (see the resolved-gaps entry below), but `place_bid`'s rejection message for an under-minimum bid states the exact threshold — a rival can deliberately underbid to read it back. See the same audit's M6.
- **The sell-on `RESALE` clause record is attached to the wrong deal** — it's on the new deal (current seller → new buyer), but the beneficiary is the *original* seller, who isn't a party to that deal and can't read it. See the same audit's M5.
- **Paperwork has no club-legal seat** — `PAPERWORK → CONFIRMED` is TransferX-staff-only with no document checklist or club-side sign-off step. See the same audit's M3.

## Resolved gaps

- **2026-07-12 — Six admin/staff destructive actions had no reason capture or audit trail, and `admin_cancel_sale` crashed outright.** From the [admin platform audit](../audits/2026-07-12-admin-platform-audit.md): force-complete, force-collapse, force-withdraw-offer, cancel-sale, delete-window, and remove-staff are now all reason-required server-side, not just UI-suggested. As a necessary side effect (the crash blocked reason capture from ever taking effect), `admin_cancel_sale` — which assigned a `SaleStatus.CANCELLED` member that doesn't exist, a 500 on every call — now delegates to the same `withdraw_sale` path clubs use, which actually releases bidders' reserved budgets, rejects linked offers, and notifies everyone affected.
- **2026-07-12 — Deal medical check was visible to the selling club, the mandated agent, and the player, not just the buyer and staff.** Special-category personal data (GDPR) and a negotiation-leverage problem — the seller could read the buyer's findings about a player they no longer control. Now buyer-club-and-staff only for both reading and writing; the writer also moved from staff-only to the buying club (their medical team, not TransferX's). Part of the wider medical-model fix — see [`audits/2026-07-11-transfer-workflow-audit.md`](../audits/2026-07-11-transfer-workflow-audit.md) M7 and [`../CHANGELOG.md`](../CHANGELOG.md).
- **2026-07-12 — `minimum_next_bid` leaked the seller-only `best_bid` by arithmetic** (`best_bid + min_increment`), making the reserve-price/best-bid confidentiality fix below cosmetic for auctions. Now hidden from non-sellers, same as `best_bid` itself.
- **2026-07-11/12 — Two accepted deals for the same player were possible** three different ways, all closed: the auction path never invited the agent or rejected rival offers (M1); accepting an offer never touched a separately-open auction sale for the same player, so a bid on it could still be accepted afterward (re-audit); and a loan's purchase option could be exercised more than once (re-audit). See [`audits/2026-07-12-transfer-workflow-audit.md`](../audits/2026-07-12-transfer-workflow-audit.md).
- **2026-07-10 — Deal access was per club-owner-account only** (TRA-146): staff of a participant club couldn't open their own club's deals at all. Fixed together with capability enforcement (TRA-151) in that order deliberately — widening visibility *before* role-gating writes would have silently granted read-only staff full deal-write access. A regression test pins the invariant: READONLY staff with deal visibility gets 403 on every deal-write endpoint.
- **2026-07-05 — No UI existed to set a deal's medical check.** The backend endpoint (staff-only at the time) was always fully functional, but nothing called it, so a `FAILED` medical could previously only be recorded via direct API access. `DealDetailPage` now shows a Medical Check panel; the write permission itself changed on 2026-07-12 (see above).
- **2026-07-04 — `AuditEvent.actor_user_id` used to be effectively always null** — no write path populated it. Every audit-emitting action now threads the caller's user id through; the JSON `GET /deals/{id}/audit-log` endpoint also gained the actor-label resolution the CSV export already had.

## Related documents

- [`../architecture/authentication-and-permissions.md`](../architecture/authentication-and-permissions.md) — the technical mechanism
- [`data-privacy-and-legal.md`](./data-privacy-and-legal.md) — the legal dimension of data exposure
- [`../product/personas.md`](../product/personas.md) — the parties whose confidentiality this document protects
