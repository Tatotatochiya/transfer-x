# Handoff: Compact sidebar (option 1a)

Written against `Tatotatochiya/transfer-x` `main` on 2026-10-02. Scope: `frontend/src/components/layout/Sidebar.tsx` only, plus a small change to `AppShell.tsx` for the tablet and phone top bar. No backend changes.

## Overview

The desktop sidebar is about **1,056px** tall for a club account. On a 13-inch laptop Chrome shows about **790px** of page, so the Club group and the footer sit below the fold and the sidebar has to scroll.

Option 1a keeps the same groups, labels, order, badges and gating, and makes the sidebar about **705px** tall. It fits a 790px viewport with about 85px to spare, and still fits when the superuser-only Admin group appears.

Where the height goes today, and what changes:

| Today | Height | Change |
|---|---|---|
| 15 rows at 40px, each with a 28px icon tile | ~600px | Rows drop to **32px** on desktop, with a bare 16px icon and no tile |
| Footer: Lite mode, Settings and a three-line user card | ~173px | Becomes **one 44px account button** that opens a menu |
| Notifications row plus its 20px gap | 60px | Moves to a **bell button in the logo row** |
| 20px gaps between groups | 80px | Gaps drop to **12px** |
| 60px logo row | 61px | Drops to **52px** |

## About the design files

`TransferX - Navigation Options.dc.html` is a design reference built in HTML, not production code. Open it in a browser and look at section **1a**, which shows the laptop view at 1440 × 790 (cropped) with the account menu open, and the iPad drawer. Sections **Now**, 1b and 1c are context only.

Rebuild it in the existing `Sidebar.tsx` with the existing Tailwind tokens, `Icon` and `Avatar`. Don't copy the mock's hex values. The mock uses grey squares where the real `Icon` glyphs go.

## Fidelity

High-fidelity for sizes, spacing and structure. Colours are the existing tokens (§6).

## Rules that still apply (RESPONSIVE.md)

- **Labels are always visible.** There is no icon-only state at any width.
- At **1024px and wider** the sidebar is persistent and stays at **232px** wide.
- **Below 1024px** it stays an off-canvas drawer, 280px wide, with the **same content and labels** and **48px touch rows** (`min-h-12`). Focus trap, Escape, backdrop and body scroll lock stay as they are.
- Nav badges are a **count**, never a bare dot, in `bg-danger`.

---

## 1. Layout (1024px and wider)

```
┌──────────────────────────────┐ 232px, h-full, border-r border-border, bg-surface
│ [▣] TransferX          [🔔3] │ 52px logo row, border-b
├──────────────────────────────┤
│ HOME                         │ group label, 22px
│ ▢ Dashboard                  │ 32px row (active)
│ ▢ Transfers in progress   1  │
│ ▢ Enquiries                  │
│                              │ 12px gap
│ BUYING                       │
│ ▢ Browse Players · Listings · Shortlists · My Offers · Recent Transfers
│ SELLING                      │
│ ▢ My Listings · Offers Received  2
│ CLUB                         │
│ ▢ My Club · Finance · Team · Approvals  1
│              (flex-1)        │
├──────────────────────────────┤
│ (◉) Riverside Athletic    ⌃  │ 44px account button, border-t
│     Rob Hale · Sporting Dir. │
└──────────────────────────────┘
```

Height budget for a club owner or Sporting Director with every item visible:

- Logo row: 52px
- Nav padding: 10 + 10 = 20px
- Group labels: 4 × 22 = 88px
- Rows: 14 × 32 = 448px
- Gaps between groups: 3 × 12 = 36px
- Footer: 1 + 16 + 44 = 61px
- **Total: about 705px**

The Admin group adds 22 + 32 + 12 = 66px, about 771px in total. Keep `overflow-y-auto` on `<nav>` as the fallback for shorter windows. A comment in the file says the opposite, but the class is there and should stay.

## 2. Components

### 2.1 Logo row

