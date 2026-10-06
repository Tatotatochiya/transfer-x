---
title: "Ask TransferX as an analyst and executive assistant"
last_updated: 2026-10-04
status: Draft (for review)
owner: "TODO — assign a Product Owner"
---

# Ask TransferX as an analyst and executive assistant

## 1. What we want

A sporting director should be able to ask anything they'd ask an analyst or an executive assistant, in their own words, and get a correct, sourced answer in seconds:

- "Show me the players who've had interest in the last 7 days."
- "Show me 5 midfielders who are transfer listed."
- "Left-backs under 24, under £10m, contract ending next summer."
- "Who are our highest earners whose contract ends within 18 months?"
- "How much have we committed this window, and how much is left?"
- "Which offers are waiting on us, and which expire this week?"
- "Compare Isak and Watkins on goals per 90 this season."
- "What happened on our transfers this week?"
- "Draft a reply to Leeds saying we'd take £21m."
- "Remind me on Friday to chase Brighton about De Cuyper."

## 2. Why today's Ask can't do this

Ask TransferX (`/ai/ask`, `app/ai/assist.py: ask`) sends the model one fixed snapshot of the club's own data: budget, open offers, deals, listings, enquiries, the squad and a list of pages. The model answers only from that snapshot. So:

- **Anything beyond the club's own data fails.** "Midfielders who are transfer listed" needs other clubs' listings, and they aren't in the snapshot.
- **Anything over time fails.** "Interest in the last 7 days" needs dated history (enquiries, offers, bids, shortlist adds). The snapshot only holds what's open now.
- **Filtering, counting and sorting are done by the model.** Over a long list that is slow, costly and error-prone, and the snapshot grows with the club.

## 3. How it would work

The model stops reading a snapshot and starts **asking TransferX questions through a fixed set of read-only tools**. Each tool is ordinary server code, scoped to the asking club, enforcing the same visibility rules as the app's pages. The model chooses tools and filters; TransferX runs them, counts and sorts; the model words the answer around the results.

```
Question ──► model (with the tool catalogue)
               │  picks: search_players(position=MID, listed=true, limit=5)
               ▼
           TransferX runs the tool as the user's club
           (permissions, masking, wage privacy applied in code)
               │  returns rows + totals + "as of"
               ▼
           model ──► answer text + blocks (table, metric, chart)
               │
               ▼
           TransferX checks it (figures and names must come from tool
           results; links must be ones the tools returned) ──► user
```

