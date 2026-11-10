import { Link } from "react-router-dom";

import { useAuth } from "../../hooks/useAuth";
import { useClubCapabilities } from "../../hooks/useClubCapabilities";

/**
 * Find players and Sell a player, in the full app's top bar on every page:
 * buying and selling are what TransferX is for, so they're never more than a
 * tap away (product owner, 2026-10-29). Styled as navigation, never blue: a
 * page's own main action is the only blue button on screen (player-actions
 * D1). Only for club members whose role can trade; not in a read-only
 * view-as tab. Lite has the same two as its home tiles.
 */
export default function MarketActions({ compact = false, divider = false }: { compact?: boolean; divider?: boolean }) {
  const { isAuthenticated, userType, hasClub, viewedBy } = useAuth();
  const { can } = useClubCapabilities();
  if (!isAuthenticated || userType !== "CLUB" || !hasClub || viewedBy || !can("MARKET_WRITE")) return null;
  const cls = `flex items-center gap-1.5 rounded-lg bg-transparent font-semibold text-text-secondary no-underline hover:bg-surface-inset hover:text-text focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent ${
    compact ? "h-9 px-2.5 text-[13px] ring-1 ring-input-border" : "h-9 px-3 text-sm"
  }`;
  return (
    <div className="flex shrink-0 items-center gap-1.5">
      <Link to="/players/market" aria-label={compact ? "Find players" : undefined} className={cls}>
        <svg aria-hidden className="h-4 w-4 shrink-0" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
          <circle cx="9" cy="8" r="3.5" />
          <path strokeLinecap="round" d="M2.5 20c.6-3.4 3.3-5.5 6.5-5.5s5.9 2.1 6.5 5.5M16 4.8a3.5 3.5 0 0 1 0 6.4M18.5 14.8c1.6.8 2.7 2.6 3 5.2" />
        </svg>
        {compact ? "Players" : "Find players"}
      </Link>
      <Link to="/sales/new" aria-label={compact ? "Sell a player" : undefined} className={cls}>
        <svg aria-hidden className="h-4 w-4 shrink-0" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
          <path strokeLinejoin="round" d="M3 12V4a1 1 0 0 1 1-1h8l9 9-9 9-9-9Z" />
          <circle cx="7.5" cy="7.5" r="1.5" />
        </svg>
        {compact ? "Sell" : "Sell a player"}
      </Link>
      {/* Sets them apart from search, in the desktop top bar. */}
      {divider && <div aria-hidden className="ml-1 h-6 w-px bg-border" />}
    </div>
  );
}
