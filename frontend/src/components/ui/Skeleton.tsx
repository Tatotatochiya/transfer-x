interface SkeletonProps {
  className?: string;
}

/** Base shimmer block — use className for sizing. */
export function Skeleton({ className = "" }: SkeletonProps) {
  return (
    <div
      className={`animate-pulse rounded-lg bg-surface-inset ${className}`}
      aria-hidden="true"
    />
  );
}

/** Skeleton for a PlayerCard grid item. */
export function PlayerCardSkeleton() {
  return (
    <div className="rounded-xl bg-surface ring-1 ring-border overflow-hidden">
      <Skeleton className="h-36 w-full rounded-none" />
      <div className="px-4 py-3 space-y-2">
        <Skeleton className="h-4 w-3/4" />
        <Skeleton className="h-3 w-1/2" />
        <Skeleton className="h-3 w-1/3" />
      </div>
    </div>
  );
}

/** Skeleton for a horizontal list row. */
export function ListRowSkeleton() {
  return (
    <div className="flex items-center gap-4 px-4 py-3 border-b border-rule-faint">
      <Skeleton className="h-9 w-9 rounded-full shrink-0" />
      <div className="flex-1 space-y-1.5">
        <Skeleton className="h-4 w-1/3" />
        <Skeleton className="h-3 w-1/4" />
      </div>
      <Skeleton className="h-6 w-16 rounded-full" />
    </div>
  );
}

/** Skeleton for a stat/metric card. */
export function StatCardSkeleton() {
  return (
    <div className="rounded-xl bg-surface ring-1 ring-border p-5 space-y-3">
      <Skeleton className="h-3 w-24" />
      <Skeleton className="h-7 w-32" />
    </div>
  );
}

/** Skeleton grid of N PlayerCard items. */
export function PlayerCardGridSkeleton({ count = 8 }: { count?: number }) {
  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
      {Array.from({ length: count }).map((_, i) => (
        <PlayerCardSkeleton key={i} />
      ))}
    </div>
  );
}

/** Skeleton list of N rows. */
export function ListSkeleton({ count = 6 }: { count?: number }) {
  return (
    <div className="rounded-xl bg-surface ring-1 ring-border overflow-hidden divide-y divide-rule-faint">
      {Array.from({ length: count }).map((_, i) => (
        <ListRowSkeleton key={i} />
      ))}
    </div>
  );
}
