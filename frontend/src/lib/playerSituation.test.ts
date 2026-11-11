import { describe, expect, it } from "vitest";
import type { ActiveDealStub } from "../types/api";
import { playerSituation, type SituationInput } from "./playerSituation";

const ME = "my-club";

function input(over: Partial<SituationInput> = {}): SituationInput {
  return {
    playerId: "p1", isAuthenticated: true, isAgent: false, isPlayerAccount: false, isMyPlayer: false,
    canList: false, listingsKnown: false, listingId: undefined, isOffPlatform: false, isFreeAgentPlayer: false,
    inPreContractWindow: false, canMarketWrite: true, activeDeal: null, myClubId: ME, contractEndDate: null,
    clubName: "Chelsea", parentClubName: null, onLoanToUs: false, hasReleaseClause: false, ...over,
  };
}

const deal = (buyer: string, seller: string): ActiveDealStub => ({
  id: "d1", status: "IN_PROGRESS", stage: "PAPERWORK", agreed_fee: 1, completed_at: null,
  buyer_club: { id: buyer, name: buyer === ME ? "Us FC" : "Arsenal" } as ActiveDealStub["buyer_club"],
  seller_club: { id: seller, name: seller === ME ? "Us FC" : "Chelsea" } as ActiveDealStub["seller_club"],
});

const ALL = ["compare", "ask-transferx", "view-club"];

describe("playerSituation: one row per situation", () => {
  it.each([
    [1, { isAuthenticated: false }, "Sign in to make an offer", undefined],
    [2, { isAgent: true }, undefined, undefined],
    [2, { isPlayerAccount: true }, undefined, undefined],
    [3, { isMyPlayer: true, canList: true, listingsKnown: true }, "List for sale", undefined],
    [4, { isMyPlayer: true, canList: true, listingsKnown: true, listingId: "s9" }, "View listing", undefined],
    [5, { isMyPlayer: true, canList: true, listingsKnown: false }, undefined, undefined],
    [6, { activeDeal: deal(ME, "chelsea") }, "View the deal", undefined],
    [7, { activeDeal: deal("arsenal", "chelsea") }, undefined, undefined],
    [8, { isOffPlatform: true, clubName: "Hamburger SV" }, undefined, undefined],
    [9, { canMarketWrite: false }, undefined, undefined],
    [10, { isFreeAgentPlayer: true, clubName: null }, "Sign him", undefined],
    [11, { inPreContractWindow: true, contractEndDate: "2027-06-30" }, "Make an offer", "Offer a pre-contract"],
    [12, {}, "Make an offer", "Ask his club"],
  ] as [number, Partial<SituationInput>, string | undefined, string | undefined][])(
    "row %i", (row, over, primary, secondary) => {
      const s = playerSituation(input(over));
      expect(s.row).toBe(row);
      expect(s.primary?.label).toBe(primary);
      expect(s.secondary?.label).toBe(secondary);
    },
  );

  it("links where it should", () => {
    expect(playerSituation(input({ isAuthenticated: false })).primary?.to).toBe("/login");
    expect(playerSituation(input()).primary?.to).toBe("/offers/new?player_id=p1");
    expect(playerSituation(input({ isMyPlayer: true, canList: true, listingsKnown: true, listingId: "s9" })).primary?.to).toBe("/sales/s9");
    expect(playerSituation(input({ activeDeal: deal(ME, "chelsea") })).primary?.to).toBe("/deals/d1");
  });

  it("More holds the right items per row", () => {
    expect(playerSituation(input({ isAuthenticated: false })).more).toEqual([]);
    expect(playerSituation(input({ isAgent: true })).more).toEqual(["view-club"]);
    expect(playerSituation(input({ isMyPlayer: true, canList: true, listingsKnown: true })).more).toEqual(["compare", "ask-transferx"]);
    expect(playerSituation(input()).more).toEqual(ALL);
    expect(playerSituation(input({ isFreeAgentPlayer: true, clubName: null })).more).toEqual(["compare", "ask-transferx"]);
  });

  it("the sentences", () => {
    expect(playerSituation(input({ isOffPlatform: true, clubName: "Hamburger SV" })).note?.text)
      .toBe("Hamburger SV is not on TransferX, so an offer could not be answered. Shortlist him to follow his form and contract.");
    expect(playerSituation(input({ canMarketWrite: false })).note?.text)
      .toBe("Your role can't send offers. Ask your club's owner or sporting director.");
    expect(playerSituation(input({ isFreeAgentPlayer: true })).note?.text)
      .toBe("Free agent. There's no fee: you agree his wage and contract.");
    expect(playerSituation(input({ inPreContractWindow: true, contractEndDate: "2027-06-30" })).note?.text)
      .toBe("His contract ends 30 Jun 2027. You can agree a free move for then, or buy him now.");
    expect(playerSituation(input()).note).toBeUndefined();
  });
});

