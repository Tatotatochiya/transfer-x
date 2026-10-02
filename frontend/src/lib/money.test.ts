import { describe, expect, it } from "vitest";

import { parseValuation } from "./money";

describe("parseValuation", () => {
  it.each([
    ["18", 18_000_000],
    ["6.7", 6_700_000],
    ["£18m", 18_000_000],
    ["18M", 18_000_000],
    ["18.5 mn", 18_500_000],
    ["750k", 750_000],
    ["£750K", 750_000],
    ["18000000", 18_000_000],
    ["18,000,000", 18_000_000],
    ["£ 22,500,000", 22_500_000],
  ])("reads %s as £%d", (input, expected) => {
    expect(parseValuation(input)).toBe(expected);
  });

  it("clears on empty and refuses what isn't a figure", () => {
    expect(parseValuation("  ")).toBeNull();
    expect(parseValuation("about 20m")).toBeUndefined();
    expect(parseValuation("20m-25m")).toBeUndefined();
  });
});
