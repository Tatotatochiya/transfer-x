interface SectionHeaderProps {
  title: string;
  actions?: React.ReactNode;
  className?: string;
}

export default function SectionHeader({ title, actions, className = "" }: SectionHeaderProps) {
  return (
    <div className={`flex items-center justify-between mb-3 ${className}`}>
      <h2 className="text-sm font-semibold uppercase tracking-wider text-text-muted">{title}</h2>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}
