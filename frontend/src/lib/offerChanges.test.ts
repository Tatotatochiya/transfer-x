import { describe, expect, it } from "vitest";
import type { Offer, OfferEvent } from "../types/api";
import { diffDraft, lastChange, offerRounds } from "./offerChanges";

const ev = (event_type: OfferEvent["event_type"], payload: Record<string, unknown>, actor = "seller"): OfferEvent =>
  ({ id: `${event_type}-${Math.random()}`, offer_id: "o", event_type, actor_club_id: actor, payload, created_at: "2026-11-07T10:00:00Z" });

const offer = (over: Partial<Offer>): Offer => ({
  deal_type: "PERMANENT", fee_amount: 9_000_000, wage_weekly: 20_000, contract_years: 3, contract_end_date: null,
  instalments: [], clauses: [], sell_on_pct: null, events: [], ...over,
} as unknown as Offer);

describe("lastChange", () => {
  it("is null before anyone counters", () => {
    expect(lastChange(offer({ events: [ev("SENT", { fee_amount: "6000000" }, "buyer")] }))).toBeNull();
  });

  it("lists only the terms the counter changed, with what they were", () => {
    const change = lastChange(offer({
      events: [
        ev("SENT", { fee_amount: "6000000" }, "buyer"),
        ev("COUNTERED", { previous: { fee_amount: "6000000", wage_weekly: "20000", contract_years: 3, instalments: [] } }),
      ],
    }));
    expect(change?.kind).toBe("COUNTERED");
    expect(change?.actorClubId).toBe("seller");
    expect(change?.changes).toEqual([{ label: "Transfer fee", was: "£6,000,000", now: "£9,000,000" }]);
  });

  it("rebuilds the previous fee for counters made before terms were kept", () => {
    const change = lastChange(offer({
      events: [
        ev("SENT", { fee_amount: "5000000" }, "buyer"),
        ev("COUNTERED", { fee_amount: "6000000" }, "seller"),
        ev("COUNTERED", { fee_amount: "9000000" }, "buyer"),
      ],
    }));
    expect(change?.actorClubId).toBe("buyer");
    expect(change?.changes).toEqual([{ label: "Transfer fee", was: "£6,000,000", now: "£9,000,000" }]);
  });

  it("compares a loan's own terms", () => {
    const change = lastChange(offer({
      deal_type: "LOAN", fee_amount: null, loan_fee: 1_000_000, wage_split_pct: 0.5,
      events: [ev("COUNTERED", { previous: { loan_fee: "500000", wage_split_pct: "0.5" } })],
    } as Partial<Offer>));
    expect(change?.changes).toEqual([{ label: "Loan fee", was: "£500,000", now: "£1,000,000" }]);
  });
});

describe("offerRounds", () => {
  it("carries the fee forward when a counter didn't send one", () => {
    const rounds = offerRounds(offer({
      from_club_id: "buyer", to_club_id: "seller",
      events: [
        ev("SENT", { fee_amount: "5000000" }, "buyer"),
        ev("COUNTERED", { wage_weekly: "30000" }, "seller"),
        ev("COUNTERED", { fee_amount: "5500000" }, "buyer"),
      ],
    } as Partial<Offer>), "seller");
    expect(rounds.map((r) => [r.side, r.kind, r.fee])).toEqual([
      ["them", "SENT", 5_000_000], ["me", "COUNTERED", 5_000_000], ["them", "COUNTERED", 5_500_000],
    ]);
  });

  it("reads a loan raise's loan fee, and names sides for a non-party", () => {
    const rounds = offerRounds(offer({
      deal_type: "LOAN", from_club_id: "buyer", to_club_id: "seller",
      events: [ev("SENT", { fee_amount: null }, "buyer"), ev("IMPROVED", { loan_fee: "750000" }, "buyer")],
    } as Partial<Offer>), "someone-else");
    expect(rounds.map((r) => [r.side, r.fee])).toEqual([["buyer", null], ["buyer", 750_000]]);
  });
});

describe("diffDraft", () => {
  it("a fee-only change", () => {
    expect(diffDraft(offer({}), { fee_amount: 9_500_000, wage_weekly: 20_000, contract_years: 3, instalments: [], clauses: [], sell_on_pct: null }))
      .toEqual([{ label: "Transfer fee", was: "£9,000,000", now: "£9,500,000" }]);
  });

  it("a structure change", () => {
    expect(diffDraft(offer({}), { fee_amount: 9_000_000, instalments: [{}, {}], clauses: [], sell_on_pct: 0.1 }))
      .toEqual([
        { label: "Payment", was: "On completion", now: "2 instalments" },
        { label: "Sell-on", was: "None", now: "10%" },
      ]);
  });

  it("no change", () => {
    expect(diffDraft(offer({}), { fee_amount: 9_000_000, wage_weekly: 20_000, contract_years: 3 })).toEqual([]);
  });
});
