---
title: "Phase 0 runbook: deploy and test on real phones"
last_updated: 2026-10-03
status: Active
owner: "TODO — assign a Product Owner"
---

# Phase 0 runbook: deploy and test on real phones

These are the two Phase 0 items that need someone with Railway access and real phones. Everything else in Phase 0 is in the code.

## 1. Deploy to Railway

What's going out: PRs #20–#24 (already on `main`), and the Phase 0 PR once merged. The API's entrypoint runs `alembic upgrade head` on start, so deploying migrates the database. Deploys are **not** automatic on push: start one by hand, and check afterwards.

### Before the deploy: set the push keys (once per environment)

Generate the keys anywhere the backend code runs (locally is fine; the keys aren't tied to a machine):

```sh
docker compose exec api python scripts/generate_vapid_keys.py
```

On Railway → the **API** service → Variables, add the three lines it prints:

| Variable | Value |
|---|---|
| `VAPID_PUBLIC_KEY` | the printed public key |
| `VAPID_PRIVATE_KEY` | the printed private key (keep it secret) |
| `VAPID_SUBJECT` | `mailto:` plus an address you read, e.g. `mailto:ops@yourdomain` |

Use **new** keys for Railway; don't reuse the ones in your local `.env`. Changing them later cuts off every subscribed phone until it turns notifications on again.

### Deploy

1. Deploy the **API** service from `main`. New dependencies (`pywebpush`, `openpyxl`) install from `backend/pyproject.toml` during the build.
2. Deploy the **frontend** service from `main` (the service worker, icons and new pages ship with it).
3. Watch the API's deploy log for:
   - `Running upgrade 0087 -> 0088` and so on, through `0092`;
   - `Import OK`;
   - `Uvicorn running`.

### Check it worked

| Check | How | Expect |
|---|---|---|
| Migration head | Railway → Postgres → Query: `select version_num from alembic_version;` | The latest migration on `main` |
| Push is on | Open `https://backend-production-ace3.up.railway.app/notifications/push/public-key` | `{"key": "B…"}`, not `null` |
| Admin health | Sign in as the admin → Health | Phone notifications shows "0 devices subscribed" (set up, no phones yet); Scheduled jobs shows "Running …" |
| Audit log | Admin → Audit log | Opens; Export to Excel downloads a file |

If **Email** shows "Not set up" on Health, that's expected: Railway has no SMTP yet (see `operations/environments-and-deployment.md`). Password reset links and staff invitations are then shown on screen to copy.

## 2. Test on real phones

Use two club accounts on Railway, e.g. **liverpool** (receives) and **leeds** (sends). The password for both is in the demo environment notes.

### iPhone or iPad (iOS/iPadOS 18.4 or later)

1. Open the Railway front end in **Safari**, sign in as liverpool.
2. Account settings → "On this phone" shows **"Add TransferX to your Home Screen first"**. Tap "Show me how" and follow the three steps (Share → Add to Home Screen).
3. Open **TransferX from the Home Screen** (not Safari). Sign in again if asked. The "Get offers on this phone" sheet should appear on first launch; tap **Turn on notifications** and allow.
4. Account settings → "On this phone" now shows the device as **On**. Tap **Send a test notification**; it should arrive within seconds, also on the lock screen.

### Android (Chrome)

1. Open the front end in Chrome, sign in as liverpool, Account settings → **Turn on notifications** → Allow.
2. **Send a test notification**.

### The real flows (on either phone)

| # | Do | Expect on liverpool's phone |
|---|---|---|
| 1 | As leeds (on a computer), make an offer for a Liverpool player | Within seconds: **"Offer for {player}: £Xm"**, then the buyer, liverpool's valuation if one is set, and "reply by …". On Android, buttons "Ask for £Ym" and "Open". |
| 2 | Tap the notification | The **decision sheet**: "Waiting on you · 1 of n", the time left, the facts, and Accept / Ask for / Say no |
| 3 | Tap Ask for, confirm | The Sent screen with **Undo · 10s**. Tap Undo: "Cancelled. Nothing was sent." Leeds sees nothing. |
| 4 | Confirm again and let the 10 seconds pass | Leeds gets **"Liverpool countered at £Ym"** (on leeds's phone, if subscribed) |
| 5 | Account settings → Quiet hours: set the start to a minute ago; have leeds message on the offer | No push now. It arrives when quiet hours end (set the end a few minutes ahead to see it). |
| 6 | Account settings → Hide amounts on the lock screen → on; repeat 1 | The notification says only **"New offer received · Open TransferX to see the details."** |
| 7 | Next morning, after the summary time (08:00 by default), with something waiting | One **"N things waiting on you"** push |
| 8 | Sign out on the phone | Account settings on another device shows the phone gone from Other devices |

Afterwards, withdraw the test offers as leeds.

### If something doesn't arrive

- **Admin → Health → Phone notifications:** does it count the device?
- **iPhone:** check iOS Settings → Notifications → TransferX → Allow Notifications, and that the app was opened from the Home Screen.
- **Android:** check Chrome's site settings for the front-end address → Notifications: Allow.
- Note the time and the account, and check the API log for `Push for notification … failed`.

Record the result in the phased plan's Progress section: date, phones and iOS/Android versions, and any step that failed.
