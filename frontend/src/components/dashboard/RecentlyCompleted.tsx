import { Link } from "react-router-dom";

import { formatCompactCurrency, formatDate } from "../../lib/utils";
import type { Deal } from "../../types/api";

/**
 * The club's last completed transfers (feature_spec/club-dashboard §4.6):
 * "Sold to Liverpool · 4 Jul 2026" or "Signed from Chelsea · 12 Apr 2026".
 */
export default function RecentlyCompleted({ deals, myClubId, limit }: { deals: Deal[]; myClubId: string; limit: number }) {
  if (deals.length === 0) return null;
  return (
    <section aria-labelledby="recently-completed-heading" className="overflow-hidden rounded-2xl bg-surface ring-1 ring-border">
      <div className="flex items-center justify-between px-4 pt-4 pb-2 sm:px-5">
        <h2 id="recently-completed-heading" className="text-section font-bold text-text">Recently completed</h2>
        <Link to="/board/history" className="text-small font-semibold text-accent hover:underline">History →</Link>
      </div>
      <ul className="divide-y divide-rule-faint">
        {deals.slice(0, limit).map((d) => {
          const sold = d.seller_club?.id === myClubId;
          const other = sold ? d.buyer_club?.name : d.seller_club?.name;
          const what = sold ? `Sold to ${other ?? "—"}` : other ? `Signed from ${other}` : "Signed as a free agent";
          return (
            <li key={d.id}>
              <Link to={`/deals/${d.id}`} className="flex items-center gap-3 px-4 py-2.5 hover:bg-surface-inset sm:px-5">
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-body font-semibold text-text">
                    {d.player?.name ?? "—"}
                    {d.player?.position && <span className="ml-1.5 text-small font-normal text-text-muted">{d.player.position}</span>}
                  </span>
                  <span className="block truncate text-small text-text-secondary">
                    {what}{d.completed_at ? ` · ${formatDate(d.completed_at)}` : ""}
                  </span>
                </span>
                <span className="shrink-0 text-body font-semibold tabular-nums text-text">
                  {d.agreed_fee ? formatCompactCurrency(d.agreed_fee) : "Free"}
                </span>
              </Link>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
