import type { ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import type { Deal } from "../../types/api";
import ClubLink from "../ui/ClubLink";
import Money from "../ui/Money";
import PlayerLink from "../ui/PlayerLink";
import { dealTypeLabel } from "../../lib/badges";
import { formatDate } from "../../lib/utils";

const POS_CLASS: Record<string, string> = {
  GK: "bg-pos-gk-bg text-pos-gk-text",
  DEF: "bg-pos-def-bg text-pos-def-text",
  MID: "bg-pos-mid-bg text-pos-mid-text",
  FWD: "bg-pos-fwd-bg text-pos-fwd-text",
};

function initials(name: string): string {
  const parts = name.trim().split(/\s+/);
  return ((parts[0]?.[0] ?? "") + (parts.length > 1 ? parts[parts.length - 1][0] : "")).toUpperCase();
}

/** "Permanent · 3 instalments", or a loan's period. */
export function dealFacts(deal: Deal): string {
  const payment = deal.deal_type === "LOAN"
    ? `${formatDate(deal.loan_start)}–${formatDate(deal.loan_end)}`
    : deal.instalments.length > 0 ? `${deal.instalments.length} instalments` : "On completion";
  return `${dealTypeLabel(deal.deal_type)} · ${payment}`;
}

/**
 * Who the deal is for (deal-room-focus §5.1): the player as the page's only
 * h1, the route between the clubs, and the fee. No status: the card says it.
 */
export default function DealHeader({ deal, moreMenu }: { deal: Deal; moreMenu: ReactNode }) {
  const navigate = useNavigate();
  const name = deal.player?.name ?? null;
  const pos = deal.player?.position ?? null;
  const facts = (
    <>
      {dealFacts(deal)}
      {deal.is_auction_deal && (
        <span className="ml-2 inline-flex rounded-full bg-text-muted/15 px-2.5 py-0.5 text-[13px] font-semibold text-text-secondary ring-1 ring-text-muted/30">
          Auction deal
        </span>
      )}
    </>
  );

  return (
    <header>
      <div className="flex items-center justify-between">
        <button
          type="button"
          onClick={() => navigate(-1)}
          className="-ml-2.5 inline-flex min-h-11 items-center px-2.5 text-[15px] font-medium text-text-secondary hover:text-text"
        >
          ← Back
        </button>
        <div className="lg:hidden">{moreMenu}</div>
      </div>

      <div className="mt-1 flex items-center gap-3.5 lg:gap-4">
        {deal.player?.photo_url ? (
          <img src={deal.player.photo_url} alt="" aria-hidden className="h-[52px] w-[52px] shrink-0 rounded-full bg-surface-inset object-cover object-top" />
        ) : (
          <span
            aria-hidden
            className={`flex h-[52px] w-[52px] shrink-0 items-center justify-center rounded-full text-lg font-bold ${
              (pos && POS_CLASS[pos]) || "bg-accent-avatar text-accent-active"
            }`}
          >
            {name ? initials(name) : "?"}
          </span>
        )}
        <div className="min-w-0 flex-1">
          <h1 className="text-[22px] font-bold leading-tight tracking-[-0.01em] text-text lg:text-2xl">
            <PlayerLink id={deal.player_id} name={name} fallback="Unknown player" />
          </h1>
          <p className="mt-0.5 text-[15px] text-text-secondary">
            {pos && <>{pos} · </>}
            {deal.seller_club_id ? (
              <ClubLink id={deal.seller_club?.id} name={deal.seller_club?.name} crestUrl={deal.seller_club?.crest_url} />
            ) : "Free agent"}
            {" → "}
            <ClubLink id={deal.buyer_club?.id} name={deal.buyer_club?.name} crestUrl={deal.buyer_club?.crest_url} />
            {deal.agent && <span className="hidden lg:inline"> · agent {deal.agent.display_name}</span>}
          </p>
        </div>
        <div className="hidden shrink-0 text-right sm:block">
          <p className="text-[22px] font-bold text-text lg:text-2xl"><Money value={deal.agreed_fee} /></p>
          <p className="text-sm text-text-muted">{facts}</p>
        </div>
        <div className="hidden lg:block">{moreMenu}</div>
      </div>

      <p className="mt-2.5 text-[15px] text-text-secondary sm:hidden">
        <span className="text-[17px] font-bold text-text"><Money value={deal.agreed_fee} /></span>
        {" · "}{facts}
      </p>
    </header>
  );
}
