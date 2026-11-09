import { describe, expect, it } from "vitest";
import { weeklyWageWarning } from "./budgetSanity";

describe("weeklyWageWarning", () => {
  it("is quiet for a real weekly budget", () => {
    expect(weeklyWageWarning(3_500_000)).toBeNull();
    expect(weeklyWageWarning("")).toBeNull();
    expect(weeklyWageWarning("abc")).toBeNull();
  });

  it("warns when the figure looks yearly", () => {
    expect(weeklyWageWarning("49900000")).toBe(
      "£49.9M a week is £2.6B a year. The biggest Premier League wage bills are about £4M a week. Is this a yearly figure? This field is per week.",
    );
  });
});
