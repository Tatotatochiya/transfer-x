import MoreMenu, { type MoreMenuItem } from "../transfer/MoreMenu";
import { askAboutPath } from "../../lib/ask";

/**
 * The deal room's secondary actions (deal-room-focus §5.7): asking TransferX
 * about the deal, and collapsing it, kept away from the main action (D6).
 */
export default function DealMoreMenu({ dealId, playerName, canAsk, canCollapse, onCollapse }: {
  dealId: string;
  playerName: string;
  canAsk: boolean;
  canCollapse: boolean;
  onCollapse: () => void;
}) {
  const items: MoreMenuItem[] = [];
  if (canAsk) items.push({ label: "Ask TransferX about this deal", to: askAboutPath("deal", dealId, playerName) });
  if (canCollapse) items.push({ label: "Collapse deal…", onSelect: onCollapse, danger: true, dividerBefore: true });
  return <MoreMenu items={items} />;
}
