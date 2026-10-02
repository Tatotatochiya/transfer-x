/**
 * Reading a money figure a person typed into a valuation box.
 *
 * Shared by the squad table and the player profile's facts strip, which
 * disagreed: the squad table read only the digits, so "18" and "£18m" both
 * saved £18, while the profile read "18" as £18m.
 *
 *  - "" or whitespace          → null (clear the valuation)
 *  - "18", "6.7"               → millions: a plain number under 1,000 is never
 *                                a real valuation in pounds
 *  - "£18m", "18M", "18.5 mn"  → millions
 *  - "750k", "£750K"           → thousands
 *  - "18000000", "18,000,000"  → pounds
 *  - anything else             → undefined (not a figure; don't save)
 */
export function parseValuation(input: string): number | null | undefined {
  const text = input.trim().toLowerCase().replace(/[£,\s]/g, "");
  if (text === "") return null;
  const m = /^(\d+(?:\.\d+)?)(m|mn|k)?$/.exec(text);
  if (!m) return undefined;
  const n = Number(m[1]);
  if (m[2] === "k") return Math.round(n * 1e3);
  if (m[2] === "m" || m[2] === "mn" || n < 1000) return Math.round(n * 1e6);
  return Math.round(n);
}
