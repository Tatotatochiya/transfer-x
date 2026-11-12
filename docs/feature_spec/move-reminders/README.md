---
title: "Move reminders: chase a stalled transfer, and escalate when it stays stuck"
last_updated: 2026-11-12
status: Implemented 2026-11-12
owner: "TODO — assign a Product Owner"
---

# Move reminders

**The problem.** A transfer stalls when the person whose move it is doesn't move. That can be the
other club not answering an offer or an enquiry, a club not doing its paperwork, an agent not
proposing his commission, or a player not answering personal terms. Today TransferX shows
"3 days without movement" on the status card and nothing else. The waiting side can only write a
message, which arrives at the same priority as everything else. The one automatic escalation
(`check_deal_sla_breaches`) covers only a confirmed deal 14 days past its completion deadline.

**Goal.** The waiting side can send a formal reminder to whoever holds the move: in-app, email and
phone push, with a fixed, factual wording and a record on the timeline. If reminders are ignored,
the next one escalates to the people who can unblock it. Gentle automatic reminders go out at 3
and 7 days, so nobody has to remember to chase. No behaviour of the transfer itself changes.

---

## 1. Decisions

- **D1. Covers every open transaction.** Open offers (`SENT`, `COUNTERED`), deals in progress
  (`IN_PROGRESS`, `PENDING_COMPLETION`) at any stage, and open enquiries.
- **D2. The server decides who is holding the move** (`reminders/service.waiting_on`). It mirrors
  the status cards (`dealStatus.ts`, `offerStatus.ts`) and never trusts the client. The holder is
  one of:
  - a **club**: the other club in an offer or enquiry, a club with paperwork outstanding, the
    buying club answering a commission or preparing personal terms;
  - an **agent**: proposing or re-proposing his commission, answering personal terms for his
    client;
  - a **player** with a TransferX account, answering his personal terms.
- **D3. Who can send.** A member of a party club whose role can trade (`MARKET_WRITE`), when the
  holder is someone else. The deal's agent can remind a club (for example, a buying club that
  hasn't answered his commission). Players don't send reminders; staff don't, and non-parties
  don't. A read-only view-as session can't send.
