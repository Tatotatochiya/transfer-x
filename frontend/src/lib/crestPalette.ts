/**
 * Colour suggestions read from a club's crest (feature_spec/club-dashboard
 * §3.2, Q3). In the browser only: a crest on a host that doesn't allow
 * cross-origin reads gives no suggestions, and the club picks by hand. The
 * server never fetches crests for this.
 */
import { INK, WHITE, contrast } from "./brandColour";

export interface ColourPair {
  primary: string;
  secondary: string;
  /** "Red and white" */
  label: string;
}

const BINS = 12; // 30° each
const MIN_HUE_GAP = 20;
const NEAR = 0.06 * 255; // within 6% of white or black
const MIN_SATURATION = 0.2; // greys have no meaningful hue

function hex(r: number, g: number, b: number): string {
  return "#" + [r, g, b].map((c) => Math.round(c).toString(16).padStart(2, "0")).join("").toUpperCase();
}

function hsl(r: number, g: number, b: number): { h: number; s: number; l: number } {
  const [x, y, z] = [r / 255, g / 255, b / 255];
  const max = Math.max(x, y, z), min = Math.min(x, y, z), l = (max + min) / 2;
  if (max === min) return { h: 0, s: 0, l };
  const d = max - min;
  const s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
  const h = max === x ? (y - z) / d + (y < z ? 6 : 0) : max === y ? (z - x) / d + 2 : (x - y) / d + 4;
  return { h: h * 60, s, l };
}

const HUE_NAMES: [number, string][] = [
  [15, "red"], [45, "orange"], [70, "yellow"], [160, "green"], [200, "teal"],
  [260, "blue"], [290, "purple"], [335, "pink"], [360, "red"],
];

export function colourName(colour: string): string {
  if (colour === WHITE) return "white";
  if (colour === INK || colour === "#000000") return "black";
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(colour.slice(i, i + 2), 16));
  const { h, s, l } = hsl(r, g, b);
  if (s < MIN_SATURATION) return l > 0.5 ? "silver" : "grey";
  const name = HUE_NAMES.find(([upTo]) => h < upTo)?.[1] ?? "red";
  return l < 0.25 ? `dark ${name}` : name;
}

function pair(primary: string, secondary: string): ColourPair {
  const label = `${colourName(primary)} and ${colourName(secondary)}`;
  return { primary, secondary, label: label[0].toUpperCase() + label.slice(1) };
}

/** Suggestions from RGBA pixels: up to two pairs, or [] when the crest has no colour. */
export function paletteFromPixels(data: ArrayLike<number>): ColourPair[] {
  const bins = Array.from({ length: BINS }, () => ({ n: 0, r: 0, g: 0, b: 0, h: 0 }));
  for (let i = 0; i + 3 < data.length; i += 4) {
    const [r, g, b, a] = [data[i], data[i + 1], data[i + 2], data[i + 3]];
    if (a < 128) continue;
    if (Math.min(r, g, b) >= 255 - NEAR || Math.max(r, g, b) <= NEAR) continue;
    const { h, s } = hsl(r, g, b);
    if (s < MIN_SATURATION) continue;
    const bin = bins[Math.floor(h / (360 / BINS)) % BINS];
    bin.n++; bin.r += r; bin.g += g; bin.b += b; bin.h += h;
  }
  const ranked = bins.filter((b) => b.n > 0).sort((x, y) => y.n - x.n)
    .map((b) => ({ colour: hex(b.r / b.n, b.g / b.n, b.b / b.n), hue: b.h / b.n }));
  if (ranked.length === 0) return [];
  const top = ranked[0];
  const hueGap = (a: number, b: number) => Math.min(Math.abs(a - b), 360 - Math.abs(a - b));
  const second = ranked.slice(1).find((c) => hueGap(c.hue, top.hue) >= MIN_HUE_GAP);
  const neutral = contrast(top.colour, WHITE) >= contrast(top.colour, INK) ? WHITE : INK;
  return [...(second ? [pair(top.colour, second.colour)] : []), pair(top.colour, neutral)];
}

/** Suggestions for a crest URL, or [] if it can't be loaded or read. */
export async function crestPalette(url: string | null | undefined): Promise<ColourPair[]> {
  if (!url) return [];
  try {
    const img = new Image();
    img.crossOrigin = "anonymous";
    // The page has already shown this crest in an <img> without crossOrigin;
    // a browser may reuse that cached copy, which a canvas can't read.
    img.src = url + (url.includes("?") ? "&" : "?") + "palette=1";
    await img.decode();
    const canvas = document.createElement("canvas");
    canvas.width = canvas.height = 64;
    const ctx = canvas.getContext("2d");
    if (!ctx) return [];
    ctx.drawImage(img, 0, 0, 64, 64);
    return paletteFromPixels(ctx.getImageData(0, 0, 64, 64).data); // throws when tainted
  } catch {
    return [];
  }
}
