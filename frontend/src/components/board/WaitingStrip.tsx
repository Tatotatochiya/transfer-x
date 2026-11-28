import { Fragment } from "react";

import { countdownLeft } from "../../lib/timeLeft";
import { useNow } from "../../hooks/useNow";
import type { BoardCard } from "./types";

/**
 * From 1280px, the your-move cards in one line above the lanes
 * (README_TRANSFERS §5): each opens the card's pop-up, as the card does.
 */
export default function WaitingStrip({ rows, onOpen }: { rows: BoardCard[]; onOpen: (c: BoardCard) => void }) {
  const now = useNow();
  if (rows.length === 0) return null;
  return (
    <div role="region" aria-label="Waiting on you"
      className="mb-5 flex flex-wrap items-center gap-x-3 gap-y-1.5 rounded-xl bg-surface px-4 py-2.5 text-small ring-1 ring-danger-ring">
      <span className="flex items-center gap-1.5 font-semibold text-danger-text">
        <span aria-hidden className="h-2 w-2 rounded-full bg-danger" />Waiting on you
      </span>
      {rows.map((c, i) => {
        const left = countdownLeft(c.deadline, now);
        const what = c.detail.replace(/\s*·\s*your move$/i, "");
        return (
          <Fragment key={c.key}>
            {i > 0 && <span aria-hidden className="text-border">|</span>}
            <button type="button" onClick={() => onOpen(c)} className="text-left text-text-secondary hover:text-text focus-visible:outline-2 focus-visible:outline-accent">
              <span className="font-semibold text-text">{c.player_name}</span>
              {what && <> · {what}</>}
              {left && <> · <span className={left.urgent ? "font-semibold text-danger-text" : undefined}>{left.text}</span></>}
            </button>
          </Fragment>
        );
      })}
    </div>
  );
}
