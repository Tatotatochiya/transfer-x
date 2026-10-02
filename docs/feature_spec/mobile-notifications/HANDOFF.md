# Handoff: Mobile notifications (Web Push)

Written against `Tatotatochiya/transfer-x` `main` on 2026-10-02. Latest migration at the time of writing: `0087_player_history`. Check the head before adding a revision.

## Overview

TransferX notifications today are in-app (bell plus a WebSocket `NOTIFICATION` refresh) and email (`EMAIL_ENABLED_TYPES` plus the daily digest). Nothing reaches the phone lock screen. This feature adds:

1. **Web Push** to phones and desktops, including iPhone and iPad once TransferX is added to the Home Screen.
2. **Three tiers** (Your move, Heads-up, FYI). Each tier decides sound, timing, quiet hours and the app badge.
3. **Decision-ready content**: a title and body that name the player, the club, the amount and the deadline. A tap deep-links to a single decision sheet.
4. **Replace, don't pile up**: one notification per subject (offer, auction, thread, deal).
5. **Install and permission flow**: a soft ask at a useful moment, an iPhone-only "Add to Home Screen" guide, and push settings.

## About the design files

`TransferX - Mobile Notifications.dc.html` is a **design reference built in HTML**. Open it in a browser. Don't ship it. Rebuild it in the existing frontend (React 19, Vite, Tailwind 4, TanStack Query, `components/ui/*`) and backend (FastAPI, SQLAlchemy async, APScheduler, Alembic), following their existing patterns.

The canvas has five sections:

- **1** Principles
- **2** Tiers
- **3** Notification-type catalogue
- **4** Phone renderings (iPhone lock screen, Android shade, decision sheet)
- **5** Setup (soft ask, iPhone install guide, settings)

## Fidelity

- **Notification content and behaviour are final**: titles, bodies, actions, tiers, grouping and timing. Build to this spec.
- **Lock-screen and Android-shade renderings are illustrative.** The operating system draws these. We control only title, body, icon, badge, actions, tag, sound and the URL a tap opens.
- **In-app screens are high-fidelity in layout and copy**: decision sheet, soft ask, install guide and settings. Use the app's existing tokens and components (`Card`, buttons, `MiniToggle`, `--color-*`), not the literal hex values in the mock.

---

## 1. Platform facts that shape the build

- **Android (Chrome, Edge, Samsung Internet) and desktop**: standard Push API through a service worker. Action buttons work, up to 2 visible on Android.
- **iPhone and iPad, iOS/iPadOS 16.4 or later**: push only works for a web app **added to the Home Screen and opened from there**. Safari tabs and Chrome on iOS can't subscribe. Permission must be requested from a user gesture.
- **iOS/iPadOS 18.4 or later** supports **Declarative Web Push**: a JSON payload (`"web_push": 8030`) that iOS displays without waking the service worker. It is more reliable, and send both shapes (§5.3).
- **Treat action buttons as Android and desktop only.** On iOS the design never depends on them: a tap opens the decision sheet. Test on a real iPhone before relying on buttons there.
- **EU iPhones** (iOS 17.4 or later under the DMA) may not get standalone Home Screen apps or push. Email stays the fallback, and the settings screen must say when push is unavailable.
- **App badge**: `navigator.setAppBadge(n)` works in installed web apps on iOS 16.4 or later and on Chromium. Feature-detect it.

## 2. Tiers

Every `NotificationType` maps to exactly one tier. Put the map in code, not the database (`app/notifications/tiers.py`), so it can change without a migration.

| Tier | Delivery | Sound | Quiet hours | Badge | Fallback |
|---|---|---|---|---|---|
| `YOUR_MOVE` | Immediately | Yes (`silent: false`) | Held until quiet hours end, **unless the subject's deadline is under 2 hours away** | Counts | Email after 30 min if the notification is still unread (§6.3) |
| `HEADS_UP` | Immediately | No (`silent: true`) | Held until quiet hours end | Doesn't count | None |
| `FYI` | **No push** | n/a | n/a | Doesn't count | In-app list. Counted in the morning summary push |

