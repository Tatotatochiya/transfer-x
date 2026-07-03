---
name: product-principles
description: Evaluate features, workflows, and product decisions against TransferX's identity as enterprise software for professional football clubs, not a consumer marketplace app. Use this whenever designing or reviewing a workflow, weighing a product trade-off, or judging whether a proposed behaviour is realistic for how real transfers, clubs, agents, and players actually operate. Bring the perspective of whichever stakeholders are affected — Selling Club, Buying Club, Sporting Director, CEO, Finance, Legal, Player, Agent — and push back on consumer-app shortcuts, unrealistic assumptions, unclear permissions, or confidentiality gaps, even if not explicitly asked to review them.
---

# TransferX Product Principles

TransferX is enterprise software built for professional football clubs, agents, and players — not a consumer marketplace app wearing a football theme. That distinction should shape every product decision, not just the ones explicitly framed as "product work." A feature can be technically correct and still be the wrong call if it wouldn't survive contact with a real Sporting Director's expectations of how a transfer should work.

## When to use this skill

- Designing a new workflow, or reviewing an existing one.
- Weighing a product trade-off ("should this be automatic or require confirmation," "who should be able to see this").
- Judging whether a proposed behaviour is realistic for professional football.
- Any time a shortcut is tempting because it's simpler to build — that's exactly when to check whether it's simpler at the cost of realism, trust, or confidentiality.

## Instructions

### 1. Optimise for these, in this order of non-negotiability

- **Realism** — does this match how a real transfer actually happens?
- **Trust** — would this make a professional counterparty more or less willing to rely on the platform?
- **Security** — does this protect what needs protecting?
- **Professional workflows** — does this fit how clubs actually operate, not how an individual user might casually prefer?
- **Enterprise usability** — clear, fast, and confidence-inspiring for someone doing this as their job, not a novelty to delight a first-time user.

### 2. Think from the affected stakeholder's seat, specifically

Don't default to "the user" as an undifferentiated concept — TransferX has genuinely different stakeholders with different, sometimes conflicting, needs. For whichever ones a decision touches, ask:

| Stakeholder | What they'd expect | What they should never see |
|---|---|---|
| **Selling Club** | Control over who sees their listing and their floor price; visibility into every bid/offer on their own player | A buying club's confidential budget, or another buyer's bid being visible to a third club |
| **Buying Club** | A fair, honest view of the market; confidence that an accepted deal won't be silently reopened by the seller | Rival clubs' bids in identifying detail; their own confidential interest leaking to the seller's other suitors |
| **Sporting Director** | Clarity on deal status at a glance, an audit trail they can point to in a dispute | A one-click action with no confirmation on a decision worth millions |
| **CEO / Ownership** | Oversight without having to share a single login with everyone on staff | No visibility into what staff are actually doing on the platform |
| **Finance** | Numbers that reconcile — reserved vs. committed vs. spent, instalments that land when scheduled | A completed deal whose numbers don't add up, or a credit that arrives before the money actually does |
| **Legal** | Consent captured explicitly, a record of who agreed to what and when | A binding step that happened without a clear consent trail |
| **Player** | To be informed and to consent to terms that affect them directly | To be transferred, or have terms changed, without ever being asked |
| **Agent** | A clear, exclusive channel to negotiate on behalf of their actual clients | The ability to act on behalf of a player they don't represent, or insert themselves into a deal uninvited |

### 3. Challenge unrealistic assumptions out loud

If a workflow assumes something that wouldn't hold in a real transfer, say so — don't quietly implement the unrealistic version because it's what was asked for literally. Real examples of the kind of gap worth catching:

- A transfer completing without the player ever consenting to personal terms. Real transfers require the player's agreement — if a workflow skips that step, ask whether the absence is intentional or an oversight, don't assume it's fine because nothing broke.
- A reserve price or a losing bidder's identity becoming visible to a rival club. In real football this is exactly the kind of leak that ends a club's willingness to use a platform, even if it's "just" a missing field-level check.
- A single unconfirmed click accepting a multi-million-pound bid. That's consumer-app UX. Enterprise software puts a deliberate confirmation step in front of hard-to-reverse, high-value actions — the friction is a feature, not a UX failure.

### 4. Confidentiality and permissions are not implementation details

Protecting confidentiality and making permissions explicit isn't a security-team concern bolted on afterward — it's core to whether professional clubs will trust the platform at all. Default to **explicit** permission checks over implicit trust: "any logged-in user can see this" is very rarely the right default for anything involving money, medical data, or another party's confidential position.

### 5. What enterprise users actually value

When two designs are otherwise close, prefer the one that gives more of: **clarity** (unambiguous current state), **speed** (doesn't waste a busy professional's time), **audit trails** (a record that survives a dispute), **confidence** (nothing feels fragile or guessable), and **traceability** (who did what, when). These aren't abstract virtues — they're what separates software a club's legal and finance teams will actually sign off on from something that merely demos well.

## Examples

**Catching a missing consent step.** A proposed simplification would let a deal advance straight from agreement to paperwork whenever there's no agent involved, skipping personal-terms consent entirely "since it's simpler." Push back: a real transfer isn't complete until the player has agreed personal terms, agent or not — the presence of an agent changes *who* negotiates those terms, not *whether* consent is required.

**Catching a confidentiality leak before it ships.** A new public "market activity" feed is proposed that would show a sale's live best bid to any visitor for engagement/transparency reasons. From the Selling Club's seat: they'd never want their floor price or the live state of their negotiation broadcast to every rival club and journalist. Recommend the information stays seller-only, matching how the rest of the platform already handles this.

**Catching consumer-app thinking.** A workflow lets a club "undo" an accepted bid by simply deleting it, the way you'd cancel an online order. From a Legal and Finance seat, an accepted bid is closer to a binding agreement — undoing it needs a recorded reason and visibility to the counterparty, not a silent delete.

## Related skills

- [`engineering-standards`](../engineering-standards/SKILL.md) — where the permissions/security/auditability bar this skill argues for gets enforced mechanically in code.
- [`linear-workflow`](../linear-workflow/SKILL.md) — the lens here for judging whether a proposed ticket is actually worth prioritising, and for whom.
- [`documentation-standards`](../documentation-standards/SKILL.md) — [`docs/product/workflows/`](../../../docs/product/workflows/README.md) and [`docs/business/glossary.md`](../../../docs/business/glossary.md) are where the realistic, professional-grade version of a workflow gets written down once it's settled.
- [`session-lifecycle`](../session-lifecycle/SKILL.md) — a stakeholder concern raised but not resolved in a session belongs in the risks/outstanding-work section of the session summary.
