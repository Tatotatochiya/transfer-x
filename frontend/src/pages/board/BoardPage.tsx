import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import api from "../../lib/api";
import { formatCompactCurrency } from "../../lib/utils";
import { timeLeft } from "../../lib/timeLeft";
import { Estimate } from "../../components/ui/Money";
import EmptyState from "../../components/ui/EmptyState";
import PageHeader from "../../components/ui/PageHeader";
import Spinner from "../../components/ui/Spinner";
import Button from "../../components/ui/Button";
import Modal from "../../components/ui/Modal";
import ConversationPanel, { type ConversationContext } from "../../components/conversation/ConversationPanel";

/**
 * The Transfers board (Phase 3, product ADR 0008): every player the club is
 * buying or selling, once, at its furthest point. Backend: app/board.
 */

type Side = "BOTH" | "BUYING" | "SELLING";
type WhoseMove = "your" | "their" | "neither";

export interface BoardCard {
  key: string;
  side: "BUYING" | "SELLING";
  column: string;
  kind: "enquiry" | "listing" | "offer" | "bid" | "deal";
  entity_id: string;
  player_id: string;
  player_name: string;
  player_position: string | null;
  counterparty: string | null;
  amount: string | number | null;
  detail: string;
  whose_move: WhoseMove;
  deadline: string | null;
  link: string;
  updated_at: string | null;
  others: number;
}

interface Board {
  columns: { key: string; label: string; cards: BoardCard[] }[];
  closed: BoardCard[];
  counts: { buying: number; selling: number; your_move: number };
}

const SIDE_KEY = "transferx-board-side";

function readSide(): Side {
  try {
    const v = localStorage.getItem(SIDE_KEY);
    return v === "BUYING" || v === "SELLING" ? v : "BOTH";
  } catch {
    return "BOTH";
  }
}

