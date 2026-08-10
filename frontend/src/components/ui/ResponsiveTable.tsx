import Spinner from "./Spinner";
import EmptyState from "./EmptyState";

export interface ResponsiveColumn<T> {
  key: string;
  header: string;
  render: (row: T) => React.ReactNode;
  /** Lower number = higher priority = shown first on the default mobile
   * card. Columns without a priority sort last. Doesn't affect desktop/
   * tablet table order — only the fallback mobile card layout. */
  priority?: number;
  className?: string;
}

interface ResponsiveTableProps<T> {
  columns: ResponsiveColumn<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  loading?: boolean;
  emptyTitle?: string;
  emptyBody?: string;
  onRowClick?: (row: T) => void;
  /** Custom mobile card, e.g. the two-line "identifier + value / state +
   * timestamp" shape in docs/design_handoff_transferx/RESPONSIVE.md. Falls
   * back to a generic card (first column as the primary line, the rest
   * ranked by priority) when omitted. */
  renderCard?: (row: T) => React.ReactNode;
}

function DefaultCard<T>({
  row, columns, onRowClick,
}: { row: T; columns: ResponsiveColumn<T>[]; onRowClick?: (row: T) => void }) {
  const sorted = [...columns].sort((a, b) => (a.priority ?? 99) - (b.priority ?? 99));
  const [primary, secondary, ...rest] = sorted;

  return (
    <div
      onClick={() => onRowClick?.(row)}
      className={`min-h-16 flex flex-col justify-center gap-1 px-4 py-3 ${onRowClick ? "cursor-pointer active:bg-surface-inset" : ""}`}
    >
      {primary && (
        <div className="flex items-center justify-between gap-3">
          <span className="text-sm font-semibold text-text">{primary.render(row)}</span>
          {secondary && <span className="text-sm font-bold text-text shrink-0">{secondary.render(row)}</span>}
        </div>
      )}
      {rest.length > 0 && (
        <div className="flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs text-text-muted">
          {rest.map((col) => (
            <span key={col.key}>{col.render(row)}</span>
          ))}
        </div>
      )}
    </div>
  );
}

/**
 * Table above 640px (full table, horizontal scroll on tablet only via the
 * wrapper's overflow-x-auto, which is a no-op once content fits at desktop
 * widths); a stacked card list below 640px — never a horizontal scroll on
 * mobile. Per docs/design_handoff_transferx/RESPONSIVE.md.
 */
export default function ResponsiveTable<T>({
  columns,
  rows,
  rowKey,
  loading,
  emptyTitle = "No results",
  emptyBody,
  onRowClick,
  renderCard,
}: ResponsiveTableProps<T>) {
  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <Spinner size="lg" />
      </div>
    );
  }

  if (rows.length === 0) {
    return <EmptyState title={emptyTitle} body={emptyBody} />;
  }

  return (
    <>
      {/* Mobile: stacked cards */}
      <div className="sm:hidden rounded-xl bg-surface ring-1 ring-border divide-y divide-rule-faint overflow-hidden">
        {rows.map((row) => (
          <div key={rowKey(row)}>
            {renderCard ? renderCard(row) : <DefaultCard row={row} columns={columns} onRowClick={onRowClick} />}
          </div>
        ))}
      </div>

      {/* Tablet/desktop: real table */}
      <div className="hidden sm:block overflow-x-auto rounded-xl ring-1 ring-border">
        <table className="min-w-full text-sm">
          <thead>
            <tr className="border-b border-rule bg-surface-header">
              {columns.map((col) => (
                <th
                  key={col.key}
                  className={`px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-text-muted ${col.className ?? ""}`}
                >
                  {col.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-rule-faint">
            {rows.map((row) => (
              <tr
                key={rowKey(row)}
                onClick={() => onRowClick?.(row)}
                className={`bg-surface ${onRowClick ? "cursor-pointer hover:bg-surface-inset" : ""} transition-colors`}
              >
                {columns.map((col) => (
                  <td key={col.key} className={`px-4 py-3 text-text-secondary ${col.className ?? ""}`}>
                    {col.render(row)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