Tier map for the current enum:

- **YOUR_MOVE**: `OFFER_RECEIVED`, `OFFER_COUNTERED`, `APPROVAL_REQUESTED`, `DEAL_PERSONAL_TERMS_SENT`
- **HEADS_UP**: `OUTBID`, `OFFER_EXPIRING`, `AUCTION_ENDING`, `AUCTION_BID_RECEIVED`, `OFFER_MESSAGE`, `NEGOTIATION_MESSAGE`, `ENQUIRY_RECEIVED`, `ENQUIRY_REPLIED`, `OFFER_ACCEPTED`, `OFFER_REJECTED`, `AUCTION_BID_ACCEPTED`, `DEAL_COLLAPSED`, `DEAL_SLA_BREACHED`, `SALE_REOPENED`, `INSTALMENT_DUE`, `RELEASE_CLAUSE_TRIGGERED`, `LOAN_RECALLED`
- **FYI**: `OFFER_WITHDRAWN`, `DEAL_COMPLETED`, `DEAL_SELL_ON`, `DEAL_AGENT_INVITED`, `DEAL_PAPERWORK`, `DEAL_CLAUSE_TRIGGERED`, `PERSONAL_TERMS_DECISION`, `PLAYER_AVAILABLE`, `SYSTEM_BROADCAST`, `VERIFICATION_APPROVED`, `VERIFICATION_REJECTED`, `REPRESENTATION_STARTED`, `REPRESENTATION_REVOKED`, `REPRESENTATION_EXPIRED`, `CLIENT_ALERT`, `STAFF_INVITATION`, `APPROVAL_DECIDED`, `LOAN_STARTED`, `LOAN_ENDING_SOON`, `LOAN_ENDED`, `LOAN_CONVERTED`
- `DAILY_DIGEST` is a preference only, as today. It now also controls the morning summary push (§6.2).
- If the Lite mode handoff's `LITE_QUESTION` lands, it goes in `HEADS_UP`.

Add a unit test that fails if any `NotificationType` member is missing from the map.

## 3. Notification content

### 3.1 Data model change

`Notification.message` is one string, but push needs a title and a body. Add nullable columns to `notifications`:

| Column | Type | Notes |
|---|---|---|
| `title` | `String(120)`, nullable | Push title. Falls back to `message` |
| `body` | `String(240)`, nullable | Push body. Falls back to `null` (title only) |
| `group_key` | `String(120)`, nullable, indexed | The subject this is about: `offer:{id}`, `sale:{id}`, `thread:{id}`, `deal:{id}`, `approval:{id}`. Used as the push `tag` |
| `deadline_at` | timestamptz, nullable | The subject's reply-by or end time. Drives the quiet-hours bypass |
| `actions_json` | JSON, nullable | List of `{action, title, url}`, max 2 (§3.3) |

Extend `create_notification(...)` and `notify_club(...)` with matching keyword arguments, all optional. Call sites keep working unchanged. Update the call sites for the types in §3.2 first. Every name of a buying club **must go through `_masked()`**.

Add `title`, `body`, `group_key` and `deadline_at` to `NotificationResponse` too, so the in-app list can show the same text.

### 3.2 Copy per type

Write in British English. Money is formatted the way the app already formats it (`£18m`, `£19.5m`, `£850k`). Times are in the recipient's timezone (§4): weekday plus 24-hour time ("Fri 18:00") within 7 days, otherwise "3 Oct". "N hours left" is used when under 24 hours.

