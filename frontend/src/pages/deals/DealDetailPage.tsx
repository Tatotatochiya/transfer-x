import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "../../lib/api";
import type { AgentNegotiation, Club, Deal } from "../../types/api";
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

// ── Agreement status chip ─────────────────────────────────────────────────────

function AgreementChip({ label, status }: { label: string; status: string }) {
  const color =
    status === "AGREED"   ? "bg-emerald-500/20 text-emerald-400 ring-emerald-500/30" :
    status === "DECLINED" ? "bg-red-500/20 text-red-400 ring-red-500/30"             :
                            "bg-slate-700 text-slate-400 ring-white/10";
  return (
    <span className={`flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ${color}`}>
      {label}: {status}
    </span>
  );
}

// ── Agent negotiation workspace (TRA-128) ─────────────────────────────────────

interface AgentNegWorkspaceProps {
  dealId: string;
  negotiation: import("../../types/api").AgentNegotiation | null;
  agentCanAdvance: boolean;
  onAdvance: () => void;
  advancePending: boolean;
}

function AgentNegotiationWorkspace({
  dealId,
  negotiation,
  agentCanAdvance,
  onAdvance,
  advancePending,
}: AgentNegWorkspaceProps) {
  const queryClient = useQueryClient();
  const { addToast } = useToast();

  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<{
    commission_pct: string; commission_amount: string; commission_payer: string;
    additional_conditions: string; proposed_wage_weekly: string;
    proposed_signing_bonus: string; proposed_length_years: string;
  }>({
    commission_pct:         negotiation?.commission_pct         != null ? String(negotiation.commission_pct)         : "",
    commission_amount:      negotiation?.commission_amount      != null ? String(negotiation.commission_amount)      : "",
    commission_payer:       negotiation?.commission_payer       ?? "BUYER",
    additional_conditions:  negotiation?.additional_conditions  ?? "",
    proposed_wage_weekly:   negotiation?.proposed_wage_weekly   != null ? String(negotiation.proposed_wage_weekly)   : "",
    proposed_signing_bonus: negotiation?.proposed_signing_bonus != null ? String(negotiation.proposed_signing_bonus) : "",
    proposed_length_years:  negotiation?.proposed_length_years  != null ? String(negotiation.proposed_length_years)  : "",
  });

  const saveMutation = useMutation({
    mutationFn: (data: Record<string, unknown>) =>
      api.patch(`/deals/${dealId}/agent-negotiation/terms`, data).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["deals", dealId, "agent-negotiation"] });
      setEditing(false);
      addToast("Terms saved.", "success");
    },
    onError: (err: unknown) => addToast(getApiError(err, "Failed to save terms."), "error"),
  });

  function handleSave() {
    const payload: Record<string, unknown> = {};
    if (draft.commission_pct !== "")         payload.commission_pct         = Number(draft.commission_pct);
    if (draft.commission_amount !== "")      payload.commission_amount      = Number(draft.commission_amount);
    if (draft.commission_payer)              payload.commission_payer       = draft.commission_payer;
    if (draft.additional_conditions !== "")  payload.additional_conditions  = draft.additional_conditions;
    if (draft.proposed_wage_weekly !== "")   payload.proposed_wage_weekly   = Number(draft.proposed_wage_weekly);
    if (draft.proposed_signing_bonus !== "") payload.proposed_signing_bonus = Number(draft.proposed_signing_bonus);
    if (draft.proposed_length_years !== "")  payload.proposed_length_years  = Number(draft.proposed_length_years);
    saveMutation.mutate(payload);
  }

  const clubAgreed   = negotiation?.club_agreement   === "AGREED";
  const playerAgreed = negotiation?.player_agreement === "AGREED";

  return (
    <div className="mb-6">
      <div className="mb-3 flex items-center justify-between">
        <p className="text-xs font-semibold uppercase tracking-wider text-purple-400">
          Negotiation Workspace
        </p>
        <div className="flex items-center gap-2">
          <AgreementChip label="Club"   status={negotiation?.club_agreement   ?? "PENDING"} />
          <AgreementChip label="Player" status={negotiation?.player_agreement ?? "PENDING"} />
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        {/* Club-side panel */}
        <div className="rounded-xl bg-purple-500/[0.05] px-5 py-4 ring-1 ring-purple-500/20">
          <p className="mb-3 text-xs font-bold uppercase tracking-wider text-purple-400">
            Club side — Commission
          </p>
          {editing ? (
            <div className="space-y-2">
              <label className="block text-xs text-slate-400">Commission % <span className="text-slate-600">(decimal, e.g. 0.05 = 5%)</span></label>
              <input
                type="number" step="0.001"
                value={draft.commission_pct}
                onChange={(e) => setDraft((d) => ({ ...d, commission_pct: e.target.value }))}
                className="w-full rounded-lg bg-slate-800 px-3 py-1.5 text-sm text-white ring-1 ring-white/10 focus:outline-none focus:ring-purple-500"
              />
              <label className="block text-xs text-slate-400 pt-1">Commission amount (€)</label>
              <input
                type="number"
                value={draft.commission_amount}
                onChange={(e) => setDraft((d) => ({ ...d, commission_amount: e.target.value }))}
                className="w-full rounded-lg bg-slate-800 px-3 py-1.5 text-sm text-white ring-1 ring-white/10 focus:outline-none focus:ring-purple-500"
              />
              <label className="block text-xs text-slate-400 pt-1">Paid by</label>
              <select
                value={draft.commission_payer}
                onChange={(e) => setDraft((d) => ({ ...d, commission_payer: e.target.value }))}
                className="w-full rounded-lg bg-slate-800 px-3 py-1.5 text-sm text-white ring-1 ring-white/10 focus:outline-none focus:ring-purple-500"
              >
                <option value="BUYER">Buying club</option>
                <option value="SELLER">Selling club</option>
                <option value="PLAYER">Player</option>
              </select>
              <label className="block text-xs text-slate-400 pt-1">Additional conditions</label>
              <textarea
                rows={2}
                value={draft.additional_conditions}
                onChange={(e) => setDraft((d) => ({ ...d, additional_conditions: e.target.value }))}
                className="w-full resize-none rounded-lg bg-slate-800 px-3 py-1.5 text-sm text-white ring-1 ring-white/10 focus:outline-none focus:ring-purple-500"
              />
            </div>
          ) : (
            <dl className="space-y-1.5 text-sm">
              {negotiation?.commission_pct != null && (
                <><dt className="text-slate-500">Commission</dt><dd className="text-white">{(negotiation.commission_pct * 100).toFixed(2)}%</dd></>
              )}
              {negotiation?.commission_amount != null && (
                <><dt className="text-slate-500">Amount</dt><dd className="text-white">{formatCurrency(negotiation.commission_amount)}</dd></>
              )}
              {negotiation?.commission_payer && (
                <><dt className="text-slate-500">Paid by</dt><dd className="text-white capitalize">{negotiation.commission_payer.toLowerCase()}</dd></>
              )}
              {negotiation?.additional_conditions && (
                <><dt className="text-slate-500">Conditions</dt><dd className="text-white text-xs">{negotiation.additional_conditions}</dd></>
              )}
              {!negotiation?.commission_pct && !negotiation?.commission_amount && (
                <p className="text-xs text-slate-600 italic">No commission terms set yet.</p>
              )}
            </dl>
          )}
          <div className="mt-3">
            {clubAgreed ? (
              <span className="text-xs font-semibold text-emerald-400">✓ Club has agreed</span>
            ) : (
              <span className="text-xs text-slate-500">Awaiting club agreement</span>
            )}
          </div>
        </div>

        {/* Player-side panel */}
        <div className="rounded-xl bg-amber-500/[0.05] px-5 py-4 ring-1 ring-amber-500/20">
          <p className="mb-3 text-xs font-bold uppercase tracking-wider text-amber-400">
            Player side — Personal Terms
          </p>
          {editing ? (
            <div className="space-y-2">
              <label className="block text-xs text-slate-400">Weekly wage (€)</label>
              <input
                type="number"
                value={draft.proposed_wage_weekly}
                onChange={(e) => setDraft((d) => ({ ...d, proposed_wage_weekly: e.target.value }))}
                className="w-full rounded-lg bg-slate-800 px-3 py-1.5 text-sm text-white ring-1 ring-white/10 focus:outline-none focus:ring-amber-500"
              />
              <label className="block text-xs text-slate-400 pt-1">Signing bonus (€)</label>
              <input
                type="number"
                value={draft.proposed_signing_bonus}
                onChange={(e) => setDraft((d) => ({ ...d, proposed_signing_bonus: e.target.value }))}
                className="w-full rounded-lg bg-slate-800 px-3 py-1.5 text-sm text-white ring-1 ring-white/10 focus:outline-none focus:ring-amber-500"
              />
              <label className="block text-xs text-slate-400 pt-1">Contract length (years)</label>
              <input
                type="number" min={1} max={10}
                value={draft.proposed_length_years}
                onChange={(e) => setDraft((d) => ({ ...d, proposed_length_years: e.target.value }))}
                className="w-full rounded-lg bg-slate-800 px-3 py-1.5 text-sm text-white ring-1 ring-white/10 focus:outline-none focus:ring-amber-500"
              />
            </div>
          ) : (
            <dl className="space-y-1.5 text-sm">
              {negotiation?.proposed_wage_weekly != null && (
                <><dt className="text-slate-500">Weekly wage</dt><dd className="text-white">{formatWage(negotiation.proposed_wage_weekly)}</dd></>
              )}
              {negotiation?.proposed_signing_bonus != null && (
                <><dt className="text-slate-500">Signing bonus</dt><dd className="text-white">{formatCurrency(negotiation.proposed_signing_bonus)}</dd></>
              )}
              {negotiation?.proposed_length_years != null && (
                <><dt className="text-slate-500">Contract length</dt><dd className="text-white">{negotiation.proposed_length_years} yr{negotiation.proposed_length_years !== 1 ? "s" : ""}</dd></>
              )}
              {!negotiation?.proposed_wage_weekly && !negotiation?.proposed_signing_bonus && !negotiation?.proposed_length_years && (
                <p className="text-xs text-slate-600 italic">No personal terms proposed yet.</p>
              )}
            </dl>
          )}
          <div className="mt-3">
            {playerAgreed ? (
              <span className="text-xs font-semibold text-emerald-400">✓ Player has agreed</span>
            ) : (
              <span className="text-xs text-slate-500">Awaiting player agreement</span>
            )}
          </div>
        </div>
      </div>

      {/* Workspace footer: edit controls + advance */}
      <div className="mt-4 flex items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          {editing ? (
            <>
              <Button
                variant="primary"
                size="sm"
                loading={saveMutation.isPending}
                onClick={handleSave}
              >
                Save terms
              </Button>
              <Button variant="ghost" size="sm" onClick={() => setEditing(false)}>
                Cancel
              </Button>
            </>
          ) : (
            <Button variant="secondary" size="sm" onClick={() => {
              setDraft({
                commission_pct:         negotiation?.commission_pct        != null ? String(negotiation.commission_pct)        : "",
                commission_amount:      negotiation?.commission_amount     != null ? String(negotiation.commission_amount)     : "",
                commission_payer:       negotiation?.commission_payer      ?? "BUYER",
                additional_conditions:  negotiation?.additional_conditions ?? "",
                proposed_wage_weekly:   negotiation?.proposed_wage_weekly  != null ? String(negotiation.proposed_wage_weekly)  : "",
                proposed_signing_bonus: negotiation?.proposed_signing_bonus != null ? String(negotiation.proposed_signing_bonus) : "",
                proposed_length_years:  negotiation?.proposed_length_years != null ? String(negotiation.proposed_length_years) : "",
              });
              setEditing(true);
            }}>
              Edit terms
            </Button>
          )}
        </div>

        <div className="flex items-center gap-3">
          {!agentCanAdvance && (
            <p className="text-xs text-slate-500">
              {!clubAgreed && !playerAgreed ? "Both sides must agree before advancing." :
               !clubAgreed  ? "Awaiting club agreement." :
                              "Awaiting player agreement."}
            </p>
          )}
          <Button
            variant="primary"
            size="sm"
            disabled={!agentCanAdvance}
            loading={advancePending}
            onClick={onAdvance}
          >
            Advance to Personal Terms →
          </Button>
        </div>
      </div>
    </div>
  );
}

