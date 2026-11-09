import type { Offer, OfferEvent } from "../../types/api";
import type { LiteOfferCard } from "../../hooks/useLite";
import { buyerLabel } from "../../lib/buyerIdentity";
import { offerStatusLabel } from "../../lib/badges";
import { lastChange, type TermChange } from "../../lib/offerChanges";
import { isLoan, loanPeriod, offerHeadline } from "../../lib/offerTerms";
import { formatCurrency, formatDate } from "../../lib/utils";

/**
 * What the offer page's status card says, for every state and viewer
 * (offer-room-focus §5.4). Pure: the page passes in who is looking and
 * whether they can act, computed exactly as before, and the Lite card when
 * it has loaded. The first matching row of the spec's table wins.
 */

export type OfferTone = "you" | "wait" | "info" | "done" | "closed";

export type OfferAction =
  | { kind: "accept"; label: string; highlight?: boolean }
  | { kind: "counter"; label: "Counter" }
  | { kind: "reject"; label: "Reject this offer" }
  | { kind: "raise"; label: "Raise your offer" }
  | { kind: "open-messages"; label: string }
  | { kind: "view-deal"; label: "View the deal" };

export interface OfferStatusView {
  tone: OfferTone;
  overline: string;
  meta?: string;
  /** Under 24 hours to answer: the overline turns red. */
  urgent?: boolean;
  headline: string;
  body?: string;
  changes: TermChange[];
  primary?: OfferAction;
  secondary?: OfferAction;
  /** Reject, rendered as a danger text button. */
  tertiary?: OfferAction;
}

export interface OfferViewer {
  side: "buyer" | "seller" | null;
  isMyTurn: boolean;
  canWrite: boolean;
  card?: LiteOfferCard;
  pushAction: string | null;
  myClubId?: string;
  now?: Date;
}

const DAY = 86_400_000;

/** The first letter upper-cased: a masked buyer ("an undisclosed club") can open a sentence. */
export function cap(s: string): string {
  return s ? s[0].toUpperCase() + s.slice(1) : s;
}

const time = (d: Date) => d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });

/** "18:00 today", "18:00 tomorrow", "Fri 13 Nov", or a date (§5.4). Null without a deadline. */
export function deadlineText(expiresAt: string | null | undefined, now: Date): { text: string; urgent: boolean } | null {
  if (!expiresAt) return null;
  const at = new Date(expiresAt);
  const ms = at.getTime() - now.getTime();
  if (ms <= 0) return { text: "deadline passed", urgent: true };
  const startOf = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  const days = Math.round((startOf(at) - startOf(now)) / DAY);
  const text = days === 0 ? `${time(at)} today`
    : days === 1 ? `${time(at)} tomorrow`
    : days <= 6 ? at.toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" })
    : formatDate(expiresAt);
  return { text, urgent: ms < DAY };
}

/** What the accept confirmation says is being agreed. For a loan with an
 *  obligation that includes a sale, which "Accept this offer?" never said. */
export function acceptMessage(offer: Offer): string {
  if (!isLoan(offer)) return "Accept this offer and create a deal?";
  const buyer = buyerLabel(offer, "the borrowing club");
  const lines = [`Loan ${offer.player?.name ?? "the player"} to ${buyer}, ${loanPeriod(offer)}.`];
  const purchase = loanPurchaseSentence(offer, buyer);
  if (purchase) lines.push(purchase);
  return lines.join(" ");
}

function loanPurchaseSentence(offer: Offer, buyer: string): string | null {
  if (offer.obligation_to_buy && offer.option_to_buy != null) {
    return `This includes an obligation: he transfers permanently for ${formatCurrency(Number(offer.option_to_buy))} when the loan ends` +
      (offer.obligation_conditions ? `, conditional on: ${offer.obligation_conditions}.` : ".");
  }
  if (offer.option_to_buy != null) {
    return `${cap(buyer)} may buy him for ${formatCurrency(Number(offer.option_to_buy))} during the loan.`;
  }
  return null;
}

/** The other club as this viewer may name it; a masked buyer stays masked. */
export function otherName(offer: Offer, side: "buyer" | "seller" | null, card?: LiteOfferCard): string {
  if (side === "buyer") return offer.to_club?.name ?? "the selling club";
  return card?.other_club ?? buyerLabel(offer, "the buying club");
}

const MOVES = new Set(["SENT", "COUNTERED", "IMPROVED"]);

function lastMove(offer: Offer, actor: (e: OfferEvent) => boolean): OfferEvent | undefined {
  const moves = (offer.events ?? []).filter((e) => MOVES.has(e.event_type) && actor(e));
  return moves[moves.length - 1];
}

