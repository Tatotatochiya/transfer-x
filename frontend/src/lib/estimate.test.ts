import { describe, expect, it } from "vitest";

import { formatCompactCurrency, formatCurrency, formatEstimate } from "./utils";

describe("money is always pounds; other currencies are estimates", () => {
  const rates = { EUR: 1.17, USD: 1.33 };

  it("writes £ whatever currency is picked", () => {
    expect(formatCurrency(18_000_000)).toBe("£18,000,000");
    expect(formatCompactCurrency(18_000_000)).toBe("£18.0m");
  });

  it("estimates in the picked currency", () => {
    expect(formatEstimate(18_000_000, "EUR", rates)).toBe("≈ €21.1m");
    expect(formatEstimate("450000", "USD", rates)).toBe("≈ $599k");
  });

  it("shows nothing for pounds, missing rates or missing amounts", () => {
    expect(formatEstimate(18_000_000, "GBP", rates)).toBe("");
    expect(formatEstimate(18_000_000, "EUR", null)).toBe("");
    expect(formatEstimate(null, "EUR", rates)).toBe("");
  });
});
