---
title: "ADR 0006: The AI Assistant Advises From Server-Scoped Facts, and Never Acts"
last_updated: 2026-09-27
status: Accepted
owner: "TODO — assign a Technical Lead"
---

# ADR 0006: The AI Assistant Advises From Server-Scoped Facts, and Never Acts

## Context

AI help was extended from scouting (squad analysis, player fit, market recommendations, natural-language search) to every step of a transfer. The new features, all in `backend/app/ai/assist.py`:

- **Offers:** the offer advisor, the negotiation summary, and rule checks on offer terms.
- **Deals and the club:** a deal's next steps, and the morning briefing on the Dashboard and in the daily email.
- **Selling:** the pricing assistant, and "Who might want him?".
- **Everywhere:** Ask TransferX.

These features touch money and confidential negotiation state: rival bids, a masked buyer's identity, and each club's budget. A language model given the wrong facts would leak them. A model that invents a number would give a club false confidence.

## Decision

1. **The server builds every fact the model sees, scoped to the viewing club.** It uses the same visibility rules as the page the club is on:
   - a club's budget only for that club;
   - competing offers only for the selling club, which already sees them in its order book;
   - an anonymous buyer only as "an undisclosed club";
   - other clubs' squads, but never their budgets.

   The model never queries data itself.
2. **TransferX computes the figures, and the model phrases them.** Our code works out:
   - gaps against the fee model, budget headroom and deadlines;
   - guide prices, from the model and comparable completed transfers;
   - which club made each negotiation move;
   - a deal's outstanding steps and who owns each.

   Model output is checked before it is shown:
   - suggested counter terms are limited to known fields, within half to double of the figures in the facts;
   - club ids in "Who might want him?" must be candidates we supplied;
   - Ask TransferX links must be paths that appear in the facts.
3. **It advises; the club acts.** No assistant endpoint changes state. A suggestion is applied through the normal confirmed form: "Use these terms" opens the counter form pre-filled, and "Use £X" fills the listing's guide price. When one is used, the server writes an `AI_SUGGESTION_USED` audit event. Lite mode's action card (`docs/feature_spec/lite-mode`, L4) is also this normal confirmed form. It only describes the action; the user's confirm calls the existing offer endpoints, with `ai_assisted: true` when an assistant suggestion filled it in.
4. **Features that don't need a model work without one.** The terms checker, a deal's steps, the guide price and the candidate clubs are all computed in code. Without an API key the UI hides the model-only features, and the digest email goes out without its briefing.
5. **Answers are cached against the state they describe** (an offer's last action, a deal's steps, the day), and only a cache miss counts against the user's hourly AI limit.

## Consequences

- New assistant features must build their facts in `assist.py` from scoped queries, never pass a whole ORM object or another club's data, and validate anything the model returns that becomes a number, link or id.
- The prompts live in `ai/prompts.py`, where admins can override them. The shared `SYSTEM_ADVISOR` prompt states that only the given figures may be used; an override must keep that rule.
- The cache and the rate limit are in memory, so they reset on restart and aren't shared between API processes. This is acceptable at current scale; a multi-process deployment would need a shared store.
