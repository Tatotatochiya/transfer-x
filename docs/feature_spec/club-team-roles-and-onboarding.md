---
title: "Feature Spec: Club Team Accounts, Roles & Onboarding"
last_updated: 2026-07-10
status: Implemented
owner: "TODO — assign a Product Owner"
---

# Feature Spec: Club Team Accounts, Roles & Onboarding

## Purpose

Implementation specification for making a club a **team, not a login**: a real role model with enforced capabilities (including read-only), staff access to the club's deals, notifications that reach the people doing the work, owner-run team management with invitation-based onboarding, spending-authority approval thresholds, and a per-persona first-run experience.

This consolidates four existing Linear tickets that are really one feature — **TRA-151** (club roles & permissions), **TRA-146** (club-staff deal access), **TRA-152** (notification routing), **TRA-86** (team management UI) — plus two pieces proposed and accepted 2026-07-05 with no ticket yet (approval thresholds; per-persona first-run). See [Linear reconciliation](#linear-reconciliation-suggested-not-executed).

Written for an implementer (human or AI agent) with **no access to the conversation that produced it**. Phases are independently shippable, but **Phase 1 must land before Phase 2** — see D4; this ordering constraint is the single most important sentence in this document.

## How to use this document

1. Read [Decisions already made](#decisions-already-made) and [Verified current state](#verified-current-state-2026-07-05) — several findings here are load-bearing and non-obvious from the models alone.
2. Implement phase by phase, in order, each against its own success criteria. Stop at any phase boundary and the product is still consistent.
3. On completion of any phase, do that phase's documentation updates; when the last implemented phase ships, set this spec `status: Implemented` with a deviations note.

Read first: repo `CLAUDE.md`, [`engineering-standards`](../../.claude/skills/engineering-standards/SKILL.md), [`product-principles`](../../.claude/skills/product-principles/SKILL.md), [gotchas appendix](#appendix-implementation-gotchas-house-specific).

## Product context and value

| Stakeholder | Value |
|---|---|
| CEO / Ownership | Oversight without sharing one login ([`product-principles`](../../.claude/skills/product-principles/SKILL.md) names this expectation verbatim); approval thresholds put a deliberate confirmation in front of high-value actions instead of one-click millions. |
| Sporting Director | Deal authority with a role that matches their real mandate; an approvals queue instead of being the shared password. |
| Scouts / Analysts | Their own accounts, scoped to what scouts do — shortlists and market views, not bids. |
| Club (as customer) | The difference between "a login someone shares" and software an organisation can adopt — this is table-stakes for enterprise procurement. |
| Agent / Player | A first-run path from empty portal to productive account (profile → verification → first client / visibility choices). |

## Verified current state (2026-07-05)

Everything below was checked against code this session — several points differ from what the docs or ticket texts imply.

| Fact | Location | Implication |
|---|---|---|
| `ClubStaff` exists: `club_id`, `user_id` (**unique** — one club per user), `role`, `created_by_user_id` | `app/clubs/models.py` | Foundation is real; multi-club membership is structurally excluded (kept — see out of scope). |
| `StaffRole` = `MANAGER`, `READONLY` (default READONLY) | `app/clubs/models.py:20` | Postgres enum — extending it needs `ALTER TYPE … ADD VALUE` (gotcha #1). |
| Read-only enforcement (`require_club_write_access`) is applied to **exactly 9 endpoints in 2 routers**: sales (4 sites: `sales/router.py:164,225,264,379`) and offers (5 sites: `offers/router.py:210,277,319,350,381`) | `app/deps.py:77` | Deals, deal room, club profile, finance, squad edits, scouting have **no** read-only check. |
| Staff cannot reach deals at all: `is_deal_participant`'s CLUB branch resolves via `get_club_by_user_id` (**owner-only**) | `app/deals/room_service.py:48-54` | TRA-146's bug, precisely located. The owner-or-staff resolver `get_club_for_user` already exists (`clubs/service.py:97`). Today this *accidentally* masks the read-only gap on deals — hence D4. |
| `get_club_and_role_for_user` already returns `('OWNER' \| 'MANAGER' \| 'READONLY')` | `clubs/service.py:108` | The capability layer builds on this, not from scratch. |
| Staff users are created with **default `user_type = CLUB`** (the `User(...)` call passes no `user_type`; column default is CLUB). `UserType.STAFF` exists (`auth/models.py:16`) but **nothing assigns it** | `admin/service.py:383` | Deliberate handling required — see D9. Do not "fix" this by assigning STAFF; it would silently break every `user_type == CLUB` branch (including `is_deal_participant`). |
| Staff creation is **platform-admin only**, with the admin setting the password | `admin/router.py:515-581` | No owner-facing management, no invitation flow, admin knows staff passwords — all addressed in Phase 4. |
| Club-directed notifications resolve to the **owner's user id only** | `notifications` call sites (TRA-152 finding) | Staff doing the daily work receive nothing — Phase 3. |
| Email delivery infra exists (SMTP fire-and-forget from `create_notification`, no-ops when `SMTP_HOST` unset) | TRA-44, shipped | Invitation emails piggyback on it; dev fallback needed (D6). |
| Sidebar identity system exists (`useIdentity` hook + role-colored footer) | `frontend/src/hooks/useIdentity.ts` | Staff identity ("Club — Staff: Manager") extends it, not a new system. |
| **No self-registration UI — deliberate standing decision** (login page is login-only; admin provisions accounts) | Product decision on record | Preserved. The invitation-acceptance page (D6) is provisioning via emailed link, *not* open signup — but it is a new auth surface and is called out as a conscious extension. |

## Decisions already made

Settled 2026-07-05. Surface conflicts rather than silently reversing ([`engineering-standards`](../../.claude/skills/engineering-standards/SKILL.md) §4).

- **D1 — Fixed role set, no custom RBAC.** Five club roles: **OWNER** (the club's primary account — a `User`, not a `ClubStaff` row), **SPORTING_DIRECTOR** (new), **MANAGER** (exists), **SCOUT** (new), **READONLY** (exists). Enumerated roles with a static capability matrix beat a role-builder at this stage — interpretable, testable, documentable.
- **D2 — Capability-based enforcement, defined once.** A `Capability` enum + one `ROLE_CAPABILITIES` matrix in one module; a single `require_club_capability(cap)` dependency replaces the scattered `require_club_write_access`. Check order inside it: **superuser bypass first** (the named house pattern in [authentication-and-permissions](../architecture/authentication-and-permissions.md)), then owner → all capabilities, then staff → matrix, else 403.
- **D3 — The server matrix is the only truth; the UI consumes it.** A `GET /clubs/me/membership` endpoint returns role + capability list; the frontend gates buttons via a `useClubCapabilities` hook. No capability logic duplicated client-side.
- **D4 — Sequencing invariant: capability enforcement (Phase 1) ships before or with staff deal access (Phase 2).** Today READONLY staff can't write to deals only because *no* staff can see deals. Fixing TRA-146 first would silently grant read-only staff full deal-write access. A regression test pins this: READONLY staff + deal access ⇒ 403 on every deal write.
- **D5 — Notification routing is role-mapped, not broadcast.** Deal/offer/bid events → OWNER + SPORTING_DIRECTOR + MANAGER; scouting events additionally → SCOUT; account/administrative events → OWNER only. Individual `NotificationPreference` opt-outs still apply per recipient.
- **D6 — Onboarding is invitation-based provisioning, never open signup.** Owner invites by email + role; invitee sets their own password via a tokenised link (single-use, hashed at rest, 7-day expiry). The login page stays login-only. Because SMTP may be unset in dev, the create-invitation response returns the accept URL once so the owner can share it manually. Admin-created staff (existing path) remains for platform support, but the invitation path means **no one but the staff member ever knows their password**.
- **D7 — Approval thresholds are per-club, single-amount, MANAGER-scoped.** One nullable `approval_threshold` (null = feature off, the default). When a MANAGER-role staff member commits money ≥ threshold (place bid, create/accept offer, accept bid), the action is captured as a pending approval instead of executing; OWNER or SPORTING_DIRECTOR approve or reject. **Nothing is reserved at request time; everything is re-validated at execution time** (budget, transfer window, auction still open) — an approval is an intent, not a hold.
- **D8 — First-run onboarding is stateless.** Per-persona checklists computed from existing data (has crest? verification requested? first mandate?) — no new backend state, no migrations; dismissal in `localStorage`. If a step's done-predicate would need a new endpoint, the step is wrong — pick one derivable from existing queries.
- **D9 — Staff users stay `user_type = CLUB`, now explicitly.** Verified: staff creation currently relies on the column default; every club-side branch (`is_deal_participant`, buyer/seller gates) switches on `user_type == CLUB`. v1 makes `user_type=UserType.CLUB` explicit at both creation sites and documents `UserType.STAFF` as a **reserved, currently-unassigned** value — repurposing it is a future migration decision, not a drive-by.
- **D10 — Staff removal = delete the `ClubStaff` row + deactivate the `User`** (`is_active=False`). A staff account has no purpose outside its club; deactivation (checked on every authenticated request) revokes access immediately even with a live token.

## The design

### Roles and capability matrix (Phase 1)

`Capability` enum: `SCOUTING_WRITE`, `MARKET_WRITE`, `DEAL_WRITE`, `CLUB_ADMIN`, `TEAM_MANAGE`, `APPROVE_ACTIONS`. (Viewing is not a capability — club visibility comes from membership itself.)

| Capability | OWNER | SPORTING_DIRECTOR | MANAGER | SCOUT | READONLY |
|---|---|---|---|---|---|
| View club data (squad, finance, listings, offers, deals†) | ✓ | ✓ | ✓ | ✓ | ✓ |
| `SCOUTING_WRITE` — shortlists, player interest | ✓ | ✓ | ✓ | ✓ | ✗ |
| `MARKET_WRITE` — create sale, place/accept bid, create/counter/accept/reject/withdraw offer, squad player edits (incl. `open_to_offers`) | ✓ | ✓ | ✓ ‡ | ✗ | ✗ |
| `DEAL_WRITE` — advance/collapse, structure/clauses/instalments, club-side terms responses, deal-room comments & attachments, invite agent | ✓ | ✓ | ✓ ‡ | ✗ | ✗ |
| `CLUB_ADMIN` — club profile edit, finance budget edits, verification request | ✓ | ✓ | ✗ | ✗ | ✗ |
| `TEAM_MANAGE` — invite staff, change roles, remove staff, set approval threshold | ✓ | ✗ | ✗ | ✗ | ✗ |
| `APPROVE_ACTIONS` — decide pending approvals (Phase 5) | ✓ | ✓ | ✗ | ✗ | ✗ |

† Deal *visibility* for staff arrives in Phase 2. ‡ Threshold-gated in Phase 5 (money-committing `MARKET_WRITE` actions only).

Implementation: `app/clubs/capabilities.py` — enum, matrix, `require_club_capability(cap)` FastAPI dependency (built on the existing `get_club_and_role_for_user`), and `capabilities_for_role(role) -> list[Capability]`. Platform-staff (`is_superuser`) bypasses first, always.

**Enforcement inventory** — every endpoint below gets the dependency (this is the completeness audit; re-grep club write routes at implementation time rather than trusting this list blindly):

| Surface | Endpoints | Capability |
|---|---|---|
| Sales | the 4 existing `require_club_write_access` sites | `MARKET_WRITE` |
| Offers | the 5 existing sites | `MARKET_WRITE` |
| Squad | `update_my_club_player` and sibling squad-posture edits | `MARKET_WRITE` |
| Deals | advance, collapse, structure/terms update, clause CRUD, instalment CRUD, club-side personal-terms/negotiation responses, agent invitation | `DEAL_WRITE` |
| Deal room | comment create, attachment upload, terms-version-producing edits | `DEAL_WRITE` |
| Scouting | shortlist CRUD, shortlist items, player interest | `SCOUTING_WRITE` |
| Club | profile PATCH, finance budget updates, verification request | `CLUB_ADMIN` |
| Team | all Phase-4 endpoints | `TEAM_MANAGE` |

`require_club_write_access` is deleted once its 9 sites are migrated (it is this feature's orphan — removing it is in scope; leaving both systems is not acceptable).

Enum migration: `ALTER TYPE staffrole ADD VALUE 'SPORTING_DIRECTOR'` / `'SCOUT'` — see gotcha #1.

New endpoint: **`GET /clubs/me/membership`** → `{"club": {…ClubSummary…}, "role": "MANAGER", "capabilities": ["SCOUTING_WRITE", "MARKET_WRITE", "DEAL_WRITE"]}`; 404 if the caller has no club. Frontend: `useClubCapabilities()` hook; all club action buttons gate on capabilities (hide for SCOUT/READONLY, not disable-with-tooltip — a scout's UI simply doesn't offer bidding). Sidebar identity extends to `"{Club} — Staff: Sporting Director"` via the existing `useIdentity`.

### Staff deal access (Phase 2 — requires Phase 1)

Fix `room_service.is_deal_participant`'s CLUB branch (`room_service.py:48-54`): resolve via `get_club_for_user` (owner-or-staff) instead of `get_club_by_user_id` (owner-only). Then audit every participant-gated read for consistency — deal detail, deal room, audit log + CSV export, medical-check GET, personal-terms GET all route through this function or its callers; verify each rather than assuming the one fix covers all.

Field-scoping: staff see exactly the club-side view their owner sees (commission fields visible — they're club/agent business; the existing player-side hiding is untouched). Writes are already covered by Phase 1's `DEAL_WRITE` gating — which is precisely why Phase 2 cannot ship first (D4).

### Notification routing (Phase 3)

New helper in `notifications/service.py`: `club_recipient_user_ids(db, club_id, notification_type) -> list[uuid.UUID]` — owner + active staff filtered by the D5 role mapping:

| Notification family | Recipients |
|---|---|
| Deal, offer, bid, negotiation, instalment/clause events | OWNER, SPORTING_DIRECTOR, MANAGER |
| Scouting / market-hit / shortlist events | OWNER, SPORTING_DIRECTOR, MANAGER, SCOUT |
| Account, verification, team-management, approval events | OWNER (+ SPORTING_DIRECTOR for approval requests) |

Sweep every call site that resolves a club to its owner today (`_db_notify_deal_parties`, `_db_notify_offer`, and siblings — grep `notify` across services for the definitive list) and route through the helper. Existing per-user `NotificationPreference` opt-outs and email subordination are applied per recipient by the existing `create_notification` path — no preference-model changes.

### Team management + invitations (Phase 4)

**Model** — `club_staff_invitations`: `id`, `club_id` FK, `email`, `role` (StaffRole), `token_hash` (`sha256` of a `secrets.token_urlsafe(32)`; raw token never stored), `invited_by_user_id`, `created_at`, `expires_at` (+7 days), `accepted_at`, `revoked_at`.

**Owner endpoints** (all `TEAM_MANAGE`), under `/clubs/me/staff`:

- `GET /clubs/me/staff` — active staff + pending invitations in one payload.
- `POST /clubs/me/staff/invitations` `{email, role}` → 201 with the invitation **and `accept_url` (returned exactly once)**. 409 if the email already belongs to any `User` (account-linking is out of scope; the error text tells the owner why). Sends the invitation email via existing infra.
- `DELETE /clubs/me/staff/invitations/{id}` — revoke (sets `revoked_at`; token dies).
- `PATCH /clubs/me/staff/{staff_id}` `{role}` — change role (existing service `update_club_staff_role`).
- `DELETE /clubs/me/staff/{staff_id}` — remove: delete row + `User.is_active = False` (D10). An owner cannot remove themselves (they're not a staff row).

**Public acceptance endpoints** (unauthenticated, in `auth/router.py`):

- `GET /auth/invitations/{token}` — preview: club name, crest, role, invited email, expiry. 404 for unknown/expired/revoked/accepted tokens (constant-time hash compare; no oracle on which failure).
- `POST /auth/invitations/{token}/accept` `{password, full_name?}` → creates `User` (**explicit `user_type=UserType.CLUB`**, D9) + `ClubStaff` row, stamps `accepted_at`, returns the normal login token pair (the accept page logs them straight in).

**Frontend**: a Team page under My Club — staff list with role badges, role-change and remove controls (remove behind the existing confirm dialog), invite form (email + role with plain-language capability descriptions from the matrix), pending invitations with copy-link and revoke. A public `/accept-invite?token=…` route: preview card + password form. The login page itself is untouched (D6).

**Audit**: check `app/audit/models.py` at implementation — if `AuditEvent` supports non-deal scoping, emit `STAFF_INVITED / STAFF_JOINED / STAFF_ROLE_CHANGED / STAFF_REMOVED` with `actor_user_id`; if it's deal-scoped only, log at INFO + notify the owner, and record "club-scoped audit surface" as the known follow-up in the Linear notes.

### Approval thresholds (Phase 5)

**Config**: `approval_threshold Numeric(15,2) NULL` on `ClubFinance` (null = disabled, the default). Set via a `TEAM_MANAGE` endpoint (`PATCH /clubs/me/approval-policy`).

**Model** — `pending_approvals`: `id`, `club_id`, `action_type` (`PLACE_BID / CREATE_OFFER / ACCEPT_OFFER / ACCEPT_BID`), `payload_json` (`JSON().with_variant(JSONB, "postgresql")` — gotcha #2), `amount Numeric(15,2)`, `requested_by_user_id`, `status` (`PENDING / APPROVED_EXECUTED / APPROVED_FAILED / REJECTED / EXPIRED / CANCELLED`), `decided_by_user_id`, `decided_at`, `failure_reason`, `created_at`, `expires_at` (+24h).

**Flow**: inside the four money-committing actions, after full validation, if caller is MANAGER-role staff (owner and SPORTING_DIRECTOR are exempt) and threshold is set and `amount ≥ threshold` → persist the validated payload as a pending approval and return **202** `{"status": "PENDING_APPROVAL", "approval_id": …}` instead of executing. Notify OWNER + SPORTING_DIRECTORs (D5 mapping).

**Decision endpoints** (`APPROVE_ACTIONS`): `GET /clubs/me/approvals?status=`, `POST /clubs/me/approvals/{id}/approve`, `POST /clubs/me/approvals/{id}/reject {reason?}`. Requester may `POST /clubs/me/approvals/{id}/cancel` (own, pending only). Approve → re-run the original service call with **requester attribution + approver recorded**; any failure (auction closed, outbid, budget insufficient, window shut — all revalidated fresh, D7) lands in `status=APPROVED_FAILED` + `failure_reason`, notifying both parties. A small daily APScheduler job expires stale approvals and notifies requesters.

**UI**: Approvals panel (badge count) for OWNER/SD on the dashboard + a queue view; requester sees "Pending approval" state on the originating page with cancel.

New `NotificationType` members (`STAFF_INVITATION`, `APPROVAL_REQUESTED`, `APPROVAL_DECIDED`) — all four frontend touchpoints each, per gotcha #4.

### Per-persona first-run (Phase 6 — frontend only)

One `OnboardingChecklist` component on the dashboard, per-persona step configs, every step's done-state derived from existing queries (D8), dismissible (`localStorage`, keyed by user id). Steps link to the real page, never wizard-modal anything.

| Persona | Steps (done-predicate) |
|---|---|
| Club owner | Complete club profile (crest + country set) → Set budgets (finance totals > 0) → **Invite your team** (≥1 staff or invitation) → Request verification (existing panel; request exists) → First market action (≥1 listing, bid, or offer) |
| Club staff (post-invite) | Role-appropriate: SCOUT → create first shortlist; MANAGER → tour of market/deals (visited-flag); READONLY → none (no empty checklist for a role with nothing to do) |
| Agent | Complete agency profile (licence no. set) → Request verification → Add first client (≥1 mandate) → Review client alerts preferences |
| Player | Set profile visibility (explicitly saved once) → Set openness to offers → Review representation (mandate exists or explicitly none) |

## Success criteria

### Phase acceptance (backend)

- [ ] **P1**: every endpoint in the enforcement inventory carries the correct capability; `require_club_write_access` no longer exists; superuser bypass is checked first in the new dependency; `GET /clubs/me/membership` returns role + capabilities for owner, each staff role, and 404 for club-less users.
- [ ] **P2**: staff of buyer/seller club can read deal detail, deal room, audit log, medical-check, personal-terms for their club's deals; staff of an *unrelated* club still 403; **the D4 invariant test exists and passes — READONLY staff with deal visibility gets 403 on every `DEAL_WRITE` endpoint.**
- [ ] **P3**: a deal event notifies owner + SD + MANAGER staff (not SCOUT/READONLY); a market-hit notifies SCOUT too; per-user notification preferences still suppress individually; no call site resolves a club to a bare owner id anymore.
- [ ] **P4**: invitation lifecycle (create → email/copy-link → preview → accept → login) works end-to-end; token is single-use, hashed at rest, dead after expiry/revocation/acceptance; accepted user has explicit `user_type=CLUB` + correct `ClubStaff` row; removal deactivates the user (next request 401s); invite to an existing email → 409.
- [ ] **P5**: MANAGER bid ≥ threshold → 202 + pending approval (nothing executed, nothing reserved); owner/SD exempt; approve re-executes with dual attribution; a stale approval against a now-closed auction lands `APPROVED_FAILED` with reason, both parties notified; threshold null ⇒ feature invisible.
- [ ] **P6**: each persona sees its checklist with real done-states; dismissal sticks per user; zero new backend endpoints were added for it.

### Scenario walkthroughs (integration fixtures)

1. **Scout lifecycle**: owner invites `scout@club.com` as SCOUT → accepts via link → sees squad, market, club deals (P2) → creates a shortlist (allowed) → `POST /sales/{id}/bids` → 403; UI never offered the button.
2. **The D4 regression**: READONLY staff opens a live deal (P2 shipped) → every advance/comment/attachment/terms endpoint → 403.
3. **Threshold flow**: threshold £5m; MANAGER places a £6m bid → 202 pending → SD approves → bid exists with requester attribution + approver recorded → seller's side notified normally. Same flow with the auction closed in between → `APPROVED_FAILED`, both notified.
4. **Routing**: offer received → owner, SD, MANAGER notified; SCOUT and READONLY not; MANAGER with that type opted out in preferences → not notified either.
5. **Invitation security**: expired token → preview 404; accepted token reused → 404; revoked mid-flight → 404; two clubs inviting the same email → second gets 409 (unique `user_id` on `ClubStaff` holds).

### Edge-case matrix

| Condition | Required behaviour |
|---|---|
| `is_superuser` caller on any club-gated endpoint | Bypass first — never blocked by role/capability/threshold |
| Owner on any capability check | Full access; owner is not a `ClubStaff` row and never threshold-gated |
| Staff whose `ClubStaff` row was deleted mid-session (valid JWT) | Next request: no membership → 403 on club surfaces (checks hit the DB per request); deactivated user → 401 |
| MANAGER action exactly at threshold | Escalates (`≥`) |
| SD places a bid over threshold | Executes directly (exempt) |
| Approval approved twice / decided then cancelled | Second transition 409 — status machine is one-way |
| `payload_json` replay after the underlying sale/offer was deleted | `APPROVED_FAILED` with reason, no 500 |
| Staff member of *neither* club calls deal endpoints | 403/404 exactly as a stranger club does today |
| Invitation email differing only by case | Case-insensitive uniqueness on both invite and accept |

### Non-functional

- [ ] Capability check adds ≤ 1 query (the existing staff lookup) per request; membership endpoint is 2 queries max.
- [ ] Permission tests enumerate: unauthenticated 401; each staff role against each capability class (matrix-driven, not hand-picked); PLAYER/AGENT account types on club endpoints unchanged from today.
- [ ] Full backend suite green (274 baseline + new); TypeScript clean.

### Definition of done — documentation (per phase, per [`documentation-standards`](../../.claude/skills/documentation-standards/SKILL.md))

- [ ] `docs/architecture/authentication-and-permissions.md` — **fill the standing "Club roles" TODO** with the role set + capability matrix (this spec is the draft for it).
- [ ] `docs/security-and-compliance/permissions-model.md` — boundary rows for staff deal access, approvals, invitations; remove TRA-146 from Known gaps when P2 ships.
- [ ] `docs/product/personas.md` — flesh out the club-staff persona (currently the "Staff" entry conflates club staff with platform admin — fix that while there, it's the same "staff" terminology collision noted in this spec).
- [ ] `docs/business/glossary.md` — "Club staff role", "Approval threshold", "Invitation" entries.
- [ ] `docs/CHANGELOG.md` + `docs/IMPLEMENTATION_STATUS.md` per phase; this spec → `Implemented` at the end.

### Demo script (end-to-end gate, phases 1–5)

1. As club owner: Team page → invite a SCOUT and a MANAGER (copy-link flow, no SMTP needed) → both accept and land logged-in.
2. Scout logs in: sidebar reads "Staff: Scout"; market visible; shortlist created; no bid/offer buttons anywhere; direct API bid → 403.
3. Owner sets approval threshold £5m. Manager negotiates and places a £6m bid → "Pending approval" state.
4. Owner's dashboard shows the approval badge → approve → bid live; deal proceeds; the manager (not just the owner) receives the deal notifications from then on.
5. Read-only board member views the deal room in full, touches nothing — every control absent.
6. Owner removes the manager → their next click lands on the login page.

## Out of scope (v1)

| Deferred | Why / where |
|---|---|
| **Agency organizations** (multi-agent agencies, shared rosters) | The equivalent feature for the agent side — structurally separate, deserves its own spec; biggest known account-model gap after this ships. |
| Open self-registration | Standing product decision, deliberately preserved (D6). |
| Cross-club membership / account linking for existing emails | `ClubStaff.user_id` unique constraint retained; 409 path documents the boundary. |
| Custom role builder, per-capability toggles | D1 — fixed matrix only. |
| SSO/SAML, 2FA | Enterprise auth hardening, separate track (production-readiness). |
| CEO oversight dashboards, per-staff activity views | READONLY membership + the audit trail are the v1 answer; dashboards later. |
| Multi-level approval chains, per-action-type thresholds | One amount, one approval, v1 (D7). |
| Repurposing `UserType.STAFF` | Reserved value, explicit future decision (D9). |

## Deviations from spec (implemented 2026-07-10)

All six phases shipped in one session, in phase order (D4 honoured: capability gates landed before the participant-check widening). Verified by 57 new backend tests — full suite 362 passed — plus TypeScript clean. Deviations, all deliberate:

1. **The enforcement inventory grew under the mandated re-grep.** Beyond the spec's list: offer negotiation messages (`POST /offers/{id}/messages`, previously ungated — speaks for the club → `MARKET_WRITE`); players-router squad writes (`POST /players`, `PATCH /players/{id}`, contract add/deactivate → `MARKET_WRITE` as "sibling squad edits"); scouting, verification, and expiring-contracts club resolution widened from owner-only to owner-or-staff (the matrix says viewing comes with membership — previously staff had *zero* scouting access).
2. **"Finance budget edits" have no club-facing endpoint** (budgets are platform-admin-set), so `CLUB_ADMIN` in practice gates profile edit + verification request. Player search views were left membership-level (benign saved filters, not in the inventory).
3. **Shared deal-room surfaces use `ensure_capability_if_club_member`** — a blanket `DEAL_WRITE` dependency would 403 agents/players, who are authorized by the participant check instead. Same pattern inline in mixed-caller endpoints (advance, personal terms, verification request).
4. **The capability check uses a lean `get_club_membership_role`** (role-only: 1 indexed query for owners, 2 for staff) rather than the full `get_club_and_role_for_user`, to hold the ≤1-added-query budget; the full resolver still backs `/clubs/me` and the membership endpoint.
5. **Approval capture happens after the router-level guards** (window, duplicate-offer, active-deal); deep validation (budget, auction state) runs only at execution — deliberately, per D7 ("an approval is an intent, not a hold"); stale state lands `APPROVED_FAILED` with the reason, both parties notified. Counterparty notifications for approval-executed actions are replicated in `approvals/service.py::_execute` since the originals live in the routers.
6. **Invitation copy-link exists only at creation time** — the raw token is never stored (D6), so the Team page can't re-show links for listed pending invitations; it says so and offers revoke + re-invite. `full_name` was dropped from the accept payload (the `User` model has no name column).
7. **A fifth club audit action, `STAFF_INVITATION_REVOKED`,** was added beyond the spec's four — revocation is a team-management action worth a trail.
8. **WS pushes widened alongside notifications** (`club_member_user_ids`, all roles) — they're "refresh this view" signals, not role-scoped content; without this, staff watching a deal never saw live updates.
9. **Not yet done:** migrations `0049`–`0051` are written but not applied to the dev Postgres (the backend entrypoint applies them on next `docker compose up`), and the § demo script has not been driven against the live stack.

## Linear reconciliation (suggested, not executed)

Per [`linear-workflow`](../../.claude/skills/linear-workflow/SKILL.md) — suggestions only:

- **TRA-151** (roles backend) = Phase 1; **TRA-146** (deal access) = Phase 2; **TRA-152** (notifications) = Phase 3; **TRA-86** (team UI) = Phase 4. Link this spec on each; add the **D4 sequencing note as a blocking relation TRA-146 ← TRA-151** — the silent-permission risk isn't recorded anywhere in Linear today.
- **New tickets**: "Approval thresholds / spending authority" (Phase 5) and "Per-persona first-run checklist" (Phase 6), both linking this spec — proposed 2026-07-05, no existing coverage (verified).
- **TRA-85/86 note**: TRA-86's title still says "Squad import wizard + role management — UI"; the role-management half is Phase 4 here — suggest retitling or splitting the same way TRA-85 was already split on 2026-07-03.
- **TRA-28** (cancelled, old MVP "club team member invitation") — now genuinely superseded by this spec; worth a closing comment pointing here for history.
- If Phase-4 audit work reveals the audit model is deal-scoped only: new small ticket "club-scoped audit events".

## Related documents

- [`../architecture/authentication-and-permissions.md`](../architecture/authentication-and-permissions.md) — gains the role model this spec defines (its open TODO)
- [`../security-and-compliance/permissions-model.md`](../security-and-compliance/permissions-model.md) — confidentiality boundaries extended per phase
- [`fair-value-vs-asking-signal.md`](./fair-value-vs-asking-signal.md) / [`injury-availability-risk-profile.md`](./injury-availability-risk-profile.md) — sibling specs; their player-account exclusions (D6 there) are unaffected by staff roles
- [`README.md`](./README.md) — spec lifecycle

## Appendix: implementation gotchas (house-specific)

1. **Postgres enum extension**: `ALTER TYPE staffrole ADD VALUE` cannot run inside a transaction block on older Postgres — use Alembic's `op.get_context().autocommit_block()`. SQLite tests are unaffected (SAEnum renders as VARCHAR there).
2. **`JSONB` breaks the SQLite test suite** — `pending_approvals.payload_json` must be `JSON().with_variant(JSONB, "postgresql")` (the `audit/models.py` pattern).
3. **Migration numbering race** — three active specs in this folder each allocate "next migration" (this one needs up to three: enum values, invitations, approvals). Chain `down_revision` off the real head at implementation time, never off a spec's assumption.
4. **New `NotificationType` members need all four touchpoints** — backend enum + `ALTER TYPE` migration, `frontend/src/types/enums.ts` union, `NotificationsPage.tsx` `TYPE_LABELS`/`TYPE_COLOURS`, `NotificationPreferencesPage.tsx` labels/groups. The last one compiles silently if missed — it's non-exhaustive. (This exact miss has happened in this repo before.)
5. **UUID coercion with aiosqlite** — `uuid.UUID(str(value))` before WHERE clauses in new service code.
6. **Superuser-bypass-first** is a named pattern (`authentication-and-permissions.md`): a pure platform-admin account has no club/agent/player profile, so any role-specific branch must be skipped for it entirely, not merely satisfied.
7. **Invitation tokens**: compare via constant-time hash equality; never log the raw token; the accept URL appears in exactly one API response.