// ── Club: commission proposal view (TRA-129) ──────────────────────────────────

function CommissionProposalView({
  dealId,
  negotiation,
}: {
  dealId: string;
  negotiation: import("../../types/api").AgentNegotiation | null;
}) {
  const queryClient = useQueryClient();
  const { addToast } = useToast();

  const respondMutation = useMutation({
    mutationFn: (agreement: string) =>
      api.post(`/deals/${dealId}/agent-negotiation/club-respond`, { agreement }).then((r) => r.data),
    onSuccess: (_, agreement) => {
      queryClient.invalidateQueries({ queryKey: ["deals", dealId, "agent-negotiation"] });
      queryClient.invalidateQueries({ queryKey: ["deals", dealId] });
      addToast(agreement === "AGREED" ? "Proposal accepted." : "Proposal declined.", agreement === "AGREED" ? "success" : "warning");
    },
    onError: (err: unknown) => addToast(getApiError(err, "Failed to respond."), "error"),
  });

  if (!negotiation) return null;

  const isPending = negotiation.club_agreement === "PENDING";

  return (
    <div className="mb-6 rounded-xl bg-purple-500/[0.07] px-5 py-4 ring-1 ring-purple-500/20">
      <p className="mb-3 text-xs font-bold uppercase tracking-wider text-purple-400">
        Agent Commission Proposal
      </p>
      <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
        {negotiation.commission_pct != null && (
          <><dt className="text-slate-400">Commission</dt><dd className="font-semibold text-white">{(negotiation.commission_pct * 100).toFixed(2)}%</dd></>
        )}
        {negotiation.commission_amount != null && (
          <><dt className="text-slate-400">Amount</dt><dd className="font-semibold text-white">{formatCurrency(negotiation.commission_amount)}</dd></>
        )}
        {negotiation.commission_payer && (
          <><dt className="text-slate-400">Paid by</dt><dd className="text-white capitalize">{negotiation.commission_payer.toLowerCase()}</dd></>
        )}
        {negotiation.additional_conditions && (
          <><dt className="col-span-2 text-slate-400">Conditions</dt><dd className="col-span-2 text-sm text-white">{negotiation.additional_conditions}</dd></>
        )}
      </dl>

      {isPending ? (
        <div className="mt-4 flex gap-2">
          <Button
            variant="primary"
            size="sm"
            loading={respondMutation.isPending}
            onClick={() => respondMutation.mutate("AGREED")}
          >
            Accept proposal
          </Button>
          <Button
            variant="danger"
            size="sm"
            loading={respondMutation.isPending}
            onClick={() => respondMutation.mutate("DECLINED")}
          >
            Decline
          </Button>
        </div>
      ) : (
        <p className={`mt-4 text-sm font-semibold ${negotiation.club_agreement === "AGREED" ? "text-emerald-400" : "text-red-400"}`}>
          {negotiation.club_agreement === "AGREED" ? "✓ You accepted this proposal" : "✗ You declined this proposal"}
        </p>
      )}
    </div>
  );
}

