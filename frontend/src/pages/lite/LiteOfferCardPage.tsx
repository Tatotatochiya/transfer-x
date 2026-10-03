import { useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";

import {
  ActionCardShell, FactRow, FeeStepper, MoneyPanel, Notes,
  dangerBtn, primaryBtn, secondaryBtn, textBtn, useDebounced,
} from "../../components/lite/ActionCard";
import Spinner from "../../components/ui/Spinner";
import { useOfferCheck } from "../../hooks/useAssistant";
import { CLUB_DASHBOARD_KEY, useClubDashboard } from "../../hooks/useClubDashboard";
import { useLiteOfferCard } from "../../hooks/useLite";
import { holdAndOpen } from "./LiteSentPage";
import { liteMoney, liteWage } from "../../lib/liteMoney";
import { getApiError } from "../../lib/utils";

type Mode = "answer" | "accept" | "counter" | "reject";

const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
const shortDate = (iso: string | null) =>
  iso ? new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" }) : "—";

/**
 * An offer waiting for the club, as an action card (README "Screen 5",
 * received offers): Accept, Counter, Say no. Each asks once more before it
 * goes, then calls the existing offer endpoints. Accept and counter show the
 * money panel from /ai/offer-check; an anonymous buyer stays masked (the
 * server names them).
 */
export default function LiteOfferCardPage() {
  const { offerId } = useParams<{ offerId: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { data: card, isLoading, error } = useLiteOfferCard(offerId);

  // From Ask anything: the action it proposed opens ready to confirm, and is
  // recorded as the assistant's suggestion when confirmed.
  const [params] = useSearchParams();
  const fromAsk = params.get("from") === "ask";
  // Opened from a phone notification: this card is the decision sheet
  // (mobile notifications §7.3, 4c).
  const fromPush = params.get("from") === "push";
  const proposed = params.get("action");
  const [mode, setMode] = useState<Mode>(
    proposed === "accept" || proposed === "reject" || proposed === "counter" ? proposed : "answer",
  );
  const [counterFee, setCounterFee] = useState<number | null>(Number(params.get("amount")) || null);
  const [busy, setBusy] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);

  const counter = counterFee ?? card?.counter_suggestion ?? null;
  const body = useMemo(
    () => (card ? { offer_id: card.offer_id, terms: mode === "counter" && counter ? { fee_amount: counter } : {} } : null),
    [card, mode, counter],
  );
  const settled = useDebounced(body);
  const check = useOfferCheck(settled);
  const money = check.data?.money;
  const current = settled === body && !check.isFetching && !!money;

  if (isLoading) return <div className="flex justify-center py-16"><Spinner size="lg" /></div>;
  if (error || !card) {
    return (
      <div className="flex flex-col items-start gap-5">
        <h1 className="text-[1.75rem] font-extrabold text-text">We couldn't open this offer</h1>
        <p className="text-[1.25rem] text-text-secondary">{getApiError(error, "It may have been withdrawn.")}</p>
        <Link to="/lite/offers" className={`${secondaryBtn} flex items-center no-underline`}>Back to offers</Link>
      </div>
    );
  }

  const player = card.player_name ?? "your player";
  const open = card.status === "SENT" || card.status === "COUNTERED";
  const left = timeLeft(card.expires_at);
  const askingValuation = card.side === "seller" && card.your_valuation != null && card.counter_suggestion === card.your_valuation;
  const loan = card.deal_type === "LOAN";
  const other = card.other_club;
  // Confirming holds the action for 10 seconds (L6, ADR 0007) and opens the
  // Sent screen; Undo there comes back here with the same choice made.
  const run = async (kind: "accept" | "counter" | "reject", extra: Record<string, unknown> = {}) => {
    setBusy(true);
    setSendError(null);
    try {
      const back = new URLSearchParams({ action: kind, ...(kind === "counter" && counter ? { amount: String(counter) } : {}) });
      await holdAndOpen(navigate, { kind, payload: { offer_id: card.offer_id, ...extra }, ai_assisted: fromAsk },
        `/lite/offers/${card.offer_id}?${back}`);
      queryClient.invalidateQueries({ queryKey: ["lite"] });
      queryClient.invalidateQueries({ queryKey: CLUB_DASHBOARD_KEY });
    } catch (err) {
      setSendError(getApiError(err, "That didn't go through."));
      setBusy(false);
    }
  };
  const accept = () => run("accept");
  const sendCounter = () => run("counter", { fee_amount: counter });
  const reject = () => run("reject");

  const buyerOverBudget = card.side === "buyer" && !!money?.over_budget;
  const title = card.side === "seller"
    ? `${cap(other)} ${loan ? "wants to loan" : "offers"} ${liteMoney(card.fee)} for ${player}`
    : card.your_move
      ? `${cap(other)} asks ${liteMoney(card.fee)} for ${player}`
      : `Your ${liteMoney(card.fee)} offer for ${player}`;
  const pill = card.side === "seller" ? "Offer for your player" : "Reply to your offer";

  return (
    <div className="flex flex-col gap-4">
      {fromPush && <WaitingHeader offerId={card.offer_id} />}
      {fromPush && !open && (
        <div role="status" className="rounded-2xl bg-warning-bg px-5 py-4 text-[1.0625rem] text-text ring-1 ring-border">
          This has changed since we told you: the offer has been {card.status.toLowerCase()}.{" "}
          <Link to={`/offers/${card.offer_id}`} className="font-bold text-accent">See what happened</Link>
        </div>
      )}
      {fromPush && open && left && (
        <p className={`text-[0.8125rem] font-bold uppercase tracking-wider ${left.urgent ? "text-danger-text" : "text-text-muted"}`}>
          {card.side === "seller" ? "Offer received" : "Reply to your offer"} · {left.text}
        </p>
      )}
      <ActionCardShell
        pill={pill}
        tone={card.side === "seller" ? "received" : "ready"}
        title={title}
        money={<MoneyPanel money={money} loading={check.isFetching} what={mode === "counter" ? "counter" : "offer"} />}
      >
        <div>
          <FactRow label="Player">{player}</FactRow>
          <FactRow label={card.side === "seller" ? "From" : "Selling club"}>{cap(other)}</FactRow>
          <FactRow label={loan ? "Loan fee" : "Fee"}>{liteMoney(card.fee)}</FactRow>
          {card.your_valuation != null && <FactRow label="Your valuation">{liteMoney(card.your_valuation)}</FactRow>}
          {open && card.expires_at && (
            <FactRow label="Reply by">
              <span className={left?.urgent ? "font-bold text-danger-text" : undefined}>
                {new Date(card.expires_at).toLocaleString("en-GB", { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}
              </span>
            </FactRow>
          )}
          {loan ? (
            <>
              <FactRow label="Wages paid by them">{card.wage_split_pct != null ? `${Math.round(card.wage_split_pct * 100)}%` : "All of them"}</FactRow>
              <FactRow label="Loan">{shortDate(card.loan_start)} to {shortDate(card.loan_end)}</FactRow>
            </>
          ) : (
            <>
              <FactRow label="Wages offered">{card.wage_weekly != null ? liteWage(card.wage_weekly) : "Agreed with him later"}</FactRow>
              {card.contract_years != null && <FactRow label="Contract">{card.contract_years} years</FactRow>}
            </>
          )}
          {card.has_add_ons && (
            <FactRow label="Other terms">
              <Link to={`/offers/${card.offer_id}`} className="text-accent">Add-ons or instalments, see the full offer</Link>
            </FactRow>
          )}
        </div>

        {mode === "counter" && counter != null && (
          <FeeStepper value={counter} onChange={setCounterFee} label="Counter fee in millions of pounds" />
        )}
        <Notes warnings={check.data?.warnings} />
        {card.disabled_reason && (
          <p className="rounded-xl bg-surface-inset px-4 py-3 text-[1.0625rem] text-text-secondary">{card.disabled_reason}</p>
        )}
        {mode === "accept" && (
          <p className="rounded-xl bg-accent-bg px-4 py-3 text-[1.0625rem] text-text">
            Accept {liteMoney(card.fee)} for {player}? This agrees the fee with {other}; the medical and personal terms come next.
          </p>
        )}
        {mode === "reject" && (
          <p className="rounded-xl bg-danger-bg px-4 py-3 text-[1.0625rem] text-danger-text">
            Say no to {other}? The offer closes and they are told. They can make a new one.
          </p>
        )}
        {sendError && <p role="alert" className="rounded-xl bg-danger-bg px-4 py-3 text-[1.0625rem] text-danger-text">{sendError}</p>}

        {!card.disabled_reason && (
          <div className="mt-auto flex flex-col gap-3 sm:flex-row sm:flex-wrap">
            {mode === "answer" && (
              <>
                <button type="button" className={primaryBtn} onClick={() => setMode("accept")} disabled={buyerOverBudget}>
                  Accept {liteMoney(card.fee)}
                </button>
                {card.counter_suggestion != null ? (
                  <button type="button" className={secondaryBtn} onClick={() => setMode("counter")}>
                    {askingValuation ? `Ask for ${liteMoney(card.counter_suggestion)}` : `Counter at ${liteMoney(card.counter_suggestion)}`}
                  </button>
                ) : loan && (
                  <Link to={`/offers/${card.offer_id}`} className={`${secondaryBtn} flex items-center justify-center no-underline`}>
                    Change the loan terms
                  </Link>
                )}
                <button type="button" className={dangerBtn} onClick={() => setMode("reject")}>Say no</button>
              </>
            )}
            {mode === "accept" && (
              <>
                <button type="button" className={primaryBtn} onClick={accept} disabled={busy || !current || buyerOverBudget}>
                  {busy ? "Sending…" : money?.requires_approval ? "Send for approval" : `Yes, accept ${liteMoney(card.fee)}`}
                </button>
                <button type="button" className={textBtn} onClick={() => setMode("answer")}>Go back</button>
              </>
            )}
            {mode === "counter" && (
              <>
                <button type="button" className={primaryBtn} onClick={sendCounter}
                  disabled={busy || !current || (card.side === "buyer" && !!money?.over_budget)}>
                  {busy ? "Sending…" : `Send counter at ${liteMoney(counter)}`}
                </button>
                <button type="button" className={textBtn} onClick={() => { setMode("answer"); setCounterFee(null); }}>Go back</button>
              </>
            )}
            {mode === "reject" && (
              <>
                <button type="button" className={`${dangerBtn} flex-1`} onClick={reject} disabled={busy}>
                  {busy ? "Sending…" : "Yes, say no"}
                </button>
                <button type="button" className={textBtn} onClick={() => setMode("answer")}>Go back</button>
              </>
            )}
          </div>
        )}
        {open && card.your_move && <p className="text-[0.9375rem] text-text-muted">You can undo for 10 seconds after sending.</p>}
        {mode === "answer" && (
          <div className="flex flex-wrap items-center gap-2">
            <button type="button" className={`${textBtn} self-start`} onClick={() => navigate("/lite/offers")}>Back to offers</button>
            {fromPush && <Link to={`/offers/${card.offer_id}`} className={`${textBtn} flex items-center no-underline`}>See full details</Link>}
          </div>
        )}
      </ActionCardShell>
    </div>
  );
}


/** "2 days left", "5 hours left"; urgent under 24 hours. */
function timeLeft(iso: string | null): { text: string; urgent: boolean } | null {
  if (!iso) return null;
  const ms = new Date(iso).getTime() - Date.now();
  if (ms <= 0) return { text: "time's up", urgent: true };
  const hours = ms / 3_600_000;
  if (hours < 1) return { text: `${Math.max(1, Math.round(ms / 60_000))} minutes left`, urgent: true };
  if (hours < 24) return { text: `${Math.floor(hours)} hour${Math.floor(hours) === 1 ? "" : "s"} left`, urgent: true };
  const days = Math.floor(hours / 24);
  return { text: `${days} day${days === 1 ? "" : "s"} left`, urgent: false };
}

/** "Waiting on you · 2 of 3" and Next, from the Dashboard's waiting list, so
 *  a director can work through everything from one notification. */
function WaitingHeader({ offerId }: { offerId: string }) {
  const { data } = useClubDashboard(true);
  const items = data?.waiting_on_you ?? [];
  const i = items.findIndex((it) => it.kind === "offer" && it.id === offerId);
  if (items.length === 0) return null;
  const next = items[(i + 1) % items.length];
  const nextHref = next && next.id !== offerId
    ? (next.kind === "offer" ? `/lite/offers/${next.id}?from=push` : next.link)
    : null;
  return (
    <div className="flex items-center justify-between gap-3">
      <Link to="/lite" className="text-[1.0625rem] font-semibold text-text-secondary no-underline">‹ Home</Link>
      <span className="text-[1rem] font-semibold text-text-secondary">
        Waiting on you{i >= 0 ? ` · ${i + 1} of ${items.length}` : ` · ${items.length}`}
      </span>
      {nextHref ? <Link to={nextHref} className="text-[1.0625rem] font-bold text-accent no-underline">Next ›</Link> : <span />}
    </div>
  );
}
