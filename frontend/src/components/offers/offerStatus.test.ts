import { describe, expect, it } from "vitest";
import type { Offer, OfferEvent, OrderBook } from "../../types/api";
import type { LiteOfferCard } from "../../hooks/useLite";
import { buyerRanking, deadlineText, getOfferStatus, type OfferViewer } from "./offerStatus";

const BUYER = "buyer-club";
const SELLER = "seller-club";
const NOW = new Date("2026-11-09T10:00:00");

const ev = (event_type: OfferEvent["event_type"], actor: string, payload: Record<string, unknown> = {}): OfferEvent =>
  ({ id: `${event_type}-${Math.random()}`, offer_id: "o", event_type, actor_club_id: actor, payload, created_at: "2026-11-08T09:00:00Z" });

function offer(over: Partial<Offer> = {}): Offer {
  return {
    id: "o", status: "SENT", deal_type: "PERMANENT", fee_amount: 4_200_000, loan_fee: null, wage_weekly: null,
    contract_years: null, contract_end_date: null, instalments: [], clauses: [], sell_on_pct: null,
    from_club_id: BUYER, to_club_id: SELLER, last_actor_club_id: BUYER, is_anonymous: false, buyer_league_name: null,
    from_club: { id: BUYER, name: "Meridian FC", crest_url: null }, to_club: { id: SELLER, name: "Ashfield United", crest_url: null },
    player: { id: "p", name: "Marcus Webb", position: "FWD" }, player_id: "p", sale_id: null, deal: null,
    expires_at: null, created_at: "2026-11-03T09:00:00Z", last_action_at: "2026-11-09T08:30:00",
    option_to_buy: null, obligation_to_buy: false, obligation_conditions: null, recall_allowed: false,
    loan_start: null, loan_end: null, wage_split_pct: null,
    events: [ev("SENT", BUYER, { fee_amount: "4200000" })],
    ...over,
  } as unknown as Offer;
}

const card = (over: Partial<LiteOfferCard> = {}): LiteOfferCard =>
  ({ other_club: "Meridian FC", your_valuation: null, counter_suggestion: null, expires_at: null, disabled_reason: null, ...over } as LiteOfferCard);

const seller = (over: Partial<OfferViewer> = {}): OfferViewer =>
  ({ side: "seller", isMyTurn: true, canWrite: true, pushAction: null, myClubId: SELLER, now: NOW, ...over });
const buyer = (over: Partial<OfferViewer> = {}): OfferViewer =>
  ({ side: "buyer", isMyTurn: false, canWrite: true, pushAction: null, myClubId: BUYER, now: NOW, ...over });