| Type | Title | Body | Actions (Android/desktop) | Tap opens | `group_key` |
|---|---|---|---|---|---|
| `OFFER_RECEIVED` | `Offer for {player}: {amount}` | `{club} · your valuation {valuation} · reply by {deadline}` (drop the valuation part if there is none) | `Ask for {valuation}` · `Open` | Decision sheet, offer | `offer:{id}` |
| `OFFER_COUNTERED` | `{club} countered at {amount}` | `{player} · up/down from {previous} · {n} hours left to reply` | `Accept {amount}` · `Open` | Decision sheet, offer | `offer:{id}` |
| `APPROVAL_REQUESTED` | `Approve a {amount} bid for {player}?` | `{requester}, {role} · budget after {budget_after}` | `Approve` · `Open` | Decision sheet, approval | `approval:{id}` |
| `AUCTION_ENDING` | `1 hour left on the {player} auction` | Seller: `Highest bid {amount} from {club} · {n} bids`. Bidder: `Your bid {amount} · highest {amount}` | `Open` | Auction page | `sale:{id}` |
| `OUTBID` | `You've been outbid on {player}` | `{club} bid {amount} · ends in {remaining}` | `Bid {next_step}` · `Open` | Bid sheet, prefilled with the next increment | `sale:{id}` |
| `NEGOTIATION_MESSAGE`, `OFFER_MESSAGE` | `{sender} ({role})` | First 120 characters of the message | `Reply` · `Open` | Negotiation thread, composer focused | `thread:{id}` |
| `DEAL_PAPERWORK` and other FYI types | the existing message | the next step, if known | none | Deal progress | `deal:{id}` |
| Morning summary (§6.2) | `{n} thing(s) waiting on you` | `{k} offers and {j} approval · first deadline {deadline}` | `Open` | Dashboard, waiting on you | `digest` |

The mock uses this sample data:

- Marcus Webb, Ashfield United, £18m offer, £21m valuation, reply by Fri 18:00
- Ashfield United countered at £19.5m
- Joel Okafor, £4.2m bid, requested by Sam Reid (Head of Recruitment), budget after £9.8m
- Yannick Sorel auction, £6.5m highest bid from Castlebrook, 6 bids
- Theo Marsh: outbid by Northgate at £3.4m, next bid £3.6m
- Dan Okoro (agent)

Types not listed in the table get `title = message`, no body and no actions until their call sites are updated.

### 3.3 Actions never change state on their own

This follows ADR 0006 and the Lite mode email-confirm pattern. A push action button **only navigates**. It opens the decision sheet with the chosen action pre-selected, and the user confirms there with the normal form. Nothing is accepted, countered or approved from the lock screen.

Action URLs:

- `/offers/{id}?from=push&action=counter&amount={pennies}`
- `/offers/{id}?from=push&action=accept`
- `/approvals/{id}?from=push&action=approve`
- `/sales/{id}?from=push&action=bid&amount={pennies}`
- `/negotiations/{thread}?from=push&action=reply`

Use the app's real routes. These are the shapes, not literal paths.

### 3.4 Replacing older notifications

- Push `tag = group_key`, with `renotify: true` for `YOUR_MOVE` only. A newer event for the same subject replaces the old one on the lock screen.
- Don't de-duplicate in-app rows. They stay as history.
- **Hourly jobs must not re-push.** `_notify_expiring_offers` runs hourly with a 24-hour window, so today it can fire repeatedly for the same offer. Before sending, check `push_deliveries` (§5.1): if this `(user_id, type, group_key)` was pushed within the last 20 hours, skip the push. Still create the in-app row only if the existing behaviour does.

## 4. Preferences

### 4.1 Tier-level (new)

Add to the existing `user_preferences` table (migration `0085`):

| Column | Type | Default |
|---|---|---|
| `push_your_move` | enum `SOUND`/`SILENT`/`OFF` | `SOUND` |
| `push_heads_up` | enum `SOUND`/`SILENT`/`OFF` | `SILENT` |
| `push_summary` | bool | `true` (the morning summary push) |
| `summary_local_time` | `time` | `08:00` |
| `quiet_hours_enabled` | bool | `true` |
| `quiet_start` / `quiet_end` | `time` | `22:00` / `07:00` (wraps midnight) |
| `timezone` | `String(64)` IANA | `Europe/London`. Set from `Intl.DateTimeFormat().resolvedOptions().timeZone` on subscribe |

Extend `GET/PATCH /users/me/preferences` with these fields.

