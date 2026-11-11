import type { ReactNode } from "react";
import type { Offer } from "../../types/api";
import ClubLink from "../ui/ClubLink";
import TransferHeader from "../transfer/TransferHeader";
import { buyerLabel, isBuyerMasked } from "../../lib/buyerIdentity";
import { offerStatusLabel } from "../../lib/badges";
import { isLoan, loanPeriod, offerHeadline } from "../../lib/offerTerms";
import { formatCompact, formatDate } from "../../lib/utils";

/**
 * Who the offer is for (offer-room-focus §5.11): the player, seller → buyer,
 * and the amount. A masked buyer is plain text with the "Anonymous" badge,
 * never a link.
 */
export default function OfferHeader({ offer, moreMenu }: { offer: Offer; moreMenu: ReactNode }) {
  const payment = isLoan(offer) ? loanPeriod(offer)
    : (offer.instalments ?? []).length > 0 ? `${offer.instalments.length} instalments` : "On completion";
  return (
    <TransferHeader
      player={{
        id: offer.player?.id ?? offer.player_id,
        name: offer.player?.name ?? null,
        position: offer.player?.position ?? null,
        photoUrl: offer.player?.photo_url ?? null,
      }}
      routeFrom={<ClubLink id={offer.to_club?.id} name={offer.to_club?.name} crestUrl={offer.to_club?.crest_url ?? null} />}
      routeTo={isBuyerMasked(offer) ? (
        <>
          {buyerLabel(offer)}
          <span className="ml-2 rounded-full bg-surface-inset px-2 py-0.5 text-[13px] font-semibold text-text-muted ring-1 ring-border">
            Anonymous
          </span>
        </>
      ) : (
        <ClubLink id={offer.from_club?.id} name={offer.from_club?.name} crestUrl={offer.from_club?.crest_url ?? null} />
      )}
      lgSubExtra={<>offer made {formatDate(offer.created_at)}</>}
      amount={offerHeadline(offer, formatCompact)}
      facts={
        <>
          {isLoan(offer) ? "Loan" : "Permanent"} · {payment}
          {offer.deal && <span className="ml-2">· Offer {offerStatusLabel(offer.status).toLowerCase()}</span>}
        </>
      }
      moreMenu={moreMenu}
    />
  );
}