describe("getOfferStatus: your move", () => {
  it("a new bid for the seller, with the gap to a higher valuation", () => {
    const v = getOfferStatus(offer(), seller({ card: card({ your_valuation: 4_800_000 }) }));
    expect(v.tone).toBe("you");
    expect(v.overline).toBe("Your move");
    expect(v.headline).toBe("Meridian FC bid £4,200,000 for Marcus Webb");
    expect(v.body).toBe("That's £600,000 under your £4,800,000 valuation.");
    expect(v.primary).toEqual({ kind: "accept", label: "Accept £4,200,000", highlight: undefined });
    expect(v.secondary?.kind).toBe("counter");
    expect(v.tertiary?.kind).toBe("reject");
  });

  it("says when the bid meets the valuation", () => {
    expect(getOfferStatus(offer(), seller({ card: card({ your_valuation: 4_000_000 }) })).body)
      .toBe("That's at or above your £4,000,000 valuation.");
  });

  it("prefers the seller's asking price to its valuation", () => {
    const v = getOfferStatus(offer(), seller({ card: card({ your_valuation: 4_800_000, your_asking_price: 5_000_000 }) }));
    expect(v.body).toBe("That's £800,000 under your £5,000,000 asking price.");
    expect(getOfferStatus(offer(), seller({ card: card({ your_asking_price: 4_000_000 }) })).body)
      .toBe("That's at or above your £4,000,000 asking price.");
  });

  it("has no gap sentence without the Lite card", () => {
    expect(getOfferStatus(offer(), seller()).body).toBeUndefined();
  });

  it("names a counter and a raise", () => {
    const countered = offer({ status: "COUNTERED", events: [ev("SENT", BUYER), ev("COUNTERED", SELLER), ev("COUNTERED", BUYER)] });
    expect(getOfferStatus(countered, seller()).headline).toBe("Meridian FC countered at £4,200,000");
    const raised = offer({ events: [ev("SENT", BUYER), ev("IMPROVED", BUYER)] });
    expect(getOfferStatus(raised, seller()).headline).toBe("Meridian FC raised their offer to £4,200,000");
  });

  it("never states the valuation to the buyer, even if a card carries one", () => {
    const o = offer({ status: "COUNTERED", last_actor_club_id: SELLER, events: [ev("SENT", BUYER), ev("COUNTERED", SELLER)] });
    const v = getOfferStatus(o, buyer({ isMyTurn: true, card: card({ other_club: "Ashfield United", your_valuation: 9_000_000, your_asking_price: 8_000_000 }) }));
    expect(v.headline).toBe("Ashfield United countered at £4,200,000");
    expect(JSON.stringify(v)).not.toMatch(/valuation|asking|9,000,000|8,000,000/);
  });

  it("without MARKET_WRITE it is the club's move, not yours, with no actions", () => {
    const v = getOfferStatus(offer(), seller({ canWrite: false, card: card({ disabled_reason: "Your role can't answer offers." }) }));
    expect(v.tone).toBe("info");
    expect(v.overline).toBe("Your club's move");
    expect(v.body).toBe("Your role can't answer offers.");
    expect(v.primary).toBeUndefined();
  });

  it("a loan with an obligation states the sale", () => {
    const o = offer({ deal_type: "LOAN", fee_amount: null, loan_fee: 450_000, option_to_buy: 18_000_000, obligation_to_buy: true } as Partial<Offer>);
    const v = getOfferStatus(o, seller());
    expect(v.headline).toBe("Meridian FC offered to take Marcus Webb on loan");
    expect(v.primary?.label).toBe("Accept the loan");
    expect(v.body).toBe("If you accept, he transfers permanently for £18,000,000 when the loan ends.");
  });

  it("a loan with an option only", () => {
    const o = offer({ deal_type: "LOAN", fee_amount: null, loan_fee: 450_000, option_to_buy: 18_000_000 } as Partial<Offer>);
    expect(getOfferStatus(o, seller()).body).toBe("Meridian FC may buy him for £18,000,000 during the loan.");
  });

  it("keeps an anonymous buyer masked, capitalised at the start of a sentence", () => {
    const o = offer({ from_club: null, is_anonymous: true, buyer_league_name: "Premier League" } as Partial<Offer>);
    expect(getOfferStatus(o, seller({ card: card({ other_club: "an undisclosed Premier League club" }) })).headline)
      .toBe("An undisclosed Premier League club bid £4,200,000 for Marcus Webb");
    expect(getOfferStatus(o, seller()).headline).toBe("A Premier League club bid £4,200,000 for Marcus Webb");
  });

  it("highlights Accept from a push", () => {
    expect(getOfferStatus(offer(), seller({ pushAction: "accept" })).primary).toMatchObject({ highlight: true });
  });
});

