/**
 * The board as a list (README_TRANSFERS §3): below 1280px the same cards are
 * grouped by whose move it is, and the column becomes the row's stage. Pure,
 * so the grouping and sorting are tested on their own.
 */
import type { Board, BoardCard } from "./types";

export const STAGES = ["talking", "offers", "fee_agreed", "terms", "paperwork"] as const; // + "done"
export type GroupKey = "yours" | "progress" | "listed" | "done";

export interface RowGroup { key: GroupKey; label: string; hint?: string; rows: BoardCard[] }

const GROUPS: { key: GroupKey; label: string; hint?: string }[] = [
  { key: "yours", label: "Waiting on you" },
  { key: "progress", label: "In progress", hint: "nothing for you yet" },
  { key: "listed", label: "Listed, no offers yet" },
  { key: "done", label: "Completed" },
];

/** Flatten the board's columns into rows, keeping the API's order inside each column. */
export function boardRows(board: Board): BoardCard[] {
  return board.columns.flatMap((c) => c.cards);
}

/** Which group a card belongs to. */
export function groupOf(c: BoardCard): GroupKey {
  if (c.column === "done") return "done";
  if (c.whose_move === "your") return "yours";
  if (c.kind === "listing") return "listed";
  return "progress";
}

/** 1–5 for the five open stages, 6 for done. */
export function stageStep(column: string): number {
  if (column === "done") return 6;
  const i = (STAGES as readonly string[]).indexOf(column);
  return i < 0 ? 1 : i + 1;
}

const time = (iso: string | null) => (iso ? new Date(iso).getTime() : 0);
const recent = (a: BoardCard, b: BoardCard) => time(b.updated_at) - time(a.updated_at);
const soonest = (a: BoardCard, b: BoardCard) => {
  if (a.deadline && b.deadline) return time(a.deadline) - time(b.deadline);
  if (a.deadline) return -1;
  if (b.deadline) return 1;
  return 0;
};

const SORT: Record<GroupKey, (a: BoardCard, b: BoardCard) => number> = {
  yours: (a, b) => soonest(a, b) || recent(a, b),
  progress: (a, b) => stageStep(b.column) - stageStep(a.column) || recent(a, b),
  listed: recent,
  done: recent,
};

/** Groups in display order, each sorted; empty groups dropped. */
export function groupRows(rows: BoardCard[]): RowGroup[] {
  return GROUPS
    .map((g) => ({ ...g, rows: rows.filter((r) => groupOf(r) === g.key).sort(SORT[g.key]) }))
    .filter((g) => g.rows.length > 0);
}

/** The "Waiting on you" cards in their group's order (the laptop strip). */
export function yourMoveRows(rows: BoardCard[]): BoardCard[] {
  return rows.filter((r) => groupOf(r) === "yours").sort(SORT.yours);
}

/** Count per stage, for the chips, after side and search filters, before the
 *  stage filter. Zero stages and done are omitted. */
export function stageCounts(rows: BoardCard[], labels: Record<string, string>): { key: string; label: string; count: number }[] {
  return STAGES
    .map((key) => ({ key, label: labels[key] ?? key, count: rows.filter((r) => r.column === key).length }))
    .filter((s) => s.count > 0);
}

/** The card's detail, unless it only repeats the stage's name ("Fee agreed" on Fee agreed). */
export function detailAfterStage(card: BoardCard, stageLabel: string): string | null {
  const d = card.detail.trim();
  return d && d.toLowerCase() !== stageLabel.trim().toLowerCase() ? d : null;
}

/** The column labels from the API, by key. */
export function stageLabels(board: Board): Record<string, string> {
  return Object.fromEntries(board.columns.map((c) => [c.key, c.label]));
}