export function getOfferStatus(offer: Offer, viewer: OfferViewer): OfferStatusView {
  const now = viewer.now ?? new Date();
  const { side, card, myClubId } = viewer;
  const P = offer.player?.name ?? "the player";
  const other = otherName(offer, side, card);
  const Other = cap(other);
  const amount = offerHeadline(offer);
  const loan = isLoan(offer);
  const closedBody = "The terms and conversation stay here as the record.";
  const base = { changes: [] as TermChange[] };

  // 1–4: closed.
  if (offer.status === "ACCEPTED") {
    return {
      ...base, tone: "done", overline: "Accepted", meta: formatDate(offer.last_action_at),
      headline: "This offer became a deal",
      secondary: offer.deal ? { kind: "view-deal", label: "View the deal" } : undefined,
    };
  }
  if (offer.status === "REJECTED") {
    const mine = !!myClubId && offer.last_actor_club_id === myClubId;
    return {
      ...base, tone: "closed", overline: "Rejected", meta: formatDate(offer.last_action_at), body: closedBody,
      headline: !side ? "This offer was rejected"
        : mine ? `You rejected ${other}'s ${amount} offer` : `${Other} rejected your ${amount} offer`,
    };
  }
  if (offer.status === "WITHDRAWN") {
    return {
      ...base, tone: "closed", overline: "Withdrawn", meta: formatDate(offer.last_action_at), body: closedBody,
      headline: side === "buyer" ? `You withdrew your ${amount} offer`
        : side === "seller" ? `${Other} withdrew their ${amount} offer` : "This offer was withdrawn",
    };
  }
  if (offer.status === "EXPIRED") {
    return {
      ...base, tone: "closed", overline: "Expired", meta: offer.expires_at ? formatDate(offer.expires_at) : undefined,
      body: closedBody, headline: "This offer expired without an answer",
    };
  }

  // 5: open, not a party.
  if (!side) {
    return {
      ...base, tone: "info", overline: offerStatusLabel(offer.status),
      headline: `${cap(buyerLabel(offer, "A club"))} offered ${amount} for ${P}`,
    };
  }

  const deadline = deadlineText(card?.expires_at ?? offer.expires_at, now);

  // 6–7: their move was last, so it's ours.
  if (viewer.isMyTurn) {
    const theirs = lastMove(offer, (e) => !myClubId || e.actor_club_id !== myClubId);
    const kind = theirs?.event_type ?? "SENT";
    const headline = loan
      ? kind === "COUNTERED" ? `${Other} countered the loan terms`
        : kind === "IMPROVED" ? `${Other} improved the loan terms`
        : `${Other} offered to take ${P} on loan`
      : kind === "COUNTERED" ? `${Other} countered at ${amount}`
        : kind === "IMPROVED" ? `${Other} raised their offer to ${amount}`
        : `${Other} bid ${amount} for ${P}`;

    if (!viewer.canWrite) {
      return {
        ...base, tone: "info", overline: "Your club's move", headline,
        body: card?.disabled_reason ?? "Your role can see offers but can't answer them.",
      };
    }

    const body: string[] = [];
    // The valuation is the selling club's alone (§9): never read for the buyer.
    const val = side === "seller" ? card?.your_valuation ?? null : null;
    if (!loan && val != null && offer.fee_amount != null) {
      const fee = Number(offer.fee_amount);
      body.push(fee < val
        ? `That's ${formatCurrency(val - fee)} under your ${formatCurrency(val)} valuation.`
        : `That's at or above your ${formatCurrency(val)} valuation.`);
    }
    if (loan) {
      const purchase = offer.obligation_to_buy && offer.option_to_buy != null
        ? `If you accept, he transfers permanently for ${formatCurrency(Number(offer.option_to_buy))} when the loan ends` +
          (offer.obligation_conditions ? `, conditional on: ${offer.obligation_conditions}.` : ".")
        : loanPurchaseSentence(offer, other);
      if (purchase) body.push(purchase);
    }

    const change = lastChange(offer);
    const changes = change && change.actorClubId !== myClubId ? change.changes : [];

    return {
      tone: "you", overline: "Your move",
      meta: deadline ? (deadline.text === "deadline passed" ? deadline.text : `reply by ${deadline.text}`) : undefined,
      urgent: deadline?.urgent,
      headline, body: body.join(" ") || undefined, changes,
      primary: {
        kind: "accept",
        label: loan ? "Accept the loan" : `Accept ${formatCurrency(Number(offer.fee_amount ?? 0))}`,
        highlight: viewer.pushAction === "accept" || undefined,
      },
      secondary: { kind: "counter", label: "Counter" },
      tertiary: { kind: "reject", label: "Reject this offer" },
    };
  }

  // 8: waiting on them.
  const mine = lastMove(offer, (e) => !!myClubId && e.actor_club_id === myClubId);
  const kind = mine?.event_type ?? "SENT";
  const headline = kind === "COUNTERED" ? `${Other} are considering your ${amount} counter`
    : kind === "IMPROVED" ? `${Other} are considering your raised ${amount} offer`
    : `${Other} are considering your ${amount} offer`;
  const since = new Date(offer.last_action_at);
  const days = Math.floor((now.getTime() - since.getTime()) / DAY);
  const canRaise = side === "buyer" && viewer.canWrite;
  const body = [
    deadline && deadline.text !== "deadline passed" ? `It expires ${deadline.text}.` : null,
    canRaise ? "You can raise it now or wait for their answer." : null,
  ].filter(Boolean).join(" ");
  return {
    ...base, tone: "wait", overline: `Waiting on ${other}`,
    meta: days >= 1 ? `${days} day${days === 1 ? "" : "s"}` : `since ${time(since)}`,
    headline, body: body || undefined,
    secondary: canRaise ? { kind: "raise", label: "Raise your offer" }
      : side === "seller" ? { kind: "open-messages", label: `Message ${other}` }
      : undefined,
  };
}
