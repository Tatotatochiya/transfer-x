import { Link } from "react-router-dom";

import { formatCompactCurrency } from "../../lib/utils";
import { countdownLeft } from "../../lib/timeLeft";
import { useNow } from "../../hooks/useNow";
import { Estimate } from "../ui/Money";
import FallbackImage from "../ui/FallbackImage";
import { ChasedBadge, StalledBadge, stalledDays } from "../transfer/ReminderBadges";
import { detailAfterStage, stageStep } from "./boardList";
import StageSteps from "./StageSteps";
import type { BoardCard, Side } from "./types";

/** "Buying from Liverpool", or "from Liverpool" with one side picked. */
function partyText(card: BoardCard, side: Side): string {
  const both = side === "BOTH";
  if (card.counterparty) {
    const to = card.side === "BUYING" ? `from ${card.counterparty}` : `to ${card.counterparty}`;
    return both ? `${card.side === "BUYING" ? "Buying" : "Selling"} ${to}` : to;
  }
  if (card.kind === "listing") return both ? "Selling · listed" : "Listed";
  return both ? (card.side === "BUYING" ? "Buying" : "Selling") : "";
}

function Badges({ card }: { card: BoardCard }) {
  const yours = card.whose_move === "your";
  const chased = yours && card.chased;
  const stalled = card.whose_move === "their" && stalledDays(card.updated_at) != null;
  if (!chased && !stalled && (card.others === 0 || !!card.other_items?.length)) return null;
  return (
    <span className="mt-1.5 flex flex-wrap items-center gap-2">
      {chased ? <ChasedBadge escalated={card.chased === "ESCALATED"} /> : stalled ? <StalledBadge since={card.updated_at} /> : null}
      {card.others > 0 && !card.other_items?.length && <span className="text-small text-text-muted">+{card.others} more</span>}
    </span>
  );
}

/**
 * One transfer below 1280px (README_TRANSFERS §4.4): a link to its page.
 * The player's name is plain text so links don't nest. `layout` "phone"
 * stacks it; "tablet" lays it in the list's columns.
 */
export default function TransferRow({ card, side, stageLabel, layout }: {
  card: BoardCard;
  side: Side;
  /** The column's label from the API. */
  stageLabel: string;
  layout: "phone" | "tablet";
}) {
  const now = useNow();
  const yours = card.whose_move === "your";
  const done = stageStep(card.column) === 6;
  const stage = done ? "Completed" : stageLabel;
  const detail = detailAfterStage(card, stageLabel);
  const left = countdownLeft(card.deadline, now);
  const party = partyText(card, side);
  const fee = card.amount != null ? formatCompactCurrency(Number(card.amount)) : null;
  const label = [card.player_name, party, fee, stage, detail, left?.text].filter(Boolean).join(", ");
  const due = left && (
    <span className={`text-small ${left.urgent || yours ? "font-semibold text-danger-text" : "text-text-muted"}`}>{left.text}</span>
  );
  const photo = (
    <FallbackImage src={card.player_photo_url} name={card.player_name} kind="player" sizeClass="h-10 w-10 text-small"
      colorClass="bg-surface-inset text-text-muted" />
  );
  const stageLine = (
    <span className={`flex min-w-0 gap-2 text-caption ${layout === "phone" ? "items-baseline" : "items-center"}`}>
      <StageSteps column={card.column} label={stageLabel} />
      <span className={`min-w-0 ${layout === "phone" ? "" : "truncate"}`}>
        <span className={`font-semibold ${done ? "text-success-text" : "text-text"}`}>{stage}</span>
        {detail && layout === "phone" && (
          <span className={yours ? "font-semibold text-danger-text" : "text-text-secondary"}> · {detail}</span>
        )}
      </span>
    </span>
  );
  const LINK = "block px-4 py-3 text-left no-underline hover:bg-surface-inset focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-accent";

  if (layout === "tablet") {
    return (
      <Link to={card.link} aria-label={label}
        className={`${LINK} grid min-h-[64px] grid-cols-[40px_minmax(0,1fr)_220px_96px_104px_16px] items-center gap-x-3`}>
        {photo}
        <span className="min-w-0">
          <span className="flex min-w-0 items-baseline gap-1.5">
            <span className="truncate text-body font-semibold text-text">{card.player_name}</span>
            {card.player_position && <span className="shrink-0 text-small text-text-muted">{card.player_position}</span>}
          </span>
          {party && <span className="block truncate text-small text-text-secondary">{party}</span>}
          <Badges card={card} />
        </span>
        <span className="min-w-0">
          {stageLine}
          {detail && (
            <span className={`mt-0.5 block truncate text-caption ${yours ? "font-semibold text-danger-text" : "text-text-secondary"}`}>{detail}</span>
          )}
        </span>
        <span className="text-right text-body font-bold tabular-nums text-text">
          {fee}{fee && <Estimate value={card.amount} />}
        </span>
        <span className="text-right">{due ?? <span className="text-small text-text-muted">—</span>}</span>
        <span aria-hidden className="text-text-muted">›</span>
      </Link>
    );
  }

  return (
    <Link to={card.link} aria-label={label} className={`${LINK} flex min-h-[64px] items-start gap-3`}>
      {photo}
      <span className="min-w-0 flex-1">
        <span className="flex items-baseline justify-between gap-2">
          <span className="flex min-w-0 items-baseline gap-1.5">
            <span className="truncate text-body font-semibold text-text">{card.player_name}</span>
            {card.player_position && <span className="shrink-0 text-small text-text-muted">{card.player_position}</span>}
          </span>
          {fee && (
            <span className="shrink-0 text-body font-bold tabular-nums text-text">{fee}<Estimate value={card.amount} /></span>
          )}
        </span>
        {(party || due) && (
          <span className="mt-0.5 flex items-baseline justify-between gap-2">
            <span className="min-w-0 truncate text-small text-text-secondary">{party}</span>
            {due && <span className="shrink-0">{due}</span>}
          </span>
        )}
        <span className="mt-1.5 block">{stageLine}</span>
        <Badges card={card} />
      </span>
      <span aria-hidden className="self-center text-text-muted">›</span>
    </Link>
  );
}
