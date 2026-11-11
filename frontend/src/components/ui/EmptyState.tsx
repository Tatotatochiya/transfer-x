import { Link } from "react-router-dom";

interface EmptyStateProps {
  title: string;
  body?: string;
  action?: { label: string; to: string } | { label: string; onClick: () => void };
}

// No illustration — a single line of text, per docs/design-system/RULES.md
// ("EmptyState loses any illustration and becomes a single line of 14px
// secondary text"). This audience reads an icon-in-a-circle as "broken", not
// "empty".
export default function EmptyState({ title, body, action }: EmptyStateProps) {
  const actionClass =
    "inline-flex items-center justify-center rounded-lg bg-accent px-4 py-2 text-body font-semibold text-on-accent transition-colors hover:bg-accent-hover";

  return (
    <div className="py-8 text-center">
      <p className="text-section font-bold text-text">{title}</p>
      {body && <p className="mt-1 text-body text-text-secondary">{body}</p>}
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
