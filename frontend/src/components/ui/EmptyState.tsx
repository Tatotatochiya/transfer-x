import { Link } from "react-router-dom";

interface EmptyStateProps {
  title: string;
  body?: string;
  action?: { label: string; to: string } | { label: string; onClick: () => void };
}

// No illustration — a single line of text, per docs/design_handoff_transferx/CLAUDE.md
// ("EmptyState loses any illustration and becomes a single line of 14px
// secondary text"). This audience reads an icon-in-a-circle as "broken", not
// "empty".
export default function EmptyState({ title, body, action }: EmptyStateProps) {
  const actionClass =
    "inline-flex items-center justify-center rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-accent-hover";

  return (
    <div className="py-8 text-center">
      <p className="text-sm text-text-secondary">{title}</p>
      {body && <p className="mt-1 text-sm text-text-muted">{body}</p>}
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