- **Tool use, not SQL.** The model never writes queries. A typed tool catalogue is safer (no data outside the club's view can be reached), testable, and keeps every visibility rule in one place. It also lets us say precisely what the assistant can answer.
- **A short loop.** At most 4 tool calls per question (for example: find the players, then fetch stats for those 5). Each tool returns at most 50 rows plus the total, so the model sees "showing 5 of 23".
- **It still never acts** (ADR 0006). Tools only read. Requests to do something produce a proposal the user confirms on the normal form or Lite action card, as today ("bid £8m for X").
- **ADR 0006 is updated, not replaced.** Decision 1 ("the server builds every fact; the model never queries data itself") becomes "the model may call read-only, server-scoped tools; it still never reads data directly".

## 4. What it can answer: the tool catalogue

Status: **Ready** means the data exists; **Needs data** means something new must be recorded first.

### 4.1 Market (other clubs' players)

| Tool | Filters | Example | Status |
|---|---|---|---|
| `search_players` | position, age, nationality, league, club, foot, height, contract ends before/after, listed (sale open), available for loan, asking price / fair value range, form, minutes, injured, free agent | "5 midfielders who are transfer listed", "left-backs under 24 under £10m" | Ready |
| `get_player` | id or name | "Tell me about Annous" (profile, contract end, fair value, form, injuries, listing) | Ready |
| `compare_players` | 2–4 players, metrics | "Compare Isak and Watkins on goals per 90" | Ready (stats coverage varies by league) |
| `search_listings` | type (open to offers, auction), loan or transfer, price, deadline, position | "Auctions ending this week" | Ready |
| `recent_transfers` | league, position, fee range, period | "Biggest Premier League fees this window" | Ready (completed transfers on TransferX and imported history) |
| `comparable_transfers` | player, or position/age/fee | "What have similar centre-backs gone for?" | Ready (the pricing assistant's comparables) |

Other clubs' wages are never returned: the public wage estimate is shown, as on the player page.

### 4.2 Our club

| Tool | Example | Status |
|---|---|---|
| `squad` (position, age, contract end, wage, valuation, minutes) | "Highest earners whose contract ends within 18 months" | Ready |
| `money` (budget, reserved, committed, spent, wage room, instalments due) | "How much is left this window?" | Ready |
| `approvals` | "What's waiting for my approval?" | Ready |
| `loans` (in and out, recall dates, options) | "Who have we got out on loan, and when do they return?" | Ready |
| `team_activity` (from the audit log, own club only) | "What did the team do this week?" | Ready |

### 4.3 Our transfers (the board, as data)

| Tool | Example | Status |
|---|---|---|
| `transfers` (side, stage, whose move, deadline, counterparty, period) | "Which offers are waiting on us and expire this week?" | Ready (the board service) |
| `history` (outcome, period, side) | "Deals that collapsed this year, and why" | Ready (board history) |
| `conversation` (one transfer) | "What did Leeds last say about Bogle?" | Ready (the conversation service, same visibility) |

### 4.4 Interest and demand

"Interest" for the asking club's own players, over a period:

| Signal | Who sees what | Status |
|---|---|---|
| Enquiries received | the asking club (masked if anonymous) | Ready |
| Offers and bids received | the asking club (masked if anonymous) | Ready |
| Added to other clubs' shortlists | a **count only**, never which clubs | Ready (shortlist items are dated) |
| Profile views by other clubs | a **count only** | **Needs data:** views aren't recorded. Count player-page views per club per day (from analytics events, or a small `player_views` table) |

Tool: `interest_in_my_players(period, signal?)`. For example, "Show me the players who've had interest in the last 7 days" returns a table: player, enquiries, offers and bids, shortlist adds and (once recorded) views, linked to each.

Market-wide demand ("which players are clubs chasing?") would leak competitive information. If offered at all, show it as a band (High / Some / None), only where at least 3 different clubs are involved. **Decision needed (§10).**

### 4.5 Performance

| Tool | Example | Status |
|---|---|---|
| `player_stats` (season, per 90, ratings, form, minutes) | "Our midfielders by minutes this season" | Ready (coverage depends on the API-Football leagues synced) |
| `injuries` (current, history, days out) | "Who's injured, and when are they back?" | Ready |
| `fixtures` | "Our next 5 games" | Ready |

### 4.6 Executive assistant

| Capability | Example | Status |
|---|---|---|
| Briefings | "Brief me on today", "Summarise the week" | Ready (the morning briefing, extended to a week) |
| Drafts | "Draft a reply to Leeds saying we'd take £21m" | Ready (drafts go into the conversation box for the user to send) |
| Explain | "Why is Annous's fair value £3m?", "What does an obligation to buy mean here?" | Ready (fair value inputs, deal terms) |
| Reminders and follow-ups | "Remind me Friday to chase Brighton about De Cuyper" | **Needs data:** a `reminders` table and a job that notifies (in-app, push, email) on the day, linked to the transfer |
| Saved questions and alerts | "Every Monday, send me listed left-backs under £10m", "Tell me when one is listed" | **Needs data:** saved questions (rerun on a schedule into the morning summary) and alerts (event-driven) |
| Meeting notes | "Summarise these notes and add the actions as reminders" | Later: pasted text in, reminders out |
| Calendar and email | "Book a call with Leeds' director next week" | Later, via connectors. Out of scope for now |

## 5. What the answer looks like

The model returns structured blocks, not just prose:

- **Text:** 1–3 sentences answering the question.
- **Table:** rows from a tool, with the columns that matter for the question. Player rows show the photo and link to the profile; offer and deal rows link to them. Sortable, with "Showing 5 of 23 · Show all".
- **Metric:** a single figure with its context ("£14.2m left of £40m").
- **Chart:** only for trends or comparisons (minutes by month, two players' per-90 numbers).
- **Sources line:** which data, with what filters, as of when: "Players listed on TransferX, midfielders, sorted by fair value, as of 09:14". A "Filters used" toggle shows them exactly.
- **Follow-ups:** 2–3 suggested next questions ("Only under 25", "Compare the top 3", "Ask Sam about them").
- **Actions:** export the table (CSV or Excel), save the question, pin it to the dashboard, or a proposal card when the user asked for an action.

Follow-up questions keep the conversation's context ("now only left-footed" filters the last table) for 30 minutes.

**Where it lives:**
- The full app gets an Ask page (`/ask`) with the thread and tables, and ⌘K opens it.
- Lite keeps its Ask screen with short answers, the top 3 rows and "See all".
- The board, player and offer pages get "Ask about this", which starts with that context.

## 6. Confidentiality: what no tool returns

Enforced in each tool's code, with a test per row:

| Never | Why |
|---|---|
| Another club's budget, finances or approvals | Commercial secret |
| Another club's contract wages | Shown only as the public estimate, as on the player page |
| Rival bids and offers on players the asking club doesn't own | Only the seller sees its order book |
| An anonymous buyer's or asker's identity | Masked as "an undisclosed club" until acceptance (ADR 0004) |
| Which clubs shortlisted or viewed a player | Counts only, and only for the club's own players |
| Another club's private deal notes, or the agent–player thread | Not theirs to read |
| Data from a club the user isn't a member of | Tools take the club from the session, never from the question |

Role rules follow the app: a scout sees what a scout can see today.

## 7. Making sure it's right

- **Figures come from tools.** The existing check (`keep_known_figures`) extends to tool results: a £ figure or count not in a result is dropped.
- **Names and links come from tools.** Every player, club and path in the answer must appear in a tool result.
- **"I don't know" is a valid answer.** If no tool covers the question, the answer says so, offers the nearest thing it can answer, and offers "Send to {Sam}" (Lite L7).
- **An evaluation set.** 150 real sporting-director questions with expected tool calls and answers, run on every prompt or model change. It covers each tool, the confidentiality rules (questions that try to get round them) and follow-ups.
- **Measured in use.** From `assistant_queries`:
  - answer rate (not a fallback);
  - links and exports used;
  - a thumbs up or down on each answer;
  - latency;
  - cost per question.
  The admin AI page shows them.

**Limits:**
- 4 tool calls and 50 rows per tool per question.
- A 20-second timeout.
- The existing per-user rate limit, with its own bucket.
- Answers cached for 10 minutes per user, question and data version.

## 7a. Known failure: the model's own football knowledge (found 2026-10-04)

**What happened.** Signed in as Chelsea, in ⌘K: "place 8m bid on Havertz". The answer:

> "K. Havertz is already in your squad, so you can't bid for him. If you meant to offer him to another club, he isn't listed for sale. Your transfer budget remaining is £111.9m, so an £8m bid would be affordable if a target existed."

Havertz is under contract with **Arsenal** on TransferX (active contract to 30 June 2030). He played for Chelsea from 2020 to 2023.

**Why.** Investigated without code changes:

1. **The data was right.** The squad sent to the model is `Player.current_club_id == Chelsea`, which doesn't include Havertz. He wasn't in the facts at all.
2. **The model answered from its own training.** With the player missing from the facts, it used what it "knew": an out-of-date club. The prompt says "answer only from these facts", but nothing checks claims about players who aren't in them.
3. **"He isn't listed for sale" was unfounded.** The only listings in the snapshot are Chelsea's own, so the model reasoned from the wrong list.
4. **⌘K has no action path.** In the full app, Ask never prepares an action. Only Lite mode resolves "bid £8m for X" on the server: it finds the player, his club and any listing, and returns a card to confirm (`bid_from_question`, `resolve_proposal`). In ⌘K the request fell through to free text.

**What the new design must guarantee:**

- **Every player named is resolved by a tool.** Before the model says anything about a player, it calls `get_player` or `search_players`. Squad membership comes only from the `squad` tool. No tool result for a player means the answer says "I can't find K. Havertz on TransferX" and offers a search.
- **The check rejects unsupported claims.** Every player named in the answer must appear in a tool result. A claim about a player's club, contract or listing must match that result, or the answer is regenerated once and then replaced with a plain lookup ("K. Havertz: Arsenal, contract to 2030, not listed") built by code.
- **The prompt says so plainly.** "Your football knowledge is out of date. Transfers, clubs and contracts come only from TransferX's tools; never from memory."
- **Action requests work the same everywhere.** ⌘K, `/ask` and Lite all send "bid / offer / counter / accept / reject" through the server-side resolver. For this question as Chelsea that means:
  - Havertz belongs to Arsenal and isn't listed, so the answer is: "K. Havertz plays for Arsenal and isn't listed. Make Arsenal an offer of £8m?";
  - the card opens the offer form filled in (player, Arsenal, £8m) for the user to check and send;
  - nothing is sent from Ask (ADR 0006).
- **Listings are searched, not inferred.** "Is he for sale?" calls `search_listings` across the market, never just the club's own listings.
- **The evaluation set includes this case** and its variants:
  - Chelsea asking to bid for a player who used to be theirs (Havertz, Mount);
  - a player at the asking club;
  - a free agent;
  - a player at a club outside TransferX;
  - a misspelled name ("Havetz");
  - two players with the same surname.

**Interim fix, before Phase A: done 2026-10-06.** Small enough to do on its own:
- route ⌘K's action requests through the existing Lite resolver;
- add the "out-of-date knowledge" rule to `ASK_USER`;
- when a question names a player the facts don't contain, add a server lookup of that name to the facts.

Built as `mentioned_players` (facts key `players_named_in_the_question`), the prompt rule in `ASK_USER` and `ASK_LITE_USER`, a guard (`contradicts_lookup`) that replaces an answer calling another club's player the asker's own, and ⌘K proposals that open `/offers/new` filled in. Checked live as Chelsea:
- "is Havertz in our squad?" → "K. Havertz plays for Arsenal, under contract to June 2030, and isn't listed for sale."
- "place 8m bid on Havertz" → "£8m is too far from his price of about £18.9m to prepare."
- "place 18m bid on Havertz" → a £18m bid to Arsenal, opened on the offer form.

Tests: `tests/test_ask_grounding.py`.

## 8. Effort and build order

| Phase | What | Size |
|---|---|---|
| **A. Foundation** | The interim fix from §7a first. Then the tool-use loop and checks (including §7a's player-claim check); the answer blocks (text, table, metric, sources); the `/ask` page and the ⌘K entry. Tools: `search_players`, `get_player`, `search_listings`, `squad`, `money`, `transfers`, `history`, `interest_in_my_players` (enquiries, offers, bids, shortlist adds). The evaluation set (first 60 questions). | L |
| **B. Depth** | `compare_players`, `player_stats`, `injuries`, `recent_transfers`, `comparable_transfers`, `loans`, `approvals`, `team_activity`, `conversation`. Charts, export, follow-ups with context, "Ask about this" on pages. Profile-view recording. | M–L |
| **C. Proactive** | Saved questions (scheduled into the morning summary), alerts ("tell me when…"), pinning to the dashboard, a weekly summary. | M |
| **D. Executive assistant** | Reminders and follow-ups, meeting-notes-to-actions, then calendar and email connectors. | M, then L |

Phase A alone answers both of the example questions in §1.

## 9. Cost and model

- A tool-use question costs roughly 2–3 model calls (choose tools, then write the answer). With a current Claude model and 50-row results, expect about 3–8p per question. That's comfortably inside the existing AI allowance at a director's volume (tens of questions a day).
- The model and prompts stay versioned and swappable (`app/ai/prompts.py`, `settings.llm_model`).

## 10. Decisions (2026-10-06)

1. **Market-wide demand: own players only.** Interest is shown only for the asking club's own players. Nothing is said about rivals' interest in other clubs' players.
2. **Profile views: recorded, as counts.** Each club's views of a player are counted per day (`player_views`). The player's own club sees how many clubs viewed him, never which.
3. **Reminders and saved questions: later.** Saved questions and alerts in Phase C, reminders in Phase D.
4. **Where it lives: a dedicated `/ask` page.** ⌘K keeps quick answers and hands off to `/ask` for tables. Lite keeps its Ask screen.
