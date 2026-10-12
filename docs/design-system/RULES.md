---
title: "Design Rules"
last_updated: 2026-10-12
status: Active
owner: "TODO — assign a Design Owner"
---

# Design rules

The non-negotiables for every frontend change. The values are in [`TOKENS.md`](./TOKENS.md), breakpoints in [`RESPONSIVE.md`](./RESPONSIVE.md), screen layouts in [`SCREENS.md`](./SCREENS.md), and the principle in [`README.md`](./README.md).

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
11. **AI controls look like AI.** Anything that asks the assistant (a button, a link, a panel
    heading) carries the ✦ mark in the assistant colour (`role-agent-text`); a button has its
    light fill (`/10`) and ring (`/30`). Use `components/ai/AskAboutButton` for "Ask about this"
    rather than restyling a plain button.

## Before finishing a UI change

- `npx tsc -b` reports no errors, and vitest passes.
- The touched routes render at 375px, 768px and 1280px, in a real browser.
- No new console errors or React key warnings.
