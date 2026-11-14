import { useId } from "react";

import { groupRows } from "./boardList";
import TransferRow from "./TransferRow";
import type { BoardCard, Side } from "./types";

const LIST = "overflow-hidden rounded-2xl bg-surface ring-1";
const ITEM = "border-t border-rule first:border-t-0";

function Group({ label, hint, count, yours, children }: {
  label: string; hint?: string; count: number; yours: boolean; children: React.ReactNode;
}) {
  const id = useId();
  return (
    <section aria-labelledby={id}>
      <h2 id={id} className="mb-2 flex flex-wrap items-baseline gap-x-2 text-section font-bold text-text">
        {yours && <span aria-hidden className="h-2 w-2 shrink-0 self-center rounded-full bg-danger" />}
        <span className={yours ? "text-danger-text" : undefined}>{label}</span>
        <span className="text-caption font-semibold tabular-nums text-text-muted">{count}</span>
        {hint && <span className="text-small font-normal text-text-muted">{hint}</span>}
      </h2>
      <ul className={`${LIST} ${yours ? "ring-danger-ring" : "ring-border"}`}>{children}</ul>
    </section>
  );
}

/** The tablet list's column heads, above the first group. */
function HeaderRow() {
  return (
    <div aria-hidden className="eyebrow grid grid-cols-[40px_minmax(0,1fr)_220px_96px_104px_16px] gap-x-3 px-4 text-text-secondary">
      <span /><span>Player</span><span>Stage</span><span className="text-right">Fee</span><span className="text-right">Due</span><span />
    </div>
  );
}

/**
 * Below 1280px, the board's cards grouped by whose move it is
 * (README_TRANSFERS §4.3): Waiting on you, In progress, Listed, Completed.
 */
export default function TransferList({ rows, side, labels, layout }: {
  rows: BoardCard[];
  side: Side;
  labels: Record<string, string>;
  layout: "phone" | "tablet";
}) {
  const groups = groupRows(rows);
  return (
    <div className="space-y-5">
      {layout === "tablet" && groups.length > 0 && <HeaderRow />}
      {groups.map((g) => (
        <Group key={g.key} label={g.label} hint={g.hint} count={g.rows.length} yours={g.key === "yours"}>
          {g.rows.map((c) => (
            <li key={c.key} className={ITEM}>
              <TransferRow card={c} side={side} stageLabel={labels[c.column] ?? c.column} layout={layout} />
            </li>
          ))}
        </Group>
      ))}
    </div>
  );
}

/** Closed transfers below 1280px: the same rows, in a plain list. */
export function ClosedList({ rows, side, labels, layout }: {
  rows: BoardCard[]; side: Side; labels: Record<string, string>; layout: "phone" | "tablet";
}) {
  return (
    <ul className={`${LIST} ring-border`}>
      {rows.map((c) => (
        <li key={`${c.key}:${c.entity_id}`} className={ITEM}>
          <TransferRow card={c} side={side} stageLabel={labels[c.column] ?? "Closed"} layout={layout} />
        </li>
      ))}
    </ul>
  );
}
