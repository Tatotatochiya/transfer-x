import type { ReactNode } from "react";
import type { Deal } from "../../types/api";
import ClubLink from "../ui/ClubLink";
import Money from "../ui/Money";
import TransferHeader from "../transfer/TransferHeader";
import { dealTypeLabel } from "../../lib/badges";
import { formatDate } from "../../lib/utils";

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
  return (
    <TransferHeader
      player={{
        id: deal.player_id,
        name: deal.player?.name ?? null,
        position: deal.player?.position ?? null,
        photoUrl: deal.player?.photo_url ?? null,
      }}
      routeFrom={deal.seller_club_id
        ? <ClubLink id={deal.seller_club?.id} name={deal.seller_club?.name} crestUrl={deal.seller_club?.crest_url} />
        : "Free agent"}
      routeTo={<ClubLink id={deal.buyer_club?.id} name={deal.buyer_club?.name} crestUrl={deal.buyer_club?.crest_url} />}
      lgSubExtra={deal.agent ? <>agent {deal.agent.display_name}</> : null}
      amount={<Money value={deal.agreed_fee} compact />}
      facts={
        <>
          {dealFacts(deal)}
          {deal.is_auction_deal && (
            <span className="ml-2 inline-flex rounded-full bg-text-muted/15 px-2.5 py-0.5 text-[13px] font-semibold text-text-secondary ring-1 ring-text-muted/30">
              Auction deal
            </span>
          )}
        </>
      }
      moreMenu={moreMenu}
    />
  );
}
