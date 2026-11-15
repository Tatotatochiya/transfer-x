---
title: "Product and production-readiness review, 15 November 2026"
last_updated: 2026-11-15
status: Active
owner: "TODO — assign a Product Owner"
---

# Product and production-readiness review

Reviewed on 15 November 2026 against `main` at `d4ae9db` (PR #83 merged). It covers the product and its workflows, the admin side, production readiness and deployment, data and vendors, and AI. It also asks whether TransferX would help a Sporting Director, a head coach or manager, and a scout. Club budgeting is deliberately out of scope, as a nice-to-have.

How each finding was checked is in [section 11](#11-how-this-was-checked). Findings marked **(verified)** were checked against the code, the local database or Railway's settings. The rest are judgement.

## Contents

1. [Summary](#1-summary)
2. [The objective, and what is undecided](#2-the-objective-and-what-is-undecided)
3. [What is strong](#3-what-is-strong)
4. [Through a club's eyes](#4-through-a-clubs-eyes)
5. [Product and workflow gaps](#5-product-and-workflow-gaps)
6. [Admin gaps](#6-admin-gaps)
7. [Production readiness and deployment](#7-production-readiness-and-deployment)
8. [Data and vendors](#8-data-and-vendors)
9. [AI](#9-ai)
10. [Recommended order](#10-recommended-order)
11. [How this was checked](#11-how-this-was-checked)

---

## 1. Summary

**TransferX is a well-built deal workflow that is not yet ready for a real club.** The transfer pipeline (enquiry, offer, counter, deal, agent, personal terms, paperwork, completion) is deeper and more careful than most products at this stage. The gaps are around it, not in it.

The ten findings that matter most, in order:

| # | Finding | Kind |
|---|---|---|
| 1 | **A club can only deal with clubs already on TransferX.** Locally, 6,073 of 6,693 players (91%) are at clubs outside it, and their pages can only say "shortlist him". The product's value depends on who else is on it, and there is no way to bring a counterparty in. | Product, strategic |
| 2 | **Uploaded deal documents are lost on every deploy.** Signed personal terms and other attachments are written to the backend container's disk, and only Postgres has a persistent volume on Railway. | Production blocker |
| 3 | **Confidential deal data goes to DeepSeek.** Production's AI model is `deepseek/deepseek-chat`. Bids, wages and negotiation history are sent to it. No club's legal team would accept this without a data agreement. | Trust blocker |
| 4 | **No email on Railway.** Invitations, password resets, digests and reminders can't be sent, so nobody outside the team can be onboarded. | Production blocker |
| 5 | **No automated checks before deploy.** There is no CI. Every merge to `main` deploys straight to the only environment, and the database migrates on start. | Production blocker |
| 6 | **Sign-in is weak for the money involved.** No two-factor, no limit on failed sign-ins, and every Railway account shares one password. | Trust blocker |
| 7 | **The scout has very little.** Shortlists with a note and a priority. No scout reports, no assignments, no video, no advanced metrics, and positions are only GK, DEF, MID and FWD. | Product |
| 8 | **Nothing regulatory.** No registration checklist (FIFA TMS, ITC, work permit), no generated agreement, no e-signature. The "paperwork" stage is a checklist of clicks. | Product |
| 9 | **Contract data is mock or missing.** Contract end dates are generated, no player has a release clause, and only 3 of 607 contracts carry the club's own valuation. Squad planning can't be trusted on this. | Data |
| 10 | **The business is undecided.** Vision, target market, pricing and competitors are all still "TODO". This decides which of the gaps above matter. | Business |

**What to do first:** fix findings 2 to 6 (about two weeks of work, none of it product design), decide finding 10, then run a pilot with two or three clubs before building more features.

---

## 2. The objective, and what is undecided

**What the product says it is** (`docs/PRODUCT_SPEC.md`): a web platform where selling clubs, buying clubs, agents and players complete a transfer as one structured deal, with finance, squad, scouting, a fair-value model and an AI assistant around it.

**What is undecided (verified: each of these documents is a placeholder):**

| Document | State |
|---|---|
| `business/vision.md` | Problem statement, mission and success measures are all TODO |
| `business/target-users-and-market.md` | Which tier of club: TODO. Competitors: TODO |
| `business/business-model.md` | Pricing and packaging: TODO |
| `product/personas.md` | Goals and pain points for every persona: TODO |
| `product/roadmap.md` | Last updated 11 October. "Decisions still needed: business model, a pilot, data sources" |

**Why it matters.** The product is trying to be three things at once, and they need different things:

| If TransferX is… | The paying user | What matters most |
|---|---|---|
| **A marketplace** (find counterparties) | Clubs, for access to other clubs | Network size, discovery, trust between strangers. Finding 1 is fatal until solved |
| **A deal workflow** (run a transfer you've already agreed by phone) | A club's football operations and legal staff | Documents, compliance, audit, working with counterparties who aren't customers |
| **Decision support** (who to buy, what to pay) | Sporting Directors and recruitment | Data depth, valuation accuracy, scouting tools, AI |

**Recommendation.** Lead with the **deal workflow plus decision support for one club**, which has value from the first customer, and let the marketplace grow from it. That means a club must be able to run a deal with a club that isn't on TransferX (section 5.1). TransferRoom is the obvious comparison for the marketplace; this review did not research competitors, and the comparison should be done before pricing.

---

## 3. What is strong

These are worth protecting, and worth leading with in a demo:

- **The deal pipeline is realistic.** Offers carry the full terms; counters are validated like new offers; agent commission and personal terms are negotiated in rounds; every answer that ends a transfer is confirmed; a confirmed deal holds the player; windows hold completion, not talks.
- **"Whose move" everywhere.** The Board, Dashboard, deal and offer pages agree on who must act, with reminders and escalation when a transfer stalls.
- **Confidentiality is designed in.** Anonymous buyers are masked on the server; a club's contract terms and valuation are its own; rivals' bids are never named to buyers; the player never sees commission.
- **Money paths are careful.** Budgets are reserved, committed and spent with row locks; spending approvals re-validate at execution.
- **Audit and admin.** Every staff change needs a reason and is audited; read-only "view as this club"; stuck-deal tools; Jobs, Errors and Health pages.
- **Lite mode and phone notifications.** Deciding from a phone, with held sends and undo, suits how a Sporting Director actually works.
- **Demo mode.** A tester can run a whole transfer alone, and reset it.
- **Engineering discipline.** 981 backend and 531 frontend tests pass, the type-check is clean, a design-system guard test enforces type and colour rules, and the docs record decisions (21 ADRs) and deviations.

---

## 4. Through a club's eyes

### 4.1 Sporting Director

**What helps today**
- One board of every transfer in and out, with what's waiting on me.
- Offers with full terms and a clear history of what changed each round.
- The offer advisor and a consistent suggested counter.
- Approvals from my phone; reminders that chase the other side.
- A fair-value figure and the last fee beside every player.

**Where it falls short**

| Gap | Why it matters to me |
|---|---|
| **I can only approach clubs on TransferX** | Most of my targets are at clubs that aren't. I'd still be on the phone and WhatsApp for those, so TransferX becomes a second system, not the system |
| **No squad planning** | I think in windows: contracts ending in 18 months, who to renew, sell or release, age profile by position, the wage structure. Today there is a squad table and a "contract ends within" filter. Contract end dates are mock data |
| **No squad rules** | The 25-man list, homegrown quotas, non-EU or work-permit limits. A deal that breaks a rule should say so before I bid |
| **The paperwork stage isn't the real paperwork** | TMS, ITC, registration and the permit are what actually delay deals. Ticking "registration submitted" doesn't help me on deadline day |
| **No agreement document** | After all that structured negotiation I still ask a lawyer to re-key the terms into a contract. The agreed terms should produce the draft |
| **Personal terms are three fields** | Wage, signing bonus and length. Real terms have appearance, goal and loyalty bonuses, image rights, a release clause, relocation, agent fees per year |
| **No swaps or player-plus-cash** | Common in practice. Enquiries note swaps as deferred |
| **No "target pipeline" by position** | I want "left-back: 5 targets, 2 contacted, 1 offer" in one view. Shortlists and the board are separate things |
| **I can't see what my team thinks** | No place for the coach's verdict or the scout's recommendation on a target, beside the deal |
| **Trust** | No two-factor sign-in, and the AI sends my negotiation to a model provider I haven't approved |

### 4.2 Head coach or manager

**What helps today**
- Lite mode: big type, few choices, "Ask anything".
- Injuries and form on a player's page; the squad's coverage by position.
- Being asked a question by the team ("Ask Sam") and answering from the phone.

**Where it falls short**

| Gap | Why it matters to me |
|---|---|
| **No way to say what I need** | "I need a left-footed centre-back who can play out" should become a brief the scouts and the Sporting Director work from. The guided position path in Lite was removed on 18 October |
| **No simple view of targets for my opinion** | I'd give a thumbs up, down or "watch more" on five candidates. Nothing collects that |
| **No availability view of my own squad** | Who is injured and until when, who is out on loan and recallable, whose contract ends. It's spread across pages |
| **The "Manager" role is a deal-runner, not a coach** | The role named Manager "runs the market and deals day to day". A head coach is closer to the read-only role plus opinions. The naming will confuse English clubs, where "manager" means the head coach |
| **Loans can't be offered from Lite** | Loans are what a coach asks for most in January |

### 4.3 Scout

This is the weakest persona **(verified: the scouting module is shortlists, a note and priority per player, and an interest level and stage)**.

**What helps today**
- Browse Players with filters, "Describe a player" search, compare, shortlists.
- A notification when a shortlisted player is listed or becomes a free agent.
- The AI's shortlist review and player-fit view.

**Where it falls short**

| Gap | Why it matters to me |
|---|---|
| **No scout reports** | My job's output is a report: match watched, date, ratings by attribute, strengths, weaknesses, a recommendation (sign, monitor, reject). A free-text note on a shortlist item isn't that. Reports should attach to the player, be visible to my club only, and follow him into an offer |
| **No assignments** | "Watch Player X on Saturday" from the head of recruitment, with a due date and a status |
| **Positions are GK, DEF, MID, FWD** | I can't search for a left-back, a number 6 or a left-footed player. `position_played` exists per season but isn't a search field, and there is no preferred foot |
| **Thin data** | Goals, assists, shots, key passes, tackles, duels, ratings. No expected goals, progressive passes, pressures, or physical data. No per-90 or percentile view against position peers |
| **Narrow coverage** | Locally: the top five leagues and two European cups. Scouts earn their keep in the Championship, the Eredivisie, Portugal, Belgium, Scandinavia, South America and youth football |
| **No video** | Not even a link field. Scouts live in Wyscout or Hudl; a link per report would do |
| **No "similar players"** | "Find me five players like Rice, under £20m, under 24" is the most common recruitment question. The comparables logic exists for valuation but isn't offered as a search |
| **No watch alerts beyond listing** | Tell me when a shortlisted player's contract enters its last year, he changes agent, he's injured long-term, or his minutes drop |
| **No phone entry** | Scouts work in stadiums. A quick report from a phone (voice note turned into a structured report) is where AI would genuinely help |

---

## 5. Product and workflow gaps

Severity: **High** blocks a real club or a realistic demo; **Medium** is noticed quickly; **Low** is polish.

### 5.1 Working with a club that isn't on TransferX (High)

**Today (verified):** an offer or enquiry to a player at an outside club is refused, and his page says his club "is not on TransferX, so an offer could not be answered".

**Options, smallest first:**
1. **"Ask TransferX to bring them in."** A button on the player's page records the buying club's interest; staff see the demand per outside club and invite it. This also tells the business which clubs to sell to.
2. **Guest counterparties.** The buying club sends an enquiry or offer to a named contact at the outside club by email. The contact opens that one transfer through a secure link, without an account, and can answer it. Accepting an offer prompts them to join.
3. **Record an off-platform deal.** A club records a transfer it agreed elsewhere so its squad, finance and history stay complete.

Option 2 is how a workflow product usually breaks the cold start. Option 1 is a day's work and should be done regardless.

### 5.2 The transfer workflow

| Gap | Severity | Notes |
|---|---|---|
| **Registration checklist** (TMS, ITC, league registration, work permit), each with an owner, due time and document | High | Planned as Phase 2; was already the recommended next task |
| **Agreement generated from the agreed terms**, and e-signature | High | Phase 4. A draft PDF from the terms is the valuable half and needs no vendor |
| **Full personal terms** (bonuses, image rights, release clause, relocation) | Medium | Phase 4. `PersonalTerms` holds three fields |
| **A real medical step** (date, place, pass with conditions that can reopen the fee) | Medium | Phase 2 |
| **Swaps and player-plus-cash** | Medium | Deferred in the enquiry spec |
| **Buy-back and matching-rights clauses** | Low | Clause types are appearances, goals, promotion, resale and other |
| **Loan offers from Lite** | Medium | Known gap; a loan-only listing gets a permanent bid from Lite, which is refused |
| **Add-on and instalment payments move no money** and aren't confirmed by both sides | Low for now | Budgeting is out of scope, but a seller will ask "has the instalment been paid?" |
| **Dashboard "Active deals" and Finance leave out confirmed deals** | Low | Found during PR #82; they ask only for in-progress deals |
| **Agent mandates need no player confirmation** | High for trust | An agent can claim a player and then answer his personal terms. Known (TRA-144) |
| **Verification gates nothing** | Medium | A verified badge exists; no action requires it |
| **Solidarity, training compensation, agent fee cap** | Low | Phase 4; needed for the numbers to be right, not to run a pilot |

### 5.3 Players and agents

| Gap | Severity | Notes |
|---|---|---|
| **A player's view of his own transfer** | Medium | He can answer terms on his profile, but has no page showing the offer, the terms and the next step |
| **Agent tools** | Medium | Mandate expiry alerts, a client contract calendar, commission tracking (Phase 5). Agents are how players and clubs get pulled onto a platform |
| **Agents can't offer a client to clubs** | Medium | A real agent's main job. Today an agent waits for a deal to reach him |
| **Licensed-agent check** | Low | FIFA publishes licensed agents; an agent's licence number is stored but not checked |

### 5.4 Smaller things noticed

- The role name "Manager" (section 4.2).
- "Rumors coming soon" placeholder on the public transfers page (known since August).
- `console.log` and `console.error` at sign-in and in the API client (known).
- No terms of service, privacy policy or cookie notice pages (known).
- English only, pounds only (EUR and USD as estimates). Fine for an English pilot; a limit for European clubs, where fees are agreed in euros.
- The anti-sniping settings are still on Railway and in the config, though auctions are retired.

---

## 6. Admin gaps

The admin panel is one of the stronger areas: users, clubs, players, sales, offers, deals, transfer windows, real-world moves, verification, demo, audit log with export, Jobs, Errors, Health, AI usage and prompts. What's missing is what running real customers needs:

| Gap | Severity | Notes |
|---|---|---|
| **Onboarding a club** | High | A club is invited, then its squad comes from API-Football with mock contract dates. There is no guided import of real contracts (a spreadsheet upload with validation would do), and "Check your squad" asks the club to fix each player by hand |
| **Club handover and closing** | Medium | A club owner can't close or hand over the account; it's "sent to TransferX" with no tool behind it |
| **Outside-club demand** | Medium | No view of which outside clubs members want to approach (section 5.1, option 1) |
| **Support tooling** | Medium | View-as is read-only, which is right. But there's no way to see what a user saw (their notifications, their last errors) from the user's admin page |
| **Agents and mandates** | Medium | No admin page for agents or mandates; disputes over who represents a player would be handled in the database |
| **Data-quality console** | Medium | Counts exist under Health → integrity. There's no list of "contracts with no end date", "players with no valuation", "transfer fees missing" to work through |
| **Billing and plans** | Later | Nothing exists; it follows the business-model decision |
| **Announcements** | Low | A broadcast endpoint exists; no scheduled maintenance banner |
| **Staff roles** | Medium | TransferX staff are all superusers. A support person shouldn't be able to edit budgets or complete deals |
| **PR #77 (staff-entered fees)** | Open | Reviewed on 15 November; three fixes requested (migration number clash, a staff note exposed publicly, errors hidden as bad requests). Notes are saved outside the repo |

---

## 7. Production readiness and deployment

### 7.1 The structure today (verified)

| Piece | How it runs |
|---|---|
| Hosting | Railway, one project, one environment named `production`. It holds demo data; the docs call it a demo environment |
| Services | `backend` (FastAPI, one process), `frontend` (static build served by `serve`), `Postgres` (one volume, 3.7 GB of 50 GB used), `stats-worker` (cron, twice a day) |
| Deploys | Every merge to `main` deploys all services automatically. The backend runs `alembic upgrade head` on start |
| Scheduled work | 22 jobs run inside the web process (APScheduler); the data refresh runs in `stats-worker` |
| Live updates | WebSocket connections held in the web process's memory |
| Files | Deal attachments on the backend container's local disk |
| Email | None (no `SMTP_HOST`) |
| Push | Web Push keys set |
| Alerts | Slack webhook not set, so no alerts go anywhere |
| AI | `LLM_MODEL=deepseek/deepseek-chat`; cache and rate limit in the web process's memory |
| Demo mode | `DEMO_ENABLED=true` in the same environment |

### 7.2 Blockers before any real club

| # | Issue | Evidence | Fix |
|---|---|---|---|
| 1 | **Deal documents are lost on deploy** | `deals/room_service.py` writes under `backend/uploads/`. `railway volume list` shows only the Postgres volume | Object storage (S3, R2 or Railway's bucket) behind the existing `save_attachment_bytes` / `read_attachment_bytes`; or, as a stopgap, a Railway volume on the backend. Add a virus scan and a content-type allowlist while there |
| 2 | **No email** | No SMTP settings on the backend | A transactional provider (Postmark, Resend, SES) with a verified sending domain. Before turning it on, replace seeded addresses on real-looking domains (for example `@elitesports.com`) |
| 3 | **No CI** | No `.github/workflows`. The only gate is the frontend build's type-check | A GitHub Action on every PR: backend tests, frontend tests and type-check, `ruff`. Protect `main` so a failing PR can't merge |
| 4 | **Tests run on SQLite, production is Postgres** | `tests/conftest.py` uses in-memory SQLite. This already hid one difference: the accent-free search needed Postgres-only SQL (PR #83) | Run the suite against Postgres in CI (a service container). Keep SQLite for speed locally if wanted |
| 5 | **One environment** | No staging. A bad migration reaches the only database | A `staging` environment on Railway deploying `main`; `production` deploys on a tag or manual promotion |
| 6 | **Migrations on start, no backup step** | `entrypoint.sh` | Confirm Railway's Postgres backups are on and test a restore. Take a backup before each production migration |
| 7 | **Sign-in** | No two-factor; no limit on failed sign-ins (rate limiting exists only for AI and the vendor API); every Railway account shares `password123`; refresh tokens are kept in the browser's `localStorage` | Two-factor (TOTP) required for anyone who can approve or complete; throttle sign-in and password reset by account and address; real passwords through invitations; consider moving the refresh token to an HttpOnly cookie |
| 8 | **AI provider** | Section 9 | A provider with a data-processing agreement and no training on inputs, or turn the AI off for real clubs until then |
| 9 | **Demo mode in the same environment as real data** | `DEMO_ENABLED=true` | Fine while it is a demo. For real clubs, run demos in staging or a separate demo environment; the journal and house clubs don't belong beside live deals |
| 10 | **No legal pages** | No terms, privacy policy or cookie notice | Write them before a pilot; a data-processing agreement for clubs |

### 7.3 Should fix soon after

| Issue | Evidence | Fix |
|---|---|---|
| **Single web process** | One uvicorn process; scheduled jobs, WebSocket connections, the AI cache and rate limits all live in its memory | Before a second instance: move jobs to a worker service (the `stats-worker` pattern), and put WebSocket fan-out and AI state in Redis |
| **Debug logging in production** | `entrypoint.sh` starts uvicorn with `--log-level debug` | `info` |
| **Dev dependencies in the image** | `Dockerfile` installs `.[dev]` | Install the runtime set only |
| **Container runs as root** | `Dockerfile` has no `USER` | A non-root user |
| **Builder mismatch** | Both `railway.json` files say `NIXPACKS`, while the docs describe the Dockerfile's `entrypoint.sh` running migrations | Confirm which builder Railway uses and make the files agree. Not verified which is in effect |
| **No uptime or error alerting** | Slack webhook unset; no external uptime check | Set the webhook; add an external check on `/health` |
| **No external error tracking** | Errors are captured in the app's own database | Fine for now. It fails silently if the database is the problem, so an external check matters |
| **No lint** | The frontend has a `lint` script but no eslint package or config, so it can't run; `ruff` is installed but not run anywhere | Set up eslint; add both to CI |
| **Monitoring retention and personal data** | Documented and limited | No change |
| **No load or security testing** | None found | A basic load test of the Board, Browse Players and the deal page; a dependency audit; an external penetration test before real clubs |
| **Incident process** | "No on-call rota or response times" | Decide severity levels and who is called, before a pilot |

### 7.4 A reasonable target structure

Small steps from today, not a rebuild:

```
GitHub PR ──► CI (tests on Postgres, type-check, lint)
                 │ merge to main
                 ▼
        staging (Railway)  ── demo mode on, seeded data
                 │ manual promote / tag
                 ▼
        production (Railway)
          backend  ×2  ── Redis (WebSocket fan-out, AI cache, rate limits)
          worker       ── scheduled jobs + data refresh
          frontend     ── static (a CDN host would also do)
          Postgres     ── daily backups, restore tested
          object store ── deal documents
          email provider, Slack alerts, uptime check
```

Railway is adequate for a pilot. The reasons to move later would be a customer's data-residency or certification demands (ISO 27001, SOC 2), not scale.

---

## 8. Data and vendors

### 8.1 What the data looks like today (verified on the local database)

| Measure | Value | Comment |
|---|---|---|
| Players | 6,693 | 607 at clubs on TransferX; 6,073 at outside clubs |
| Competitions | 7 locally; 11 on Railway per the docs | Top five leagues and cups |
| Players with a valuation | 2,524 (38%) | The rest lack the minutes the model needs |
| Transfer history rows | 3,047, of which 553 have a fee | Fees are the model's ground truth, and they're sparse |
| Active contracts | 607; 566 with an end date (mock), 0 with a release clause, 3 with the club's valuation | Contract data is the weakest area |
| Injuries | 4,146 across 517 players | |
| Positions | GK, DEF, MID, FWD | No detailed position or preferred foot |

**Valuation accuracy** (from the October calibration): within ±25% of the real fee for 31% of transfers, median bias −9%. It's a useful guide, not a price. PR #77's last-fee anchor is built but switched off until a backtest is reviewed.

### 8.2 What's already wired but unused (verified)

`backend/app/enrichment/` has adapters for **Capology** (wages), **ETV** (transfer values) and a **Transfermarkt scraper** marked prototype-only and blocked in production for terms-of-service reasons. None has an API key. The player model already has `capology_slug` and `etv_player_id`.

### 8.3 Vendors to consider

Not researched for this review: names and coverage are from general knowledge, and **prices, terms and API availability must be confirmed with each vendor**. Redistribution rights matter most, since TransferX shows the data to many clubs.

| Need | Candidates | Notes |
|---|---|---|
| **Wider and deeper match data** (more leagues, detailed positions, expected goals, event data) | Opta (Stats Perform), StatsBomb (Hudl), Wyscout (Hudl), Sportmonks, Impect | The enterprise three are what clubs already trust and are expensive. Sportmonks is a cheaper step up from API-Football with xG and more leagues. Check first whether API-Football's own higher plans and endpoints (lineups with positions, more leagues) close part of the gap |
| **Wages and contracts** | Capology | The adapter exists. Estimated wages, contract dates and clauses. Would replace the mock contract dates for outside players |
| **Market values and transfer fees** | Transfermarkt (licence), FootballTransfers' ETV, CIES Football Observatory | Transfermarkt has no public API; a licence is a commercial negotiation, already listed as a decision in the roadmap. A second value beside TransferX's own builds trust in both |
| **Physical and tracking data** | SkillCorner, Second Spectrum | Broadcast-derived tracking. A later differentiator for scouting |
| **Video** | Wyscout, Hudl | Clubs have their own licences. Start with a link field on scout reports; no integration needed |
| **Registration and compliance** | FIFA TMS, FIFA Clearing House, national association systems | No public API for clubs' TMS actions. TransferX should track the steps and hold the documents, not try to replace TMS. FIFA's list of licensed agents can verify an agent's licence |
| **E-signature** | DocuSign, Adobe Acrobat Sign, Dropbox Sign | Standard APIs. Needed for Phase 4's signed agreement |
| **Identity checks** | Onfido, Sumsub, Veriff | For verifying agents and club officials, if verification is to gate anything |
| **News and rumours** | A news API, or licensed feeds | For "what's being said about this player". Low priority; the placeholder page suggests it was once intended |
| **Injuries** | API-Football (in use), Transfermarkt's injury history (licence) | Enough for now |
| **Work-permit points** (GBE) | The FA's published criteria; computed from caps, minutes and league bands | No vendor needed: it's a calculation over data largely already held |

**Recommended data order:** real contract data for member clubs through onboarding (no vendor), then Capology for outside players' wages and contracts, then a match-data upgrade for detailed positions and more leagues, then a transfer-fee source to improve the valuation.

---

## 9. AI

### 9.1 What exists (verified)

- **Advice on a transfer:** offer advisor, terms checks, negotiation summary, deal next steps, listing price advice, "who might want him?", message drafts.
- **Ask TransferX:** an analyst with 17 read-only, club-scoped tools, tables, charts and Excel export. Its evaluation scored 71 of 72.
- **Scouting:** describe-a-player search, squad analysis, player fit, shortlist review, recommendations.
- **Design rule (ADR 0006):** it advises and never acts; facts are built on the server from what the asking club may see; figures are computed by TransferX. Since PR #82 the suggested counter fee is TransferX's own number, not the model's.
- **Admin:** usage per feature with a keep-or-remove verdict; editable prompts.

This is a sound design. The model is kept away from data access and from arithmetic, which is where assistants usually go wrong.

### 9.2 Risks

| Risk | Detail | Fix |
|---|---|---|
| **Provider** | Production uses `deepseek/deepseek-chat` (verified in Railway's settings). Offers, wages, budgets and negotiation messages are sent to it. The code's default is a Claude model | Choose a provider with a data-processing agreement, no training on inputs, and a region the clubs accept. State it in the privacy policy. Offer a per-club switch to turn AI off |
| **Evaluation was on a different model?** | The 71 of 72 score should be re-run on whichever model production uses | Re-run the evaluation per model before switching |
| **State in memory** | Cache and rate limits are per process | Redis, with the second instance |
| **No record of what was sent** | Usage is tracked; the facts sent to the model for a given answer aren't kept | Keep the facts and the answer for a short period, so a club's question "why did it say that?" can be answered |
| **Advice quality isn't measured** | "Suggestion used" is tracked. Whether advice was good isn't | Track outcomes: did a countered offer at the suggested fee get accepted? |

### 9.3 Where AI would help a club most

Ordered by value to the personas in section 4:

1. **Scout reports from voice or rough notes.** A scout dictates on the way home; the AI produces the structured report (ratings, strengths, weaknesses, recommendation) for him to correct. This is the highest-value AI feature not yet built, and it creates the club's own data.
2. **"Players like him."** Similar-player search from a named player plus constraints (age, price, league, contract). The describe search and comparables logic are most of the way there.
3. **The coach's brief.** Turn "a left-footed centre-back who can play out, under £15m" into a saved search with a ranked list, kept up to date, and tell the scouts when someone new fits.
4. **A negotiation pack.** Before an offer: the player's value and range, comparable deals, the selling club's situation (contract length, squad depth at his position, recent sales), and a suggested opening and ceiling. Mostly assembling what the tools already return.
5. **Contract and document reading.** Upload a contract or a signed terms sheet; extract dates, wage, clauses and bonuses into the contract record for a person to confirm. This would also solve onboarding real contract data (section 6).
6. **Window planning.** "What should we do this window?" from contracts ending, age profile, injuries and position cover: renew, sell, buy, with reasons. It needs real contract data first.
7. **A weekly digest that says something.** Changes to shortlisted players (form, injury, contract, listing), movement on targets, and what rivals did in the market.
8. **Proactive flags on a deal.** "This fee is 40% over the model", "his contract ends in six months: a pre-contract is possible in January", "this would be your fourth loan from abroad".
9. **Drafting the agreement** from the agreed terms, for the lawyers to review (with section 5.2's generated agreement).
10. **Ask TransferX, Phase C** (saved questions and reminders): already specified, not built.

Items 1, 2 and 5 are the ones a club would notice in a demo.

---

## 10. Recommended order

**Now: make it safe to show a real club (about two weeks, no product design)**
1. Object storage for deal documents.
2. Email provider and sending domain; fix seeded addresses first.
3. CI on every PR, with the backend suite on Postgres; protect `main`.
4. A staging environment; production deploys by promotion; backups confirmed and a restore tested.
5. Sign-in throttling, real passwords, two-factor for approvers.
6. An AI provider with a data agreement, or AI off for real clubs.
7. Info-level logging, runtime-only image, Slack alerts, an uptime check.
8. Terms of service and a privacy policy.

**Next: decide, and learn from real users**
9. Decide the business questions in section 2 (who it's for, what it is first, how it's paid for).
10. A pilot with two or three clubs that already deal with each other, with real contract data loaded through a spreadsheet import.
11. "Ask TransferX to bring them in" on outside players (section 5.1, option 1), to measure demand.

**Then: the gaps a pilot will hit first**
12. The registration checklist and a real medical step (Phase 2).
13. Scout reports, assignments, detailed positions and a video link (section 4.3).
14. Guest counterparties, so a deal can run with a club that isn't a member (section 5.1, option 2).
15. A generated agreement from the agreed terms, then e-signature.
16. Squad planning: renewals, age profile, squad rules.

**Later**
17. Deeper match data and a wage source (section 8.3).
18. Full personal terms; swaps; a player's view; agent tools.
19. The AI features in section 9.3, starting with scout reports from voice and similar players.

**Open already:** PR #77 needs its three fixes before merging.

---

## 11. How this was checked

**Read:** `PRODUCT_SPEC.md`, `IMPLEMENTATION_STATUS.md`, the roadmap and the Q4 phased plan, the business and persona documents, the operations and security documents.

**Checked against the code:** deployment files (`Dockerfile`s, `entrypoint.sh`, `railway.json`, `docker-compose.yml`), settings, sign-in and password rules, rate limiting, file storage, the scheduler and WebSocket manager, the scouting, stats and player models, the AI endpoints and analyst tools, the enrichment adapters, the admin endpoints, and the route list.

**Checked on Railway (read-only):** the list of volumes and the names of the backend's settings. No secret values were read or printed.

**Counted on the local database:** players, valuations, contracts, transfers, injuries and competitions. Railway's data wasn't queried; the docs say it has 11 competitions.

**Not done:**
- No vendor, competitor or pricing research; section 8.3 is from general knowledge and needs confirming.
- No load, security or accessibility testing.
- No conversations with real club staff; section 4 is a reasoned walk-through, not user research. A pilot would replace it.
- Railway's backup settings, region and which builder is in effect weren't verified.
- Club budgeting and finance were left out on request.

## Related documents

- [`../PRODUCT_SPEC.md`](../PRODUCT_SPEC.md)
- [`../IMPLEMENTATION_STATUS.md`](../IMPLEMENTATION_STATUS.md): the known gaps this review builds on
- [`../feature_spec/phased-plan-2026-q4/README.md`](../feature_spec/phased-plan-2026-q4/README.md): the plan from the 3 October review
- [`../operations/environments-and-deployment.md`](../operations/environments-and-deployment.md)
