/** First and last name, asked when someone joins: their team, approvals and
 *  the audit trail show who did what by name. */
export default function NameFields({
  first, last, onFirst, onLast,
}: { first: string; last: string; onFirst: (v: string) => void; onLast: (v: string) => void }) {
  const input =
    "w-full rounded-lg bg-surface px-3 py-2.5 text-sm text-text placeholder-text-muted ring-1 ring-input-border focus:outline-none focus:ring-accent transition-colors";
  return (
    <div className="grid grid-cols-2 gap-3">
      <div>
        <label htmlFor="first-name" className="mb-1.5 block text-sm font-medium text-text-secondary">First name</label>
        <input id="first-name" autoComplete="given-name" required maxLength={80} value={first}
          onChange={(e) => onFirst(e.target.value)} className={input} />
      </div>
      <div>
        <label htmlFor="last-name" className="mb-1.5 block text-sm font-medium text-text-secondary">Last name</label>
        <input id="last-name" autoComplete="family-name" required maxLength={80} value={last}
          onChange={(e) => onLast(e.target.value)} className={input} />
      </div>
    </div>
  );
}
