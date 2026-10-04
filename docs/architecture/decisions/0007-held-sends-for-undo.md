---
title: "ADR 0007: Held Sends for Undo"
last_updated: 2026-10-03
status: Accepted
owner: "TODO — assign a Technical Lead"
---

# ADR 0007: Held Sends for Undo

## Context

Lite mode (docs/feature_spec/lite-mode) lets a director confirm a bid, a counter, an acceptance or a refusal from one card. Before L6 the confirm called the offer endpoints directly, so a mistaken tap reached the other club at once. Withdrawing an offer after the other club has been notified is visible to them, and in a negotiation that's embarrassing.

Undo has to happen before anything is sent, which means a new state-changing mechanism: an action that exists but has not happened yet.

## Decision

1. **A confirmed Lite action is held, not sent.** `POST /lite/actions` stores a `held_actions` row (`HELD`, `execute_at = now + 10s`) and returns at once. `POST /lite/actions/{id}/undo` cancels it while it is still held; afterwards it answers 409.
2. **Nothing happens while it is held:**
   - no notification, email or websocket event;
   - no budget reservation;
   - no approval capture.

   Undoing leaves no trace for the other club. The person's own audit trail records that it was held and cancelled.
3. **Problems show at confirm time.** The hold runs the endpoint's own rules without its side effects:
   - window open, one open offer per player, no deal in progress;
   - `offers.service.check_new_offer`;
   - party and turn;
   - over budget unless an approval would capture it, using `assist.check_offer_terms`.

   The endpoints themselves notify and email, so they can't be dry-run.
4. **The normal endpoint sends it.** An executor (`main.py`, every 2 seconds, one instance at a time) takes due rows with `FOR UPDATE SKIP LOCKED`. It calls the offers router function as the user who confirmed it, so the action takes the full-app path: guards, approval capture, reservation, notifications, `ai_assisted` audit.
   - Capability dependencies don't run on a direct call, so the executor checks `MARKET_WRITE` (and buyer access for a bid) itself.
   - The row is marked `EXECUTED` in the same transaction the endpoint commits. An undo racing the executor waits on the row lock, then finds it sent.
   - If the endpoint refuses because something changed in the ten seconds, the row ends `FAILED` with the endpoint's reason, and the Sent screen says so.
5. **Not the assistant.** Held actions are created only by a person's confirm (ADR 0006). The assistant can propose an action, which opens the card; it can't hold or send one.

## Consequences

- An action reaches the other club 10–12 seconds after the tap rather than at once. That's the price of undo.
- Validation runs twice, at hold and at send. The second, authoritative check can still refuse, so the UI must show a failed send, not assume success.
- `held_actions.channel` is `APP` now. L8 (decisions from email) will hold with `EMAIL`, and may use a longer window.
- `held_action.*` audit events record what was held, cancelled, sent or refused, and by whom.