describe("playerSituation: extras", () => {
  it("pre-contract with a release clause: the clause and Ask his club in More", () => {
    const s = playerSituation(input({ inPreContractWindow: true, contractEndDate: "2027-06-30", hasReleaseClause: true }));
    expect(s.more).toEqual(["ask-club", ...ALL, "release-clause"]);
  });

  it("a release clause is never the primary, and goes last in More", () => {
    const s = playerSituation(input({ hasReleaseClause: true }));
    expect(s.primary?.key).toBe("make-offer");
    expect(s.more[s.more.length - 1]).toBe("release-clause");
  });

  it("a loaned-in player: row 5 with the loan note", () => {
    const s = playerSituation(input({ isMyPlayer: true, onLoanToUs: true, parentClubName: "Brighton" }));
    expect(s.row).toBe(5);
    expect(s.primary).toBeUndefined();
    expect(s.note?.text).toBe("He's on loan to you from Brighton. Only Brighton can sell him.");
  });

  it("a deal where the viewer is the seller: row 6, naming the buyer and the stage", () => {
    const s = playerSituation(input({ isMyPlayer: true, canList: true, listingsKnown: true, activeDeal: deal("arsenal", ME) }));
    expect(s.row).toBe(6);
    expect(s.note).toEqual({ tone: "info", text: "Your deal with Arsenal is at paperwork. New offers are paused until it finishes or falls through." });
  });

  it("a deal where the viewer is neither club: row 7, the banner and no link", () => {
    const s = playerSituation(input({ activeDeal: deal("arsenal", "chelsea") }));
    expect(s.row).toBe(7);
    expect(s.dealBanner).toBe(true);
    expect(s.primary).toBeUndefined();
    expect(JSON.stringify(s)).not.toContain("/deals/");
  });

  it("a player on loan elsewhere: ask the parent club", () => {
    const s = playerSituation(input({ parentClubName: "Brighton" }));
    expect(s.secondary).toEqual({ key: "ask-club", label: "Ask Brighton" });
  });

  it("signed out, at a club off TransferX: no primary", () => {
    const s = playerSituation(input({ isAuthenticated: false, isOffPlatform: true }));
    expect(s.row).toBe(8);
    expect(s.primary).toBeUndefined();
    expect(s.more).toEqual(["compare", "view-club"]);
  });

  it("a completed deal changes nothing", () => {
    const done = { ...deal(ME, "chelsea"), status: "COMPLETED" } as ActiveDealStub;
    expect(playerSituation(input({ activeDeal: done })).row).toBe(12);
  });

  it("our open offer: View your offer, with whose move it is", () => {
    const waiting = playerSituation(input({ myOffer: { id: "o7", amount: "£30M", otherName: "Chelsea", isMyTurn: false } }));
    expect(waiting.primary).toEqual({ key: "view-offer", label: "View your offer", to: "/offers/o7" });
    expect(waiting.secondary?.label).toBe("Ask his club");
    expect(waiting.note).toEqual({ tone: "neutral", text: "Your £30M offer is with Chelsea." });
    const ours = playerSituation(input({ myOffer: { id: "o7", amount: "£34M", otherName: "Chelsea", isMyTurn: true } }));
    expect(ours.note).toEqual({ tone: "info", text: "Chelsea countered at £34M. It's your move." });
  });

  it("our open offer in the pre-contract window keeps the pre-contract beside it", () => {
    const s = playerSituation(input({
      inPreContractWindow: true, contractEndDate: "2027-06-30",
      myOffer: { id: "o7", amount: "£30M", otherName: "Chelsea", isMyTurn: false },
    }));
    expect(s.primary?.key).toBe("view-offer");
    expect(s.secondary?.key).toBe("pre-contract");
  });
});

