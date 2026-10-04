---
title: "Mobile notifications (Web Push)"
last_updated: 2026-10-02
status: Active
owner: "TODO — assign a Product Owner"
---

# Mobile notifications (Web Push)

The design handoff is [`HANDOFF.md`](./HANDOFF.md), with the HTML reference. It adds phone and desktop pushes (iPhone once TransferX is on the Home Screen), three tiers that decide sound, timing and quiet hours, pushes that name the player, club, amount and deadline, and a soft ask, install guide and settings. This file records the decisions taken at review (2026-10-02), which override the handoff where they disagree.

## Decisions

1. **"Hide amounts on the lock screen"** (`user_preferences.push_hide_amounts`, off by default). When on, a push says only what happened ("New offer received", "Open TransferX to see the details."): no figures, club names, player names or message text, and no action buttons (their labels carry figures). The handoff showed the offer and the club's private valuation on the lock screen with no way to hide them.
2. **Safer quiet-hours rule.** A "your move" push breaks through quiet hours when its deadline falls **before quiet hours end plus an hour**, not only when it is under 2 hours away. Under the handoff's rule an offer arriving at 23:00 that expires at 03:00 was held until 07:00, after it had expired. Heads-up pushes always wait.
3. **The hourly reminders tell each person once**, in-app as well as by push. Before this, `notify_upcoming_events` (hourly) re-sent "Your offer is expiring soon" every hour for the offer's last 24 hours, and "Instalment due" every hour from three days before the due date for as long as it stayed unpaid. Each is now sent once per person per subject (`create_notification(..., group_key=..., once=True)`); an instalment gets one more when it goes overdue. Rows from before this change have no `group_key`, so each open subject gets one more notification after deploy, then no more.

Also decided while building:

- **Pushes are sent after the commit**, from a session `after_commit` hook, never from inside the request. The handoff's `create_task` from `create_notification` would race the commit (the task could miss the row) and could push something the request then rolled back.
- **The repeat check is for the scheduled reminders only** (`OFFER_EXPIRING`, `AUCTION_ENDING`, `INSTALMENT_DUE`). Applied to every type, the handoff's 20-hour window would have dropped a genuine second counter-offer on the same offer.
- **The service worker reports a tap with a token in the push**, good for that one notification. It can't use the login: the access token lives in the page's memory.
- **A device belongs to whoever subscribed on it last.**
- **Corrections to the handoff:**
  - Amounts in action URLs are in pounds; the app has no pennies.
  - There is no `/approvals/{id}` page (approvals are at `/club/approvals`), and negotiation threads live at `/deals/{id}`.
  - `frontend/public/` and `tx.svg` don't exist yet, so the icons are made from scratch.
  - "Undo for 10 seconds" waits for Lite L6.

## Phases

1. Backend: tiers, migration `0088`, `push.py`, endpoints, VAPID settings, quiet hours with the release job, repeat check, the once-only reminders.
2. Frontend setup: manifest, icons, `sw.js`, `lib/push.ts`, the "On this phone" settings card and the Push column.
3. Content and asking: the push wording for the 7 types, one shared buyer-masking helper, the soft ask and the iPhone install guide.
4. The decision sheet, then the morning summary and the email fallback.

## Progress

- **2026-10-02, phase 1 built** (branch `mobile-notifications`):
  - `app/notifications/tiers.py`: the tier map and the hidden-amounts wording.
  - `app/notifications/push.py`: the decision (tier, settings, repeat check, quiet hours), the payload (declarative and classic in one), sending with `pywebpush`, device clean-up (404/410, or 5 failures), the open token, and `release_held_pushes` (every 5 minutes).
  - Endpoints under `/notifications/push/*` and `POST /notifications/{id}/opened`. `/users/me/preferences` carries the push settings, and `/notifications/preferences` carries `push_enabled` and each type's tier.
  - `scripts/generate_vapid_keys.py`.
  - Tests: `tests/test_push.py` (27).
  - Not yet sent from a real device: that needs phase 2's service worker.