describe("getOfferStatus: changes", () => {
  const countered = (actor: string) => offer({
    status: "COUNTERED", last_actor_club_id: actor, fee_amount: 4_200_000, wage_weekly: 30_000, contract_years: 4, sell_on_pct: 0.1,
    instalments: [{ due_date: "2027-01-01", amount: 2_100_000 }, { due_date: "2028-01-01", amount: 2_100_000 }],
    clauses: [{ clause_type: "APPEARANCES", trigger_description: "50 games", amount: 500_000, cap: null }],
    events: [ev("SENT", BUYER), ev("COUNTERED", actor, { previous: {
      fee_amount: "5000000", instalments: [], clauses: [], sell_on_pct: null, wage_weekly: "20000", contract_years: 3,
    } })],
  } as unknown as Partial<Offer>);

  it("lists what the other side changed", () => {
    const v = getOfferStatus(countered(BUYER), seller());
    expect(v.changes.map((c) => c.label)).toEqual(["Transfer fee", "Payment", "Add-ons", "Sell-on", "Wage", "Contract"]);
  });

  it("not what I changed", () => {
    expect(getOfferStatus(countered(SELLER), buyer({ isMyTurn: false, myClubId: SELLER, side: "seller" })).changes).toEqual([]);
  });
});

describe("getOfferStatus: waiting for approval", () => {
  it("our acceptance waiting on an approver replaces the buttons", () => {
    const o = offer({ pending_approval: { id: "a1", requested_by: "Sam Reid", requested_at: "2026-11-09T08:00:00", expires_at: "2026-11-10T08:00:00" } } as Partial<Offer>);
    const v = getOfferStatus(o, seller());
    expect(v).toMatchObject({ tone: "hold", overline: "Waiting for approval", headline: "Accepting £4,200,000 is waiting for approval" });
    expect(v.body).toBe("Sam Reid accepted it. It goes ahead when an approver at your club agrees, and lapses 08:00 tomorrow if no one decides.");
    expect(v.primary).toBeUndefined();
    expect(v.secondary).toEqual({ kind: "view-approvals", label: "Open approvals" });
  });
});

describe("getOfferStatus: waiting", () => {
  it("a buyer who can write may raise", () => {
    const v = getOfferStatus(offer({ expires_at: "2026-11-09T18:00:00" }), buyer());
    expect(v.tone).toBe("wait");
    expect(v.overline).toBe("Waiting on Ashfield United");
    expect(v.meta).toBe("since 08:30");
    expect(v.headline).toBe("Ashfield United are considering your £4,200,000 offer");
    expect(v.body).toBe("It expires 18:00 today. You can raise it now or wait for their answer.");
    expect(v.secondary).toEqual({ kind: "raise", label: "Raise your offer" });
  });

  it("a buyer who can't write has nothing to do", () => {
    const v = getOfferStatus(offer(), buyer({ canWrite: false }));
    expect(v.secondary).toBeUndefined();
    expect(v.body).toBeUndefined();
  });

  it("a seller who countered can message", () => {
    const o = offer({ status: "COUNTERED", last_actor_club_id: SELLER, last_action_at: "2026-11-06T09:00:00",
      events: [ev("SENT", BUYER), ev("COUNTERED", SELLER)] });
    const v = getOfferStatus(o, seller({ isMyTurn: false }));
    expect(v.headline).toBe("Meridian FC are considering your £4,200,000 counter");
    expect(v.meta).toBe("3 days");
    expect(v.secondary).toEqual({ kind: "open-messages", label: "Message Meridian FC" });
  });
});

