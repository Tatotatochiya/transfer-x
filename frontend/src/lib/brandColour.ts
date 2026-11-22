/**
 * A club's own colours on its Dashboard band (feature_spec/club-dashboard §3.3).
 * The band's text is white or ink, whichever reaches 4.5:1 on the band; if
 * neither does, the band is darkened until white does. Club colour is used
 * only in the band and the sidebar's crest ring, never on buttons or links.
 */

export const WHITE = "#FFFFFF";
export const INK = "#14171F";
const AA = 4.5;
/** A stripe this close to the band (by contrast) can't be seen. */
const STRIPE_MIN = 1.2;

function channels(hex: string): [number, number, number] {
  const h = hex.replace("#", "");
  return [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16)) as [number, number, number];
}

function luminance(hex: string): number {
  const [r, g, b] = channels(hex).map((c) => {
    const x = c / 255;
    return x <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

/** The WCAG contrast ratio of two #RRGGBB colours. */
export function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

/** `hex` with a share of black mixed in: 0.25 is 25% darker. */
export function darken(hex: string, share: number): string {
  return "#" + channels(hex)
    .map((c) => Math.round(c * (1 - share)).toString(16).padStart(2, "0"))
    .join("")
    .toUpperCase();
}

export interface BandColours {
  /** The band's background: the primary, or a darker version of it. */
  bg: string;
  text: typeof WHITE | typeof INK;
  /** The stripe when there's no usable secondary. */
  stripeFallback: string;
}

function lightRule(primary: string): Omit<BandColours, "stripeFallback"> {
  if (contrast(primary, WHITE) >= AA) return { bg: primary, text: WHITE };
  if (contrast(primary, INK) >= AA) return { bg: primary, text: INK };
  // Neither reads: darken in 8% steps until white does (it always will).
  for (let step = 1; step <= 12; step++) {
    const bg = darken(primary, 0.08 * step);
    if (contrast(bg, WHITE) >= AA) return { bg, text: WHITE };
  }
  return { bg: INK, text: WHITE };
}

/** The band's background and text for a primary colour in a theme. */
export function bandColours(primary: string, theme: "light" | "dark"): BandColours {
  // Dark mode starts 25% darker, so the band doesn't glare on a dark page.
  const start = theme === "dark" ? darken(primary, 0.25) : primary;
  const picked = theme === "dark" && contrast(start, WHITE) >= AA
    ? { bg: start, text: WHITE as typeof WHITE }
    : lightRule(start);
  return { ...picked, stripeFallback: picked.text === WHITE ? "rgba(255, 255, 255, 0.9)" : INK };
}

/** The bottom stripe: the secondary, unless there is none or it would vanish into the band. */
export function stripeColour(secondary: string | null | undefined, band: BandColours): string {
  if (!secondary || contrast(secondary, band.bg) < STRIPE_MIN) return band.stripeFallback;
  return secondary;
}
