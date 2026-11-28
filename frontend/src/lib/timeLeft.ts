/** "3 hours left", "2 days left", "time's up": how long until a deadline,
 *  and whether that's urgent (under a day). */
export function timeLeft(iso: string | null | undefined): { text: string; urgent: boolean } | null {
  if (!iso) return null;
  const ms = new Date(iso).getTime() - Date.now();
  if (ms <= 0) return { text: "time's up", urgent: true };
  const hours = ms / 3_600_000;
  if (hours < 1) return { text: `${Math.max(1, Math.round(ms / 60_000))} minutes left`, urgent: true };
  if (hours < 24) return { text: `${Math.floor(hours)} hour${Math.floor(hours) === 1 ? "" : "s"} left`, urgent: true };
  const days = Math.floor(hours / 24);
  return { text: `${days} day${days === 1 ? "" : "s"} left`, urgent: false };
}

/** A countdown for a board row: "3d 4h left", "4h 12m left", "12m left".
 *  Urgent in the last day. Re-render it with useNow to keep it counting. */
export function countdownLeft(iso: string | null | undefined, now = Date.now()): { text: string; urgent: boolean } | null {
  if (!iso) return null;
  const ms = new Date(iso).getTime() - now;
  if (ms <= 0) return { text: "time's up", urgent: true };
  const mins = Math.max(1, Math.floor(ms / 60_000));
  const d = Math.floor(mins / 1440), h = Math.floor((mins % 1440) / 60), m = mins % 60;
  const text = d > 0 ? `${d}d ${h}h left` : h > 0 ? `${h}h ${m}m left` : `${m}m left`;
  return { text, urgent: ms < 86_400_000 };
}
