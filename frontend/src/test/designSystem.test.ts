import { describe, expect, it } from "vitest";
import allowlist from "./design-allowlist.json";

/**
 * Guards for the type scale and colour roles (docs/design-system/TOKENS.md).
 *
 * 1. Banned classes: raw Tailwind sizes, uppercase outside `eyebrow`, opacity
 *    tints on colour tokens, extra-bold outside Lite, white text on accent.
 * 2. A ratchet: design-allowlist.json holds each file's remaining count per
 *    rule. A count may only go down, and the list must match exactly, so a fix
 *    is recorded when it's made. Regenerate it after a sweep with
 *    `UPDATE_DESIGN_ALLOWLIST=1 npx vitest run src/test/designSystem.test.ts`.
 * 3. Contrast: every text/background pair in TOKENS.md reaches 4.5:1 in both
 *    themes.
 */

// Vitest doesn't serve CSS as ?raw, so index.css is read from disk.
const fs = await import(/* @vite-ignore */ "node:fs" as string);
const proc = (globalThis as unknown as { process: { env: Record<string, string | undefined>; cwd(): string } }).process;
const env = proc.env;
// Paths from the frontend folder, where vitest runs (jsdom's import.meta.url isn't a file URL).
const css: string = fs.readFileSync(`${proc.cwd()}/src/index.css`, "utf8");

const sources = import.meta.glob(["../**/*.{ts,tsx}", "!../**/*.test.{ts,tsx}", "!../test/**"], {
  query: "?raw", import: "default", eager: true,
}) as Record<string, string>;

type Rule = "size" | "uppercase" | "tint" | "extrabold" | "white-on-accent";
type Counts = Partial<Record<Rule, number>>;

const LITE = /^src\/(pages|components)\/lite\//;

/** Comments out, strings and class names kept. `://` (a URL) isn't a comment. */
function stripComments(src: string): string {
  return src.replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|[^:"'`])\/\/.*$/gm, "$1");
}

function count(path: string, src: string): Counts {
  const code = stripComments(src);
  const out: Counts = {};
  const add = (rule: Rule, n: number) => { if (n) out[rule] = (out[rule] ?? 0) + n; };
  add("size", (code.match(/\btext-(xs|sm|base|lg|xl|[2-9]xl)\b/g) ?? []).length);
  add("size", (code.match(/\btext-\[[\d.]+(px|rem)\]/g) ?? []).length);
  add("uppercase", (code.match(/\buppercase\b/g) ?? []).length);
  for (const line of code.split("\n")) {
    // D7: overlays (bg-ink/N, not a listed hue), progress fills (data-progress)
    // and focus rings drawn from accent keep their opacity.
    if (line.includes("data-progress")) continue;
    const tints = line.match(/(?:[\w-]+:)*(?:bg|ring|border)-(?:success|warning-fill|danger|accent|text-muted|role-agent-text)\/\d+/g) ?? [];
    add("tint", tints.filter((t) => !/^(focus|focus-visible|focus-within):ring-accent\//.test(t)).length);
    if (/\bbg-accent\b(?![-/])/.test(line) && /\btext-white\b/.test(line)) add("white-on-accent", 1);
  }
  if (!LITE.test(path)) add("extrabold", (code.match(/\bfont-(extrabold|black)\b/g) ?? []).length);
  return out;
}

const actual: Record<string, Counts> = {};
for (const [key, src] of Object.entries(sources)) {
  const path = key.replace(/^\.\.\//, "src/");
  const c = count(path, src);
  if (Object.keys(c).length) actual[path] = c;
}

describe("design system: banned classes", () => {
  it("only goes down: each file matches its allowlist entry", () => {
    const sorted = Object.fromEntries(Object.entries(actual).sort(([a], [b]) => a.localeCompare(b)));
    if (env.UPDATE_DESIGN_ALLOWLIST) {
      fs.writeFileSync(`${proc.cwd()}/src/test/design-allowlist.json`, JSON.stringify(sorted, null, 1) + "\n");
      return;
    }
    const allowed = allowlist as Record<string, Counts>;
    const problems: string[] = [];
    for (const path of new Set([...Object.keys(actual), ...Object.keys(allowed)])) {
      for (const rule of ["size", "uppercase", "tint", "extrabold", "white-on-accent"] as Rule[]) {
        const now = actual[path]?.[rule] ?? 0;
        const was = allowed[path]?.[rule] ?? 0;
        if (now > was) problems.push(`${path}: ${now} ${rule} (allowed ${was}). Use the type roles and tint tokens instead.`);
        else if (now < was) problems.push(`${path}: ${rule} is down to ${now} (allowlist says ${was}). Lower the allowlist.`);
      }
    }
    const totals: Counts = {};
    for (const c of Object.values(actual)) for (const [r, n] of Object.entries(c)) totals[r as Rule] = (totals[r as Rule] ?? 0) + n;
    console.info(`design allowlist: ${Object.keys(actual).length} files`, totals);
    expect(problems).toEqual([]);
  });
});

// ── Contrast ────────────────────────────────────────────────────────────────

function palette(block: string): Record<string, string> {
  return Object.fromEntries([...block.matchAll(/--([a-z0-9-]+):\s*(#[0-9a-fA-F]{3,8});/g)].map((m) => [m[1], m[2]]));
}

const LIGHT = palette(css.match(/:root\s*\{([^}]*)\}/)![1]);
const DARK = { ...LIGHT, ...palette(css.match(/\[data-theme="dark"\]\s*\{([^}]*)\}/)![1]) };

function luminance(hex: string): number {
  let h = hex.replace("#", "");
  if (h.length === 3) h = [...h].map((c) => c + c).join("");
  if (h.length !== 6) throw new Error(`${hex}: contrast needs an opaque colour`);
  const [r, g, b] = [0, 2, 4].map((i) => {
    const c = parseInt(h.slice(i, i + 2), 16) / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

const PAIRS: [string, string][] = [
  ["text", "surface"], ["text", "page"], ["text", "surface-inset"],
  ["text-secondary", "surface"], ["text-secondary", "surface-inset"],
  ["text-muted", "surface"],
  ["accent", "surface"],
  ["on-accent", "accent"],
  ["danger-text", "danger-bg"], ["danger-text", "surface"],
  ["warning-text", "warning-bg"],
  ["success-text", "success-bg"], ["success-text", "surface"],
  ["ai-text", "ai-bg"], ["ai-text", "surface"],
  ...(["gk", "def", "mid", "fwd"].map((p) => [`pos-${p}-text`, `pos-${p}-bg`]) as [string, string][]),
];

describe("design system: contrast", () => {
  it.each([["light", LIGHT], ["dark", DARK]] as const)("every pair reaches 4.5:1 (%s)", (_theme, pal) => {
    const failing = PAIRS.flatMap(([fg, bg]) => {
      if (!pal[fg] || !pal[bg]) return [`${fg} on ${bg}: token missing`];
      const r = contrast(pal[fg], pal[bg]);
      return r < 4.5 ? [`${fg} on ${bg}: ${r.toFixed(2)}:1`] : [];
    });
    expect(failing).toEqual([]);
  });
});
