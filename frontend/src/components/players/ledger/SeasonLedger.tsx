import { Fragment, type ReactNode } from "react";

/**
 * The season ledger (docs/feature_spec/player-profile-ledger, HANDOFF.md §5c):
 * one row per season, an optional fold-out of sub-rows, optional rows after a
 * season (transfers), and a career footer. Every tab renders through it.
 */

export interface LedgerSubRow {
  id: string;
  season?: ReactNode;
  club: ReactNode;
  cells: ReactNode[];
}

export interface LedgerRowSpec {
  id: string;
  season: string;
  club: ReactNode;
  cells: ReactNode[];
  sub?: LedgerSubRow[];
  /** Rows shown directly under this one, expanded or not (e.g. transfers). */
  after?: ReactNode;
}

export const MUTED = <span className="text-text-muted">—</span>;

export function ClubCell({ name, logo, loan }: { name: ReactNode; logo?: string | null; loan?: boolean }) {
  return (
    <span className="flex min-w-0 items-center gap-2">
      {logo ? (
        <img src={logo} alt="" loading="lazy" className="h-4 w-4 shrink-0 object-contain" />
      ) : (
        <span className="h-2 w-2 shrink-0 rounded-sm bg-border" aria-hidden="true" />
      )}
      <span className="truncate text-text-secondary">{name}</span>
      {loan && <span className="shrink-0 text-[10px] font-bold tracking-wide text-warning-text">LOAN</span>}
    </span>
  );
}

export function SeasonLedger({
  headers, template, rows, footer, expanded, onToggle, highlightLast = false, empty,
}: {
  headers: string[];
  /** CSS grid template: Season, Club, then one track per header. */
  template: string;
  rows: LedgerRowSpec[];
  footer?: { label: string; sub?: string; cells: ReactNode[] };
  expanded: Set<string>;
  onToggle: (id: string) => void;
  /** Highlight the last column (the Overview's rating / yellow cards). */
  highlightLast?: boolean;
  empty?: string;
}) {
  const grid = { gridTemplateColumns: template };
  const statCell = (i: number, n: number) =>
    `text-right tabular-nums ${highlightLast && i === n - 1 ? "font-semibold text-warning-text" : ""}`;
  return (
    <div className="-mx-1 overflow-x-auto px-1">
      <div className="min-w-[640px]">
        <div style={grid} className="grid gap-x-2 border-b border-rule px-2.5 pb-2 text-[11px] font-bold uppercase tracking-[0.05em] text-text-muted">
          <span>Season</span>
          <span>Club</span>
          {headers.map((h) => <span key={h} className="text-right">{h}</span>)}
        </div>
        {rows.length === 0 && <p className="px-2.5 py-6 text-center text-sm text-text-muted">{empty ?? "No seasons on record."}</p>}
        {rows.map((row) => {
          const canExpand = !!row.sub?.length;
          const open = canExpand && expanded.has(row.id);
          return (
            <Fragment key={row.id}>
              <div
                style={grid}
                role={canExpand ? "button" : undefined}
                tabIndex={canExpand ? 0 : undefined}
                aria-expanded={canExpand ? open : undefined}
                onClick={canExpand ? () => onToggle(row.id) : undefined}
                onKeyDown={canExpand ? (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onToggle(row.id); } } : undefined}
                className={`grid items-center gap-x-2 border-b border-rule-faint px-2.5 py-2 text-sm text-text ${
                  canExpand ? "cursor-pointer hover:bg-surface-inset focus:outline-none focus-visible:ring-2 focus-visible:ring-accent" : ""
                } ${open ? "bg-surface-inset" : ""}`}
              >
                <span className="flex items-center gap-1.5 font-semibold tabular-nums">
                  <span className="w-2 text-[10px] text-text-muted" aria-hidden="true">{canExpand ? (open ? "▾" : "▸") : ""}</span>
                  {row.season}
                </span>
                <span className="min-w-0">{row.club}</span>
                {row.cells.map((c, i) => <span key={i} className={statCell(i, row.cells.length)}>{c}</span>)}
              </div>
              {open && (
                <div className="border-b border-rule-faint bg-surface-inset/60 py-0.5 pb-1.5">
                  {row.sub!.map((s) => (
                    <div key={s.id} style={grid} className="grid items-center gap-x-2 px-2.5 py-1 text-[13px] text-text-secondary">
                      <span className="pl-3.5 tabular-nums">{s.season ?? ""}</span>
                      <span className="min-w-0 truncate">{s.club}</span>
                      {s.cells.map((c, i) => <span key={i} className="text-right tabular-nums">{c}</span>)}
                    </div>
                  ))}
                </div>
              )}
              {row.after}
            </Fragment>
          );
        })}
        {footer && rows.length > 0 && (
          <div style={grid} className="grid items-center gap-x-2 rounded-b-lg bg-surface-inset px-2.5 py-2.5 text-sm font-bold text-text">
            <span>{footer.label}</span>
            <span className="truncate font-normal text-text-muted">{footer.sub}</span>
            {footer.cells.map((c, i) => <span key={i} className={statCell(i, footer.cells.length)}>{c}</span>)}
          </div>
        )}
      </div>
    </div>
  );
}
