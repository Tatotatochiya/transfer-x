import { useEffect, useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import {
  ActionCardShell, Done, FactRow, FeeStepper, MoneyPanel, Notes,
  primaryBtn, secondaryBtn, textBtn, useDebounced,
} from "../../components/lite/ActionCard";
import Spinner from "../../components/ui/Spinner";
import { useOfferCheck } from "../../hooks/useAssistant";
import { useLiteOfferDraft } from "../../hooks/useLite";
import api from "../../lib/api";
import { liteMoney, liteWage } from "../../lib/liteMoney";
import { getApiError } from "../../lib/utils";

/**
 * A new bid as an action card (README "Screen 5"), from "Make an offer" in the
 * Buy results. Confirm calls POST /offers directly (L4 has no undo; L6 moves
 * this to held sends). The money panel is /ai/offer-check's `money` block,
 * and confirm waits until it describes the fee on screen.
 */
export default function LiteBidPage() {
  const [params] = useSearchParams();
  const playerId = params.get("player_id");
  // From Ask anything: a fee the server checked, and the offer is recorded as
  // the assistant's suggestion when confirmed.
  const fromAsk = params.get("from") === "ask";
  const proposedFee = Number(params.get("fee")) || null;
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { data: draft, isLoading, error } = useLiteOfferDraft(playerId);

  const [fee, setFee] = useState<number | null>(null);
  const [editing, setEditing] = useState(false);
  const [sending, setSending] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);
  const [done, setDone] = useState<null | { kind: "sent"; offerId: string } | { kind: "approval" }>(null);

  useEffect(() => {
    if (draft && fee == null) setFee(proposedFee ?? draft.fee ?? 1_000_000);
  }, [draft, fee, proposedFee]);

  const terms = useMemo(() => draft && fee != null ? {
    player_id: draft.player_id,
    to_club_id: draft.to_club_id,
    sale_id: draft.sale_id,
    fee_amount: fee,
    wage_weekly: draft.wage_weekly,
    contract_years: draft.contract_years,
  } : null, [draft, fee]);
  const settled = useDebounced(terms);
  const check = useOfferCheck(settled ? { terms: settled } : null);
  const money = check.data?.money;
  const current = settled === terms && !check.isFetching && !!money;

  // "Carry on where you left off" until the bid is sent.
  useEffect(() => {
    if (!draft || done) return;
    api.put("/lite/resume", { title: `Bid for ${draft.name}`, href: `/lite/bid?player_id=${draft.player_id}` })
      .then(() => queryClient.invalidateQueries({ queryKey: ["lite", "home"] }))
      .catch(() => undefined);
  }, [draft, done, queryClient]);

  if (isLoading || (draft && fee == null)) return <div className="flex justify-center py-16"><Spinner size="lg" /></div>;
  if (error || !draft || fee == null) {
    return (
      <div className="flex flex-col items-start gap-5">
        <h1 className="text-[1.75rem] font-extrabold text-text">You can't make this offer</h1>
        <p className="text-[1.25rem] text-text-secondary">{getApiError(error, "We couldn't find that player.")}</p>
        <button type="button" onClick={() => navigate(-1)} className={secondaryBtn}>Go back</button>
      </div>
    );
  }

  const club = draft.to_club_name ?? "his club";
  if (done?.kind === "sent") {
    return (
      <Done
        title={`Bid sent to ${club}`}
        body={`${liteMoney(fee)} for ${draft.name}. We'll tell you when they reply.`}
        links={[{ to: "/lite", label: "Back to home" }, { to: `/offers/${done.offerId}`, label: "See the offer" }]}
      />
    );
  }
  if (done?.kind === "approval") {
    return (
      <Done
        title="Sent for approval"
        body={`Your ${liteMoney(fee)} bid for ${draft.name} goes to ${club} once your owner or sporting director approves it.`}
        links={[{ to: "/lite", label: "Back to home" }]}
      />
    );
  }

  // Over budget is said by the money panel; this is every other reason.
  const blocked = draft.disabled_reason;
  const confirm = async () => {
    if (!terms) return;
    setSending(true);
    setSendError(null);
    try {
      const resp = await api.post("/offers", fromAsk ? { ...terms, ai_assisted: true } : terms);
      await api.delete("/lite/resume").catch(() => undefined);
      queryClient.invalidateQueries({ queryKey: ["lite"] });
      setDone(resp.status === 202 ? { kind: "approval" } : { kind: "sent", offerId: resp.data.id });
    } catch (err) {
      setSendError(getApiError(err, "The bid couldn't be sent."));
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <ActionCardShell
        pill="Ready to send · check before confirming"
        tone="ready"
        title={`Bid ${liteMoney(fee)} for ${draft.name}`}
        money={<MoneyPanel money={money} loading={check.isFetching} what="bid" />}
      >
        <div>
          <FactRow label="Player">{draft.name}{draft.age != null ? `, ${draft.age}` : ""}</FactRow>
          <FactRow label="Sent to">{club}</FactRow>
          <FactRow label="Fee">
            {liteMoney(fee)}
            {draft.asking_price != null && <span className="block text-base font-normal text-text-muted">They ask {liteMoney(draft.asking_price)}</span>}
          </FactRow>
          <FactRow label="Wages offered">{draft.wage_weekly != null ? liteWage(draft.wage_weekly) : "Agreed with him later"}</FactRow>
          <FactRow label="Contract">{draft.contract_years} years</FactRow>
        </div>
        {editing && <FeeStepper value={fee} onChange={setFee} label="Fee in millions of pounds" />}
        <Notes warnings={check.data?.warnings} />
        {blocked && (
          <p className="rounded-xl bg-surface-inset px-4 py-3 text-[1.0625rem] text-text-secondary">
            {blocked}
            {draft.existing_offer_id && (
              <> <Link to={`/lite/offers/${draft.existing_offer_id}`} className="font-semibold text-accent">See your offer</Link></>
            )}
          </p>
        )}
        {sendError && <p role="alert" className="rounded-xl bg-danger-bg px-4 py-3 text-[1.0625rem] text-danger-text">{sendError}</p>}
        <div className="mt-auto flex flex-col gap-3 sm:flex-row sm:flex-wrap">
          <button type="button" className={primaryBtn} disabled={!!blocked || !current || !!money?.over_budget || sending} onClick={confirm}>
            {sending ? "Sending…" : money?.requires_approval ? "Send for approval" : "Confirm and send bid"}
          </button>
          {!editing && (
            <button type="button" className={secondaryBtn} onClick={() => setEditing(true)} disabled={!!draft.disabled_reason}>
              Change amount
            </button>
          )}
          <button type="button" className={textBtn} onClick={() => navigate(-1)}>Cancel</button>
        </div>
        {money?.requires_approval && !blocked && (
          <p className="text-base text-text-secondary">
            Bids of this size need your owner's or sporting director's approval, so it waits for them before {club} sees it.
          </p>
        )}
      </ActionCardShell>
    </div>
  );
}
