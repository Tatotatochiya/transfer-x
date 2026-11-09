import { formatCompact } from "./utils";

// The biggest Premier League wage bills are about £4M a week (≈ £200M a
// year). A weekly budget above this is far more likely a yearly figure typed
// into the weekly field than a real one.
export const WEEKLY_WAGE_SANITY_LIMIT = 5_000_000;

/** A warning for an implausible weekly wage budget, or null. Never blocks the save. */
export function weeklyWageWarning(value: string | number | null | undefined): string | null {
  const weekly = Number(value);
  if (!Number.isFinite(weekly) || weekly <= WEEKLY_WAGE_SANITY_LIMIT) return null;
  return `${formatCompact(weekly)} a week is ${formatCompact(weekly * 52)} a year. The biggest Premier League wage bills are about £4M a week. Is this a yearly figure? This field is per week.`;
}
