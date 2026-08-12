# Open decisions

Questions that need a human answer. Each says when it blocks work, and what happens if no one
answers — so nothing stalls waiting for a meeting.

## Blocking soon

### 1. The "whose move" derivation rule
**Blocks:** Session 4 (Dashboard), and everything after it.
**Question:** is the rule in `README.md` correct for every entity — offers, deals, listings,
auctions, approvals? Specifically: when a deal sits at `AGENT_NEGOTIATION` and the agent has gone
quiet, is that *your* move or *their* move?
**Default if unanswered:** treat agent silence as **your move** after 72 hours, on the grounds
that chasing is an action. Ship it behind the temporary `lib/whoseMove.ts` helper so it is
changeable in one place.

### 2. Roles and the dashboard
**Blocks:** Session 4.
**Question:** TransferX has club admins, managers, agents and platform admins. The redesigned
dashboard is drawn for a **sporting director at a club**. Do managers and agents get the same
four-tier dashboard with different content, or a different screen?
**Default if unanswered:** same four tiers, role-filtered content. A manager sees requests they
have raised rather than approvals they must grant; an agent sees their mandates. No new routes.

### 3. Does the dark theme survive as an option?
**Blocks:** Session 1 — building a token layer that supports two themes costs more than one that
does not, and it is expensive to retrofit.
**Question:** is the light theme a replacement, or does dark remain available as a preference?
**Default if unanswered:** **replacement.** No dark mode. Reintroducing it later is a contained
piece of work if the tokens are semantic, which they are.
**Decided (Phase 1, 2026-08-10):** the default was *not* taken — dark survives as a preference.
`index.css` carries a full dark set overriding all 50 tokens, and `context/ThemeContext.tsx`
persists the choice. Light remains the designed default: `TOKENS.md` specifies light only, and
the dark values are derived from the app's pre-redesign slate/emerald palette rather than
specified by the handoff. A Light/Dark control was added to Account Settings on 2026-08-12; until
then the mechanism had no UI and could only be switched from the console. **`prefers-color-scheme`
is deliberately not honoured** — dark has never been reviewed screen-by-screen against this spec,
so nothing should route a user there without them choosing it. Revisit once it has been.

## Blocking mid-project

### 4. Tables → cards on mobile
**Blocks:** Session 2 (the `ResponsiveTable` primitive).
**Question:** confirm the rule in `RESPONSIVE.md` — below 640px, tables become stacked cards
rather than scrolling horizontally. It costs more to build and means some columns are dropped
on phones.
**Default if unanswered:** proceed as specified. It is the right call for this audience.

### 5. Present-value calculation on negotiated terms
**Blocks:** the "effect on you" column in the deal room, Session 6.
**Question:** what discount rate should an instalment schedule be valued at, and who owns that
number — finance, or a platform-wide default?
**Default if unanswered:** show the nominal difference only, and omit the present-value line
until finance provides a rate. Do not invent a rate.

### 6. Squad minimums
**Blocks:** Session 8 — the "1 of 3 minimum" verdict lines.
**Question:** are position minimums league rules, club configuration, or a TransferX default?
**Default if unanswered:** club configuration with a sensible default (2 GK, 4 DEF, 4 MID, 3 FWD),
editable in club settings.

## Not blocking, but worth deciding

### 7. Notification alignment
The "whose move" state should drive notifications — if something becomes your move, that is
exactly when to email. Out of scope for these 13 sessions, but the field created in B1 is what
you would build it on. Worth confirming nobody duplicates the logic in the notification service.

### 8. What "Updated 2 minutes ago" means
The dashboard shows a freshness stamp. Confirm whether the data is polled, refetched on focus, or
websocket-driven, and make the stamp truthful. If it is TanStack Query's default staleness
behaviour, say "Updated just now" on focus refetch rather than a running clock.

### 9. Copy tone
The redesign uses neutral corporate naming ("Dashboard", not "War Room") per your earlier answer.
Two labels still carry personality and can be changed in one place if you want them flatter:
"Waiting on you" and "Everything in motion". Both are load-bearing — they explain the section —
so I would keep them.
