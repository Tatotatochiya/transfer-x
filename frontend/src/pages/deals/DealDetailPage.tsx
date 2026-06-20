import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "../../lib/api";
import type { Club, Deal } from "../../types/api";
import { useAuthStore } from "../../store/auth";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import ClubLink from "../../components/ui/ClubLink";
import Metric from "../../components/ui/Metric";
import Panel from "../../components/ui/Panel";
import Spinner from "../../components/ui/Spinner";
import StageTracker from "../../components/deals/StageTracker";
import { dealStatusVariant, dealStageLabel } from "../../lib/badges";
import { formatCurrency, formatDate, formatWage, getApiError } from "../../lib/utils";
import { useToast } from "../../context/ToastContext";

// ── Note form ─────────────────────────────────────────────────────────────────

function NoteForm({ dealId }: { dealId: string }) {
  const queryClient = useQueryClient();
  const [body, setBody] = useState("");
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: (text: string) =>
      api.post(`/deals/${dealId}/notes`, { body: text }).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["deals", dealId] });
      setBody("");
      setError(null);
    },
    onError: (err: unknown) => {
      setError(getApiError(err, "Failed to add note."));
    },
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = body.trim();
    if (!trimmed) return;
    mutation.mutate(trimmed);
  }

  return (
    <form onSubmit={handleSubmit} className="flex gap-2 pt-2">
      <input
        type="text"
        value={body}
        onChange={(e) => setBody(e.target.value)}
        placeholder="Add a note…"
        className="flex-1 rounded-lg bg-slate-800 px-3 py-2 text-sm text-white placeholder-slate-500 ring-1 ring-white/10 focus:outline-none focus:ring-emerald-500 transition-colors"
      />
      <Button type="submit" variant="secondary" size="sm" loading={mutation.isPending}>
        Add
      </Button>
      {error && <p className="text-xs text-red-400 self-center">{error}</p>}
    </form>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function DealDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { addToast } = useToast();
  const { accessToken } = useAuthStore();
  const isAuthenticated = !!accessToken;
  const [showCollapsePanel, setShowCollapsePanel] = useState(false);
  const [collapseReason, setCollapseReason] = useState("");

  const { data: deal, isLoading, isError } = useQuery<Deal>({
    queryKey: ["deals", id],
    queryFn: () => api.get<Deal>(`/deals/${id}`).then((r) => r.data),
    enabled: !!id,
  });

  const { data: myClub } = useQuery<Club>({
    queryKey: ["clubs", "me"],
    queryFn: () => api.get<Club>("/clubs/me").then((r) => r.data),
    enabled: isAuthenticated,
    staleTime: 60_000,
  });

  const advanceMutation = useMutation({
    mutationFn: () =>
      api.post<Deal>(`/deals/${id}/advance`).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["deals", id] });
      addToast("Deal advanced to next stage.", "success");
    },
    onError: (err) => addToast(getApiError(err, "Failed to advance deal."), "error"),
  });

  const collapseMutation = useMutation({
    mutationFn: () =>
      api.post<Deal>(`/deals/${id}/collapse`).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["deals", id] });
      queryClient.invalidateQueries({ queryKey: ["deals"] });
      setShowCollapsePanel(false);
      setCollapseReason("");
      addToast("Deal collapsed.", "warning");
    },
    onError: (err) => addToast(getApiError(err, "Failed to collapse deal."), "error"),
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Spinner size="lg" />
      </div>
    );
  }

  if (isError || !deal) {
    return (
      <div className="rounded-xl bg-red-500/10 px-5 py-4 text-sm text-red-400 ring-1 ring-red-500/30">
        Deal not found.{" "}
        <button onClick={() => navigate(-1)} className="underline">
          Go back
        </button>
      </div>
    );
  }

  const myClubId   = myClub?.id;
  const isBuyer    = myClubId === deal.buyer_club_id;
  const isSeller   = myClubId === deal.seller_club_id;
  const isParty    = isBuyer || isSeller;
  const isActive   = deal.status === "IN_PROGRESS" || deal.status === "PENDING_COMPLETION";

  const atAgentNegotiation = deal.stage === "AGENT_NEGOTIATION";
  const atPersonalTerms    = deal.stage === "PERSONAL_TERMS";
  // At PAPERWORK stage, clubs cannot advance — only staff can
  const atPaperwork        = deal.stage === "PAPERWORK";
  const atConfirmed        = deal.stage === "CONFIRMED";
  const clubCanAdvance     = isParty && isActive && !atPaperwork && !atAgentNegotiation && !atPersonalTerms && !deal.is_auction_deal;
  const clubCanCollapse    = isParty && isActive;

  const advanceError =
    advanceMutation.isError ? getApiError(advanceMutation.error, "Failed.") : null;

  return (
    <div>
      <button
        onClick={() => navigate(-1)}
        className="mb-6 flex items-center gap-1.5 text-sm text-slate-400 hover:text-white transition-colors"
      >
        ← Back to deals
      </button>

      {/* Stage tracker */}
      <div className="mb-6 rounded-xl bg-slate-900 px-6 py-5 ring-1 ring-white/[0.08]">
        <div className="mb-4 flex items-center justify-between">
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">
            Deal Progress
          </p>
          <Badge variant={dealStatusVariant(deal.status)}>
            {deal.status.replace(/_/g, " ")}
          </Badge>
        </div>
        <StageTracker stage={deal.stage} status={deal.status} />
      </div>

      {/* PAPERWORK banner */}
      {atPaperwork && isParty && deal.status === "IN_PROGRESS" && (
        <div className="mb-6 rounded-xl bg-sky-500/10 px-5 py-4 text-sm text-sky-300 ring-1 ring-sky-500/20">
          <p className="font-semibold mb-1">TransferX is handling the paperwork</p>
          <p className="text-sky-400/80">
            Our team is processing the documentation. You'll be notified when it's ready for confirmation.
          </p>
        </div>
      )}

      {/* CONFIRMED / Ready to Execute banner */}
      {atConfirmed && isParty && deal.status === "IN_PROGRESS" && (
        <div className="mb-6 rounded-xl bg-emerald-500/10 px-5 py-4 text-sm text-emerald-300 ring-1 ring-emerald-500/20">
          <p className="font-semibold mb-1">Documents verified — ready to execute</p>
          <p className="text-emerald-400/80">
            TransferX has processed all documentation. Use the <strong>Execute Transfer</strong> button to complete the deal and register the player.
          </p>
        </div>
      )}

      {/* AGENT_NEGOTIATION banner */}
      {atAgentNegotiation && isParty && deal.status === "IN_PROGRESS" && (
        <div className="mb-6 rounded-xl bg-purple-500/10 px-5 py-4 text-sm text-purple-300 ring-1 ring-purple-500/20">
          <p className="font-semibold mb-1">Agent negotiation in progress</p>
          <p className="text-purple-400/80">
            The mandated agent is negotiating commission terms with the buying club and personal terms with the player. You will be notified once both parties agree.
          </p>
        </div>
      )}

      {/* PERSONAL_TERMS banner */}
      {atPersonalTerms && isParty && deal.status === "IN_PROGRESS" && (
        <div className="mb-6 rounded-xl bg-amber-500/10 px-5 py-4 text-sm text-amber-300 ring-1 ring-amber-500/20">
          <p className="font-semibold mb-1">Awaiting player consent on personal terms</p>
          <p className="text-amber-400/80">
            The agent has proposed personal contract terms. The deal will advance once the player confirms acceptance.
          </p>
        </div>
      )}

      {/* Auction deal banner */}
      {deal.is_auction_deal && isParty && deal.status === "IN_PROGRESS" && (
        <div className="mb-6 rounded-xl bg-amber-500/10 px-5 py-4 text-sm text-amber-300 ring-1 ring-amber-500/20">
          <p className="font-semibold mb-1">Auction deal</p>
          <p className="text-amber-400/80">
            This deal was created from an auction result. Stage advancement is handled by TransferX staff.
          </p>
        </div>
      )}

      {/* Completed banner */}
      {deal.status === "COMPLETED" && (
        <div className="mb-6 rounded-xl bg-emerald-500/10 px-5 py-4 text-sm text-emerald-300 ring-1 ring-emerald-500/20">
          <p className="font-semibold">Transfer completed</p>
          {deal.completed_at && (
            <p className="text-emerald-400/80 mt-1">
              Completed on {formatDate(deal.completed_at)}
            </p>
          )}
        </div>
      )}

      {/* Collapsed banner */}
      {deal.status === "COLLAPSED" && (
        <div className="mb-6 rounded-xl bg-red-500/10 px-5 py-4 text-sm text-red-300 ring-1 ring-red-500/20">
          <p className="font-semibold">Deal collapsed</p>
          <p className="text-red-400/80 mt-1">This transfer has fallen through.</p>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-3">
        {/* ── Left: info ── */}
        <div className="lg:col-span-1 space-y-4">
          {/* Player */}
          <Card>
            <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-400">
              Player
            </p>
            <button
              onClick={() =>
                deal.player_id && navigate(`/players/market/${deal.player_id}`)
              }
              className="text-lg font-semibold text-white hover:text-emerald-400 transition-colors text-left"
            >
              {deal.player?.name ?? "Unknown"}
            </button>
            {deal.player?.position && (
              <p className="text-xs text-slate-500 mt-0.5">{deal.player.position}</p>
            )}
          </Card>

          {/* Terms */}
          <Card>
            <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-400">
              Agreed Terms
            </p>
            <div className="space-y-2">
              <Metric label="Transfer fee" value={formatCurrency(deal.agreed_fee)} />
              {deal.agreed_wage_weekly != null && (
                <Metric label="Wage" value={formatWage(deal.agreed_wage_weekly)} />
              )}
              <Metric
                label="Buyer"
                valueNode={<ClubLink id={deal.buyer_club?.id} name={deal.buyer_club?.name} />}
              />
              <Metric
                label="Seller"
                valueNode={<ClubLink id={deal.seller_club?.id} name={deal.seller_club?.name} />}
              />
              <Metric label="Type" value={deal.deal_type === "LOAN" ? "Loan" : "Permanent"} />
              <Metric label="Stage" value={dealStageLabel(deal.stage)} />
              <Metric label="Created" value={formatDate(deal.created_at)} />
              {deal.is_auction_deal && (
                <p className="mt-1 text-xs text-amber-400/70 border-t border-white/[0.06] pt-2">
                  Auction deal
                </p>
              )}
            </div>
          </Card>

          {/* Actions */}
          {isParty && isActive && (
            <Card>
              <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-400">
                Actions
              </p>
              <div className="space-y-2">
                {clubCanAdvance && (
                  <Button
                    variant="primary"
                    size="sm"
                    className="w-full"
                    loading={advanceMutation.isPending}
                    onClick={() => advanceMutation.mutate()}
                  >
                    {atConfirmed ? "Execute Transfer" : `Advance to ${dealStageLabel(nextStage(deal.stage))}`}
                  </Button>
                )}
                {advanceError && (
                  <p className="text-xs text-red-400">{advanceError}</p>
                )}
                {clubCanCollapse && !showCollapsePanel && (
                  <button
                    onClick={() => setShowCollapsePanel(true)}
                    className="w-full rounded-lg px-3 py-2 text-sm text-slate-500 hover:text-red-400 hover:bg-red-500/[0.06] ring-1 ring-white/[0.06] hover:ring-red-500/20 transition-colors"
                  >
                    Collapse deal…
                  </button>
                )}
              </div>

              {/* Inline collapse confirmation panel */}
              {clubCanCollapse && showCollapsePanel && (
                <div className="mt-3 rounded-lg bg-red-500/[0.06] ring-1 ring-red-500/20 px-4 py-4 space-y-3">
                  <div className="flex items-start gap-2">
                    <svg className="h-4 w-4 text-red-400 shrink-0 mt-0.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v4m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
                    </svg>
                    <div>
                      <p className="text-sm font-semibold text-red-400">Collapse this deal?</p>
                      <p className="text-xs text-slate-400 mt-0.5">This cannot be undone. The transfer will fall through and reserved budget will be released.</p>
                    </div>
                  </div>
                  <div>
                    <label className="mb-1.5 block text-xs text-slate-400">Reason (optional)</label>
                    <textarea
                      rows={2}
                      value={collapseReason}
                      onChange={(e) => setCollapseReason(e.target.value)}
                      placeholder="e.g. Clubs could not agree on fee"
                      className="w-full rounded-lg bg-slate-800 px-3 py-2 text-sm text-white placeholder-slate-600 ring-1 ring-white/10 focus:outline-none focus:ring-red-500/50 resize-none transition-colors"
                    />
                  </div>
                  <div className="flex gap-2">
                    <Button
                      variant="danger"
                      size="sm"
                      loading={collapseMutation.isPending}
                      onClick={() => collapseMutation.mutate()}
                    >
                      Confirm collapse
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => { setShowCollapsePanel(false); setCollapseReason(""); }}
                    >
                      Cancel
                    </Button>
                  </div>
                </div>
              )}
            </Card>
          )}
        </div>

        {/* ── Right: builder panels + notes + timeline ── */}
        <div className="lg:col-span-2 space-y-4">

          {/* Loan details (TRA-56) */}
          {deal.deal_type === "LOAN" && (
            <Panel title="Loan Details">
              <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
                {deal.loan_start && (
                  <><dt className="text-slate-500">Loan start</dt><dd className="text-white">{formatDate(deal.loan_start)}</dd></>
                )}
                {deal.loan_end && (
                  <><dt className="text-slate-500">Loan end</dt><dd className="text-white">{formatDate(deal.loan_end)}</dd></>
                )}
                {deal.loan_fee != null && (
                  <><dt className="text-slate-500">Loan fee</dt><dd className="text-white">{formatCurrency(deal.loan_fee)}</dd></>
                )}
                {deal.option_to_buy != null && (
                  <><dt className="text-slate-500">Option to buy</dt><dd className="text-white">{formatCurrency(deal.option_to_buy)}</dd></>
                )}
                {deal.obligation_to_buy && (
                  <><dt className="text-slate-500">Obligation to buy</dt><dd className="text-amber-300">Yes{deal.obligation_conditions ? ` — ${deal.obligation_conditions}` : ""}</dd></>
                )}
                {deal.sell_on_pct != null && (
                  <><dt className="text-slate-500">Sell-on %</dt><dd className="text-white">{(deal.sell_on_pct * 100).toFixed(1)}%</dd></>
                )}
              </dl>
            </Panel>
          )}

          {/* Add-on clauses (TRA-57) */}
          {deal.clauses.length > 0 && (
            <Panel title={`Add-on Clauses (${deal.clauses.length})`}>
              <div className="space-y-2">
                {deal.clauses.map((c) => (
                  <div key={c.id} className="rounded-lg bg-slate-800/60 px-3 py-2.5 flex items-center justify-between gap-3">
                    <div className="min-w-0">
                      <p className="text-xs font-semibold text-slate-300 capitalize">
                        {c.clause_type.toLowerCase()} clause
                      </p>
                      <p className="text-xs text-slate-500 truncate">{c.trigger_description}</p>
                    </div>
                    <div className="text-right shrink-0">
                      <p className="text-sm font-semibold text-white">{formatCurrency(c.amount)}</p>
                      {c.cap != null && (
                        <p className="text-[10px] text-slate-500">cap {formatCurrency(c.cap)}</p>
                      )}
                    </div>
                    <span className={`text-[10px] px-1.5 py-0.5 rounded font-semibold ${
                      c.status === "PAID"      ? "bg-emerald-500/20 text-emerald-400" :
                      c.status === "TRIGGERED" ? "bg-amber-500/20 text-amber-400"    :
                                                  "bg-slate-700 text-slate-400"
                    }`}>{c.status}</span>
                  </div>
                ))}
              </div>
            </Panel>
          )}

          {/* Instalment schedule (TRA-58) */}
          {deal.instalments.length > 0 && (
            <Panel title={`Payment Schedule (${deal.instalments.length} instalments)`}>
              <div className="space-y-1.5">
                {deal.instalments.map((inst) => (
                  <div key={inst.id} className="flex items-center justify-between text-sm">
                    <span className="text-slate-400">{formatDate(inst.due_date)}</span>
                    <span className="font-semibold text-white">{formatCurrency(inst.amount)}</span>
                    <span className={inst.paid ? "text-emerald-400 text-xs" : "text-slate-500 text-xs"}>
                      {inst.paid ? `Paid ${inst.paid_at ? formatDate(inst.paid_at) : ""}` : "Pending"}
                    </span>
                  </div>
                ))}
              </div>
            </Panel>
          )}

          {/* Commission block (TRA-59) — shown when set */}
          {deal.agent_commission_pct != null || deal.agent_commission_amount != null ? (
            <Panel title="Agent Commission">
              <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
                {deal.agent_commission_pct != null && (
                  <><dt className="text-slate-500">Commission %</dt><dd className="text-white">{(deal.agent_commission_pct * 100).toFixed(2)}%</dd></>
                )}
                {deal.agent_commission_amount != null && (
                  <><dt className="text-slate-500">Commission amount</dt><dd className="text-white">{formatCurrency(deal.agent_commission_amount)}</dd></>
                )}
                {deal.commission_payer && (
                  <><dt className="text-slate-500">Paid by</dt><dd className="text-white capitalize">{deal.commission_payer.toLowerCase()}</dd></>
                )}
              </dl>
            </Panel>
          ) : null}

          {/* Personal terms consent status (TRA-60) */}
          {deal.personal_terms && (
            <Panel title="Personal Terms">
              <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
                {deal.personal_terms.wage_weekly != null && (
                  <><dt className="text-slate-500">Proposed wage</dt><dd className="text-white">{formatWage(deal.personal_terms.wage_weekly)}</dd></>
                )}
                {deal.personal_terms.signing_bonus != null && (
                  <><dt className="text-slate-500">Signing bonus</dt><dd className="text-white">{formatCurrency(deal.personal_terms.signing_bonus)}</dd></>
                )}
                {deal.personal_terms.length_years != null && (
                  <><dt className="text-slate-500">Contract length</dt><dd className="text-white">{deal.personal_terms.length_years} yr{deal.personal_terms.length_years !== 1 ? "s" : ""}</dd></>
                )}
                <dt className="text-slate-500">Player consent</dt>
                <dd className={
                  deal.personal_terms.player_consent === "AGREED"   ? "text-emerald-400 font-semibold" :
                  deal.personal_terms.player_consent === "DECLINED" ? "text-red-400 font-semibold"     :
                                                                        "text-amber-400"
                }>{deal.personal_terms.player_consent}</dd>
              </dl>
            </Panel>
          )}

          <Panel title="Deal Notes">
            {deal.deal_notes.length === 0 ? (
              <p className="text-sm text-slate-500 pb-2">No notes yet.</p>
            ) : (
              <div className="space-y-3 mb-4">
                {deal.deal_notes.map((note) => (
                  <div
                    key={note.id}
                    className="rounded-lg bg-slate-800/60 px-4 py-3"
                  >
                    <div className="flex items-center justify-between mb-1">
                      <p className="text-xs font-semibold text-slate-400">
                        {note.author_club?.name ?? "System"}
                      </p>
                      <p className="text-[10px] text-slate-500">
                        {formatDate(note.created_at)}
                      </p>
                    </div>
                    <p className="text-sm text-slate-300">{note.body}</p>
                  </div>
                ))}
              </div>
            )}
            {isParty && isActive && <NoteForm dealId={deal.id} />}
          </Panel>

          <Panel title="Activity Timeline">
            <DealTimeline deal={deal} />
          </Panel>
        </div>
      </div>
    </div>
  );
}

