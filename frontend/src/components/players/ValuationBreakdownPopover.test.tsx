import { describe, it, expect } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import ValuationBreakdownPopover from "./ValuationBreakdownPopover";
import type { FairValueSignal } from "../../types/api";

function makeSignal(overrides: Partial<FairValueSignal> = {}): FairValueSignal {
  return {
    player_id: "p1",
    fair_value: 41_500_000,
    fair_value_low: 35_300_000,
    fair_value_high: 47_800_000,
    currency: "GBP",
    performance_score: 71.5,
    confidence: "HIGH",
    model_version: "market-v2",
    league_tier: 1,
    age_factor: 0.91,
    age: 29,
    minutes: 2700,
    as_of: new Date().toISOString(),
    breakdown: [{ label: "Goals per 90", value: "0.50", norm: 0.62, weight: 35, contribution: 21.9 }],
    divergence: null,
    ...overrides,
  };
}

const drivers = [
  { key: "anchor", label: "Position anchor", detail: "", factor: null, value_after: 19_000_000 },
  { key: "league", label: "League", detail: "", factor: 1.0, value_after: 19_000_000 },
  { key: "performance", label: "Performance", detail: "", factor: 4.86, value_after: 92_300_000 },
  { key: "contract", label: "Contract", detail: "0.5 years remaining", factor: 0.5, value_after: 41_500_000 },
];

describe("ValuationBreakdownPopover", () => {
  it("shows the market-v2 value build-up, hiding neutral steps", () => {
    render(<ValuationBreakdownPopover signal={makeSignal({ drivers, comparables_used: 6 })} />);
    fireEvent.click(screen.getByLabelText("Valuation breakdown"));
    expect(screen.getByText("How the value builds")).toBeInTheDocument();
    expect(screen.getByText("Contract")).toBeInTheDocument();
    expect(screen.queryByText("League")).not.toBeInTheDocument(); // ×1.00
    expect(screen.getByText(/6 comparable transfers/)).toBeInTheDocument();
    expect(screen.getByText(/not an official valuation/)).toBeInTheDocument();
  });

  it("renders v1 valuations exactly as before", () => {
    render(<ValuationBreakdownPopover signal={makeSignal({ model_version: "boxscore-v1" })} />);
    fireEvent.click(screen.getByLabelText("Valuation breakdown"));
    expect(screen.queryByText("How the value builds")).not.toBeInTheDocument();
    expect(screen.getByText("Top drivers")).toBeInTheDocument();
  });
});
