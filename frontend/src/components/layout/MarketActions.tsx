import { Link } from "react-router-dom";

import { useAuth } from "../../hooks/useAuth";
import { useClubCapabilities } from "../../hooks/useClubCapabilities";

/**
 * Buy and Sell, in the full app's top bar on every page: buying and selling
 * are what TransferX is for, so they're never more than a tap away (product
 * owner, 2026-10-29). Only for club members whose role can trade; not in a
 * read-only view-as tab. Lite has the same two as its home tiles.
 */
export default function MarketActions({ compact = false }: { compact?: boolean }) {
  const { isAuthenticated, userType, hasClub, viewedBy } = useAuth();
  const { can } = useClubCapabilities();
  if (!isAuthenticated || userType !== "CLUB" || !hasClub || viewedBy || !can("MARKET_WRITE")) return null;
  const size = compact ? "h-9 px-3 text-[13px]" : "h-9 px-4 text-sm";
  return (
    <div className="flex shrink-0 items-center gap-2">
      <Link
        to="/players/market"
        className={`flex items-center rounded-lg bg-accent font-semibold text-white no-underline hover:opacity-90 ${size}`}
      >
        {compact ? "Buy" : "Buy a player"}
      </Link>
      <Link
        to="/sales/new"
        className={`flex items-center rounded-lg bg-surface font-semibold text-text no-underline ring-1 ring-border hover:ring-accent ${size}`}
      >
        {compact ? "Sell" : "Sell a player"}
      </Link>
    </div>
  );
}
