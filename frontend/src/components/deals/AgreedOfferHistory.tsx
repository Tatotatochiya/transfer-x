import { useQuery } from "@tanstack/react-query";
import api from "../../lib/api";
import type { Offer } from "../../types/api";
import OfferThread from "../offers/OfferThread";
import { NegotiationSummaryPanel } from "../ai/Assistant";
import { formatDate } from "../../lib/utils";

/**
 * One page per transfer: the negotiation that produced this deal, shown in
 * the deal room so a club follows a transfer from first approach to
 * completion. The disclosure row or the desktop tab is its container.
 */
export default function AgreedOfferHistory({ offerId, myClubId }: { offerId: string; myClubId?: string }) {
  const { data: offer } = useQuery<Offer>({
    queryKey: ["offers", offerId],
    queryFn: () => api.get<Offer>(`/offers/${offerId}`).then((r) => r.data),
  });
  if (!offer) return null;
  return (
    <div>
      <p className="text-body text-text-secondary">
        Offer made {formatDate(offer.created_at)} — {offer.messages.length} message
        {offer.messages.length === 1 ? "" : "s"}, {offer.events.length} step
        {offer.events.length === 1 ? "" : "s"} in the negotiation
      </p>
      <div className="mt-3">
        <div className="mb-3"><NegotiationSummaryPanel offer={offer} /></div>
        <OfferThread offer={offer} myClubId={myClubId} canMessage={false} />
      </div>
    </div>
  );
}
