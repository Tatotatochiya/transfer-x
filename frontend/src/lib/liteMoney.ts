import { formatCompact } from "./utils";

/** Money as Lite writes it, the app's one compact format (docs/feature_spec/lite-mode, CLAUDE.md rule 8):
 *  "£22M", "£22.5M", "£140K", "£35K a week". */
export function liteMoney(value: number | null | undefined): string {
  return formatCompact(value);
}

export function liteWage(value: number | null | undefined): string {
  return value == null ? "—" : `${liteMoney(value)} a week`;
}