### 4.2 Per-type (existing table)

Add `push_enabled: bool default true` to `notification_preferences`, next to `enabled` and `email_enabled`. Push sends only when `enabled AND push_enabled AND` the tier setting isn't `OFF`. Extend `NotificationPreferenceItem` and `NotificationPreferenceUpdateRequest` with `push_enabled`.

## 5. Backend: Web Push

### 5.1 Tables

`push_subscriptions`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `user_id` | UUID FK users, cascade | indexed |
| `endpoint` | `Text`, unique | |
| `p256dh`, `auth` | `String(200)` | |
| `platform` | enum `IOS_HOME_SCREEN`/`ANDROID`/`DESKTOP`/`OTHER` | sent by the client |
| `user_agent` | `String(300)` | shown as the device label |
| `created_at`, `last_success_at`, `last_failure_at` | timestamptz | |
| `failure_count` | int default 0 | |

`push_deliveries` (de-duplication, the 30-minute email fallback, and metrics)

| Column | Type |
|---|---|
| `id` | UUID PK |
| `notification_id` | UUID FK notifications, nullable (null for the summary) |
| `user_id` | UUID |
| `type` | `notificationtype` |
| `group_key` | `String(120)` |
| `status` | enum `SENT`/`HELD`/`SKIPPED_DUPLICATE`/`FAILED` |
| `send_after` | timestamptz (quiet hours) |
| `sent_at` | timestamptz, nullable |
| `opened_at` | timestamptz, nullable (§5.4) |

Indexes: `(user_id, type, group_key, sent_at)` and `(status, send_after)`.

### 5.2 Endpoints (under the existing `/notifications` router)

- `GET /notifications/push/public-key` returns `{ key }`, the VAPID public key in base64url.
- `POST /notifications/push/subscriptions` takes `{ endpoint, keys: {p256dh, auth}, platform, timezone }`. Upsert on `endpoint`, and update `user_preferences.timezone`.
- `DELETE /notifications/push/subscriptions` takes `{ endpoint }`.
- `GET /notifications/push/subscriptions` lists this user's devices for settings: `{ id, platform, label, created_at, last_success_at }`.
- `POST /notifications/push/test` sends "Notifications are working" to the device whose `endpoint` is in the body.
- `POST /notifications/{id}/opened` is called by the service worker on `notificationclick`. It sets `opened_at` and marks the notification read.

Settings: `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_SUBJECT` (`mailto:`). Without them, push is skipped and logged, the same way `_send_sync` skips without `SMTP_HOST`.

### 5.3 Sending

New module `app/notifications/push.py`, using the `pywebpush` library.

- `create_notification` already fires the WebSocket push and the email with `asyncio.create_task`. Add `maybe_send_push(notification_id)` the same way. It opens its own session and must never share the request's session.
- Steps:
  1. Resolve the tier and preferences.
  2. Apply quiet hours: if inside them and not (`YOUR_MOVE` with `deadline_at` under 2 hours away), write a `HELD` delivery with `send_after = quiet_end`.
  3. Check for duplicates (§3.4).
  4. Send to each subscription.
- Payload. Send both shapes in one message. iOS 18.4 or later uses the declarative keys. Every other browser's service worker reads `notification` and ignores `web_push`.

```jsonc
{
  "web_push": 8030,
  "notification": {
    "title": "Offer for Marcus Webb: £18m",
    "body": "Ashfield United · your valuation £21m · reply by Fri 18:00",
    "navigate": "https://app.transferx…/offers/{id}?from=push&nid={notification_id}",
    "tag": "offer:{id}",
    "silent": false,
    "lang": "en-GB",
    "app_badge": "3",
    "actions": [
      { "action": "counter", "title": "Ask for £21m", "navigate": ".../offers/{id}?from=push&action=counter&amount=2100000000&nid=…" },
      { "action": "open", "title": "Open", "navigate": ".../offers/{id}?from=push&nid=…" }
    ],
    "data": { "nid": "…", "tier": "YOUR_MOVE" }
  }
}
```

