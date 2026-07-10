import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import FairValueBadge from "./FairValueBadge";
import type { FairValueSignal, ValuationDivergence } from "../../types/api";
import type { ValuationBand } from "../../types/enums";

function makeSignal(overrides: Partial<FairValueSignal> = {}): FairValueSignal {
  return {
    player_id: "p1",
    fair_value: 66_500_000,
    fair_value_low: 56_600_000,
    fair_value_high: 76_500_000,
    currency: "GBP",
    performance_score: 90.58,
    confidence: "HIGH",
    model_version: "boxscore-v1",
    league_tier: 1,
    age_factor: 1.0,
    age: 25,
    minutes: 2700,
    as_of: new Date().toISOString(),
    breakdown: [
      { label: "Goals per 90", value: "0.80", norm: 1.0, weight: 35, contribution: 35.0 },
      { label: "Average rating", value: "7.6", norm: 0.8, weight: 20, contribution: 16.0 },
    ],
    divergence: null,
    ...overrides,
  };
}

function divergence(band: ValuationBand, pct: number): ValuationDivergence {
  return { reference_price: 80_000_000, pct, band };
}

describe("FairValueBadge", () => {
  it("renders nothing when signal is null", () => {
    const { container } = render(<FairValueBadge signal={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders nothing when signal is undefined", () => {
    const { container } = render(<FairValueBadge signal={undefined} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("full strip shows model value, range, divergence and confidence", () => {
    render(
      <FairValueBadge
        signal={makeSignal({ divergence: divergence("ABOVE", 20.3) })}
      />
    );
    expect(screen.getByText(/Asking £80\.0m/)).toBeInTheDocument();
    expect(screen.getByText(/Model £66\.5m/)).toBeInTheDocument();
    expect(screen.getByText(/range £56\.6m–£76\.5m/)).toBeInTheDocument();
    expect(screen.getByText(/\+20% above model/)).toBeInTheDocument();
    expect(screen.getByText(/HIGH confidence/)).toBeInTheDocument();
  });

  it("uses the referenceLabel when given", () => {
    render(
      <FairValueBadge
        signal={makeSignal({ divergence: divergence("IN_LINE", 2.0) })}
        referenceLabel="Agreed fee"
      />
    );
    expect(screen.getByText(/Agreed fee £80\.0m/)).toBeInTheDocument();
  });

  it("omits reference and divergence when divergence is null", () => {
    render(<FairValueBadge signal={makeSignal()} />);
    expect(screen.queryByText(/Asking/)).not.toBeInTheDocument();
    expect(screen.queryByText(/above model|below model|in line/i)).not.toBeInTheDocument();
    expect(screen.getByText(/Model £66\.5m/)).toBeInTheDocument();
  });

  const bandCases: Array<[ValuationBand, number, RegExp, string]> = [
    ["WELL_BELOW", -30.0, /−30% well below model/, "text-emerald-500"],
    ["BELOW", -19.4, /−19% below model/, "text-emerald-400"],
    ["IN_LINE", 2.0, /\+2% in line with model/, "text-slate-400"],
    ["ABOVE", 20.3, /\+20% above model/, "text-amber-400"],
    ["WELL_ABOVE", 45.0, /\+45% well above model/, "text-rose-400"],
  ];

  bandCases.forEach(([band, pct, phrase, colour]) => {
    it(`renders ${band} with its phrase and colour`, () => {
      render(<FairValueBadge signal={makeSignal({ divergence: divergence(band, pct) })} />);
      const el = screen.getByText(phrase);
      expect(el).toHaveClass(colour);
    });
  });

  it("LOW confidence mutes the band colour and shows the low-confidence tag", () => {
    render(
      <FairValueBadge
        signal={makeSignal({ confidence: "LOW", divergence: divergence("WELL_ABOVE", 45.0) })}
      />
    );
    expect(screen.getByText(/Low confidence/)).toBeInTheDocument();
    const el = screen.getByText(/\+45% well above model/);
    expect(el).toHaveClass("text-slate-500");
    expect(el).not.toHaveClass("text-rose-400");
  });

  it("compact renders one pill with model value and divergence pct", () => {
    render(
      <FairValueBadge
        signal={makeSignal({ divergence: divergence("ABOVE", 20.3) })}
        compact
      />
    );
    expect(screen.getByText(/Model £66\.5m/)).toBeInTheDocument();
    expect(screen.getByText(/\+20%/)).toBeInTheDocument();
    // compact pill never shows the range
    expect(screen.queryByText(/range/)).not.toBeInTheDocument();
  });

  it("compact without divergence shows just the model value", () => {
    render(<FairValueBadge signal={makeSignal()} compact />);
    expect(screen.getByText(/Model £66\.5m/)).toBeInTheDocument();
    expect(screen.queryByText(/%/)).not.toBeInTheDocument();
  });

  it("flags stale valuations (as_of older than 60 days)", () => {
    const old = new Date(Date.now() - 90 * 86_400_000).toISOString();
    render(<FairValueBadge signal={makeSignal({ as_of: old })} />);
    expect(screen.getByText(/as of /)).toBeInTheDocument();
  });
});
