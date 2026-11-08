import { describe, expect, it } from "vitest";
import type { Offer, OfferEvent } from "../types/api";
import { lastChange } from "./offerChanges";

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
