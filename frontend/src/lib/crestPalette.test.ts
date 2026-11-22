import { describe, expect, it } from "vitest";
import { INK, WHITE } from "./brandColour";
import { colourName, crestPalette, paletteFromPixels } from "./crestPalette";

/** RGBA pixels: [r, g, b, a] repeated `n` times each. */
function pixels(...runs: [number, number, number, number, number][]): number[] {
  return runs.flatMap(([r, g, b, a, n]) => Array.from({ length: n }, () => [r, g, b, a]).flat());
}

describe("paletteFromPixels", () => {
  it("picks the two most common distinct hues, then the top one with white or ink", () => {
    const got = paletteFromPixels(pixels([219, 0, 7, 255, 60], [3, 70, 148, 255, 30], [230, 10, 20, 255, 10]));
    expect(got).toHaveLength(2);
    expect(got[0].label).toBe("Red and blue");
    expect(got[0].primary).toMatch(/^#[0-9A-F]{6}$/);
    expect(got[1]).toMatchObject({ primary: got[0].primary, secondary: WHITE, label: "Red and white" });
  });

  it("ignores transparent, near-white, near-black and grey pixels", () => {
    const got = paletteFromPixels(pixels(
      [255, 255, 255, 255, 500], [5, 5, 5, 255, 500], [128, 128, 128, 255, 500],
      [0, 0, 255, 50, 500], [245, 196, 0, 255, 5],
    ));
    expect(got).toEqual([expect.objectContaining({ secondary: INK, label: "Yellow and black" })]);
  });

  it("gives nothing for a crest with no colour", () => {
    expect(paletteFromPixels(pixels([255, 255, 255, 255, 10], [0, 0, 0, 255, 10]))).toEqual([]);
  });
});

describe("colourName", () => {
  it("names common club colours", () => {
    expect(colourName("#DB0007")).toBe("red");
    expect(colourName("#034694")).toBe("blue");
    expect(colourName("#0A1A3A")).toBe("dark blue");
    expect(colourName(WHITE)).toBe("white");
  });
});

describe("crestPalette", () => {
  it("returns [] with no URL, and when the image can't be read", async () => {
    expect(await crestPalette(null)).toEqual([]);
    // jsdom can't decode images: the same path as a crest that fails to load.
    expect(await crestPalette("https://crests.test/arsenal.png")).toEqual([]);
  });
});
