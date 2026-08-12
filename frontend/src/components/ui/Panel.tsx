interface PanelProps {
  title?: string;
  subtitle?: string;
  actions?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}

export default function Panel({ title, subtitle, actions, children, className = "" }: PanelProps) {
  return (
    <div className={`bg-surface rounded-xl ring-1 ring-border ${className}`}>
      {(title || actions) && (
        <div className="flex items-center justify-between px-5 py-4 border-b border-rule">
          <div>
            <h3 className="text-sm font-bold text-text">{title}</h3>
            {subtitle && <p className="mt-0.5 text-xs text-text-muted">{subtitle}</p>}
          </div>
          {actions && <div className="flex items-center gap-2">{actions}</div>}
        </div>
      )}
      <div className="px-5 py-4">{children}</div>
    </div>
  );
}
