import type { Offer } from "../../types/api";
import MoreMenu, { type MoreMenuItem } from "../transfer/MoreMenu";
import { askAboutPath } from "../../lib/ask";

/**
 * The offer page's secondary actions (offer-room-focus §5.10): the listing,
 * asking TransferX, and withdrawing (D7), away from Accept and Counter.
 */
export default function OfferMoreMenu({ offer, isParty, canWithdraw, onWithdraw }: {
  offer: Offer;
  isParty: boolean;
  canWithdraw: boolean;
  onWithdraw: () => void;
}) {
  const items: MoreMenuItem[] = [];
  if (offer.sale_id) items.push({ label: "View the listing", to: `/sales/${offer.sale_id}` });
  if (isParty) items.push({ label: "Ask TransferX about this offer", to: askAboutPath("offer", offer.id, offer.player?.name ?? "") });
  if (canWithdraw) items.push({ label: "Withdraw offer…", onSelect: onWithdraw, danger: true, dividerBefore: true });
  return <MoreMenu items={items} />;
}
