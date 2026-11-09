import { describe, expect, it } from "vitest";
import { DEFAULT_PLAYER_FILTERS } from "../components/players/PlayerFilters";
import { marketParams } from "./marketQuery";

describe("marketParams", () => {
  it("sends the price in pounds and the market value in euros, both from millions", () => {
    const p = marketParams({ ...DEFAULT_PLAYER_FILTERS, min_price: "5", max_price: "20", min_value: "3" });
    expect(p).toMatchObject({ min_price: 5_000_000, max_price: 20_000_000, min_market_value: 3_000_000 });
    expect(p).not.toHaveProperty("max_market_value");
  });

  it("sends nothing for an empty filter but the sort and buyable", () => {
    expect(marketParams(DEFAULT_PLAYER_FILTERS)).toEqual({ sort_by: "name", sort_dir: "asc", buyable: true });
  });
});
