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
