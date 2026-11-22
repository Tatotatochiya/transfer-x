import { describe, expect, it } from "vitest";
import { seasonLabel } from "./season";

describe("seasonLabel", () => {
  it("turns over on 1 July", () => {
    expect(seasonLabel(new Date(2026, 5, 30))).toBe("2025/26");
    expect(seasonLabel(new Date(2026, 6, 1))).toBe("2026/27");
    expect(seasonLabel(new Date(2026, 10, 22))).toBe("2026/27");
  });

  it("pads the century turn", () => {
    expect(seasonLabel(new Date(2099, 8, 1))).toBe("2099/00");
    expect(seasonLabel(new Date(2008, 8, 1))).toBe("2008/09");
  });
});
