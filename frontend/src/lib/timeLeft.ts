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