- **2026-10-02, phase 2 built:**
  - `frontend/public/`: `manifest.webmanifest`, the icons (192, 512, maskable 512, Apple touch 180, a 72px monochrome badge, and `tx.svg`, which the favicon link already pointed at), and `sw.js`. The service worker shows pushes, opens the right page on a tap (an action button only opens its own page), and reports the tap with the push's token. It is registered as `/sw.js?api=<API base URL>`, since `public/` files aren't processed by Vite.
  - `src/lib/push.ts`:
    - push state detection, including `not-configured` when the server has no keys;
    - subscribe from the click, with the permission prompt first, as iOS requires;
    - unsubscribe, which runs on sign-out so the next person on a shared device doesn't get this person's pushes;
    - a once-per-page-load re-sync of this device's subscription (renews one the browser replaced, keeps the timezone current);
    - marking a push opened without the service worker (iOS 18.4+ declarative) as read;
    - the app badge from the Dashboard's "waiting on you".
  - **Settings, at `/account`:** the "On this phone" card and a Push column in the notification table (FYI disabled; disabled too while in-app is off, since there is then no notification to push).
    - Found while building: the full table with the Email column and the daily summary switch lived in `NotificationPreferencesPage`, which no route has reached since the first commit (`/notifications/preferences` redirects to `/account`). `/account` showed a 15-type in-app-only list, so nobody could turn off email or the digest. The account page now has the full table, and the dead page is deleted.
  - The FYI row says "not pushed" and has no morning-summary controls yet: the summary is phase 4.
  - Tests: `lib/push.test.ts` (state matrix, platforms, the opened-from-URL check), `NotificationTypesTable.test.tsx`, `PushSettingsCard.test.tsx`.
  - Checked end to end in desktop Chrome with Google's push service:
    - turning on saved the device ("Linux · Chrome");
    - the test push arrived;
    - an offer-received notification created on the server was pushed after commit and shown with its title, body, `offer:` tag and both buttons;
    - signing out removed the device on the server and in the browser.
  - Not yet checked on a real iPhone or Android phone.
- **2026-10-02, phase 3 built** (branch `notifications-phase-3`):
  - **One masking rule**, `app/common/masking.py` (`buyer_is_masked`, `masked_name`, `buyer_name`). The order book, the assistant and the offer notifications now use it, instead of three copies.
  - **Push wording**, `app/notifications/copy.py`, at each place these are created:

    | Type | Title, body |
    |---|---|
    | Offer received | "Offer for {player}: £5m" · "{buyer} · your valuation £8m · reply by Fri 18:00". The buyer is masked while anonymous; a loan, free transfer or pre-contract is named as such. |
    | Counter, or the buyer raising | "{club} countered at £7m" · "{player} · up from £5m · 5 hours left to reply" |
    | Message on an offer | "{club} · {player}", then the message's first 120 characters |
    | Negotiation and deal-room messages | "{sender} ({role})", then the message |
    | Auction ending | "47 minutes left on the {player} auction". The seller sees the best bid and the number of bids; a bidder sees its own bid against the best. |
    | Outbid | "You've been outbid on {player}" · "Highest bid now £3.4m · ends in 50 minutes" |
    | Approval requested | "Approve a £4.2m offer for {player}?" (worded per kind of approval) · "{requester}, Manager · budget after £95.8m" |
  - **Deadlines** are tokens in the stored text (`{deadline}`, `{time_left}`, `{time_remaining}`), written out per recipient in their timezone when the push is sent and when the list is read. One notification can go to several staff in different timezones.
  - **Action buttons:**
    - "Ask for £8m" and "Accept £7m" open the Lite offer card with that action chosen. The card still asks once more before anything is sent.
    - "Bid £3.6m" opens the sale with the bid box filled (`?bid=`).
    - Messages get "Reply".
  - **In-app:** the list shows the new title and body, and the API gives each notification's tier.
  - **Soft ask** (`PushSoftAsk`), on phones and tablets for club members:
    - It appears when an unread "your move" notification arrives and this device can get notifications but doesn't.
    - Never in the first session; 14 days after "Not now"; at most three times.
    - The Home Screen app's first launch (`?source=homescreen`) asks straight away.
    - If permission is blocked, it says how to unblock it.
  - **Install guide** (`InstallGuide`): the three steps, with the Share pointer at the bottom on iPhone and top right on iPad. It opens from the soft ask and from Settings ("Show me how").
  - **Analytics:** `push_ask_shown`, `push_ask_dismissed` and `push_install_guide_shown` are recorded as click events.
  - **Tests:** `tests/test_push_copy.py` (23), `PushSoftAsk.test.tsx`, and the ask rules in `lib/push.test.ts`. The test suite now switches pushes off globally (`tests/conftest.py`): with VAPID keys in a developer's `.env`, every test commit used to start a real push task against the development database.
