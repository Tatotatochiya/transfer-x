import { describe, it, expect } from "vitest";
import {
  positionVariant,
  playerStatusVariant,
  playerStatusLabel,
  saleTypeLabel,
  offerStatusVariant,
  offerOutcome,
  dealStatusVariant,
  dealStageLabel,
} from "./badges";

describe("positionVariant", () => {
  it("GK → warning (amber)", () => expect(positionVariant("GK")).toBe("warning"));
  it("DEF → info (blue)",    () => expect(positionVariant("DEF")).toBe("info"));
  it("MID → success (emerald)", () => expect(positionVariant("MID")).toBe("success"));
  it("FWD → danger (red)",   () => expect(positionVariant("FWD")).toBe("danger"));
});

describe("playerStatusVariant", () => {
  it("FREE_AGENT → success", () => expect(playerStatusVariant("FREE_AGENT")).toBe("success"));
  it("CONTRACTED → info",    () => expect(playerStatusVariant("CONTRACTED")).toBe("info"));
  // ADR 0003: EXTERNAL must never get the green "available" styling — that
  // pairing is what made ~7.8k contracted professionals look signable.
  it("EXTERNAL → info, never success", () => expect(playerStatusVariant("EXTERNAL")).toBe("info"));
});

describe("playerStatusLabel", () => {
  it("FREE_AGENT → Free Agent",  () => expect(playerStatusLabel("FREE_AGENT")).toBe("Free Agent"));
  it("CONTRACTED → Contracted",  () => expect(playerStatusLabel("CONTRACTED")).toBe("Contracted"));
  it("EXTERNAL → Contracted",    () => expect(playerStatusLabel("EXTERNAL")).toBe("Contracted"));
});

describe("saleTypeLabel", () => {
  it("AUCTION → Auction",               () => expect(saleTypeLabel("AUCTION")).toBe("Auction"));
  it("OPEN_TO_OFFERS → Open to Offers", () => expect(saleTypeLabel("OPEN_TO_OFFERS")).toBe("Open to Offers"));
  it("FIXED_PRICE → Fixed Price",       () => expect(saleTypeLabel("FIXED_PRICE")).toBe("Fixed Price"));
});

describe("offerStatusVariant", () => {
  it("SENT → info",      () => expect(offerStatusVariant("SENT")).toBe("info"));
  it("ACCEPTED → success", () => expect(offerStatusVariant("ACCEPTED")).toBe("success"));
  it("REJECTED → danger", () => expect(offerStatusVariant("REJECTED")).toBe("danger"));
  it("COUNTERED → warning", () => expect(offerStatusVariant("COUNTERED")).toBe("warning"));
  it("EXPIRED → neutral", () => expect(offerStatusVariant("EXPIRED")).toBe("neutral"));
});

describe("dealStatusVariant", () => {
  it("IN_PROGRESS → info",           () => expect(dealStatusVariant("IN_PROGRESS")).toBe("info"));
  it("COMPLETED → success",          () => expect(dealStatusVariant("COMPLETED")).toBe("success"));
  it("COLLAPSED → danger",           () => expect(dealStatusVariant("COLLAPSED")).toBe("danger"));
  it("PENDING_COMPLETION → warning", () => expect(dealStatusVariant("PENDING_COMPLETION")).toBe("warning"));
});

describe("dealStageLabel", () => {
  it("AGREEMENT → Agreement", () => expect(dealStageLabel("AGREEMENT")).toBe("Agreement"));
  it("PAPERWORK → Paperwork", () => expect(dealStageLabel("PAPERWORK")).toBe("Paperwork"));
  it("CONFIRMED → Confirmed", () => expect(dealStageLabel("CONFIRMED")).toBe("Confirmed"));
  it("COMPLETED → Completed", () => expect(dealStageLabel("COMPLETED")).toBe("Completed"));
});

describe("offerOutcome", () => {
  it("no deal yet → the offer's own status", () => {
    expect(offerOutcome("SENT", null)).toEqual({ label: "Sent", variant: "info" });
  });

  // The defect this exists to prevent: an accepted offer whose deal later
  // collapsed still rendered ACCEPTED in the green success badge, so a dead
  // transfer read as a win.
  it("accepted, then the deal collapsed → danger, never success", () => {
    const out = offerOutcome("ACCEPTED", { status: "COLLAPSED", stage: "PERSONAL_TERMS" });
    expect(out.variant).toBe("danger");
    expect(out.label).toBe("Collapsed");
    expect(out.note).toBe("at personal terms");
  });

  it("collapsed with no stage recorded still reads as collapsed", () => {
    expect(offerOutcome("ACCEPTED", { status: "COLLAPSED", stage: null }).variant).toBe("danger");
  });

  it("deal completed → success", () => {
    expect(offerOutcome("ACCEPTED", { status: "COMPLETED", stage: "COMPLETED" }).variant).toBe("success");
  });

  it("deal live → the stage, not the acceptance", () => {
    const out = offerOutcome("ACCEPTED", { status: "IN_PROGRESS", stage: "PAPERWORK" });
    expect(out).toEqual({ label: "Paperwork", variant: "info", note: "deal in progress" });
  });
});