- **D4. When.** The button appears once the move has been with the holder for **24 hours**
  (measured from the last movement: the deal's, offer's or enquiry's `updated_at`). After a
  reminder, the next one from the same side waits **48 hours**.
  - Deadline days: when the current transfer window closes within 72 hours, both shorten, to
    **2 hours** and **12 hours**.
- **D5. Escalation.** A reminder escalates when the holder has already ignored **two** reminders
  for this move, or the move has been waiting **7 days**. Reminders are counted since the last
  movement, automatic ones included. "Escalate" adds people and stronger wording; the holder is
  always told too.

  | Holder | First reminders go to | An escalation also tells |
  |---|---|---|
  | A club | The club's usual recipients (owner, sporting directors, managers) | The club's owner and sporting directors by name in the wording ("needs a decision from the club"). This is the top of the club, so there's no one further to add |
  | An agent | The agent | The player, if he has an account (it's his transfer), and the other club, so it knows why the deal isn't moving |
  | A player | The player | His agent if he has one, otherwise the selling club |

- **D6. Automatic reminders.** At **3 days** and **7 days** without movement, the holder gets a
  reminder from TransferX ("Sent by TransferX"). The 7-day one escalates, by D5. Each is sent once
  per move: a movement resets the clock. The waiting side sees "TransferX reminded them on …".
- **D7. Fixed wording, optional note.** The message is built by the server from facts:
  "Tottenham is waiting for your commission proposal on L. Hall (£34.5M) · 3 days". The sender may
  add a note of up to 200 characters, shown in quotes. No free-form subject, no capital letters for
  urgency.
- **D8. On the record.** Every reminder is an audit event on its transaction (`MOVE_REMINDER`,
  `MOVE_ESCALATED`), so the deal timeline shows "Tottenham sent Sofia Reyes a reminder". Both sides
  see that a reminder was sent and when; the note is visible to both.
- **D9. Rate limits are the server's.** A request inside the cooldown, from a non-party, or when
  it's the sender's own move is refused with a sentence saying why.
- **D10. Notification preferences still apply** to in-app, email and push. Reminders are two new
  types, `MOVE_REMINDER` and `MOVE_ESCALATED`, on by default for all three, in the "Your move" push
  tier.

### Not doing

- A public "slow responder" score or a ranking of clubs or agents.
- Reminding someone who can't act: a role without trading rights, or a club when the move is the
  agent's.
- SMS, or calling anyone.
- Changing the deal's or offer's state. A reminder never moves, expires or collapses anything.

---

## 2. Data

New table `move_reminders` (migration `0111`):

| Column | Type | Notes |
|---|---|---|
| `id` | uuid | |
| `subject_type` | `offer` / `deal` / `enquiry` | |
| `subject_id` | uuid | |
| `move_key` | string(80) | What was being waited for, e.g. `deal:AGENT_NEGOTIATION:propose-commission`. Shown in wording; groups counts |
| `holder_kind` | `club` / `agent` / `player` | |
| `holder_id` | uuid | Club id, agent profile id or player id |
| `sender_user_id` | uuid, null | Null for an automatic reminder |
| `sender_club_id` | uuid, null | The club that sent it (null for an agent or TransferX) |
| `escalated` | bool | |
| `automatic` | bool | |
| `note` | string(200), null | |
| `created_at` | timestamptz | |

Index on `(subject_type, subject_id, created_at)`. Notification types `MOVE_REMINDER`,
`MOVE_ESCALATED` (to the holder) and `MOVE_STALLED` (to the people told on an escalation) are added
to `notificationtype` (`MOVE_STALLED` in migration `0112`, since `0111` had already shipped). All
three are in `EMAIL_ENABLED_TYPES`.

## 3. API

- `GET /reminders/{subject_type}/{subject_id}` → `ReminderState`, for a party (or the agent):
  - `holder`: `{ kind, name }` or null when nobody else holds the move;
  - `waiting_since`, `can_send` with `reason` when not ("You reminded them 5 hours ago. You can send
    another from 14:30.", "It's your move.");
  - `next_allowed_at`, `would_escalate`;
  - `last`: the latest reminder (`at`, `by` "Tottenham" / "TransferX", `escalated`, `note`).
- `POST /reminders/{subject_type}/{subject_id}` with `{ note? }` → `ReminderState`. Sends now, or
  `409` with the reason.

Both return `404` to anyone who isn't a party, so an offer's existence isn't revealed.

## 4. Interface

- **Status card** (deal, offer, enquiry) when the tone is "waiting" and `can_send`: a quiet
  secondary button **"Send a reminder"** (or **"Escalate"** when `would_escalate`). It opens a
  small sheet: the exact message they'll get, an optional note, and "Send reminder". Afterwards the
  card's meta reads "Reminder sent today" and a toast says who was told.
- When a reminder can't be sent yet, the button isn't shown; the meta says "Reminded {date}".
- **Lite**: the sent-offer page ("Waiting on Chelsea") gets **"Remind them"**, with the same sheet in
  Lite's sizes.
- **Timeline**: reminders and escalations show as events with the note.
- **Colour** (TOKENS.md colour roles; `components/transfer/ReminderBadges.tsx`). The words say the
  step, the colour says how serious it is:

  | Who sees it | State | Badge |
  |---|---|---|
  | The waiting side | Waiting 3+ days, not yet reminded | Amber "Stalled · N days" |
  | | Reminded, still fresh | Grey "Reminded" |
  | | Reminded and stalled, or escalated | Amber "Reminded" / "Escalated" |
  | The holder (being chased) | Reminded or escalated | Red "Reminded" / "Escalated", with who and the note; no button |
  | Told on escalation (an agent's player, the other club) | `MOVE_STALLED` notification | Amber "Transfer stuck" + "Escalated" |

  Never red on the waiting side (nothing is needed from them). The Board's cards and the
  Dashboard's working panels carry the same badges: amber "Stalled" on cards waiting on the other
  side, red "Reminded"/"Escalated" on the club's own-move cards it has been chased about
  (`BoardCard.chased`).
- **Notifications page and email**: the fixed wording, a link to the transaction, and for an
  escalation the line "This is the third reminder" or "This has been waiting 7 days".

## 5. Success criteria

- [ ] `waiting_on` names the right holder for every waiting row of the deal and offer status
      tables, and for enquiries; unit-tested row by row.
- [ ] A party can send after 24 hours, not before; a second from the same side waits 48 hours; on
      deadline days 2 and 12 hours.
- [ ] The third reminder, or one after 7 days, escalates to the people in D5.
- [ ] Automatic reminders at 3 and 7 days, once per move; a movement resets them.
- [ ] Non-parties get 404; a party whose move it is, or whose role can't trade, gets 409 with a
      reason.
- [ ] Every reminder is an audit event and appears on the deal timeline.
- [ ] Email and push go out through the existing notification pipeline and respect preferences.
- [ ] Backend and frontend tests pass.

---

## 6. As built (2026-11-12)

Branch `move-reminders`, on top of `type-and-colour` (PR #70). Backend `app/reminders/`
(`models.py`, `service.py`, `router.py`), migration `0111`, the hourly `move_reminders` job;
frontend `components/transfer/MoveReminder.tsx`, on the deal and offer status cards, the enquiry
page and Lite's sent page.

Checked on the running stack: Chelsea reminded Man City about the £30M offer for D. Mukasa from the
offer page; the reminder was recorded, Man City got the notification, and the email arrived in
Mailpit with the fixed wording.

### Deviations

- **D10** no longer says escalations can't be turned off in-app: preferences apply to both types,
  like every other notification.
- **The email carries the fixed sentence, not the note.** The note is in the in-app notification,
  the push body, the deal timeline and on both sides' status cards. The notification email has no
  body field today.
- **Confirmed deals have no reminders.** Completion already has its own deadline and escalation
  (`check_deal_sla_breaches`).
- **"Either club can act" moves** (moving a deal on from Agreement, or on from personal terms once
  the player agreed) hold both clubs, so neither can remind the other; the automatic reminders
  still go to both.
- **Automatic reminders skip anything idle more than 30 days**, so switching the job on doesn't
  chase abandoned transactions.
- **An offer's clock** is its latest send, counter or raise (offers have no `updated_at`); a message
  doesn't count as movement. A deal's is `updated_at`, an enquiry's `updated_at`.
- **In a demo** ([demo mode](../demo-mode.md#house-clubs-answer-on-their-own), 2026-11-13) a
  reminder can go straight away, one a minute, and the house answers it at once; the automatic
  reminders skip demo transactions, which a reset would otherwise leave reminders behind for.
- **Times in reasons** ("You can send another from 14:30") are UK time.

### Not checked

- Lite's "Remind them" on a real phone, and the escalation emails to a player and the other club on
  the running stack (covered by tests).
