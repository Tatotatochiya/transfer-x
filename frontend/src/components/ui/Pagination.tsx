interface PaginationProps {
  page: number;
  total: number;
  pageSize: number;
  onChange: (page: number) => void;
}

export default function Pagination({ page, total, pageSize, onChange }: PaginationProps) {
  const totalPages = Math.ceil(total / pageSize);
  if (totalPages <= 1) return null;

  const start = (page - 1) * pageSize + 1;
  const end = Math.min(page * pageSize, total);

  return (
    <div className="flex items-center justify-between pt-4 text-sm">
      <span className="text-text-muted">
        {start}–{end} of {total}
      </span>
      <div className="flex items-center gap-1">
        <button
          onClick={() => onChange(page - 1)}
          disabled={page <= 1}
          className="rounded-lg px-3 py-1.5 text-text-muted hover:bg-surface-inset hover:text-text disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          ←
        </button>
        {Array.from({ length: totalPages }, (_, i) => i + 1)
          .filter((p) => p === 1 || p === totalPages || Math.abs(p - page) <= 1)
          .reduce<(number | "…")[]>((acc, p, i, arr) => {
            if (i > 0 && p - (arr[i - 1] as number) > 1) acc.push("…");
            acc.push(p);
            return acc;
          }, [])
          .map((p, i) =>
            p === "…" ? (
              <span key={`ellipsis-${i}`} className="px-2 text-text-muted">…</span>
            ) : (
              <button
                key={p}
                onClick={() => onChange(p as number)}
                className={`min-w-[2rem] rounded-lg px-2 py-1.5 transition-colors ${
                  p === page
                    ? "bg-accent-bg text-accent font-semibold"
                    : "text-text-muted hover:bg-surface-inset hover:text-text"
                }`}
              >
                {p}
              </button>
            )
          )}
        <button
          onClick={() => onChange(page + 1)}
          disabled={page >= totalPages}
          className="rounded-lg px-3 py-1.5 text-text-muted hover:bg-surface-inset hover:text-text disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          →
        </button>
      </div>
    </div>
  );
}
