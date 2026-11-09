import type { Offer } from "../types/api";
import { formatCurrency, formatDate, formatWage } from "./utils";
import { isLoan } from "./offerTerms";

/** One term the latest counter or raise changed: what it was and what it is now. */
export interface TermChange {
  label: string;
  was: string;
  now: string;
}

export interface LastChange {
  kind: "COUNTERED" | "IMPROVED";
  actorClubId: string | null;
  changes: TermChange[];
}

type Terms = Record<string, unknown>;

const money = (v: unknown) => (v == null || v === "" ? "None" : formatCurrency(Number(v)));
const pct = (v: unknown) => (v == null ? "None" : `${Math.round(Number(v) * 1000) / 10}%`);
const date = (v: unknown) => (v == null ? "Not set" : formatDate(String(v)));
const yesNo = (yes: string, no: string) => (v: unknown) => (v ? yes : no);
const count = (one: string, none: string) => (v: unknown) => {
  const n = Array.isArray(v) ? v.length : 0;
  return n === 0 ? none : `${n} ${one}${n === 1 ? "" : "s"}`;
};

// The terms a club reads on the offer, in the order the Terms card shows them.
const PERMANENT: [string, string, (v: unknown) => string][] = [
  ["fee_amount", "Transfer fee", money],
  ["instalments", "Payment", count("instalment", "On completion")],
  ["clauses", "Add-ons", count("add-on", "None")],
  ["sell_on_pct", "Sell-on", pct],
  ["wage_weekly", "Wage", (v) => (v == null ? "Not set" : formatWage(Number(v)))],
  ["contract_years", "Contract", (v) => (v == null ? "Not set" : `${v} years`)],
  ["contract_end_date", "Ends", date],
];

const LOAN: [string, string, (v: unknown) => string][] = [
  ["loan_start", "Loan starts", date],
  ["loan_end", "Loan ends", date],
  ["loan_fee", "Loan fee", money],
  ["wage_split_pct", "Wage share", (v) => (v == null ? "100%" : pct(v))],
  ["option_to_buy", "Purchase price", money],
  ["obligation_to_buy", "Obligation to buy", yesNo("Yes", "No")],
  ["recall_allowed", "Early recall", yesNo("Allowed", "Not allowed")],
];

/**
 * The latest counter or raise on an offer, and each term it changed. The
 * offer only holds its latest terms; the event keeps the ones it replaced
 * (`payload.previous`). Events from before that was kept carry only the new
 * fee, so for those the old fee is rebuilt from the events before.
 */
export function lastChange(offer: Offer): LastChange | null {
  const events = (offer.events ?? []).filter((e) =>
    e.event_type === "SENT" || e.event_type === "COUNTERED" || e.event_type === "IMPROVED");
  let last = -1;
  events.forEach((e, i) => { if (e.event_type !== "SENT") last = i; });
  if (last < 0) return null;
  const event = events[last];

  let previous = event.payload?.previous as Terms | undefined;
  if (!previous) {
    let fee: unknown = null;
    for (const e of events.slice(0, last)) {
      if (e.payload?.fee_amount != null) fee = e.payload.fee_amount;
    }
    previous = fee != null ? { fee_amount: fee } : {};
  }

  const current = offer as unknown as Terms;
  const changes = (isLoan(offer) ? LOAN : PERMANENT)
    .filter(([field]) => field in previous!)
    .map(([field, label, format]) => ({ label, was: format(previous![field]), now: format(current[field]) }))
    .filter((c) => c.was !== c.now);

  return { kind: event.event_type as LastChange["kind"], actorClubId: event.actor_club_id, changes };
}

/**
 * What a draft counter would change, against the offer as it stands: the
 * laptop counter's "What {Other} will see" panel (offer-room-focus §5.6).
 * `draft` holds the draft's full terms in the offer's own field names (the
 * same object the live rule check reads); only fields it carries are compared,
 * with the labels and formats lastChange uses.
 */
export function diffDraft(offer: Offer, draft: Terms): TermChange[] {
  const current = offer as unknown as Terms;
  return (isLoan(offer) ? LOAN : PERMANENT)
    .filter(([field]) => field in draft)
    .map(([field, label, format]) => ({ label, was: format(current[field]), now: format(draft[field]) }))
    .filter((c) => c.was !== c.now);
}

/** One move in the negotiation: the offer, each counter and each raise. */
export interface OfferRound {
  side: "me" | "them" | "buyer" | "seller";
  kind: "SENT" | "COUNTERED" | "IMPROVED";
  at: string;
  actorClubId: string | null;
  /** The fee after this move (a loan raise: its loan fee). Carried forward
   *  when the move didn't send one, since a counter that left the fee alone
   *  sends none. */
  fee: number | null;
}

/**
 * The rounds of an offer, oldest first (offer-room-focus §5.8). For a party
 * each is "me" or "them"; for anyone else, "buyer" or "seller".
 */
export function offerRounds(offer: Offer, myClubId: string | undefined): OfferRound[] {
  const party = !!myClubId && (myClubId === offer.from_club_id || myClubId === offer.to_club_id);
  let fee: number | null = null;
  return (offer.events ?? [])
    .filter((e) => e.event_type === "SENT" || e.event_type === "COUNTERED" || e.event_type === "IMPROVED")
    .map((e) => {
      const p = e.payload ?? {};
      const raw = isLoan(offer) && e.event_type === "IMPROVED" ? p.loan_fee : p.fee_amount;
      if (raw != null && raw !== "") fee = Number(raw);
      // A SENT event carries no actor on legacy offers; the buyer sends.
      const actor = e.actor_club_id ?? (e.event_type === "SENT" ? offer.from_club_id : null);
      const side: OfferRound["side"] = party
        ? actor === myClubId ? "me" : "them"
        : actor === offer.from_club_id ? "buyer" : "seller";
      return { side, kind: e.event_type as OfferRound["kind"], at: e.created_at, actorClubId: actor, fee };
    });
}
