/**
 * What the Dashboard's squad card shows (feature_spec/club-dashboard §5).
 * One team today. When a club has teams (leagues-and-club-teams Phase B), the
 * page builds one TeamSummary per team the viewer can see and nothing else
 * here changes.
 */

/** The minimum a squad should carry in each position. */
export const POSITION_TARGETS = [
  { pos: "GK", min: 2, label: "Goalkeepers" },
  { pos: "DEF", min: 4, label: "Defenders" },
  { pos: "MID", min: 4, label: "Midfielders" },
  { pos: "FWD", min: 3, label: "Forwards" },
] as const;

export type Position = (typeof POSITION_TARGETS)[number]["pos"];

export interface SquadSummary {
  count: number;
  /** One decimal; null when no player has an age. */
  averageAge: number | null;
  byPosition: Record<Position, number>;
  under21: number;
  /** Contracts ending within 180 days. */
  endingSoon: number;
  /** Positions short of their minimum, with how many are needed. */
  gaps: { pos: Position; need: number }[];
}

export interface TeamSummary {
  key: string;
  name: string;
  summary: SquadSummary;
}

export function squadSummary(
  players: { age: number | null; position: string | null }[],
  expiring: { days_remaining: number }[],
): SquadSummary {
  const ages = players.map((p) => p.age).filter((a): a is number => a != null);
  const byPosition = Object.fromEntries(
    POSITION_TARGETS.map((t) => [t.pos, players.filter((p) => p.position === t.pos).length]),
  ) as Record<Position, number>;
  return {
    count: players.length,
    averageAge: ages.length ? Math.round((ages.reduce((a, b) => a + b, 0) / ages.length) * 10) / 10 : null,
    byPosition,
    under21: ages.filter((a) => a <= 21).length,
    endingSoon: expiring.filter((c) => c.days_remaining <= 180).length,
    gaps: POSITION_TARGETS.filter((t) => byPosition[t.pos] < t.min).map((t) => ({ pos: t.pos, need: t.min - byPosition[t.pos] })),
  };
}