- `app_badge` is the recipient's current `waiting_on_you` count from `dashboard_service.get_dashboard`, the same source as the digest. Omit it for users who aren't club members. Recompute it per send, and cache it per user for 60 seconds.
- Use web push `urgency: "high"` for `YOUR_MOVE` and `"normal"` otherwise, and `TTL: 86400`. With `topic = group_key` (hashed to 32 characters or fewer, URL-safe), the push service drops an older undelivered message for the same subject.
- On a `404` or `410` response, delete the subscription. On other errors, increment `failure_count`, and delete after 5 consecutive failures.

### 5.4 Scheduler jobs (add in `main.py` next to the existing jobs)

- `release_held_pushes`, every 5 minutes: send `HELD` deliveries whose `send_after` has passed. If the notification is already read, mark it `SKIPPED` instead.
- `send_morning_summaries`, every 15 minutes: for each user with `push_summary` on, at or after `summary_local_time` in their timezone and not yet sent today, send the summary push if `waiting_on_you` isn't empty. Record a delivery with `group_key = "digest"` so it sends at most once per local day. The email digest is unchanged.
- `email_fallback`, every 5 minutes: §6.3.

## 6. Interaction with email

### 6.1 Unchanged

Per-type `email_enabled`, `EMAIL_ENABLED_TYPES` and the daily digest email all stay as they are for users without a push subscription.

### 6.2 Morning summary

The morning summary is a push version of the digest. It uses the same `waiting_on_you` list and the same "only when something is waiting" rule. The `DAILY_DIGEST` preference switches both: if `enabled` is false, neither is sent.

### 6.3 Email fallback for `YOUR_MOVE`

When a user has at least one active push subscription and the type is `YOUR_MOVE`, don't send the immediate email. Record the delivery instead. `email_fallback` sends the existing email 30 minutes after `sent_at` if the notification is still unread. Users without push get the email immediately, exactly as today.

## 7. Frontend

### 7.1 Installable app

- `public/manifest.webmanifest`:
  - `name` "TransferX", `short_name` "TransferX"
  - `start_url` "/dashboard?source=homescreen", `scope` "/", `display` "standalone"
  - `theme_color` and `background_color` from the light theme surface
  - icons at 192 and 512 px PNG, plus a 512 px maskable icon
- `index.html`:
  - `<link rel="manifest">`
  - `<link rel="apple-touch-icon" href="/apple-touch-icon.png">` at 180 × 180
  - `<meta name="apple-mobile-web-app-title" content="TransferX">`
  - `<meta name="theme-color">`
- Icons: render from the existing `public/tx.svg` on a solid brand background. **Assets to produce**: 180, 192 and 512 px, and 512 px maskable with a 20% safe zone.
- `public/sw.js`, a hand-written service worker. No Workbox is needed, and it does no caching.
  - `push`: if `event.data.json().notification` exists, call `showNotification(title, {body, tag, renotify, silent, actions, data, icon: "/icons/192.png", badge: "/icons/badge-72.png"})`. If `app_badge` is present, call `navigator.setAppBadge`.
  - `notificationclick`: choose the URL from `event.action` (match it against `actions[].navigate`, otherwise use `navigate`). Focus an existing TransferX client and `navigate()` it, or `clients.openWindow(url)`. Also `fetch('/api/notifications/{nid}/opened', {method:'POST', credentials:'include'})`. Check how `lib/api.ts` authenticates: if it uses a bearer token in memory, put a short-lived signed token in `data` instead.
  - `pushsubscriptionchange`: re-subscribe and POST the new subscription.
- Register the service worker in `main.tsx` after load, only when `'serviceWorker' in navigator`.

### 7.2 Push client (`src/lib/push.ts`)

```ts
type PushState =
  | "unsupported"          // no Notification/PushManager
  | "needs-install"        // iOS/iPadOS Safari tab, not standalone
  | "default"              // can ask
  | "granted-subscribed"
  | "granted-unsubscribed" // permission ok, no subscription on this device
  | "denied";
```

