import { Link } from "react-router-dom";

interface EmptyStateProps {
  title: string;
  body?: string;
  action?: { label: string; to: string } | { label: string; onClick: () => void };
}

export default function EmptyState({ title, body, action }: EmptyStateProps) {
  const actionClass =
    "inline-flex items-center justify-center rounded-lg bg-emerald-500 px-4 py-2 text-sm font-semibold text-white transition-all duration-150 hover:bg-emerald-400 hover:-translate-y-px";

  return (
    <div className="rounded-xl border border-dashed border-white/[0.08] bg-slate-900/50 p-8 text-center">
      <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-slate-800">
        <svg className="h-6 w-6 text-slate-500" fill="none" stroke="currentColor" strokeWidth="1.5" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
        </svg>
      </div>
      <p className="text-sm font-semibold text-white">{title}</p>
      {body && <p className="mt-1 text-sm text-slate-500">{body}</p>}
      {action && (
        <div className="mt-4">
          {"onClick" in action ? (
            <button type="button" onClick={action.onClick} className={actionClass}>
              {action.label}
            </button>
          ) : (
            <Link to={action.to} className={actionClass}>
              {action.label}
            </Link>
          )}
        </div>
      )}
    </div>
  );
}
