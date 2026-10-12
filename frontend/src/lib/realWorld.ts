import type { RealWorldMove } from "../types/api";
import { formatDate } from "./utils";

/** One plain sentence for a real-world move: what API-Football says happened. */
export function describeMove(m: RealWorldMove): string {
  const club = m.real_club ?? "another club";
  const on = m.moved_on ? ` on ${formatDate(m.moved_on)}` : "";
  switch (m.kind) {
    case "transfer":
      return `Joined ${club}${on}${m.fee ? ` (${m.fee === "Free" ? "free transfer" : m.fee})` : ""}.`;
    case "loan":
      return `Joined ${club} on loan${on}.`;
    case "loan_return":
      return `Went back to ${club} at the end of his loan${on}.`;
    default:
      return `Has been playing for ${club} this season${m.last_played ? ` (last game ${formatDate(m.last_played)})` : ""}.`;
  }
}

export const MOVE_KIND_LABEL: Record<RealWorldMove["kind"], string> = {
  transfer: "Transfer",
  loan: "Loan",
  loan_return: "Loan ended",
  playing: "Playing there",
};