// ── Helpers ───────────────────────────────────────────────────────────────────

import type { DealStage } from "../../types/enums";

const STAGE_SEQ: DealStage[] = [
  "AGREEMENT", "AGENT_NEGOTIATION", "PERSONAL_TERMS", "PAPERWORK", "CONFIRMED", "COMPLETED",
];

function nextStage(stage: DealStage): DealStage {
  const idx = STAGE_SEQ.indexOf(stage);
  return idx >= 0 && idx < STAGE_SEQ.length - 1 ? STAGE_SEQ[idx + 1] : stage;
}

// ── Deal timeline ─────────────────────────────────────────────────────────────

interface TimelineEvent {
  id: string;
  ts: string;
  label: string;
  sublabel?: string;
  dot: "emerald" | "sky" | "amber" | "red" | "slate";
}

function DealTimeline({ deal }: { deal: Deal }) {
  const events: TimelineEvent[] = [];

  // Deal created
  events.push({
    id: "created",
    ts: deal.created_at,
    label: "Deal created",
    sublabel: `Agreed fee: ${formatCurrency(deal.agreed_fee)}`,
    dot: "emerald",
  });

  // Notes in chronological order
  const sortedNotes = [...deal.deal_notes].sort(
    (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
  );
  for (const note of sortedNotes) {
    events.push({
      id: `note-${note.id}`,
      ts: note.created_at,
      label: note.author_club?.name ? `Note by ${note.author_club.name}` : "System note",
      sublabel: note.body,
      dot: "sky",
    });
  }

  // Terminal states
  if (deal.status === "COMPLETED" && deal.completed_at) {
    events.push({
      id: "completed",
      ts: deal.completed_at,
      label: "Transfer completed",
      dot: "emerald",
    });
  } else if (deal.status === "COLLAPSED") {
    events.push({
      id: "collapsed",
      ts: deal.updated_at,
      label: "Deal collapsed",
      dot: "red",
    });
  }

  events.sort((a, b) => new Date(a.ts).getTime() - new Date(b.ts).getTime());

  const dotClass: Record<TimelineEvent["dot"], string> = {
    emerald: "bg-emerald-500",
    sky:     "bg-sky-500",
    amber:   "bg-amber-500",
    red:     "bg-red-500",
    slate:   "bg-slate-600",
  };

  return (
    <div className="relative pl-4">
      {/* Vertical line */}
      <div className="absolute left-[7px] top-2 bottom-2 w-px bg-white/[0.06]" />

      <div className="space-y-5">
        {events.map((ev) => (
          <div key={ev.id} className="relative flex gap-3">
            <div className={`mt-1 h-3 w-3 shrink-0 rounded-full ring-2 ring-slate-900 ${dotClass[ev.dot]}`} />
            <div className="min-w-0">
              <div className="flex items-baseline gap-2">
                <span className="text-sm font-medium text-white">{ev.label}</span>
                <span className="text-[10px] text-slate-500 shrink-0">
                  {new Date(ev.ts).toLocaleString("en-GB", {
                    day: "numeric", month: "short", year: "numeric",
                    hour: "2-digit", minute: "2-digit",
                  })}
                </span>
              </div>
              {ev.sublabel && (
                <p className="mt-0.5 text-xs text-slate-400 break-words">{ev.sublabel}</p>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
