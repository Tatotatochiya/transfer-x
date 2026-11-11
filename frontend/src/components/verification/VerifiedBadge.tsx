import Icon from "../layout/Icon";

export default function VerifiedBadge({ className = "" }: { className?: string }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full bg-accent-bg px-2 py-0.5 text-caption font-semibold text-accent ring-1 ring-accent-ring ${className}`}
    >
      <Icon name="check" className="h-3 w-3" />
      Verified
    </span>
  );
}