- Wrapper: `flex h-[52px] items-center gap-2.5 border-b border-border pl-[18px] pr-3`
- Logo tile: `h-6 w-6 rounded-[7px] bg-accent` containing the `bolt` icon at `h-3.5 w-3.5 text-white`.
- Wordmark: `flex-1 text-[15px] font-bold text-text whitespace-nowrap`, linking to `/dashboard`.
- **Bell button** (authenticated users only). This replaces `NotificationNavItem`:
  - A `NavLink` to `/notifications`: `relative flex h-8 w-8 items-center justify-center rounded-lg ring-1 ring-inset ring-border text-text-secondary hover:bg-surface-inset`.
  - Active (`isActive`): `bg-accent-bg text-accent ring-accent/30`.
  - Icon `bell` at `h-4 w-4`.
  - Badge: keep the same query and badge as today (`["notifications","unread-count"]`, `refetchInterval: 300_000`). Position it `absolute -right-1.5 -top-1.5`, styled `h-4 min-w-[1rem] rounded-full bg-danger px-1 text-[11px] font-bold leading-none text-white`. Show 99+ above 99, and nothing at 0.
  - Accessibility: `aria-label` is `"Notifications"`, or `"Notifications, {n} unread"` when there are unread items. `title` is `"Notifications"`.

### 2.2 Nav

- Wrapper: `<nav className="flex-1 overflow-y-auto px-2.5 py-2.5 flex flex-col gap-3">`
- **Group label**: `flex h-[22px] items-center px-2 text-[11px] font-semibold uppercase tracking-[0.04em] text-text-muted`. Remove the label's `mb-1.5`, because the 22px height includes the spacing.
- **Group items**: a `flex flex-col` wrapper with no `space-y`, so rows sit flush.
- **`SidebarLink` row**:
  - Desktop: `flex items-center gap-2.5 rounded-[7px] px-2 h-8 text-[13.5px] font-medium no-underline transition-colors`
  - Touch (below 1024px): `min-h-12 lg:min-h-0 lg:h-8`. Keep the 48px drawer rows. On desktop use `lg:h-8`, not `min-h-0` with padding.
  - Icon: `<Icon name={item.icon} className="h-4 w-4 shrink-0" />`, with **no tile wrapper**. Colour is `text-text-muted` when idle and `text-accent` when active.
  - Label: `whitespace-nowrap`. Idle `text-text-secondary`, active `text-accent font-semibold`.
  - Row background: idle is transparent with `hover:bg-surface-inset`, active is `bg-accent-bg`.
  - Waiting badge: unchanged (`ml-auto`, same classes, same `aria-label`).
  - Focus: `focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-accent`, an inset outline so it isn't clipped by `overflow-y-auto`.
- "Transfers in progress" is the longest label. At 13.5px it fits in 232 − 20 − 16 − 16 − 10 = 170px with a badge. Check that it doesn't wrap. If it does, use 13px.

### 2.3 Footer: account button and menu

This replaces the "Switch to Lite mode" row, the "Settings" row and the user card.

