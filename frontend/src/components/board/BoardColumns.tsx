import AskAboutButton from "../ai/AskAboutButton";
import { useNavigate } from "react-router-dom";

import { formatCompactCurrency } from "../../lib/utils";
import { timeLeft } from "../../lib/timeLeft";
import { Estimate } from "../ui/Money";
import Button from "../ui/Button";
import Modal from "../ui/Modal";
import ConversationPanel, { type ConversationContext } from "../conversation/ConversationPanel";
import PlayerLink from "../ui/PlayerLink";
import { ChasedBadge, StalledBadge, stalledDays } from "../transfer/ReminderBadges";
import type { Board, BoardCard } from "./types";

/**
 * The board from 1280px (product ADR 0008, README_TRANSFERS §5): stage
 * columns of cards, a card opening its summary and conversation.
 */

export const SIDE_STYLE: Record<BoardCard["side"], { label: string; tag: string; bar: string }> = {
  // Categories, so neutral: the label says which (TOKENS.md colour roles).
  BUYING: { label: "Buying", tag: "bg-surface-inset text-text-secondary", bar: "bg-text-secondary" },
  SELLING: { label: "Selling", tag: "bg-surface-inset text-text-secondary", bar: "bg-text-secondary" },
};

function SideTag({ side }: { side: BoardCard["side"] }) {
  return (
    <span className={`mr-1 inline-block rounded px-1.5 py-px text-caption font-semibold ${SIDE_STYLE[side].tag}`}>
      {SIDE_STYLE[side].label}
    </span>
  );
}