- Detect iOS with `/iPad|iPhone|iPod/` or `navigator.maxTouchPoints > 1 && /Macintosh/`. Detect standalone with `matchMedia('(display-mode: standalone)').matches || navigator.standalone`.
- `subscribe()` must run **inside the click handler**. It calls `Notification.requestPermission()`, then `pushManager.subscribe({userVisibleOnly: true, applicationServerKey})`, then POSTs the subscription.
- Expose a `usePushState()` hook with TanStack Query key `["push","state"]`.
- On app focus (`visibilitychange`), refetch the badge count and call `navigator.setAppBadge(count)`, or `clearAppBadge()` when the count is 0.

### 7.3 Screens

**5a — Soft ask (bottom sheet).**

- **When**: the first time a club member sees a `YOUR_MOVE` notification in-app (bell or WebSocket event), on a viewport under 1024 px, with `PushState` of `default` or `needs-install`. Never on the first session.
- **Copy**:
  - Title: "Get offers on this phone"
  - Body: "{club} just made an offer for {player}. We can tell you about the next one straight away, so you can reply before the deadline." When there's no subject: "We can tell you straight away when an offer or approval needs you, so you can reply before the deadline."
  - Two lines: "• Offers and approvals: straight away" and "• Everything else: one morning summary"
  - Primary button: "Turn on notifications". Text button: "Not now".
- **"Not now"**: store `push_ask_dismissed_at` in localStorage. Ask again after 14 days, at most 3 times. The settings entry point always stays available.
- **Primary button**: if `needs-install`, open 5b. Otherwise call `subscribe()`, then show a toast: "Notifications are on for this phone".
- **If permission is denied**: replace the sheet body with "Notifications are blocked for TransferX. Turn them on in your phone's Settings, then come back." and a "Close" button. Don't retry.
- **Layout**: overlay at 35% black over the app. The sheet has 26 px top radius, 22 px 20 px 26 px padding, a 12 px gap, and a 40 × 5 grabber. Title 20/700, body 14/1.5 muted, buttons full width 48 px tall, 12 px radius.

**5b — iPhone install guide.** Full-screen sheet, iOS/iPadOS Safari only (`needs-install`).

- Title: "Add TransferX to your Home Screen"
- Lead: "iPhone only sends notifications to web apps opened from the Home Screen. It takes three taps."
- Numbered steps (28 px circles, accent-subtle fill):
  1. "Tap Share" — "The square with an arrow, in Safari's bar"
  2. "Tap Add to Home Screen" — "Scroll down the list if you can't see it"
  3. "Open TransferX from your Home Screen" — "Then tap Turn on notifications"
- At the bottom, a pointer to Safari's toolbar: "Share is in the bar below ↓". On iPad, Share is at the top right, so flip the pointer.
- On first launch in standalone mode (`?source=homescreen` and no subscription), show 5a immediately, without the 14-day rule.

**4c — Decision sheet.**

- **When**: on viewports under 640 px, when the URL has `from=push`. Offer, approval and sale detail pages render this compact layout instead of the full page. A "See full details" link at the bottom opens the normal page. On wider screens, the normal page opens with the matching action pre-selected.
- **Header**: a back chevron, and "Waiting on you · {i} of {n}" (from `waiting_on_you`). Swiping or "Next" goes to the next item.
- **Overline** (12/700 uppercase, `--color-danger-text` when under 24 hours, otherwise muted): "Offer received · 2 days left"
- **Content**: player name 22/700, then "{club} offered {amount}" 14 muted.
- **2 × 2 facts card**:
  - Their offer
  - Your valuation
  - Reply by (danger-text if under 24 hours)
  - Budget if accepted, as "£22m → £40m" in success-text, from the Lite §4 money block
- **Buttons, bottom, stacked**:
  - Primary: "Ask for {valuation}"
  - Secondary: "Accept {amount}"
  - Destructive text button: "Turn down"
  - Note below: "You can undo for 10 seconds after sending."
