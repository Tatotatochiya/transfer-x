/** Money as Lite writes it (docs/feature_spec/lite-mode, CLAUDE.md rule 8):
 *  "£22m", "£22.5m", "£140k", "£35k a week". */
export function liteMoney(value: number | null | undefined): string {
  if (value == null) return "—";
  const n = Math.abs(value);
  const sign = value < 0 ? "-" : "";
  if (n >= 1_000_000) {
    const m = n / 1_000_000;
    return `${sign}£${Number.isInteger(Math.round(m * 10) / 10) ? Math.round(m) : (Math.round(m * 10) / 10).toFixed(1)}m`;
  }
  if (n >= 1_000) return `${sign}£${Math.round(n / 1_000)}k`;
  return `${sign}£${Math.round(n)}`;
}

export function liteWage(value: number | null | undefined): string {
  return value == null ? "—" : `${liteMoney(value)} a week`;
}
