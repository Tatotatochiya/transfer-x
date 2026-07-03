import Icon from "../layout/Icon";

export default function VerifiedBadge({ className = "" }: { className?: string }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full bg-sky-500/15 px-2 py-0.5 text-[11px] font-semibold text-sky-400 ring-1 ring-sky-500/30 ${className}`}
    >
      <Icon name="check" className="h-3 w-3" />
      Verified
    </span>
  );
}
