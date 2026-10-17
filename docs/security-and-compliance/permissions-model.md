---
title: "Permissions Model — Risk Posture"
last_updated: 2026-10-17
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

**Verified 2026-07-04, rows updated 2026-10-11** against the code (see [`CHANGELOG.md`](../CHANGELOG.md) for the fixes that closed the gaps this table used to list as open).

| Entity / field | Who can see it | Enforced in |
|---|---|---|
| Sale `reserve_price`, `best_bid`, `bid_count` | Seller club, staff. `minimum_next_bid` stays visible to everyone — a bidder needs it to place a valid bid at all. | `GET /sales`, `GET /sales/{id}` |
| Deal medical check | Buyer club, seller club, mandated agent, the player, staff | `GET /deals/{id}/medical-check` |
| Deal personal terms | Same participants as above | `GET /deals/{id}/personal-terms` |
| Deal detail (stage, terms, notes, clauses, etc.) | Same participants as above | `GET /deals/{id}` |
| Deal commission terms (`agent_commission_pct`/`amount`, `commission_payer`, `commission_agent_id`) | Buyer club, seller club, mandated agent, staff — **not** the player, mirroring the same split already used for `AgentNegotiation` | `GET /deals/{id}` (field-scoped response) |
| Deal audit log (+ CSV export) | Same participants as the deal itself, with actor UUIDs resolved to display labels in both the JSON response and the CSV | `GET /deals/{id}/audit-log`, `GET /deals/{id}/audit-log/export.csv` |
| Player registration/ownership | A club can only list a player for sale, or accept a transfer naming them as seller, if that player is actually registered to them (active contract, or — before a contract exists — whichever club created the player record) | `POST /sales`, `POST /offers/{id}/accept` |
| Setting personal terms (`PUT /deals/{id}/personal-terms`) | The mandated agent for that specific deal (verified against `AgentNegotiation.agent_id`, not just "any agent"), or the buying club when there's no mandate, or staff | `backend/app/deals/router.py::set_personal_terms` |
| Consenting to personal terms | The player if he has an account; his mandated agent whether or not he has one; with neither, the buying club, attaching the signed terms (product ADRs 0002, 0006, 0007) | `POST /deals/{id}/personal-terms/player-consent` and the club-records-consent path |
| Advancing a deal's stage, and paperwork | The relevant party for each transition; the mandated agent for `AGENT_NEGOTIATION → PERSONAL_TERMS`. `PAPERWORK` is a club checklist: both clubs sign, and the buyer records a passed medical and submits registration. The last step confirms the deal. Staff can override | `deals/router.py::advance_deal`, the paperwork endpoints |
| Staff deal access (deal detail, deal room, audit log + CSV, medical check, personal terms) | Staff of the buyer/seller club see exactly the club-side view their owner sees (commission fields included — they're club business). Staff of an *unrelated* club get 403 like any stranger. Every club-side **write** additionally requires the `DEAL_WRITE` capability — READONLY/SCOUT staff see everything, change nothing | `room_service.is_deal_participant` (owner-or-staff) + `app/clubs/capabilities.py` |
| Club write actions by role (market, deals, scouting, club admin) | Enforced by a single capability matrix — see the table in [`../architecture/authentication-and-permissions.md`](../architecture/authentication-and-permissions.md#club-roles). Every previously-ungated club write (offer negotiation messages, squad player edits, player/contract creation) now carries a capability gate | `require_club_capability` / `ensure_club_capability` at every club write route |
| Staff invitations | The raw invitation token is never stored (sha256 hash only), returned exactly once at creation, single-use, dead after expiry/revocation/acceptance — preview and accept return an identical 404 for every invalid state, so there is no oracle on *why* a token failed. Inviting an email that already has an account is refused (409); account-linking is deliberately out of scope | `clubs_service.create_staff_invitation` / `get_live_invitation_by_token` |
| Spending approvals | A pending approval stores the validated payload only — nothing is reserved or executed at capture. Deciding requires `APPROVE_ACTIONS` (owner/sporting director); the requester can only cancel their own. Execution re-validates budget/window/auction state from scratch, so an approver can never resurrect an action against stale state | `app/approvals/service.py` |
| Notification routing by role | Club-directed deal/offer/bid events reach OWNER + SPORTING_DIRECTOR + MANAGER; scouting/market events additionally reach SCOUT; account/administrative events (verification, staff joins) reach the owner only. READONLY staff receive none — they observe, they're not worked | `notifications/service.py::club_recipient_user_ids` |
| Anonymous buyer | A buyer who approaches anonymously is shown to the seller as "A {league} club"; ids and names are masked server-side in every offer, enquiry, order book, board card and AI fact. Revealed only on acceptance ([ADR 0004](../architecture/decisions/0004-anonymous-buyer-masked-server-side.md)) | `offers/service._offer_response`, `common/masking.py` |
| A club's contract terms (wage, signing date, notes, its own valuation) | The club itself. Rival clubs see only what's public: end date and release clause | Player and contract responses; `tests/test_contract_confidentiality.py`. The email decision page (`/lite/confirm/{token}`) shows the valuation only to the email's recipient, signed in (`tests/test_lite_email_decisions.py`) |
| Interest in a club's own players | Counts only (enquiries, offers, bids, shortlists, profile views), never which clubs | `ai/analyst/tools.py::interest_in_my_players` |
| The AI assistant and Ask TransferX | Facts are built server-side from what the asking club may see; the model never queries data itself; figures are computed by TransferX ([ADR 0006](../architecture/decisions/0006-ai-assistant-advises-from-scoped-facts.md)) | `app/ai/` |
| Monitoring data (job logs, error events with tracebacks and request context) | TransferX staff only; limited retention; Slack gets titles and counts only | `app/monitoring/router.py` (`get_current_superuser`) |
| "View as this club" | Staff, read-only, 30 minutes, reason required and audited | `admin` view-as; `get_current_user` refuses writes |

## Known gaps

Verified 2026-10-11.
- **Agent mandates don't require player confirmation.** A mandate is `ACTIVE` as soon as it's created; there is no pending state (Linear TRA-144).
- **Verification gates nothing.** A verified club, agent or player gets a badge, but no action requires being verified.
- **Two-factor sign-in isn't built,** including for people who can approve or complete deals.

## Resolved gaps

- **2026-09-28 — Player identity claims weren't attested** (TRA-143). Anyone could register as a player by picking a record. Players now join only by their club's invitation, and self-registration is refused (product ADR 0007).
- **2026-09-27 — Medical and paperwork were staff-only.** Clubs now run the paperwork checklist, and the buyer records the medical.
- **2026-07-10 — Deal access was per club-owner-account only** (TRA-146): staff of a participant club couldn't open their own club's deals at all. Fixed together with capability enforcement (TRA-151) in that order deliberately — widening visibility *before* role-gating writes would have silently granted read-only staff full deal-write access. A regression test pins the invariant: READONLY staff with deal visibility gets 403 on every deal-write endpoint.
- **2026-07-05 — No UI existed to set a deal's medical check.** The backend endpoint (staff-only) was always fully functional, but nothing called it, so a `FAILED` medical (the only thing that blocks `PAPERWORK → CONFIRMED`) could previously only be recorded via direct API access. `DealDetailPage` now shows a Medical Check panel — read-only status/notes for every deal participant, with a staff-only edit control.
- **2026-07-04 — `AuditEvent.actor_user_id` used to be effectively always null** — no write path populated it. Every audit-emitting action now threads the caller's user id through; the JSON `GET /deals/{id}/audit-log` endpoint also gained the actor-label resolution the CSV export already had.

## Related documents

- [`../architecture/authentication-and-permissions.md`](../architecture/authentication-and-permissions.md) — the technical mechanism
- [`data-privacy-and-legal.md`](./data-privacy-and-legal.md) — the legal dimension of data exposure
- [`../product/personas.md`](../product/personas.md) — the parties whose confidentiality this document protects
