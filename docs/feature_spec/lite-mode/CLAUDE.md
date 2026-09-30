---
title: "Lite Mode — Rules for Implementation Sessions"
last_updated: 2026-09-29
status: Active
owner: "TODO — assign a Product Owner"
---

# Lite mode: rules for implementation sessions

Read these files in this folder first:
- `README.md`: screens and the reasons behind them.
- `BACKEND.md`: API and data changes.
- `SESSIONS.md`: build order.

Then read `docs/architecture/decisions/0006-ai-assistant-advises-from-scoped-facts.md` and the top of `backend/app/ai/assist.py`.

The rules in `docs/design_handoff_transferx/CLAUDE.md` still apply:
- tokens only;
- light and dark themes both work;
- whose-move badges;
- contrast floors;
- gap-based layout;
- focus rings.

## How this differs from the UI redesign rules

- Lite **adds** a route (`/lite/*`) and endpoints. That's expected. Don't restyle or restructure full-app pages in a Lite session.
- Lite type and tap targets are larger: body text 17–18px or more, buttons 52px or more.

## Non-negotiables

1. **Reuse the assistant.** Extend `assist.ask`, `check_offer_terms` and `deal_steps`. Never write a second assistant, money check or step machine.
2. **The assistant never acts (ADR 0006).**
   - A `proposal` only pre-fills the action card.
   - The user's confirm calls the existing endpoints (or `POST /lite/actions` from L6), with `ai_assisted: true`.
   - Every proposal field is validated in code before it's returned.
3. **Figures come from code.** The money panel uses the `offer-check` money block, never text from the model.
4. **Mask anonymous buyers everywhere:** tiles, cards, progress, emails. Use `_masked()` / "an undisclosed club".
5. **No model call without a user action.** The home screen, money previews and progress must not use the user's AI allowance.
6. **Nothing reaches the other club while an action is held.**
7. **Email links never act on GET.**
8. **Plain English.** No internal terms ("tier 1", "SLA", "capability", enum names) in Lite copy. Money is written "£8m" and "£35k a week".
9. **Disabled with a reason, never hidden** when a role can't do something.
10. The design file is a reference. Never copy its inline styles.
11. **The product owner's decisions of 2026-09-29 override the screens** (README.md, top): off by default until L4, four position groups, rules-first Buy results, sign-in for money from email, text size in Lite only.
