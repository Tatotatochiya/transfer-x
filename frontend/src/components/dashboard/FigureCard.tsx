import type { ReactNode } from "react";

import Card from "../ui/Card";

/** Tier-2 "standing figure" stat card — shared by the club and agent dashboards. */
export default function FigureCard({
  label,
  value,
  note,
  bar,
}: {
  label: string;
  value: ReactNode;
  note?: string;
  bar?: { pct: number; colour: string };
}) {
  return (
    <Card tier={2}>
      <p className="text-caption font-semibold text-text-secondary">{label}</p>
      <p className="mt-1.5 text-headline font-bold tabular-nums tracking-[-0.01em] text-text sm:text-title">{value}</p>
      {note && <p className="mt-[3px] text-small text-text-muted">{note}</p>}
      {bar && (
        <div className="mt-2.5 h-1.5 w-full overflow-hidden rounded-full bg-border-quiet">
          <div className={bar.colour} style={{ width: `${bar.pct}%`, height: "100%" }} />
        </div>
      )}
    </Card>
  );
}
