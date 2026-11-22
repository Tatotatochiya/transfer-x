import Badge from "../ui/Badge";

const DAY = 86_400_000;
/** From this many days without movement, a transaction waiting on someone else is stalled. */
export const STALLED_DAYS = 3;

/** Whole days since `iso`, or null when it's under STALLED_DAYS. */
export function stalledDays(iso: string | null | undefined, now = new Date()): number | null {
  if (!iso) return null;
  const days = Math.floor((now.getTime() - new Date(iso).getTime()) / DAY);
  return days >= STALLED_DAYS ? days : null;
}

/**
 * Colour for chasing (docs/feature_spec/move-reminders §4): amber on the side
 * that's waiting (caution: it's slowing down, not their fault), red on the side
 * being chased (it's their move). The words say which step it is.
 */
export function StalledBadge({ since, now }: { since: string | null | undefined; now?: Date }) {
  const days = stalledDays(since, now);
  if (days == null) return null;
  return <Badge variant="warning">Stalled · {days} days</Badge>;
}

/** On the waiting side: we chased it. Amber once it's stalled or escalated. */
export function SentBadge({ escalated, stalled }: { escalated: boolean; stalled: boolean }) {
  return <Badge variant={escalated || stalled ? "warning" : "neutral"}>{escalated ? "Escalated" : "Reminded"}</Badge>;
}

/** On the side being chased: red, it's their move. */
export function ChasedBadge({ escalated }: { escalated: boolean }) {
  return <Badge variant="danger">{escalated ? "Escalated" : "Reminded"}</Badge>;
}
