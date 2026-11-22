/** "2026/27": a season runs July to June, as in England. */
export function seasonLabel(today: Date = new Date()): string {
  const start = today.getMonth() >= 6 ? today.getFullYear() : today.getFullYear() - 1;
  return `${start}/${String((start + 1) % 100).padStart(2, "0")}`;
}