- Wrapper: `border-t border-border px-2.5 py-2`
- **Button**: `<button aria-haspopup="menu" aria-expanded={open}>`, styled `flex h-11 w-full items-center gap-2.5 rounded-lg bg-surface-inset px-2 text-left hover:bg-border/40`.
  - `Avatar` at `size="sm"`, about 28px.
  - Text block (`min-w-0 flex-1`):
    - Line 1: `identity.name ?? user.email` at `truncate text-[13px] font-semibold text-text`.
    - Line 2: `truncate text-[11.5px] text-text-muted`. Build it from what `useIdentity` already exposes, joining the parts with " · ": `subLabel` (the person's name or role) when there is one, otherwise `ROLE_LABEL[identity.role]`. Add a "Staff" pill when `isSuperuser`, using the same style as today.
  - Chevron: the `chevron-up` icon (or `chevron-down` rotated 180°) at `h-3.5 w-3.5 text-text-muted`. If `Icon` has neither, add one.
  - Below 1024px use `min-h-12`.
- **Menu**: `role="menu"`, opening **upwards**.
  - Position: `absolute bottom-[calc(100%+6px)] left-2.5 right-2.5 z-50`
  - Style: `rounded-xl bg-surface p-1.5 shadow-xl ring-1 ring-border`. It is 212px wide and matches the button's width.
  - Items are `role="menuitem"`, each `flex min-h-9 lg:min-h-9 min-h-12 w-full items-center rounded-lg px-2.5 text-[13.5px] text-text hover:bg-surface-inset`:
    1. **Settings**: `NavLink` to `/account`
    2. **Notification settings**: link to the notification preferences route (the page that renders `NotificationPreferencesPage`)
    3. **Switch to Lite mode**: club accounts only. Keep the same `useUpdatePreferences` mutation and the navigation to `/lite`, and disable it while pending.
    4. A divider (`my-1 h-px bg-rule`), then **Log out** in `text-danger-text-alt`. It runs the same `handleLogout`.
  - Signed out: no account button. Show a single **Login** row styled like a nav row, linking to `/login`.
- **Behaviour**: copy `ProfileMenu` from `LiteLayout.tsx`.
  - Close on outside `mousedown` and on `Escape`, then return focus to the button.
  - **ArrowUp/ArrowDown** move between items, and Home/End jump to the first and last.
  - Opening from the keyboard focuses the first item.
  - Close on route change (`useLocation` effect).
  - Inside the drawer (below 1024px) the menu opens upwards in the same way. The drawer's focus trap must include it, which it does if the menu is rendered inside `<aside>`.

## 3. Below 1024px: drawer and top bar

- Drawer content is the same as desktop, with rows at `min-h-12` (48px), labels at `text-[15px]`, icons at `h-[18px] w-[18px]`, and the same 12px group gap. On phones the drawer content scrolls, which is acceptable inside a drawer.
- The bell sits in the drawer's logo row as on desktop, and also stays in the top bar.
- `AppShell` top bar: add a bell button between `GlobalSearch` and `Avatar`.
  - Size and target: `h-11 w-11`.
  - Uses the same badge and query.
  - This replaces the drawer's old Notifications row as the quick way in on touch devices.
- **Leave the `yourMoveCount` TODO alone.** Wiring it is a separate task.

## 4. What is removed

- `NotificationNavItem`: replaced by the bell button. Reuse its query logic.
- The 28px icon tile `div` in `SidebarLink`.
- Footer rows "Switch to Lite mode" and "Settings", and the inline user card with its "Logout" text button. All of these move into the account menu.

Nothing else changes: `getNavGroups`, `WAITING_ROUTE`, the gating, the agent and player variants, and the Admin group.

## 5. Agent and player accounts

The same compact styles apply. Their nav is shorter, so it fits easily. The account menu has no "Switch to Lite mode", because that item is club-only, as today.

## 6. Tokens used (existing)

- **Backgrounds**: `bg-surface`, `bg-surface-inset`, `bg-accent-bg`, `bg-accent`, `bg-danger`
- **Text**: `text-text`, `text-text-secondary`, `text-text-muted`, `text-accent`, `text-danger-text-alt`
- **Borders and rules**: `border-border`, `ring-border`, `bg-rule`

Mock reference values (light theme):

| Use | Hex |
|---|---|
| Accent | `#215fbc` |
| Accent background | `#eaf1fb` |
| Inset surface | `#f2f4f7` |
| Border | `#e4e7ec` |
| Secondary text | `#475467` |
| Muted text | `#667085` |
| Danger | `#c53637` |

Both themes must work, so use the tokens, not these hex values.

## 7. Tests (vitest + Testing Library)

- Every nav item for a club owner still renders with its label. The gated items (Team, Approvals) are still hidden when the capability is missing.
- Bell:
  - Shows an unread badge from `/notifications/unread-count` (msw), with 99+ capping.
  - Its `aria-label` includes the count.
  - It is active on `/notifications`.
- Account menu:
  - Opens on click and closes on Escape and on an outside click.
  - Focus returns to the button.
  - Arrow keys move between items.
  - "Switch to Lite mode" appears for club accounts only and calls the mutation.
  - "Log out" calls `logout` and navigates to `/login`.
- Waiting badges still map by route (`WAITING_ROUTE`).
- Manual checks:
  - 1440 × 790 (13-inch): the nav doesn't scroll.
  - 1024 × 700: it scrolls cleanly with no clipped focus rings.
  - The drawer at 768px and 375px has 48px rows.
  - Dark theme.
  - 200% zoom at 1280px.

## 8. Docs

Update `docs/design_handoff_transferx/RESPONSIVE.md` under **Navigation**:

- Desktop rows are 32px.
- Notifications is a bell in the logo row.
- The footer is a single account menu.

The "no icon-only rail" rule stays.

## Files

- `TransferX - Navigation Options.dc.html`: the design reference. Section 1a is the chosen option. It needs `support.js` next to it.
- Source to change: `frontend/src/components/layout/Sidebar.tsx` and `frontend/src/components/layout/AppShell.tsx`. Reference for the menu pattern: `frontend/src/components/lite/LiteLayout.tsx` (`ProfileMenu`).