- **Deviations in phase 3:**
  - **Outbid** doesn't name the rival club, as the handoff's "{club} bid £3.4m" did. Bidders see the book anonymised, so naming the rival in a push would leak who is bidding.
  - **Approvals:** the requester is named by username and staff role, since users have no first name on record. The button is "Review", opening the approvals page; there is no page for one approval yet.
  - **The soft ask's second line** read "Everything else: in the app, when you look" until the morning summary existed; phase 4 restored the handoff's "Everything else: one morning summary".
  - **Deal paperwork and other FYI types** are never pushed, so their wording is unchanged.
- **2026-10-03, phase 4 built** (with Lite L6, branch `lite-l6-undo`):
  - **Decision sheet = the Lite offer card.** On a phone (under 640px), an offer push opens `/offers/{id}?from=push`, which goes to `/lite/offers/{id}?from=push`. It shows:
    - "Waiting on you · 1 of 3" with Next, through the Dashboard's waiting list;
    - "Offer received · 2 days left" (red under 24 hours);
    - your valuation and Reply by;
    - "Ask for £21m" (the counter is the club's own valuation when it's above the offer), Accept, Say no;
    - "You can undo for 10 seconds after sending.", and confirming holds the action (L6);
    - "See full details";
    - "This has changed since we told you: …" if the offer is no longer open.

    Wider screens open the normal offer page.
  - **Morning summary push** (`push.send_morning_summaries`, every 15 minutes):
    - one a day, at the person's chosen time in their timezone, only when something is waiting;
    - wording like "3 things waiting on you" · "2 offers and 1 approval · first deadline today 19:00";
    - it opens the Dashboard, or Lite home for Lite users;
    - turned off by its own switch (Settings: "FYI, and a morning summary", with the time), or by the Daily digest preference.
  - **Email fallback** (`push.send_email_fallbacks`, every 5 minutes; migration `0091`):
    - a "your move" email-type notification for someone whose phone will get the push waits 30 minutes (`notifications.email_due_at`), and is emailed only if still unread;
    - without a subscribed phone, or with push off for that type or tier, the email goes at once, as before.
  - **Tests:** `tests/test_push_phase4.py` (7) and `LiteOfferCardPage.test.tsx` (3).
- **Deviations in phase 4** (all closed 2026-10-04, Phase 3 of the Q4 plan):
  - ~~Approvals have no decision sheet~~: an approval push opens `/club/approvals?id={id}`, which on a phone goes to `/lite/approvals/{id}?from=push`. The sheet shows what is asked, who asked, the player, the budget after and the time left, with Approve (asks once more, since it carries the action out at once) and Decline (with an optional reason). Wider screens highlight that approval on the approvals page. `GET /clubs/me/approvals/{id}` serves it.
  - ~~Swiping isn't built~~: on a decision sheet opened from a push, swipe left for the next item and right for the previous one. "‹ Previous" and "Next ›" do the same.
  - ~~Wider screens don't pre-select the push's action~~: action buttons now open `/offers/{id}?action=counter&amount=…` (or `action=accept`). A phone goes on to the Lite card with that action ready; a wider screen opens the counter form filled in, or highlights Accept.
  - Also: **taps on iPhone are counted.** iOS opens declarative pushes without the service worker, so each push link carries the push's open token (`ot`). The page reports the tap, which marks it read and records `opened_at`, then removes `nid` and `ot` from the address bar.
  - Also fixed: the dashboard's approval items linked to `/approvals`, which isn't a page.
