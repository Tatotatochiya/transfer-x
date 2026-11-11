import { describe, expect, it } from "vitest";
import type { FairValueSignal, Player } from "../types/api";
import { askingPrice, playerPrice } from "./playerPrice";

const player = (over: Partial<Player> = {}) => ({ market_value: null, status: "CONTRACTED", ...over }) as Player;
const signal = (fair: number, reference?: number) =>
  ({ fair_value: fair, divergence: reference != null ? { reference_price: reference, pct: 0, band: "IN_LINE" } : null }) as unknown as FairValueSignal;

describe("playerPrice", () => {
  it("uses the asking price when there is one", () => {
    expect(playerPrice(player(), signal(20_000_000, 7_400_000))).toEqual({ amount: 7_400_000, basis: "asking", text: "£7.4M" });
  });

  it("falls back to the model", () => {
    expect(playerPrice(player(), signal(12_000_000))).toEqual({ amount: 12_000_000, basis: "model", text: "£12M" });
  });

  it("knows nothing without either", () => {
    expect(playerPrice(player())).toEqual({ amount: null, basis: null, text: "—" });
  });

  it("a free agent costs nothing", () => {
    expect(playerPrice(player({ status: "FREE_AGENT" }), signal(5_000_000, 4_000_000))).toEqual({ amount: 0, basis: "free agent", text: "Free" });
  });

  it("askingPrice keeps the list row's market value fallback", () => {
    expect(askingPrice(player({ market_value: 3_000_000 }))).toBe(3_000_000);
    expect(askingPrice(player({ market_value: 3_000_000 }), signal(1, 2_000_000))).toBe(2_000_000);
  });
});
