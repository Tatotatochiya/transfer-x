import { describe, expect, it } from "vitest";
import { DEFAULT_PLAYER_FILTERS, type PlayerFilterState } from "../players/PlayerFilters";
import { activeFilterChips, clearFilters } from "./ActiveFilterChips";

const f = (over: Partial<PlayerFilterState> = {}): PlayerFilterState => ({ ...DEFAULT_PLAYER_FILTERS, ...over });
const labels = (over: Partial<PlayerFilterState>) => activeFilterChips(f(over)).map((c) => c.label);

describe("activeFilterChips", () => {
  it("defaults give only On TransferX", () => {
    expect(labels({})).toEqual(["On TransferX"]);
    expect(labels({ buyable: false })).toEqual([]);
  });

  it("labels each field", () => {
    const all = labels({
      position: "MID", status: "FREE_AGENT", min_age: "18", max_age: "25", min_value: "5", max_value: "20",
      contract_expiry_months: "12", min_form_score: "60", open_to_offers: true, nationality: "Sweden",
      club_search: "Arsenal", min_goals: "10", min_assists: "5", min_appearances: "20", min_avg_rating: "7",
    });
    expect(all).toEqual([
      "On TransferX", "MID", "Free agents", "Age 18–25", "€5–20M market value", "Contract ends within 12 months",
      "Form 60+", "Listed", "Sweden", "Club: Arsenal", "Goals 10+", "Assists 5+", "Apps 20+", "Rating 7.0+",
    ]);
  });

  it("one-sided ages and values", () => {
    expect(labels({ max_age: "25" })).toContain("Under 26");
    expect(labels({ min_age: "26" })).toContain("26 and over");
    expect(labels({ min_value: "5" })).toContain("€5M+ market value");
    expect(labels({ max_value: "20" })).toContain("Up to €20M market value");
  });

  it("search and sort never make a chip", () => {
    expect(labels({ search: "Isak", sort_by: "price", sort_dir: "asc" })).toEqual(["On TransferX"]);
  });

  it("removing a chip resets its field; removing On TransferX turns it off", () => {
    const chips = activeFilterChips(f({ min_age: "18", max_age: "25" }));
    expect(chips.find((c) => c.key === "age")!.remove(f({ min_age: "18", max_age: "25" }))).toMatchObject({ min_age: "", max_age: "" });
    expect(chips.find((c) => c.key === "buyable")!.remove(f()).buyable).toBe(false);
  });

  it("Clear keeps the search and the sort", () => {
    expect(clearFilters(f({ search: "Isak", position: "GK", sort_by: "price", sort_dir: "asc", buyable: false })))
      .toEqual(f({ search: "Isak", sort_by: "price", sort_dir: "asc" }));
  });
});
