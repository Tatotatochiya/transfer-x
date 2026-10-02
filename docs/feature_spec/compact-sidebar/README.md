---
title: "Compact sidebar"
last_updated: 2026-10-02
status: Active
owner: "TODO — assign a Product Owner"
---

# Compact sidebar

The design handoff is [`HANDOFF.md`](./HANDOFF.md) (option 1a in the HTML reference). The desktop sidebar was 1,074px tall for a club (1,159px with Admin), so on a 13-inch laptop (about 790px of page) Club and the footer sat below the fold. Rows drop to 32px with bare icons, Notifications becomes a bell in the logo row, and the footer becomes one account menu. Groups, labels, order, badges and gating are unchanged. This file records the decisions taken at review (2026-10-02), which override the handoff where they disagree.

## Decisions

1. **"Notification settings" links to `/account#notifications`.** The handoff pointed it at the page that renders `NotificationPreferencesPage`, but that page had no route and was deleted in PR #20; the notification settings live on Account settings. The section has `id="notifications"`, and the page scrolls to it as the cards above it load.
2. **Escape in the account menu stops there.** The drawer's focus trap also listens for Escape on the document; without stopping it, one Escape inside the drawer would close the menu and the drawer together.
3. **The menu's keyboard handling is built, not copied.** Lite's `ProfileMenu` has Escape and outside click only. This one also has arrows, Home and End, focuses the first item when opened from the keyboard, returns focus to the button on Escape, and closes on Tab and on route change.

Also:

- `Icon` gains `chevron-up`. It points up while the menu is closed, since the menu opens upwards.
- The menu items' row height is `min-h-12 lg:min-h-9`; the handoff's `min-h-9 lg:min-h-9 min-h-12` contradicted itself.
- The stale comment saying the nav had no `overflow-y-auto` is corrected; the class stays, and focus outlines are inset.
- The account button's second line is the staff role, or the account type when there is none, plus a Staff pill for TransferX staff. The old card showed the account type and the staff role together.

## Progress

- **2026-10-02, built** (branch `compact-sidebar`):
  - `Sidebar.tsx`: logo row with the bell (`NotificationBell`, also used in `AppShell`'s top bar), compact rows, the account menu.
  - `Icon.tsx`: `chevron-up`. `AccountSettingsPage.tsx`: the `#notifications` anchor.
  - Tests: `Sidebar.test.tsx` (14).
  - Checked in Chrome:

    | Account | Window | Height | Nav scrolls? |
    |---|---|---|---|
    | Club | 1440 × 790 | 705px | no |
    | Admin | 1440 × 790 | 771px | no |
    | Club | 1024 × 700 | 705px | yes, cleanly |

    - "Transfers in progress" fits on one line.
    - The drawer at 768px and 375px has 48px rows and a 48px account button, and the top-bar bell is 44px.
    - Escape in the drawer's menu leaves the drawer open.
    - Light and dark theme.
    - At 200% zoom a 1280px window is 640px wide, so the drawer applies; covered by the 768px and 375px checks.