function Card({ card, showSide, onOpen }: { card: BoardCard; showSide: boolean; onOpen: (c: BoardCard) => void }) {
  const yours = card.whose_move === "your";
  const left = timeLeft(card.deadline);
  return (
    <button
      type="button"
      onClick={() => onOpen(card)}
      className={`w-full rounded-xl bg-surface p-3 text-left ring-1 transition-colors hover:ring-accent/50 focus-visible:outline-2 focus-visible:outline-accent ${
        yours ? "ring-accent/40" : "ring-border"
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <p className="min-w-0 truncate text-sm font-semibold text-text">
          {card.player_name}
          {card.player_position && <span className="ml-1.5 text-xs font-normal text-text-muted">{card.player_position}</span>}
        </p>
        {yours && <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-accent" aria-label="Your move" />}
      </div>
      {(card.counterparty || showSide) && (
        <p className="mt-0.5 truncate text-xs text-text-muted">
          {showSide && <span className="font-semibold">{card.side === "BUYING" ? "Buying" : "Selling"}</span>}
          {showSide && card.counterparty && " · "}
          {card.counterparty && (card.side === "BUYING" ? `from ${card.counterparty}` : `to ${card.counterparty}`)}
        </p>
      )}
      {card.amount != null && (
        <p className="mt-1.5 text-sm font-bold tabular-nums text-text">
          {formatCompactCurrency(Number(card.amount))}
          <Estimate value={card.amount} />
        </p>
      )}
      <p className={`mt-1 text-xs ${yours ? "font-semibold text-accent" : "text-text-secondary"}`}>{card.detail}</p>
      {(left || card.others > 0) && (
        <p className="mt-1 flex flex-wrap gap-x-2 text-xs text-text-muted">
          {left && <span className={left.urgent ? "font-semibold text-danger-text" : ""}>{left.text}</span>}
          {card.others > 0 && <span>+{card.others} more</span>}
        </p>
      )}
    </button>
  );
}

const OPEN_LABEL: Record<BoardCard["kind"], string> = {
  enquiry: "Open the enquiry", offer: "Open the offer", deal: "Open the deal", listing: "Open the listing", bid: "Open the auction",
};

/** A card opened: its summary, a way to the full page, and the transfer's
 *  conversation (enquiries, offers and deals have one; listings don't). */
function CardDetail({ card, onClose }: { card: BoardCard; onClose: () => void }) {
  const navigate = useNavigate();
  const context: ConversationContext | null =
    card.kind === "offer" ? { offerId: card.entity_id }
      : card.kind === "deal" ? { dealId: card.entity_id }
      : card.kind === "enquiry" ? { enquiryId: card.entity_id } : null;
  return (
    <Modal open onClose={onClose} title={card.player_name} size="lg">
      <div className="space-y-4 px-6 py-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="text-sm">
            <p className="text-text-secondary">
              {card.side === "BUYING" ? "Buying" : "Selling"}
              {card.counterparty && (card.side === "BUYING" ? ` from ${card.counterparty}` : ` to ${card.counterparty}`)}
              {card.amount != null && <> · <span className="font-semibold text-text">{formatCompactCurrency(Number(card.amount))}</span></>}
            </p>
            <p className={card.whose_move === "your" ? "font-semibold text-accent" : "text-text-muted"}>{card.detail}</p>
          </div>
          <Button size="sm" onClick={() => navigate(card.link)}>{OPEN_LABEL[card.kind]}</Button>
        </div>
        {context ? (
          <div className="border-t border-rule-faint pt-4">
            <h3 className="mb-3 text-xs font-bold uppercase tracking-[0.06em] text-text-muted">Conversation</h3>
            <ConversationPanel context={context} compact />
          </div>
        ) : (
          <p className="text-sm text-text-muted">Conversations start with an enquiry or an offer.</p>
        )}
      </div>
    </Modal>
  );
}

export default function BoardPage() {
  const [side, setSideState] = useState<Side>(readSide);
  const [showClosed, setShowClosed] = useState(false);
  const [opened, setOpened] = useState<BoardCard | null>(null);
  const setSide = (s: Side) => {
    setSideState(s);
    try { localStorage.setItem(SIDE_KEY, s); } catch { /* the choice still applies here */ }
  };
  const { data, isLoading, isError } = useQuery<Board>({
    queryKey: ["board", side],
    queryFn: () => api.get<Board>("/board", { params: { side } }).then((r) => r.data),
    refetchInterval: 60_000,
  });
  const total = data ? data.columns.reduce((n, c) => n + c.cards.length, 0) : 0;

  return (
    <div>
      <PageHeader
        title="Transfers"
        subtitle={data ? `${data.counts.your_move} waiting on you · ${data.counts.buying} buying · ${data.counts.selling} selling` : undefined}
        actions={
          <div role="radiogroup" aria-label="Show" className="flex rounded-lg bg-surface-inset p-0.5 ring-1 ring-border">
            {(["BOTH", "BUYING", "SELLING"] as Side[]).map((s) => (
              <button
                key={s}
                role="radio"
                aria-checked={side === s}
                onClick={() => setSide(s)}
                className={`rounded-md px-3 py-1.5 text-sm font-medium ${side === s ? "bg-surface text-text shadow-sm" : "text-text-secondary"}`}
              >
                {s === "BOTH" ? "Both" : s === "BUYING" ? "Buying" : "Selling"}
              </button>
            ))}
          </div>
        }
      />

      {isLoading ? (
        <div className="flex justify-center py-16"><Spinner size="lg" /></div>
      ) : isError || !data ? (
        <EmptyState title="Couldn't load the board" body="Try again in a moment." />
      ) : (
        <>
          {total === 0 && (
            <div className="mb-4">
              <EmptyState
                title="Nothing in progress"
                body="Players you list, enquire about or make offers for appear here, one card each."
                action={{ label: "Browse players", to: "/players/market" }}
              />
            </div>
          )}
          <div className="-mx-4 flex snap-x scroll-px-4 gap-3 overflow-x-auto px-4 pb-3 md:mx-0 md:scroll-px-0 md:px-0">
            {data.columns.map((col) => (
              <section key={col.key} aria-label={col.label} className="w-[260px] shrink-0 snap-start lg:w-auto lg:min-w-0 lg:flex-1">
                <h2 className="mb-2 flex items-baseline justify-between px-1 text-xs font-bold uppercase tracking-[0.06em] text-text-muted">
                  {col.label}
                  <span className="tabular-nums">{col.cards.length}</span>
                </h2>
                <div className="flex flex-col gap-2">
                  {col.cards.map((c) => <Card key={c.key} card={c} showSide={side === "BOTH"} onOpen={setOpened} />)}
                  {col.cards.length === 0 && (
                    <p className="rounded-xl border border-dashed border-border px-3 py-4 text-center text-xs text-text-muted">None</p>
                  )}
                </div>
              </section>
            ))}
          </div>

          {data.closed.length > 0 && (
            <div className="mt-6">
              <button
                type="button"
                onClick={() => setShowClosed((v) => !v)}
                aria-expanded={showClosed}
                className="text-sm font-semibold text-text-secondary hover:text-text"
              >
                Closed ({data.closed.length}) {showClosed ? "▾" : "▸"}
              </button>
              {showClosed && (
                <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
                  {data.closed.map((c) => <Card key={`${c.key}:${c.entity_id}`} card={c} showSide={side === "BOTH"} onOpen={setOpened} />)}
                </div>
              )}
            </div>
          )}
        </>
      )}
      {opened && <CardDetail card={opened} onClose={() => setOpened(null)} />}
    </div>
  );
}
