# TransferX — UI redesign rules

Rules for any session working on the frontend redesign. Read `design_handoff_transferx/` for the
full specification: `TOKENS.md` (values), `RESPONSIVE.md` (breakpoints), `SCREENS.md` (per-screen
layout), `SESSIONS.md` (the plan and its order).

## Stack

React 19 + TypeScript + Vite + Tailwind CSS v4 + TanStack Query + React Router.
Tailwind v4 is CSS-first: tokens live in `@theme` in `src/index.css`. There is no
`tailwind.config.js` to edit.

## Non-negotiables

1. **Tokens only.** No hex value appears in a component file. If a colour is needed and no token
   covers it, add the token to `index.css` and say so — do not inline it.
2. **The four-tier hierarchy** (see `README.md`) applies to every club-facing screen. Tier 1 is
   the only loud thing on a page.
3. **Every row representing a negotiation carries a "whose move" badge.** Your move / Their move
   / Neither. The value comes from the API, not from component logic.
4. **`#667085` is the lightest colour any text may be.** No exceptions for captions, labels or
   timestamps.
5. **Minimum type size is 11px, and only for uppercase overlines.** Body copy never goes below
   13px. If content does not fit, remove content — never shrink type.
6. **44×44px minimum touch target below 1024px.**
7. **Tables become stacked cards below 640px**, via the shared `ResponsiveTable`. Never a
   horizontal scroll on a phone.
8. **Flex or grid with `gap` for every sibling group.** No margin-based spacing between siblings.
9. **Focus rings stay.** `outline: 2px solid var(--color-accent); outline-offset: 2px`.
10. **Colour is never the only carrier of meaning.** Every coloured state has a text label.

## Scope discipline

- The redesign changes **styling, layout and hierarchy**. It does not change routing, data
  models, permissions or business logic.
- No page is added or removed. Every screen maps to an existing file in `src/pages/`.
- If a change appears to require a new endpoint, stop and check `SESSIONS.md` → "Backend work".
  It is probably one of B1–B7. Do not invent an endpoint.
- Do not refactor unrelated code. Do not upgrade dependencies. Do not reorganise folders.

## The design files are references, not code

`design_handoff_transferx/*.dc.html` are HTML prototypes. They use inline styles because of how
they were authored. **Never copy their markup or styles into the app.** Read them for layout,
spacing, copy and colour; implement with the project's own primitives and Tailwind classes.

## Before finishing any session

- The app builds with no TypeScript errors.
- The touched routes render at 375px, 768px and 1280px.
- The backend test suite is at or above the recorded baseline.
- No new console errors or React key warnings.
- Nothing outside the session's stated scope was modified.

## Sample data

All names in the design files (Meridian FC, Marcus Webb, Ashfield United, Yannick Sorel) are
fictional. They exist to show realistic density. Never commit them as fixtures or defaults.
