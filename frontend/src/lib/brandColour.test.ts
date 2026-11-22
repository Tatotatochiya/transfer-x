import { describe, expect, it } from "vitest";
import { INK, WHITE, bandColours, contrast, darken, stripeColour } from "./brandColour";

describe("contrast", () => {
  it("matches WCAG", () => {
    expect(contrast("#FFFFFF", "#000000")).toBeCloseTo(21, 5);
    expect(contrast("#DB0007", WHITE)).toBeCloseTo(5.23, 2);
    expect(contrast(WHITE, "#DB0007")).toBe(contrast("#DB0007", WHITE));
  });
});

describe("bandColours", () => {
  it("puts white text on a primary white reads on", () => {
    expect(bandColours("#DB0007", "light")).toMatchObject({ bg: "#DB0007", text: WHITE });
    expect(bandColours("#034694", "light")).toMatchObject({ bg: "#034694", text: WHITE });
  });

  it("puts ink on a light primary", () => {
    expect(bandColours("#F5C400", "light")).toMatchObject({ bg: "#F5C400", text: INK });
  });

  it("darkens a primary neither text reads on until white does", () => {
    const band = bandColours("#777777", "light");
    expect(band).toMatchObject({ bg: "#6D6D6D", text: WHITE });
  });

  it("starts 25% darker in dark mode", () => {
    expect(darken("#DB0007", 0.25)).toBe("#A40005");
    expect(bandColours("#DB0007", "dark")).toMatchObject({ bg: "#A40005", text: WHITE });
    // White at 25% darker is still light: white text fails, so ink.
    expect(bandColours("#FFFFFF", "dark")).toMatchObject({ bg: "#BFBFBF", text: INK });
  });

  it("never returns a pair under 4.5:1", () => {
    for (const hex of ["#000000", "#FFFFFF", "#777777", "#808080", "#00FF00", "#FFFF00", "#FF00FF", "#3A7BD5"]) {
      for (const theme of ["light", "dark"] as const) {
        const { bg, text } = bandColours(hex, theme);
        expect(contrast(bg, text), `${hex} ${theme}`).toBeGreaterThanOrEqual(4.5);
      }
    }
  });
});

describe("stripeColour", () => {
  it("uses the secondary when it shows against the band", () => {
    expect(stripeColour("#FFFFFF", bandColours("#DB0007", "light"))).toBe("#FFFFFF");
  });

  it("falls back when there's no secondary or it matches the band", () => {
    const red = bandColours("#DB0007", "light");
    expect(stripeColour(null, red)).toBe("rgba(255, 255, 255, 0.9)");
    expect(stripeColour("#DA0008", red)).toBe("rgba(255, 255, 255, 0.9)");
    expect(stripeColour(undefined, bandColours("#F5C400", "light"))).toBe(INK);
  });
});