- **Behaviour**:
  - The pre-selected action from `action=` gets focus but **is not sent**.
  - Confirming calls the existing offer, approval or bid endpoints. Reuse the Lite held-action and undo flow if it has shipped. Otherwise confirm with the existing dialog.
- **Error states**:
  - If the subject changed since the push (status no longer actionable), show: "This has changed since we told you: {new status}." and a "See what happened" link.
  - If the user can't see the subject (different club, removed from staff), show the existing 403 page.

**5c — Notification settings.** Add an **"On this phone"** card at the top of `NotificationPreferencesPage`, above "Daily summary".

- Tier rows, each with a coloured dot and an "Edit" control (a segmented control or select with Sound, Silent, Off):
  - "Your move" — "Straight away, with sound"
  - "Heads-up" — "Straight away, silent"
  - "FYI" — "Morning summary at 08:00", where the time can be edited
- Quiet hours: a toggle, "22:00 to 07:00" (editable), and the helper "Deadlines under 2 hours still come through."
- This device: the platform label (for example "iPhone · Home Screen app") with status On, Off or Blocked, and a "Send a test notification" link.
- Other devices: a list with "Remove".
- If `PushState` is `needs-install`, show the 5b entry point. If `unsupported`, show: "This browser can't show notifications. You'll still get email."
- In the per-type table, add a third column, **Push**, next to In-app and Email, using the same `MiniToggle`. For FYI types, the Push toggle is disabled, with the tooltip "Included in the morning summary".

### 7.4 Tier colours (tokens from `design_handoff_transferx/TOKENS.md`)

- Your move: `--color-danger` (`#c53637`)
- Heads-up: amber (`oklch(70% 0.15 70)` in the mock). Use the app's warning token if one exists.
- FYI: muted (`#98a2b3`)

## 8. Analytics

Write an `AuditEvent` for each of these:

- `push_subscribed` (platform)
- `push_unsubscribed`
- `push_ask_shown`
- `push_ask_dismissed`
- `push_install_guide_shown`

`push_deliveries` gives sent to opened time per type. The success measure is the median time from `OFFER_RECEIVED` to the first response, compared with users who have email only.

## 9. Tests

**Backend:**

- Every enum member appears in the tier map.
- Quiet hours: held, then released, including the window that wraps midnight and the under-2-hour bypass.
- The de-duplication window stops the hourly `OFFER_EXPIRING` from re-pushing.
- A `410` response deletes the subscription.
- The payload contains both the declarative and the classic shape.
- Club names are masked in titles and bodies.
- Email fallback: sent only if the notification is unread after 30 minutes, and only for users with a subscription.
- The morning summary is sent at most once per local day and skipped when nothing is waiting.
- Preference combinations (`enabled`, `push_enabled`, tier `OFF`).

**Frontend** (vitest + msw):

- `PushState` detection matrix, including iOS Safari tab, iOS standalone, Android and denied.
- The soft-ask frequency rules.
- The decision sheet renders from `from=push&action=counter` with the action focused but not sent.
- The settings Push column, including FYI disabled.

**Manual:** a real iPhone (Home Screen app, iOS 18.4 or later), Android Chrome, and desktop Chrome and Safari.

## 10. Order of work

1. Migration: the `notifications` columns, `user_preferences` push fields, `notification_preferences.push_enabled`, `push_subscriptions` and `push_deliveries`.
2. `tiers.py`, `push.py`, the endpoints and the VAPID settings.
3. Manifest, icons, `sw.js` and `lib/push.ts`.
4. Settings card (5c) and the Push column. This makes it testable end to end.
5. Copy builders and call sites for the 7 types in §3.2.
6. Soft ask (5a) and the install guide (5b).
7. Decision sheet (4c).
8. Quiet hours, morning summary and email fallback jobs.

## Files

- `TransferX - Mobile Notifications.dc.html`: the design reference (sections 1–5). Open it in a browser. It needs `support.js` next to it.
- Related: `design_handoff_lite_mode/` (email decisions, held actions and undo, the money block) and `design_handoff_transferx/TOKENS.md` (colour tokens).