// ── Player: proposed terms view (TRA-129) ─────────────────────────────────────

function PlayerTermsProposalView({
  dealId,
  negotiation,
}: {
  dealId: string;
  negotiation: import("../../types/api").AgentNegotiation | null;
}) {
  const queryClient = useQueryClient();
  const { addToast } = useToast();

  const respondMutation = useMutation({
    mutationFn: (agreement: string) =>
      api.post(`/deals/${dealId}/agent-negotiation/player-respond`, { agreement }).then((r) => r.data),
    onSuccess: (_, agreement) => {
      queryClient.invalidateQueries({ queryKey: ["deals", dealId, "agent-negotiation"] });
      queryClient.invalidateQueries({ queryKey: ["deals", dealId] });
      addToast(agreement === "AGREED" ? "Terms accepted." : "Terms declined.", agreement === "AGREED" ? "success" : "warning");
    },
    onError: (err: unknown) => addToast(getApiError(err, "Failed to respond."), "error"),
  });

  if (!negotiation) return null;

  const isPending = negotiation.player_agreement === "PENDING";

  return (
    <div className="mb-6 rounded-xl bg-amber-500/[0.07] px-5 py-4 ring-1 ring-amber-500/20">
      <p className="mb-3 text-xs font-bold uppercase tracking-wider text-amber-400">
        Proposed Contract Terms
      </p>
      <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
        {negotiation.proposed_wage_weekly != null && (
          <><dt className="text-slate-400">Weekly wage</dt><dd className="font-semibold text-white">{formatWage(negotiation.proposed_wage_weekly)}</dd></>
        )}
        {negotiation.proposed_signing_bonus != null && (
          <><dt className="text-slate-400">Signing bonus</dt><dd className="font-semibold text-white">{formatCurrency(negotiation.proposed_signing_bonus)}</dd></>
        )}
        {negotiation.proposed_length_years != null && (
          <><dt className="text-slate-400">Contract length</dt><dd className="text-white">{negotiation.proposed_length_years} yr{negotiation.proposed_length_years !== 1 ? "s" : ""}</dd></>
        )}
      </dl>

      {isPending ? (
        <div className="mt-4 flex gap-2">
          <Button
            variant="primary"
            size="sm"
            loading={respondMutation.isPending}
            onClick={() => respondMutation.mutate("AGREED")}
          >
            Accept terms
          </Button>
          <Button
            variant="danger"
            size="sm"
            loading={respondMutation.isPending}
            onClick={() => respondMutation.mutate("DECLINED")}
          >
            Decline
          </Button>
        </div>
      ) : (
        <p className={`mt-4 text-sm font-semibold ${negotiation.player_agreement === "AGREED" ? "text-emerald-400" : "text-red-400"}`}>
          {negotiation.player_agreement === "AGREED" ? "✓ You accepted these terms" : "✗ You declined these terms"}
        </p>
      )}
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function DealDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { addToast } = useToast();
  const { accessToken, user } = useAuthStore();
  const isAuthenticated = !!accessToken;
  const isAgent  = user?.user_type === "AGENT";
  const isPlayer = user?.user_type === "PLAYER";
  const [showCollapsePanel, setShowCollapsePanel] = useState(false);
  const [collapseReason, setCollapseReason] = useState("");

  // Deal builder state (TRA-59)
  const [editingDealStructure, setEditingDealStructure] = useState(false);
  const [dealDraft, setDealDraft] = useState({
    deal_type: "PERMANENT",
    loan_start: "", loan_end: "", loan_fee: "",
    option_to_buy: "", sell_on_pct: "",
  });
  const [addingClause, setAddingClause] = useState(false);
  const [clauseDraft, setClauseDraft] = useState({
    clause_type: "APPEARANCES", trigger_description: "", amount: "", cap: "",
  });
  const [editingInstalments, setEditingInstalments] = useState(false);
  const [instalmentRows, setInstalmentRows] = useState<Array<{due_date: string; amount: string}>>([]);

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

  // Deal builder mutations (TRA-59)
  const updateDealMutation = useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api.patch<Deal>(`/deals/${id}`, body).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["deals", id] });
      setEditingDealStructure(false);
      addToast("Deal updated.", "success");
    },
    onError: (err: unknown) => addToast(getApiError(err, "Failed to update deal."), "error"),
  });

  const addClauseMutation = useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api.post(`/deals/${id}/clauses`, body).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["deals", id] });
      setAddingClause(false);
      setClauseDraft({ clause_type: "APPEARANCES", trigger_description: "", amount: "", cap: "" });
      addToast("Clause added.", "success");
    },
    onError: (err: unknown) => addToast(getApiError(err, "Failed to add clause."), "error"),
  });

  const setInstalmentsMutation = useMutation({
    mutationFn: (instalments: Array<{due_date: string; amount: number}>) =>
      api.put(`/deals/${id}/instalments`, { instalments }).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["deals", id] });
      setEditingInstalments(false);
      addToast("Payment schedule saved.", "success");
    },
    onError: (err: unknown) => addToast(getApiError(err, "Failed to save schedule."), "error"),
  });

  // Load AgentNegotiation when deal is in that stage (TRA-128/129)
  const { data: negotiation } = useQuery<AgentNegotiation>({
    queryKey: ["deals", id, "agent-negotiation"],
    queryFn: () =>
      api.get<AgentNegotiation>(`/deals/${id}/agent-negotiation`).then((r) => r.data),
    enabled: !!id && !!deal && deal.stage === "AGENT_NEGOTIATION",
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

  const atAgreement        = deal.stage === "AGREEMENT";
  const atAgentNegotiation = deal.stage === "AGENT_NEGOTIATION";
  const atPersonalTerms    = deal.stage === "PERSONAL_TERMS";
  // At PAPERWORK stage, clubs cannot advance — only staff can
  const atPaperwork        = deal.stage === "PAPERWORK";
  const atConfirmed        = deal.stage === "CONFIRMED";
  const clubCanAdvance     = isParty && !isAgent && isActive && !atPaperwork && !atAgentNegotiation && !atPersonalTerms && !deal.is_auction_deal;
  // Agent can advance when both sides have AGREED (TRA-128)
  const agentCanAdvance    = isAgent && isActive && atAgentNegotiation &&
    negotiation?.club_agreement === "AGREED" && negotiation?.player_agreement === "AGREED";
  const clubCanCollapse       = isParty && isActive;
  const canEditDealStructure  = isParty && isActive && atAgreement;

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

      {/* AGENT_NEGOTIATION banner — clubs only; agent and player get dedicated panels below */}
      {atAgentNegotiation && isParty && !isAgent && !isPlayer && deal.status === "IN_PROGRESS" && (
        <div className="mb-6 rounded-xl bg-purple-500/10 px-5 py-4 text-sm text-purple-300 ring-1 ring-purple-500/20">
          <p className="font-semibold mb-1">Agent negotiation in progress</p>
          <p className="text-purple-400/80">
            The mandated agent is negotiating commission terms with the buying club and personal terms with the player. You will be notified once both parties agree.
          </p>
        </div>
      )}

      {/* Agent workspace — two-panel negotiation hub (TRA-128) */}
      {isAgent && atAgentNegotiation && deal.status === "IN_PROGRESS" && id && (
        <AgentNegotiationWorkspace
          dealId={id}
          negotiation={negotiation ?? null}
          agentCanAdvance={agentCanAdvance}
          onAdvance={() => advanceMutation.mutate()}
          advancePending={advanceMutation.isPending}
        />
      )}

      {/* Club: commission proposal from agent (TRA-129) */}
      {isParty && !isAgent && !isPlayer && atAgentNegotiation && deal.status === "IN_PROGRESS" && id && (
        <CommissionProposalView
          dealId={id}
          negotiation={negotiation ?? null}
        />
      )}

      {/* Player: proposed personal terms from agent (TRA-129) */}
      {isPlayer && atAgentNegotiation && deal.status === "IN_PROGRESS" && id && (
        <PlayerTermsProposalView
          dealId={id}
          negotiation={negotiation ?? null}
        />
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

          {/* Deal Structure (TRA-56/59) — editable in AGREEMENT stage */}
          {(canEditDealStructure || deal.deal_type === "LOAN") && (
            <Panel title="Deal Structure">
              {editingDealStructure ? (
                <div className="space-y-3">
                  <div>
                    <label className="mb-1 block text-xs text-slate-400">Transfer type</label>
                    <div className="flex gap-2">
                      {(["PERMANENT", "LOAN"] as const).map((t) => (
                        <button
                          key={t}
                          type="button"
                          onClick={() => setDealDraft((d) => ({ ...d, deal_type: t }))}
                          className={`flex-1 rounded-lg px-3 py-1.5 text-xs font-semibold ring-1 transition-colors ${
                            dealDraft.deal_type === t
                              ? "bg-emerald-500/20 text-emerald-400 ring-emerald-500/40"
                              : "bg-slate-800 text-slate-400 ring-white/10 hover:text-white"
                          }`}
                        >
                          {t === "PERMANENT" ? "Permanent" : "Loan"}
                        </button>
                      ))}
                    </div>
                  </div>
                  {dealDraft.deal_type === "LOAN" && (
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="mb-1 block text-xs text-slate-400">Loan start</label>
                        <input type="date" value={dealDraft.loan_start} onChange={(e) => setDealDraft((d) => ({ ...d, loan_start: e.target.value }))} className="w-full rounded-lg bg-slate-800 px-3 py-1.5 text-sm text-white ring-1 ring-white/10 focus:outline-none focus:ring-emerald-500" />
                      </div>
                      <div>
                        <label className="mb-1 block text-xs text-slate-400">Loan end</label>
                        <input type="date" value={dealDraft.loan_end} onChange={(e) => setDealDraft((d) => ({ ...d, loan_end: e.target.value }))} className="w-full rounded-lg bg-slate-800 px-3 py-1.5 text-sm text-white ring-1 ring-white/10 focus:outline-none focus:ring-emerald-500" />
                      </div>
                      <div>
                        <label className="mb-1 block text-xs text-slate-400">Loan fee (€)</label>
                        <input type="number" min={0} value={dealDraft.loan_fee} onChange={(e) => setDealDraft((d) => ({ ...d, loan_fee: e.target.value }))} className="w-full rounded-lg bg-slate-800 px-3 py-1.5 text-sm text-white ring-1 ring-white/10 focus:outline-none focus:ring-emerald-500" />
                      </div>
                      <div>
                        <label className="mb-1 block text-xs text-slate-400">Option to buy (€)</label>
                        <input type="number" min={0} value={dealDraft.option_to_buy} onChange={(e) => setDealDraft((d) => ({ ...d, option_to_buy: e.target.value }))} className="w-full rounded-lg bg-slate-800 px-3 py-1.5 text-sm text-white ring-1 ring-white/10 focus:outline-none focus:ring-emerald-500" />
                      </div>
                      <div className="col-span-2">
                        <label className="mb-1 block text-xs text-slate-400">Sell-on % (decimal, e.g. 0.05 = 5%)</label>
                        <input type="number" step="0.01" min={0} max={1} value={dealDraft.sell_on_pct} onChange={(e) => setDealDraft((d) => ({ ...d, sell_on_pct: e.target.value }))} className="w-full rounded-lg bg-slate-800 px-3 py-1.5 text-sm text-white ring-1 ring-white/10 focus:outline-none focus:ring-emerald-500" />
                      </div>
                    </div>
                  )}
                  <div className="flex gap-2 pt-1">
                    <Button
                      variant="primary"
                      size="sm"
                      loading={updateDealMutation.isPending}
                      onClick={() => {
                        const payload: Record<string, unknown> = { deal_type: dealDraft.deal_type };
                        if (dealDraft.deal_type === "LOAN") {
                          if (dealDraft.loan_start)   payload.loan_start   = dealDraft.loan_start;
                          if (dealDraft.loan_end)     payload.loan_end     = dealDraft.loan_end;
                          if (dealDraft.loan_fee)     payload.loan_fee     = Number(dealDraft.loan_fee);
                          if (dealDraft.option_to_buy) payload.option_to_buy = Number(dealDraft.option_to_buy);
                          if (dealDraft.sell_on_pct)  payload.sell_on_pct  = Number(dealDraft.sell_on_pct);
                        }
                        updateDealMutation.mutate(payload);
                      }}
                    >
                      Save
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => setEditingDealStructure(false)}>Cancel</Button>
                  </div>
                </div>
              ) : (
                <>
                  <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
                    <dt className="text-slate-500">Type</dt>
                    <dd className="text-white">{deal.deal_type === "LOAN" ? "Loan" : "Permanent"}</dd>
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
                  {canEditDealStructure && (
                    <button
                      onClick={() => {
                        setDealDraft({
                          deal_type: deal.deal_type ?? "PERMANENT",
                          loan_start: deal.loan_start ?? "",
                          loan_end: deal.loan_end ?? "",
                          loan_fee: deal.loan_fee != null ? String(deal.loan_fee) : "",
                          option_to_buy: deal.option_to_buy != null ? String(deal.option_to_buy) : "",
                          sell_on_pct: deal.sell_on_pct != null ? String(deal.sell_on_pct) : "",
                        });
                        setEditingDealStructure(true);
                      }}
                      className="mt-3 text-xs text-slate-500 hover:text-emerald-400 transition-colors"
                    >
                      Edit deal structure →
                    </button>
                  )}
                </>
              )}
            </Panel>
          )}

          {/* Add-on clauses (TRA-57/59) */}
          {(canEditDealStructure || deal.clauses.length > 0) && (
            <Panel title={`Add-on Clauses${deal.clauses.length > 0 ? ` (${deal.clauses.length})` : ""}`}>
              {deal.clauses.length > 0 && (
                <div className="space-y-2 mb-3">
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
              )}
              {canEditDealStructure && !addingClause && (
                <button
                  onClick={() => setAddingClause(true)}
                  className="text-xs text-slate-500 hover:text-emerald-400 transition-colors"
                >
                  + Add clause
                </button>
              )}
              {addingClause && (
                <div className="rounded-lg bg-slate-800/60 px-4 py-3 ring-1 ring-white/[0.06] space-y-2">
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="mb-1 block text-xs text-slate-400">Type</label>
                      <select
                        value={clauseDraft.clause_type}
                        onChange={(e) => setClauseDraft((d) => ({ ...d, clause_type: e.target.value }))}
                        className="w-full rounded-lg bg-slate-800 px-2.5 py-1.5 text-sm text-white ring-1 ring-white/10 focus:outline-none focus:ring-emerald-500"
                      >
                        {["APPEARANCES", "GOALS", "PROMOTION", "RESALE", "OTHER"].map((t) => (
                          <option key={t} value={t}>{t.charAt(0) + t.slice(1).toLowerCase()}</option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="mb-1 block text-xs text-slate-400">Amount (€)</label>
                      <input
                        type="number" min={0}
                        value={clauseDraft.amount}
                        onChange={(e) => setClauseDraft((d) => ({ ...d, amount: e.target.value }))}
                        className="w-full rounded-lg bg-slate-800 px-2.5 py-1.5 text-sm text-white ring-1 ring-white/10 focus:outline-none focus:ring-emerald-500"
                      />
                    </div>
                  </div>
                  <div>
                    <label className="mb-1 block text-xs text-slate-400">Trigger description</label>
                    <input
                      type="text"
                      value={clauseDraft.trigger_description}
                      onChange={(e) => setClauseDraft((d) => ({ ...d, trigger_description: e.target.value }))}
                      placeholder="e.g. Player makes 10+ appearances"
                      className="w-full rounded-lg bg-slate-800 px-2.5 py-1.5 text-sm text-white placeholder-slate-600 ring-1 ring-white/10 focus:outline-none focus:ring-emerald-500"
                    />
                  </div>
                  <div>
                    <label className="mb-1 block text-xs text-slate-400">Cap (€, optional)</label>
                    <input
                      type="number" min={0}
                      value={clauseDraft.cap}
                      onChange={(e) => setClauseDraft((d) => ({ ...d, cap: e.target.value }))}
                      className="w-full rounded-lg bg-slate-800 px-2.5 py-1.5 text-sm text-white ring-1 ring-white/10 focus:outline-none focus:ring-emerald-500"
                    />
                  </div>
                  <div className="flex gap-2 pt-1">
                    <Button
                      variant="primary"
                      size="sm"
                      loading={addClauseMutation.isPending}
                      disabled={!clauseDraft.trigger_description || !clauseDraft.amount}
                      onClick={() => addClauseMutation.mutate({
                        clause_type: clauseDraft.clause_type,
                        trigger_description: clauseDraft.trigger_description,
                        amount: Number(clauseDraft.amount),
                        ...(clauseDraft.cap ? { cap: Number(clauseDraft.cap) } : {}),
                      })}
                    >
                      Add clause
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => setAddingClause(false)}>Cancel</Button>
                  </div>
                </div>
              )}
            </Panel>
          )}

          {/* Instalment schedule (TRA-58/59) */}
          {(canEditDealStructure || deal.instalments.length > 0) && (
            <Panel title={`Payment Schedule${deal.instalments.length > 0 ? ` (${deal.instalments.length} instalments)` : ""}`}>
              {deal.instalments.length > 0 && !editingInstalments && (
                <div className="space-y-1.5 mb-3">
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
              )}
              {canEditDealStructure && !editingInstalments && (
                <button
                  onClick={() => {
                    setInstalmentRows(
                      deal.instalments.length > 0
                        ? deal.instalments.map((i) => ({ due_date: i.due_date, amount: String(i.amount) }))
                        : [{ due_date: "", amount: "" }]
                    );
                    setEditingInstalments(true);
                  }}
                  className="text-xs text-slate-500 hover:text-emerald-400 transition-colors"
                >
                  {deal.instalments.length > 0 ? "Edit schedule →" : "Set payment schedule"}
                </button>
              )}
              {editingInstalments && (
                <div className="space-y-2">
                  {instalmentRows.map((row, i) => (
                    <div key={i} className="flex items-center gap-2">
                      <input
                        type="date"
                        value={row.due_date}
                        onChange={(e) => setInstalmentRows((rows) => rows.map((r, j) => j === i ? { ...r, due_date: e.target.value } : r))}
                        className="flex-1 rounded-lg bg-slate-800 px-2.5 py-1.5 text-sm text-white ring-1 ring-white/10 focus:outline-none focus:ring-emerald-500"
                      />
                      <input
                        type="number"
                        min={0}
                        placeholder="Amount (€)"
                        value={row.amount}
                        onChange={(e) => setInstalmentRows((rows) => rows.map((r, j) => j === i ? { ...r, amount: e.target.value } : r))}
                        className="flex-1 rounded-lg bg-slate-800 px-2.5 py-1.5 text-sm text-white placeholder-slate-600 ring-1 ring-white/10 focus:outline-none focus:ring-emerald-500"
                      />
                      <button
                        onClick={() => setInstalmentRows((rows) => rows.filter((_, j) => j !== i))}
                        className="px-1 text-slate-500 hover:text-red-400 transition-colors text-xs"
                        title="Remove"
                      >
                        ✕
                      </button>
                    </div>
                  ))}
                  <div className="text-xs text-slate-500 pt-1">
                    Total: <span className="text-white font-semibold">{formatCurrency(instalmentRows.reduce((s, r) => s + (Number(r.amount) || 0), 0))}</span>
                    {" / "}
                    <span className="text-slate-400">{formatCurrency(deal.agreed_fee)} agreed fee</span>
                  </div>
                  <div className="flex items-center gap-3 flex-wrap pt-1">
                    <button
                      onClick={() => setInstalmentRows((rows) => [...rows, { due_date: "", amount: "" }])}
                      className="text-xs text-slate-500 hover:text-emerald-400 transition-colors"
                    >
                      + Add instalment
                    </button>
                    <Button
                      variant="primary"
                      size="sm"
                      loading={setInstalmentsMutation.isPending}
                      disabled={instalmentRows.some((r) => !r.due_date || !r.amount)}
                      onClick={() => setInstalmentsMutation.mutate(
                        instalmentRows.map((r) => ({ due_date: r.due_date, amount: Number(r.amount) }))
                      )}
                    >
                      Save schedule
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => setEditingInstalments(false)}>Cancel</Button>
                  </div>
                </div>
              )}
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