describe("getOfferStatus: closed", () => {
  it("rejected by me, by them, and for a non-party", () => {
    const o = offer({ status: "REJECTED", last_actor_club_id: SELLER });
    expect(getOfferStatus(o, seller()).headline).toBe("You rejected Meridian FC's £4,200,000 offer");
    expect(getOfferStatus(o, buyer()).headline).toBe("Ashfield United rejected your £4,200,000 offer");
    expect(getOfferStatus(o, { ...buyer(), side: null, myClubId: "x" }).headline).toBe("This offer was rejected");
    expect(getOfferStatus(o, seller()).tone).toBe("closed");
  });

  it("withdrawn, for both sides", () => {
    const o = offer({ status: "WITHDRAWN" });
    expect(getOfferStatus(o, buyer()).headline).toBe("You withdrew your £4,200,000 offer");
    expect(getOfferStatus(o, seller()).headline).toBe("Meridian FC withdrew their £4,200,000 offer");
  });

  it("expired", () => {
    expect(getOfferStatus(offer({ status: "EXPIRED" }), seller()).headline).toBe("This offer expired without an answer");
  });

  it("accepted, for a non-party, links to the deal", () => {
    const v = getOfferStatus(offer({ status: "ACCEPTED", deal: { id: "d1" } } as Partial<Offer>), { ...buyer(), side: null });
    expect(v.tone).toBe("done");
    expect(v.secondary).toEqual({ kind: "view-deal", label: "View the deal" });
  });

  it("an open offer seen by a non-party", () => {
    const v = getOfferStatus(offer(), { ...buyer(), side: null, myClubId: undefined, isMyTurn: false });
    expect(v.tone).toBe("info");
    expect(v.headline).toBe("Meridian FC offered £4,200,000 for Marcus Webb");
    expect(v.primary).toBeUndefined();
  });
});

describe("deadlineText", () => {
  it("today, tomorrow, within a week and later; red under 24 hours", () => {
    expect(deadlineText("2026-11-09T18:00:00", NOW)).toEqual({ text: "18:00 today", urgent: true });
    expect(deadlineText("2026-11-10T09:00:00", NOW)).toEqual({ text: "09:00 tomorrow", urgent: true });
    expect(deadlineText("2026-11-10T12:00:00", NOW)?.urgent).toBe(false);
    expect(deadlineText("2026-11-13T12:00:00", NOW)?.text).toBe("Fri 13 Nov");
    expect(deadlineText("2026-11-30T12:00:00", NOW)?.text).toBe("30 Nov 2026");
    expect(deadlineText(null, NOW)).toBeNull();
  });

  it("puts the deadline in the overline's meta", () => {
    const v = getOfferStatus(offer({ expires_at: "2026-11-09T18:00:00" }), seller());
    expect(v.meta).toBe("reply by 18:00 today");
    expect(v.urgent).toBe(true);
  });
});

describe("buyerRanking", () => {
  const book = (over: Partial<OrderBook>): OrderBook =>
    ({ role: "buyer", active_count: 4, your_rank: 2, is_leading: false, tiers: [], entries: [], your_entry: null, ...over } as OrderBook);

  it("names the place, the lead, or the only offer", () => {
    expect(buyerRanking(book({}))).toEqual({ short: "2nd of 4", sentence: "You're 2nd of 4 offers." });
    expect(buyerRanking(book({ your_rank: 3, active_count: 13 }))?.short).toBe("3rd of 13");
    expect(buyerRanking(book({ your_rank: 11, active_count: 12 }))?.short).toBe("11th of 12");
    expect(buyerRanking(book({ your_rank: 1, is_leading: true }))).toEqual({ short: "Leading", sentence: "Yours is the leading offer of 4." });
    expect(buyerRanking(book({ your_rank: 1, is_leading: true, active_count: 1 }))?.short).toBe("Only offer");
  });

  it("says nothing without a rank, or to a seller", () => {
    expect(buyerRanking(undefined)).toBeNull();
    expect(buyerRanking(book({ your_rank: null }))).toBeNull();
    expect(buyerRanking(book({ role: "seller" }))).toBeNull();
  });

  it("goes first in the waiting buyer's status card, and never in the seller's", () => {
    const ranking = buyerRanking(book({}));
    expect(getOfferStatus(offer(), buyer({ ranking })).body)
      .toBe("You're 2nd of 4 offers. You can raise it now or wait for their answer.");
    const o = offer({ status: "COUNTERED", last_actor_club_id: SELLER, events: [ev("SENT", BUYER), ev("COUNTERED", SELLER)] });
    expect(getOfferStatus(o, seller({ isMyTurn: false, ranking })).body).toBeUndefined();
  });
});

