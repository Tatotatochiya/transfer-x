import { Link } from "react-router-dom";

import { formatCompactCurrency } from "../../lib/utils";
import type { BoardCard } from "./types";

/**
 * A player's other open items in the same stage (a second offer for him),
 * each a link to its own page: "Also Bournemouth · £16.5M · Offer received".
 * The card shows the most pressing one; these are the rest.
 */
export default function OtherItems({ card, className = "" }: { card: BoardCard; className?: string }) {
  const items = card.other_items ?? [];
  if (items.length === 0) return null;
  return (
    <ul className={`space-y-0.5 ${className}`} aria-label={`Other ${card.kind === "offer" ? "offers" : "items"} for ${card.player_name}`}>
      {items.map((o) => (
        <li key={o.entity_id}>
          <Link
            to={o.link}
            onClick={(e) => e.stopPropagation()}
            className="inline-flex max-w-full items-baseline gap-1 text-left text-small text-text-secondary no-underline hover:text-text hover:underline"
          >
            <span className="min-w-0">
              Also <span className="font-semibold text-text">{o.counterparty ?? "another club"}</span>
              {o.amount != null && <> · {formatCompactCurrency(Number(o.amount))}</>}
              {" · "}
              <span className={o.whose_move === "your" ? "font-semibold text-danger-text" : undefined}>{o.detail}</span>
            </span>
            <span aria-hidden className="shrink-0 text-text-muted">›</span>
          </Link>
        </li>
      ))}
    </ul>
  );
}
