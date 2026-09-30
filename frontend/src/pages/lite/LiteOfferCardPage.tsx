import { useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router-dom";

import {
  ActionCardShell, Done, FactRow, FeeStepper, MoneyPanel, Notes,
  dangerBtn, primaryBtn, secondaryBtn, textBtn, useDebounced,
} from "../../components/lite/ActionCard";
import Spinner from "../../components/ui/Spinner";
import { useOfferCheck } from "../../hooks/useAssistant";
import { CLUB_DASHBOARD_KEY } from "../../hooks/useClubDashboard";
import { useLiteOfferCard } from "../../hooks/useLite";
import api from "../../lib/api";
import { liteMoney, liteWage } from "../../lib/liteMoney";
import { getApiError } from "../../lib/utils";

type Mode = "answer" | "accept" | "counter" | "reject";
type Result = { kind: "accepted"; dealId: string } | { kind: "approval" } | { kind: "countered" } | { kind: "rejected" };

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

  const [mode, setMode] = useState<Mode>("answer");
  const [counterFee, setCounterFee] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);
  const [result, setResult] = useState<Result | null>(null);

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
  const loan = card.deal_type === "LOAN";
  const other = card.other_club;
  if (result) {
    const back = { to: "/lite/offers", label: "Back to offers" };
    if (result.kind === "accepted") {
      return <Done title="Accepted" body={`You agreed ${liteMoney(card.fee)} for ${player} with ${other}. Next come the medical and personal terms.`}
        links={[back, { to: `/deals/${result.dealId}`, label: "Open the deal" }]} />;
    }
    if (result.kind === "approval") {
      return <Done title="Sent for approval" body={`Accepting ${liteMoney(card.fee)} for ${player} waits for your owner or sporting director to approve it.`} links={[back]} />;
    }
    if (result.kind === "countered") {
      return <Done title={`Counter sent to ${other}`} body={`You asked for ${liteMoney(counter)} for ${player}. We'll tell you when they reply.`} links={[back]} />;
    }
    return <Done title="You said no" body={`${cap(other)} has been told you turned down the offer for ${player}.`} links={[back]} />;
  }

  const run = async (fn: () => Promise<Result>) => {
    setBusy(true);
    setSendError(null);
    try {
      setResult(await fn());
      queryClient.invalidateQueries({ queryKey: ["lite"] });
      queryClient.invalidateQueries({ queryKey: CLUB_DASHBOARD_KEY });
    } catch (err) {
      setSendError(getApiError(err, "That didn't go through."));
    } finally {
      setBusy(false);
    }
  };
  const accept = () => run(async () => {
    const r = await api.post(`/offers/${card.offer_id}/accept`, {});
    return r.status === 202 ? { kind: "approval" } : { kind: "accepted", dealId: r.data.id };
  });
  const sendCounter = () => run(async () => {
    await api.post(`/offers/${card.offer_id}/counter`, { fee_amount: counter });
    return { kind: "countered" };
  });
  const reject = () => run(async () => {
    await api.post(`/offers/${card.offer_id}/reject`, {});
    return { kind: "rejected" };
  });

  const buyerOverBudget = card.side === "buyer" && !!money?.over_budget;
  const title = card.side === "seller"
    ? `${cap(other)} ${loan ? "wants to loan" : "offers"} ${liteMoney(card.fee)} for ${player}`
    : card.your_move
      ? `${cap(other)} asks ${liteMoney(card.fee)} for ${player}`
      : `Your ${liteMoney(card.fee)} offer for ${player}`;
  const pill = card.side === "seller" ? "Offer for your player" : "Reply to your offer";

  return (
    <div className="flex flex-col gap-4">
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
                    Counter at {liteMoney(card.counter_suggestion)}
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
        {mode === "answer" && (
          <button type="button" className={`${textBtn} self-start`} onClick={() => navigate("/lite/offers")}>Back to offers</button>
        )}
      </ActionCardShell>
    </div>
  );
}