// "Your move" is red (needs you), never blue: blue is only for what you can
// tap (TOKENS.md colour roles). Hover and focus stay accent.
export function Card({ card, showSide, onOpen }: { card: BoardCard; showSide: boolean; onOpen: (c: BoardCard) => void }) {
  const yours = card.whose_move === "your";
  const left = timeLeft(card.deadline);
  return (
    // A clickable card rather than a <button>: the player's name inside is
    // a link to his profile, and a link can't sit inside a button.
    <div
      role="button"
      tabIndex={0}
      aria-label={`${card.player_name}: ${card.detail}`}
      onClick={() => onOpen(card)}
      onKeyDown={(e) => { if (e.target === e.currentTarget && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); onOpen(card); } }}
      className={`w-full cursor-pointer rounded-xl bg-surface p-3 text-left ring-1 transition-colors hover:ring-accent-ring focus-visible:outline-2 focus-visible:outline-accent ${
        yours ? "ring-danger-ring" : "ring-border"
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <p className="flex min-w-0 items-center gap-1.5 text-body font-semibold text-text">
          <PlayerLink id={card.player_id} name={card.player_name} photoUrl={card.player_photo_url ?? null} size="md" />
          {card.player_position && <span className="shrink-0 text-small font-normal text-text-muted">{card.player_position}</span>}
        </p>
        {yours && <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-danger" aria-label="Your move" />}
      </div>
      {(card.counterparty || showSide) && (
        <p className="mt-0.5 truncate text-small text-text-muted">
          {showSide && <SideTag side={card.side} />}
          {showSide && card.counterparty && " "}
          {card.counterparty && (card.side === "BUYING" ? `from ${card.counterparty}` : `to ${card.counterparty}`)}
        </p>
      )}
      {card.amount != null && (
        <p className="mt-1.5 text-body font-bold tabular-nums text-text">
          {formatCompactCurrency(Number(card.amount))}
          <Estimate value={card.amount} />
        </p>
      )}
      <p className={`mt-1 text-caption ${yours ? "font-semibold text-danger-text" : "text-text-secondary"}`}>{card.detail}</p>
      {(left || card.others > 0) && (
        <p className="mt-1 flex flex-wrap gap-x-2 text-small text-text-muted">
          {left && <span className={left.urgent ? "font-semibold text-danger-text" : ""}>{left.text}</span>}
          {card.others > 0 && <span>+{card.others} more</span>}
        </p>
      )}
      {(yours && card.chased) || (card.whose_move === "their" && stalledDays(card.updated_at) != null) ? (
        <div className="mt-2">
          {yours && card.chased
            ? <ChasedBadge escalated={card.chased === "ESCALATED"} />
            : <StalledBadge since={card.updated_at} />}
        </div>
      ) : null}
    </div>
  );
}

const OPEN_LABEL: Record<BoardCard["kind"], string> = {
  enquiry: "Open the enquiry", offer: "Open the offer", deal: "Open the deal", listing: "Open the listing",
};

/** A card opened: its summary, a way to the full page, and the transfer's
 *  conversation (enquiries, offers and deals have one; listings don't). */
export function CardDetail({ card, onClose }: { card: BoardCard; onClose: () => void }) {
  const navigate = useNavigate();
  const context: ConversationContext | null =
    card.kind === "offer" ? { offerId: card.entity_id }
      : card.kind === "deal" ? { dealId: card.entity_id }
      : card.kind === "enquiry" ? { enquiryId: card.entity_id } : null;
  return (
    <Modal open onClose={onClose} title={card.player_name} size="lg">
      <div className="space-y-4 px-6 py-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="text-small">
            <PlayerLink id={card.player_id} name={card.player_name} photoUrl={card.player_photo_url ?? null} size="lg"
              className="mb-2 text-body font-semibold text-text" />
            <p className="text-text-secondary">
              {card.side === "BUYING" ? "Buying" : "Selling"}
              {card.counterparty && (card.side === "BUYING" ? ` from ${card.counterparty}` : ` to ${card.counterparty}`)}
              {card.amount != null && <> · <span className="font-semibold text-text">{formatCompactCurrency(Number(card.amount))}</span></>}
            </p>
            <p className={card.whose_move === "your" ? "font-semibold text-danger-text" : "text-text-muted"}>{card.detail}</p>
          </div>
          <div className="flex gap-2">
            {card.kind === "deal" || card.kind === "offer"
              ? <AskAboutButton size="sm" about={card.kind} id={card.entity_id} name={card.player_name} />
              : <AskAboutButton size="sm" about="player" id={card.player_id} name={card.player_name} />}
            <Button size="sm" onClick={() => navigate(card.link)}>{OPEN_LABEL[card.kind]}</Button>
          </div>
        </div>
        {context ? (
          <div className="border-t border-rule-faint pt-4">
            <h3 className="mb-3 text-section font-bold text-text">Conversation</h3>
            <ConversationPanel context={context} compact />
          </div>
        ) : (
          <p className="text-small text-text-muted">Conversations start with an enquiry or an offer.</p>
        )}
      </div>
    </Modal>
  );
}

export function Columns({ columns, pick, collapsed, showSide, onOpen }: {
  columns: Board["columns"];
  pick: (c: BoardCard) => boolean;
  /** Columns empty in every lane shown: a thin strip, so the open ones have room. */
  collapsed: Set<string>;
  showSide: boolean;
  onOpen: (c: BoardCard) => void;
}) {
  return (
    <div className="flex items-stretch gap-3 pb-3">
      {columns.map((col) => {
        if (collapsed.has(col.key)) {
          return (
            <section key={col.key} aria-label={`${col.label}: none`}
              className="flex min-h-[120px] w-[52px] shrink-0 flex-col items-center gap-2 rounded-xl border border-dashed border-border py-3">
              <span className="text-caption font-semibold tabular-nums text-text-muted">0</span>
              <span className="rotate-180 text-caption font-semibold text-text-muted [writing-mode:vertical-rl]">{col.label}</span>
            </section>
          );
        }
        const cards = col.cards.filter(pick);
        return (
          <section key={col.key} aria-label={col.label} className="min-w-0 flex-1">
            <h3 className="mb-2 flex items-baseline justify-between px-1 text-section font-bold text-text">
              {col.label}
              <span className="tabular-nums">{cards.length}</span>
            </h3>
            <div className="flex flex-col gap-2">
              {cards.map((c) => <Card key={c.key} card={c} showSide={showSide} onOpen={onOpen} />)}
              {cards.length === 0 && (
                <p className="rounded-xl border border-dashed border-border px-3 py-4 text-center text-small text-text-muted">None</p>
              )}
            </div>
          </section>
        );
      })}
    </div>
  );
}
