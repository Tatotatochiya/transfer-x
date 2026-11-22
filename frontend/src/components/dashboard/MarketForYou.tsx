import { Link } from "react-router-dom";

import { formatCompactCurrency } from "../../lib/utils";
import type { ShortlistHit } from "../../types/api";

/** Players on your shortlists who are now listed (feature_spec/club-dashboard §4.6). Top 3. */
export default function MarketForYou({ hits }: { hits: ShortlistHit[] }) {
  if (hits.length === 0) return null;
  return (
    <section aria-labelledby="market-for-you-heading" className="overflow-hidden rounded-2xl bg-surface ring-1 ring-border">
      <div className="flex items-center justify-between px-4 pt-4 pb-2 sm:px-5">
        <h2 id="market-for-you-heading" className="text-section font-bold text-text">For you in the market</h2>
        <Link to="/scouting/shortlists" className="text-small font-semibold text-accent hover:underline">Shortlists →</Link>
      </div>
      <ul className="divide-y divide-rule-faint">
        {hits.slice(0, 3).map((h) => (
          <li key={`${h.player_id}-${h.sale_id}`}>
            <Link to={`/sales/${h.sale_id}`} className="flex items-center gap-3 px-4 py-2.5 hover:bg-surface-inset sm:px-5">
              <span className="min-w-0 flex-1">
                <span className="block truncate text-body font-semibold text-text">
                  {h.player_name}{h.position && <span className="ml-1.5 text-small font-normal text-text-muted">{h.position}</span>}
                </span>
                <span className="block truncate text-small text-text-secondary">On your {h.shortlist_name} shortlist · now listed</span>
              </span>
              <span className="shrink-0 text-body font-semibold tabular-nums text-text">
                {h.asking_price != null ? formatCompactCurrency(h.asking_price) : "Open"}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
