import { Link } from "react-router-dom";

import TransferRow from "../board/TransferRow";
import { boardRows, stageLabels, stageStep } from "../board/boardList";
import type { Board, BoardCard } from "../board/types";
import { useMediaQuery } from "../../hooks/useMediaQuery";

/** Your move first, then the furthest stage first. */
export function inProgressRows(board: Board | undefined): BoardCard[] {
  if (!board) return [];
  return boardRows(board)
    .filter((c) => c.column !== "done")
    .sort((a, b) =>
      Number(b.whose_move === "your") - Number(a.whose_move === "your") || stageStep(b.column) - stageStep(a.column));
}

/**
 * Every open transfer, once each (feature_spec/club-dashboard §4.5): the
 * Transfers board's rows, from the board's own query. Your-move rows also
 * appear in Needs you, deliberately: that's the to-do list, this is the
 * overview, and the row's red "your move" says the same thing in both.
 */
export default function TransfersInProgress({ board }: { board: Board | undefined }) {
  const sm = useMediaQuery("(min-width: 640px)");
  const rows = inProgressRows(board);
  const limit = sm ? 4 : 3;
  const labels = board ? stageLabels(board) : {};

  return (
    <section aria-labelledby="in-progress-heading" className="overflow-hidden rounded-2xl bg-surface ring-1 ring-border">
      <div className="flex items-center gap-2 px-4 pt-4 pb-2 sm:px-5">
        <h2 id="in-progress-heading" className="text-section font-bold text-text">Transfers in progress</h2>
        <span className="text-caption font-semibold tabular-nums text-text-muted">{rows.length}</span>
        <Link to="/board" className="ml-auto text-small font-semibold text-accent hover:underline">Transfers →</Link>
      </div>
      {rows.length === 0 ? (
        <p className="px-4 pb-4 text-body text-text-secondary sm:px-5">
          Nothing in progress. <Link to="/players/market" className="font-semibold text-accent hover:underline">Browse players →</Link>
        </p>
      ) : (
        <ul className="divide-y divide-rule-faint">
          {rows.slice(0, limit).map((c) => (
            <li key={c.key}>
              <TransferRow card={c} side="BOTH" stageLabel={labels[c.column] ?? c.column} layout={sm ? "tablet" : "phone"} />
            </li>
          ))}
        </ul>
      )}
      {rows.length > limit && (
        <Link to="/board" className="block border-t border-rule px-4 py-2.5 text-small font-semibold text-accent hover:underline sm:px-5">
          +{rows.length - limit} more →
        </Link>
      )}
    </section>
  );
}
