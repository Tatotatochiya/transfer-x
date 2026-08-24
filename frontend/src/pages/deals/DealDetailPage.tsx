import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "../../lib/api";
import type { AgentNegotiation, Club, Deal, DealTermsVersion, FairValueSignal, TermsDiff } from "../../types/api";
import type { DealStage, DealType } from "../../types/enums";
import { useAuthStore } from "../../store/auth";
import FairValueBadge from "../../components/players/FairValueBadge";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import ClubLink from "../../components/ui/ClubLink";
import CurrencyInput from "../../components/ui/CurrencyInput";
import Metric from "../../components/ui/Metric";
import Panel from "../../components/ui/Panel";
import ResponsiveTable, { type ResponsiveColumn } from "../../components/ui/ResponsiveTable";
import Spinner from "../../components/ui/Spinner";
import StageTracker from "../../components/deals/StageTracker";
import NegotiationMessageThread from "../../components/deals/NegotiationMessageThread";
import DealRoomPanel from "../../components/deals/DealRoomPanel";
import { dealStatusVariant, dealStageLabel, dealTypeLabel } from "../../lib/badges";
import { formatCurrency, formatDate, formatWage, getApiError } from "../../lib/utils";
import { useToast } from "../../context/ToastContext";
import { useClubCapabilities } from "../../hooks/useClubCapabilities";

const STAGE_SEQ: DealStage[] = [
  "AGREEMENT", "AGENT_NEGOTIATION", "PERSONAL_TERMS", "PAPERWORK", "CONFIRMED", "COMPLETED",
];

function nextStage(stage: DealStage): DealStage {
  const idx = STAGE_SEQ.indexOf(stage);
  return idx >= 0 && idx < STAGE_SEQ.length - 1 ? STAGE_SEQ[idx + 1] : stage;
}

function daysSince(iso: string): number {
  return Math.floor((Date.now() - new Date(iso).getTime()) / 86_400_000);
}

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
        className="flex-1 rounded-lg bg-surface px-3 py-2 text-sm text-text placeholder-text-muted ring-1 ring-input-border focus:outline-none focus:ring-accent transition-colors"
      />
      <Button type="submit" variant="secondary" size="sm" loading={mutation.isPending}>
        Add
      </Button>
      {error && <p className="text-xs text-danger-text self-center">{error}</p>}
    </form>
  );
}

// ── Agreement status chip ─────────────────────────────────────────────────────

function AgreementChip({ label, status }: { label: string; status: string }) {
  const color =
    status === "AGREED"   ? "bg-success/15 text-success-text ring-success/30" :
    status === "DECLINED" ? "bg-danger/15 text-danger-text ring-danger/30"     :
                             "bg-surface-inset text-text-muted ring-border";
  return (
    <span className={`flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ${color}`}>
      {label}: {status}
    </span>
  );
}

// ── Agent negotiation workspace (TRA-128) ─────────────────────────────────────

interface AgentNegWorkspaceProps {
  dealId: string;
  negotiation: AgentNegotiation | null;
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
    additional_conditions: string;
  }>({
    commission_pct:        negotiation?.commission_pct        != null ? String(negotiation.commission_pct)        : "",
    commission_amount:     negotiation?.commission_amount     != null ? String(negotiation.commission_amount)     : "",
    commission_payer:      negotiation?.commission_payer      ?? "BUYER",
    additional_conditions: negotiation?.additional_conditions ?? "",
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
    if (draft.commission_pct !== "")        payload.commission_pct        = Number(draft.commission_pct);
    if (draft.commission_amount !== "")     payload.commission_amount     = Number(draft.commission_amount);
    if (draft.commission_payer)             payload.commission_payer      = draft.commission_payer;
    if (draft.additional_conditions !== "") payload.additional_conditions = draft.additional_conditions;
    saveMutation.mutate(payload);
  }

  const clubAgreed = negotiation?.club_agreement === "AGREED";

  return (
    <div className="mb-6">
      <div className="mb-3 flex items-center justify-between">
        <p className="text-xs font-semibold uppercase tracking-wider text-role-agent-text">
          Negotiation Workspace
        </p>
        <AgreementChip label="Club" status={negotiation?.club_agreement ?? "PENDING"} />
      </div>

      <div className="rounded-xl bg-role-agent-bg px-5 py-4 ring-1 ring-role-agent-text/20">
        <p className="mb-3 text-xs font-bold uppercase tracking-wider text-role-agent-text">
          Club side — Commission
        </p>
        {editing ? (
          <div className="space-y-2">
            <label className="block text-xs text-text-muted">Commission % <span className="text-text-muted/70">(decimal, e.g. 0.05 = 5%)</span></label>
            <input
              type="number" step="0.001"
              value={draft.commission_pct}
              onChange={(e) => setDraft((d) => ({ ...d, commission_pct: e.target.value }))}
              className="w-full rounded-lg bg-surface px-3 py-1.5 text-sm text-text ring-1 ring-input-border focus:outline-none focus:ring-accent"
            />
            <label className="block text-xs text-text-muted pt-1">Commission amount (€)</label>
            <CurrencyInput
              value={draft.commission_amount}
              onChange={(v) => setDraft((d) => ({ ...d, commission_amount: v }))}
              className="w-full rounded-lg bg-surface px-3 py-1.5 text-sm text-text ring-1 ring-input-border focus:outline-none focus:ring-accent"
            />
            <label className="block text-xs text-text-muted pt-1">Paid by</label>
            <select
              value={draft.commission_payer}
              onChange={(e) => setDraft((d) => ({ ...d, commission_payer: e.target.value }))}
              className="w-full rounded-lg bg-surface px-3 py-1.5 text-sm text-text ring-1 ring-input-border focus:outline-none focus:ring-accent"
            >
              <option value="BUYER">Buying club</option>
              <option value="SELLER">Selling club</option>
              <option value="PLAYER">Player</option>
            </select>
            <label className="block text-xs text-text-muted pt-1">Additional conditions</label>
            <textarea
              rows={2}
              value={draft.additional_conditions}
              onChange={(e) => setDraft((d) => ({ ...d, additional_conditions: e.target.value }))}
              className="w-full resize-none rounded-lg bg-surface px-3 py-1.5 text-sm text-text ring-1 ring-input-border focus:outline-none focus:ring-accent"
            />
          </div>
        ) : (
          <dl className="space-y-1.5 text-sm">
            {negotiation?.commission_pct != null && (
              <><dt className="text-text-muted">Commission</dt><dd className="text-text">{(negotiation.commission_pct * 100).toFixed(2)}%</dd></>
            )}
            {negotiation?.commission_amount != null && (
              <><dt className="text-text-muted">Amount</dt><dd className="text-text">{formatCurrency(negotiation.commission_amount)}</dd></>
            )}
            {negotiation?.commission_payer && (
              <><dt className="text-text-muted">Paid by</dt><dd className="text-text capitalize">{negotiation.commission_payer.toLowerCase()}</dd></>
            )}
            {negotiation?.additional_conditions && (
              <><dt className="text-text-muted">Conditions</dt><dd className="text-text text-xs">{negotiation.additional_conditions}</dd></>
            )}
            {!negotiation?.commission_pct && !negotiation?.commission_amount && (
              <p className="text-xs text-text-muted italic">No commission terms set yet.</p>
            )}
          </dl>
        )}
        <div className="mt-3">
          {clubAgreed ? (
            <span className="text-xs font-semibold text-success-text">✓ Club has agreed</span>
          ) : (
            <span className="text-xs text-text-muted">Awaiting club agreement</span>
          )}
        </div>
        {negotiation && (
          <NegotiationMessageThread negotiationId={negotiation.id} thread="CLUB_SIDE" />
        )}
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
                commission_pct:        negotiation?.commission_pct        != null ? String(negotiation.commission_pct)        : "",
                commission_amount:     negotiation?.commission_amount     != null ? String(negotiation.commission_amount)     : "",
                commission_payer:      negotiation?.commission_payer      ?? "BUYER",
                additional_conditions: negotiation?.additional_conditions ?? "",
              });
              setEditing(true);
            }}>
              Edit terms
            </Button>
          )}
        </div>

        <div className="flex items-center gap-3">
          {!agentCanAdvance && (
            <p className="text-xs text-text-muted">Awaiting club agreement on commission.</p>
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
  canRespond = true,
}: {
  dealId: string;
  negotiation: AgentNegotiation | null;
  canRespond?: boolean;
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
    <div className="mb-6 rounded-xl bg-role-agent-bg px-5 py-4 ring-1 ring-role-agent-text/20">
      <p className="mb-3 text-xs font-bold uppercase tracking-wider text-role-agent-text">
        Agent Commission Proposal
      </p>
      <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
        {negotiation.commission_pct != null && (
          <><dt className="text-text-muted">Commission</dt><dd className="font-semibold text-text">{(negotiation.commission_pct * 100).toFixed(2)}%</dd></>
        )}
        {negotiation.commission_amount != null && (
          <><dt className="text-text-muted">Amount</dt><dd className="font-semibold text-text">{formatCurrency(negotiation.commission_amount)}</dd></>
        )}
        {negotiation.commission_payer && (
          <><dt className="text-text-muted">Paid by</dt><dd className="text-text capitalize">{negotiation.commission_payer.toLowerCase()}</dd></>
        )}
        {negotiation.additional_conditions && (
          <><dt className="col-span-2 text-text-muted">Conditions</dt><dd className="col-span-2 text-sm text-text">{negotiation.additional_conditions}</dd></>
        )}
      </dl>

      {isPending && !canRespond ? (
        <p className="mt-4 text-sm text-text-muted">Awaiting a decision from your club.</p>
      ) : isPending ? (
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
        <p className={`mt-4 text-sm font-semibold ${negotiation.club_agreement === "AGREED" ? "text-success-text" : "text-danger-text"}`}>
          {negotiation.club_agreement === "AGREED" ? "✓ You accepted this proposal" : "✗ You declined this proposal"}
        </p>
      )}
      <NegotiationMessageThread negotiationId={negotiation.id} thread="CLUB_SIDE" />
    </div>
  );
}

// ── Set personal terms (ADR 0001) ──────────────────────────────────────────────

function SetPersonalTermsForm({ dealId }: { dealId: string }) {
  const queryClient = useQueryClient();
  const { addToast } = useToast();

  const [wageWeekly, setWageWeekly] = useState("");
  const [signingBonus, setSigningBonus] = useState("");
  const [lengthYears, setLengthYears] = useState("");

  const mutation = useMutation({
    mutationFn: () =>
      api.put(`/deals/${dealId}/personal-terms`, {
        wage_weekly: wageWeekly !== "" ? Number(wageWeekly) : null,
        signing_bonus: signingBonus !== "" ? Number(signingBonus) : null,
        length_years: lengthYears !== "" ? Number(lengthYears) : null,
      }).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["deals", dealId] });
      addToast("Personal terms sent to the player.", "success");
    },
    onError: (err: unknown) => addToast(getApiError(err, "Failed to set personal terms."), "error"),
  });

  return (
    <Panel title="Set Personal Terms">
      <div className="space-y-2">
        <div>
          <label className="mb-1 block text-xs text-text-muted">Weekly wage (€)</label>
          <CurrencyInput
            value={wageWeekly}
            onChange={setWageWeekly}
            className="w-full rounded-lg bg-surface px-3 py-1.5 text-sm text-text ring-1 ring-input-border focus:outline-none focus:ring-accent"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs text-text-muted">Signing bonus (€)</label>
          <CurrencyInput
            value={signingBonus}
            onChange={setSigningBonus}
            className="w-full rounded-lg bg-surface px-3 py-1.5 text-sm text-text ring-1 ring-input-border focus:outline-none focus:ring-accent"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs text-text-muted">Contract length (years)</label>
          <input
            type="number" min={1} max={10}
            value={lengthYears}
            onChange={(e) => setLengthYears(e.target.value)}
            className="w-full rounded-lg bg-surface px-3 py-1.5 text-sm text-text ring-1 ring-input-border focus:outline-none focus:ring-accent"
          />
        </div>
        <Button
          variant="primary"
          size="sm"
          loading={mutation.isPending}
          disabled={wageWeekly === "" || lengthYears === ""}
          onClick={() => mutation.mutate()}
        >
          Send to player
        </Button>
      </div>
    </Panel>
  );
}

// ── Medical check (TRA-61) ──────────────────────────────────────────────────

const MEDICAL_STATUS_STYLE: Record<string, string> = {
  PASSED:  "text-success-text",
  FAILED:  "text-danger-text",
  PENDING: "text-warning-text",
};

function MedicalCheckPanel({
  dealId,
  medicalCheck,
  isStaff,
}: {
  dealId: string;
  medicalCheck: Deal["medical_check"];
  isStaff: boolean;
}) {
  const queryClient = useQueryClient();
  const { addToast } = useToast();
  const [editing, setEditing] = useState(false);
  const [statusDraft, setStatusDraft] = useState<"PENDING" | "PASSED" | "FAILED">(
    medicalCheck?.status ?? "PENDING"
  );
  const [notesDraft, setNotesDraft] = useState(medicalCheck?.notes ?? "");

  const mutation = useMutation({
    mutationFn: () =>
      api.put(`/deals/${dealId}/medical-check`, {
        status: statusDraft,
        notes: notesDraft.trim() || null,
      }).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["deals", dealId] });
      setEditing(false);
      addToast("Medical check saved.", "success");
    },
    onError: (err: unknown) => addToast(getApiError(err, "Failed to save medical check."), "error"),
  });

  if (!isStaff && !medicalCheck) return null;

  return (
    <Panel title="Medical Check">
      {!editing ? (
        <>
          {medicalCheck ? (
            <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
              <dt className="text-text-muted">Status</dt>
              <dd className={`font-semibold ${MEDICAL_STATUS_STYLE[medicalCheck.status] ?? "text-text-secondary"}`}>
                {medicalCheck.status}
              </dd>
              {medicalCheck.notes && (
                <><dt className="text-text-muted">Notes</dt><dd className="text-text">{medicalCheck.notes}</dd></>
              )}
              <dt className="text-text-muted">Last updated</dt>
              <dd className="text-text-muted">{formatDate(medicalCheck.updated_at)}</dd>
            </dl>
          ) : (
            <p className="text-sm text-text-muted pb-1">Not yet requested — doesn't block progression.</p>
          )}
          {medicalCheck?.status === "FAILED" && (
            <p className="mt-2 text-xs text-danger-text/80">Blocks Paperwork → Confirmed until changed.</p>
          )}
          {isStaff && (
            <button
              onClick={() => {
                setStatusDraft(medicalCheck?.status ?? "PENDING");
                setNotesDraft(medicalCheck?.notes ?? "");
                setEditing(true);
              }}
              className="mt-2 text-xs text-text-muted hover:text-accent transition-colors"
            >
              {medicalCheck ? "Update →" : "Record medical check"}
            </button>
          )}
        </>
      ) : (
        <div className="space-y-2">
          <div>
            <label className="mb-1 block text-xs text-text-muted">Status</label>
            <select
              value={statusDraft}
              onChange={(e) => setStatusDraft(e.target.value as "PENDING" | "PASSED" | "FAILED")}
              className="w-full rounded-lg bg-surface px-3 py-1.5 text-sm text-text ring-1 ring-input-border focus:outline-none focus:ring-accent"
            >
              <option value="PENDING">Pending</option>
              <option value="PASSED">Passed</option>
              <option value="FAILED">Failed</option>
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs text-text-muted">Notes</label>
            <textarea
              value={notesDraft}
              onChange={(e) => setNotesDraft(e.target.value)}
              rows={3}
              placeholder="Optional notes…"
              className="w-full rounded-lg bg-surface px-3 py-1.5 text-sm text-text placeholder-text-muted ring-1 ring-input-border focus:outline-none focus:ring-accent"
            />
          </div>
          <div className="flex items-center gap-3">
            <Button variant="primary" size="sm" loading={mutation.isPending} onClick={() => mutation.mutate()}>
              Save
            </Button>
            <Button variant="ghost" size="sm" onClick={() => setEditing(false)}>Cancel</Button>
          </div>
        </div>
      )}
    </Panel>
  );
}

// ── Blocked-on header ─────────────────────────────────────────────────────────

const BLOCKER_LABEL: Partial<Record<DealStage, string>> = {
  AGREEMENT: "Club terms",
  AGENT_NEGOTIATION: "Agent commission",
  PERSONAL_TERMS: "Player consent",
  PAPERWORK: "TransferX paperwork",
  CONFIRMED: "Execution",
};

function DealRoomHeader({ deal }: { deal: Deal }) {
  const isOpen = deal.status === "IN_PROGRESS" || deal.status === "PENDING_COMPLETION";
  const blocker = isOpen ? BLOCKER_LABEL[deal.stage] : undefined;
  const idleDays = daysSince(deal.updated_at);

  return (
    <div className="mb-6 rounded-xl bg-surface px-6 py-5 ring-1 ring-border">
      <div className="mb-4 flex items-center justify-between">
        {blocker ? (
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-wider text-text-muted">Blocked on</p>
            <p className="text-[22px] font-bold text-warning-text">{blocker}</p>
            {idleDays > 0 && (
              <p className="mt-0.5 text-xs text-text-muted">{idleDays} day{idleDays === 1 ? "" : "s"} without movement</p>
            )}
          </div>
        ) : (
          <p className="text-xs font-semibold uppercase tracking-wider text-text-muted">Deal Progress</p>
        )}
        <Badge variant={dealStatusVariant(deal.status)}>
          {deal.status.replace(/_/g, " ")}
        </Badge>
      </div>
      <StageTracker stage={deal.stage} status={deal.status} />
    </div>
  );
}

// ── Three lanes ───────────────────────────────────────────────────────────────

type LaneStatus = "done" | "blocking" | "pending";

function Lane({ status, title, description, metricLabel, metricValue }: {
  status: LaneStatus; title: string; description: string; metricLabel: string; metricValue: string;
}) {
  const stripClass = status === "done" ? "bg-success" : status === "blocking" ? "bg-warning-fill" : "bg-border";
  const overlineClass = status === "done" ? "text-success-text" : status === "blocking" ? "text-warning-text" : "text-text-muted";
  const overlineLabel = status === "done" ? "Agreed" : status === "blocking" ? "Blocking" : "Not started";

  return (
    <div className="relative overflow-hidden rounded-xl bg-surface px-4 pb-3.5 pt-4 ring-1 ring-border">
      <div className={`absolute inset-x-0 top-0 h-1 ${stripClass}`} />
      <p className={`text-[11px] font-bold uppercase tracking-wider ${overlineClass}`}>{overlineLabel}</p>
      <p className="mt-1 text-[15px] font-bold text-text">{title}</p>
      <p className="mt-1 text-xs leading-snug text-text-muted">{description}</p>
      <div className="mt-3 flex items-center justify-between border-t border-rule pt-2.5">
        <span className="text-[11px] text-text-muted">{metricLabel}</span>
        <span className="text-sm font-bold text-text">{metricValue}</span>
      </div>
    </div>
  );
}

function laneStatus(deal: Deal, stage: DealStage): LaneStatus {
  const dealIdx = STAGE_SEQ.indexOf(deal.stage);
  const laneIdx = STAGE_SEQ.indexOf(stage);
  if (dealIdx > laneIdx) return "done";
  if (dealIdx === laneIdx) return "blocking";
  return "pending";
}

function ThreeLanes({ deal, negotiation }: { deal: Deal; negotiation: AgentNegotiation | undefined }) {
  const clubStatus: LaneStatus = deal.stage === "AGREEMENT" ? "blocking" : "done";
  // deal.commission_agent_id is only set once commission is finalized — a
  // negotiation in flight (still being proposed) is an equally real signal
  // that this deal has an agent, so either one shows the lane.
  const hasAgent = deal.commission_agent_id != null || negotiation != null;
  const agentStatus = laneStatus(deal, "AGENT_NEGOTIATION");
  const personalStatus = laneStatus(deal, "PERSONAL_TERMS");

  const commissionPct = deal.agent_commission_pct ?? negotiation?.commission_pct ?? null;

  return (
    <div className="mb-6 grid gap-3" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(230px, 1fr))" }}>
      <Lane
        status={clubStatus}
        title="Club to club"
        description={clubStatus === "blocking" ? "Finalising fee and deal structure between clubs." : "Fee and structure agreed between clubs."}
        metricLabel="Agreed fee"
        metricValue={formatCurrency(deal.agreed_fee)}
      />
      {hasAgent && (
        <Lane
          status={agentStatus}
          title="Agent commission"
          description={
            agentStatus === "pending" ? "Not yet started." :
            agentStatus === "blocking" ? "Agent and club negotiating commission terms." :
            "Commission terms agreed."
          }
          metricLabel="Commission"
          metricValue={commissionPct != null ? `${(commissionPct * 100).toFixed(1)}%` : "—"}
        />
      )}
      <Lane
        status={personalStatus}
        title="Personal terms"
        description={
          personalStatus === "pending" ? "Not yet started." :
          personalStatus === "blocking" ? "Awaiting player consent." :
          "Personal terms confirmed."
        }
        metricLabel="Wage"
        metricValue={deal.personal_terms?.wage_weekly != null ? formatWage(deal.personal_terms.wage_weekly) : "—"}
      />
    </div>
  );
}

// ── Terms diff — the spine of the screen ──────────────────────────────────────

const TERMS_FIELD_LABELS: Record<string, string> = {
  agreed_fee: "Agreed fee",
  agreed_wage_weekly: "Weekly wage",
  deal_type: "Deal type",
  loan_start: "Loan start",
  loan_end: "Loan end",
  loan_fee: "Loan fee",
  option_to_buy: "Option to buy",
  obligation_to_buy: "Obligation to buy",
  obligation_conditions: "Obligation conditions",
  sell_on_pct: "Sell-on %",
};

const CURRENCY_FIELDS = new Set(["agreed_fee", "agreed_wage_weekly", "loan_fee", "option_to_buy"]);

function formatTermValue(field: string, value: unknown): string {
  if (value == null || value === "") return "—";
  if (field === "sell_on_pct") return `${(Number(value) * 100).toFixed(1)}%`;
  if (CURRENCY_FIELDS.has(field)) return formatCurrency(Number(value));
  if (typeof value === "boolean") return value ? "Yes" : "No";
  // Without this the diff spine prints the raw enum ("FREE_TRANSFER").
  if (field === "deal_type") return dealTypeLabel(value as DealType);
  return String(value);
}

interface DiffRow { field: string; oldValue: unknown; newValue: unknown }

function TermsDiffSpine({ dealId, isBuyer }: { dealId: string; isBuyer: boolean }) {
  const { data: versions = [], isLoading } = useQuery<DealTermsVersion[]>({
    queryKey: ["deals", dealId, "versions"],
    queryFn: () => api.get<DealTermsVersion[]>(`/deals/${dealId}/versions`).then((r) => r.data),
  });

  const { data: diff } = useQuery<TermsDiff>({
    queryKey: ["deals", dealId, "versions", "diff"],
    queryFn: () => api.get<TermsDiff>(`/deals/${dealId}/versions/diff`).then((r) => r.data),
    enabled: versions.length >= 2,
  });

  if (isLoading) return null;
  if (versions.length === 0 || !diff || diff.changes.length === 0) return null;

  const latest = [...versions].sort((a, b) => b.version_number - a.version_number)[0];
  const unchangedCount = Math.max(0, Object.keys(latest.terms_snapshot ?? {}).length - diff.changes.length);

  const rows: DiffRow[] = diff.changes.map((c) => ({ field: c.field, oldValue: c.old_value, newValue: c.new_value }));

  // DECISIONS.md item 5: no present-value model exists — nominal difference
  // only, never an invented discount rate. "Effect on you" only applies to
  // currency fields; everything else has no clean monetary framing.
  function effect(row: DiffRow): { text: string; className: string } {
    if (!CURRENCY_FIELDS.has(row.field)) return { text: "—", className: "text-text-muted" };
    const oldN = Number(row.oldValue ?? 0);
    const newN = Number(row.newValue ?? 0);
    const delta = newN - oldN;
    if (delta === 0) return { text: "No change", className: "text-text-muted" };
    // A higher fee/wage/loan-fee/option is worse for the buyer, better for the seller.
    const worseForMe = isBuyer ? delta > 0 : delta < 0;
    const magnitude = formatCurrency(Math.abs(delta));
    return {
      text: `${worseForMe ? "−" : "+"}${magnitude}`,
      className: worseForMe ? "text-danger-text" : "text-success-text",
    };
  }

  const netDelta = rows
    .filter((r) => CURRENCY_FIELDS.has(r.field))
    .reduce((sum, r) => {
      const delta = Number(r.newValue ?? 0) - Number(r.oldValue ?? 0);
      return sum + (isBuyer ? -delta : delta);
    }, 0);

  const columns: ResponsiveColumn<DiffRow>[] = [
    { key: "term", header: "Term", priority: 1, render: (r) => (
      <span className="font-medium text-text">{TERMS_FIELD_LABELS[r.field] ?? r.field}</span>
    ) },
    { key: "old", header: `Agreed (v${(latest.version_number - 1)})`, priority: 3, render: (r) => (
      <span className="text-text-muted line-through">{formatTermValue(r.field, r.oldValue)}</span>
    ) },
    { key: "new", header: `Proposed (v${latest.version_number})`, priority: 2, render: (r) => (
      <span className="font-bold text-text">{formatTermValue(r.field, r.newValue)}</span>
    ) },
    { key: "effect", header: "Effect on you", priority: 4, className: "text-right", render: (r) => {
      const e = effect(r);
      return <span className={`font-semibold ${e.className}`}>{e.text}</span>;
    } },
  ];

  return (
    <Card noPadding className="mb-6">
      <div className="border-b border-rule px-5 py-4">
        <p className="text-sm font-bold text-text">
          Terms — version {latest.version_number} proposed by {latest.changed_by_label ?? "the deal"}
        </p>
        <p className="mt-0.5 text-xs text-text-muted">
          {diff.changes.length} term{diff.changes.length === 1 ? "" : "s"} changed
          {unchangedCount > 0 && ` · ${unchangedCount} unchanged`}
          {" · sent "}{formatDate(latest.created_at)}
        </p>
      </div>
      <div className="p-5">
        <ResponsiveTable
          columns={columns}
          rows={rows}
          rowKey={(r) => r.field}
          renderCard={(r) => {
            const e = effect(r);
            return (
              <div className="px-4 py-3">
                <p className="text-sm font-semibold text-text">{TERMS_FIELD_LABELS[r.field] ?? r.field}</p>
                <div className="mt-1 flex items-center justify-between text-sm">
                  <span className="text-text-muted line-through">{formatTermValue(r.field, r.oldValue)}</span>
                  <span className="font-bold text-text">{formatTermValue(r.field, r.newValue)}</span>
                </div>
                <p className={`mt-0.5 text-right text-xs font-semibold ${e.className}`}>{e.text}</p>
              </div>
            );
          }}
        />
      </div>
      {netDelta !== 0 && (
        <div className="border-t border-rule px-5 py-3">
          <p className="text-xs text-text-muted">
            Net change against version {latest.version_number - 1}:{" "}
            <span className={netDelta < 0 ? "text-danger-text font-semibold" : "text-success-text font-semibold"}>
              {netDelta < 0 ? "−" : "+"}{formatCurrency(Math.abs(netDelta))}
            </span>{" "}
            to you over the life of the deal.
          </p>
        </div>
      )}
    </Card>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function DealDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { addToast } = useToast();
  const { can } = useClubCapabilities();
  const { accessToken, user } = useAuthStore();
  const isAuthenticated = !!accessToken;
  const isAgent  = user?.user_type === "AGENT";
  const isPlayer = user?.user_type === "PLAYER";
  const isStaff  = user?.is_superuser ?? false;
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

  // TRA-92: fair value vs the agreed fee, for club/agent/staff identities only —
  // a player identity must never fire the call (the server 403s it anyway, D6)
  const { data: fairValue = null } = useQuery<FairValueSignal | null>({
    queryKey: ["valuation", deal?.player_id, { reference: deal?.agreed_fee }],
    queryFn: () =>
      api
        .get<FairValueSignal>(`/valuation/players/${deal!.player_id}`, {
          params: deal!.agreed_fee != null ? { reference_price: deal!.agreed_fee } : {},
        })
        .then((r) => r.data)
        .catch(() => null),
    enabled: !!deal?.player_id && isAuthenticated && !isPlayer,
    staleTime: 300_000,
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

  // Load AgentNegotiation when deal is in that stage (TRA-128/129) — commission
  // only; personal terms live entirely in PersonalTerms from PERSONAL_TERMS on.
  const { data: negotiation } = useQuery<AgentNegotiation>({
    queryKey: ["deals", id, "agent-negotiation"],
    queryFn: () =>
      api.get<AgentNegotiation>(`/deals/${id}/agent-negotiation`).then((r) => r.data),
    enabled: !!id && !!deal && deal.stage === "AGENT_NEGOTIATION",
    retry: false,
  });

  // Mandated agent responding on the player's behalf when they have no
  // account (mirrors the club-side proxy rule already used at AGENT_NEGOTIATION).
  const personalTermsConsentMutation = useMutation({
    mutationFn: (agreement: string) =>
      api.post(`/deals/${id}/personal-terms/player-consent`, { agreement }).then((r) => r.data),
    onSuccess: (_, agreement) => {
      queryClient.invalidateQueries({ queryKey: ["deals", id] });
      addToast(
        agreement === "AGREED" ? "Accepted on behalf of the player." : "Declined on behalf of the player.",
        agreement === "AGREED" ? "success" : "warning"
      );
    },
    onError: (err: unknown) => addToast(getApiError(err, "Failed to respond."), "error"),
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
      <div className="rounded-xl bg-danger-bg px-5 py-4 text-sm text-danger-text ring-1 ring-danger-border">
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
  // TRA-151 (D4): club-side deal writes need DEAL_WRITE — SCOUT/READONLY staff
  // keep full visibility but every mutating control below disappears for them.
  const canDealWrite       = can("DEAL_WRITE");
  const clubCanAdvance     = isParty && !isAgent && isActive && !atPaperwork && !atAgentNegotiation && !deal.is_auction_deal && canDealWrite;
  // Agent can advance once the club has agreed commission (TRA-128) — personal
  // terms are a separate proposal + consent, at PERSONAL_TERMS.
  const agentCanAdvance    = isAgent && isActive && atAgentNegotiation &&
    negotiation?.club_agreement === "AGREED";
  const clubCanCollapse       = isParty && isActive && canDealWrite;
  const canEditDealStructure  = isParty && isActive && atAgreement && canDealWrite;
  // Set personal terms (ADR 0001): the mandated agent if this deal went through
  // AGENT_NEGOTIATION, otherwise the buying club when there's no mandate at all.
  const canSetPersonalTerms   = isActive && atPersonalTerms && !deal.personal_terms && (
    (isAgent && deal.commission_agent_id != null) ||
    (isBuyer && !isAgent && !isPlayer && deal.commission_agent_id == null && canDealWrite)
  );

  const advanceError =
    advanceMutation.isError ? getApiError(advanceMutation.error, "Failed.") : null;

  const viewerSide = isBuyer ? "buyer" : isSeller ? "seller" : null;
  const myClubName = isBuyer ? deal.buyer_club?.name : isSeller ? deal.seller_club?.name : undefined;
  const theirClubName = isBuyer ? deal.seller_club?.name : isSeller ? deal.buyer_club?.name : undefined;

  return (
    <div>
      <button
        onClick={() => navigate(-1)}
        className="mb-6 flex items-center gap-1.5 text-sm text-text-muted hover:text-text transition-colors"
      >
        ← Back to deals
      </button>

      <DealRoomHeader deal={deal} />

      <ThreeLanes deal={deal} negotiation={negotiation} />

      {/* PAPERWORK banner */}
      {atPaperwork && isParty && deal.status === "IN_PROGRESS" && (
        <div className="mb-6 rounded-xl bg-accent-bg px-5 py-4 text-sm text-accent-active ring-1 ring-accent/20">
          <p className="font-semibold mb-1">TransferX is handling the paperwork</p>
          <p className="text-accent-active/80">
            Our team is processing the documentation. You'll be notified when it's ready for confirmation.
          </p>
        </div>
      )}

      {/* CONFIRMED / Ready to Execute banner */}
      {atConfirmed && isParty && deal.status === "IN_PROGRESS" && (
        <div className="mb-6 rounded-xl bg-success/10 px-5 py-4 text-sm text-success-text ring-1 ring-success/20">
          <p className="font-semibold mb-1">Documents verified — ready to execute</p>
          <p className="text-success-text/80">
            TransferX has processed all documentation. Use the <strong>Execute Transfer</strong> button to complete the deal and register the player.
          </p>
        </div>
      )}

      {/* AGENT_NEGOTIATION banner — clubs only; agent gets a dedicated panel below */}
      {atAgentNegotiation && isParty && !isAgent && !isPlayer && deal.status === "IN_PROGRESS" && (
        <div className="mb-6 rounded-xl bg-role-agent-bg px-5 py-4 text-sm text-role-agent-text ring-1 ring-role-agent-text/20">
          <p className="font-semibold mb-1">Agent negotiation in progress</p>
          <p className="text-role-agent-text/80">
            The mandated agent is negotiating commission terms with the buying club. Personal terms follow once this stage is agreed.
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
          canRespond={canDealWrite}
        />
      )}

      {/* PERSONAL_TERMS banner */}
      {atPersonalTerms && isParty && deal.status === "IN_PROGRESS" && (
        <div className="mb-6 rounded-xl bg-warning-bg px-5 py-4 text-sm text-warning-text ring-1 ring-warning-fill/20">
          <p className="font-semibold mb-1">Awaiting player consent on personal terms</p>
          <p className="text-warning-text/80">
            The agent has proposed personal contract terms. The deal will advance once the player confirms acceptance.
          </p>
        </div>
      )}

      {/* Auction deal banner */}
      {deal.is_auction_deal && isParty && deal.status === "IN_PROGRESS" && (
        <div className="mb-6 rounded-xl bg-warning-bg px-5 py-4 text-sm text-warning-text ring-1 ring-warning-fill/20">
          <p className="font-semibold mb-1">Auction deal</p>
          <p className="text-warning-text/80">
            This deal was created from an auction result. Stage advancement is handled by TransferX staff.
          </p>
        </div>
      )}

      {/* Completed banner */}
      {deal.status === "COMPLETED" && (
        <div className="mb-6 rounded-xl bg-success/10 px-5 py-4 text-sm text-success-text ring-1 ring-success/20">
          <p className="font-semibold">Transfer completed</p>
          {deal.completed_at && (
            <p className="text-success-text/80 mt-1">
              Completed on {formatDate(deal.completed_at)}
            </p>
          )}
        </div>
      )}

      {/* Collapsed banner */}
      {deal.status === "COLLAPSED" && (
        <div className="mb-6 rounded-xl bg-danger-bg px-5 py-4 text-sm text-danger-text ring-1 ring-danger-border">
          <p className="font-semibold">Deal collapsed</p>
          <p className="text-danger-text/80 mt-1">This transfer has fallen through.</p>
        </div>
      )}

      {id && <TermsDiffSpine dealId={id} isBuyer={isBuyer} />}

      <div className="grid gap-6 lg:grid-cols-3">
        {/* ── Left: info ── */}
        <div className="lg:col-span-1 space-y-4">
          {/* Player */}
          <Card>
            <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-text-muted">
              Player
            </p>
            <button
              onClick={() =>
                deal.player_id && navigate(`/players/market/${deal.player_id}`)
              }
              className="text-lg font-semibold text-text hover:text-accent transition-colors text-left"
            >
              {deal.player?.name ?? "Unknown"}
            </button>
            {deal.player?.position && (
              <p className="text-xs text-text-muted mt-0.5">{deal.player.position}</p>
            )}
          </Card>

          {/* Terms */}
          <Card>
            <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-text-muted">
              Agreed Terms
            </p>
            <div className="space-y-2">
              <Metric label="Transfer fee" value={formatCurrency(deal.agreed_fee)} />
              {/* Fair-value signal vs agreed fee (TRA-92) — never for a player identity */}
              {!isPlayer && fairValue && (
                <div className="border-b border-rule pb-2">
                  <FairValueBadge signal={fairValue} referenceLabel="Agreed fee" />
                </div>
              )}
              {deal.agreed_wage_weekly != null && (
                <Metric label="Wage" value={formatWage(deal.agreed_wage_weekly)} />
              )}
              <Metric
                label="Buyer"
                valueNode={
                  <ClubLink
                    id={deal.buyer_club?.id}
                    name={deal.buyer_club?.name}
                    crestUrl={deal.buyer_club?.crest_url}
                  />
                }
              />
              <Metric
                label="Seller"
                valueNode={
                  <ClubLink
                    id={deal.seller_club?.id}
                    name={deal.seller_club?.name}
                    crestUrl={deal.seller_club?.crest_url}
                  />
                }
              />
              <Metric label="Type" value={dealTypeLabel(deal.deal_type)} />
              <Metric label="Stage" value={dealStageLabel(deal.stage)} />
              <Metric label="Created" value={formatDate(deal.created_at)} />
              {deal.is_auction_deal && (
                <p className="mt-1 text-xs text-warning-text/80 border-t border-rule pt-2">
                  Auction deal
                </p>
              )}
            </div>
          </Card>

          {/* Actions */}
          {isParty && isActive && (
            <Card>
              <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-text-muted">
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
                  <p className="text-xs text-danger-text">{advanceError}</p>
                )}
                {clubCanCollapse && !showCollapsePanel && (
                  <button
                    onClick={() => setShowCollapsePanel(true)}
                    className="w-full rounded-lg px-3 py-2 text-sm text-text-muted hover:text-danger-text hover:bg-danger-bg ring-1 ring-border hover:ring-danger-border transition-colors"
                  >
                    Collapse deal…
                  </button>
                )}
              </div>

              {/* Inline collapse confirmation panel */}
              {clubCanCollapse && showCollapsePanel && (
                <div className="mt-3 rounded-lg bg-danger-bg ring-1 ring-danger-border px-4 py-4 space-y-3">
                  <div className="flex items-start gap-2">
                    <svg className="h-4 w-4 text-danger-text shrink-0 mt-0.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v4m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
                    </svg>
                    <div>
                      <p className="text-sm font-semibold text-danger-text">Collapse this deal?</p>
                      <p className="text-xs text-text-muted mt-0.5">This cannot be undone. The transfer will fall through and reserved budget will be released.</p>
                    </div>
                  </div>
                  <div>
                    <label className="mb-1.5 block text-xs text-text-muted">Reason (optional)</label>
                    <textarea
                      rows={2}
                      value={collapseReason}
                      onChange={(e) => setCollapseReason(e.target.value)}
                      placeholder="e.g. Clubs could not agree on fee"
                      className="w-full rounded-lg bg-surface px-3 py-2 text-sm text-text placeholder-text-muted ring-1 ring-input-border focus:outline-none focus:ring-danger resize-none transition-colors"
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
                    <label className="mb-1 block text-xs text-text-muted">Transfer type</label>
                    {/* FREE_TRANSFER and PRE_CONTRACT are derived by the signing
                        paths, not chosen — offering a two-way toggle for them
                        rendered with neither option selected, and retyping one
                        would contradict how the deal was created. */}
                    {dealDraft.deal_type === "PERMANENT" || dealDraft.deal_type === "LOAN" ? (
                      <div className="flex gap-2">
                        {(["PERMANENT", "LOAN"] as const).map((t) => (
                          <button
                            key={t}
                            type="button"
                            onClick={() => setDealDraft((d) => ({ ...d, deal_type: t }))}
                            className={`flex-1 rounded-lg px-3 py-1.5 text-xs font-semibold ring-1 transition-colors ${
                              dealDraft.deal_type === t
                                ? "bg-accent-bg text-accent-active ring-accent/40"
                                : "bg-surface-inset text-text-muted ring-border hover:text-text"
                            }`}
                          >
                            {dealTypeLabel(t)}
                          </button>
                        ))}
                      </div>
                    ) : (
                      <p className="text-sm text-text">{dealTypeLabel(dealDraft.deal_type as DealType)}</p>
                    )}
                  </div>
                  {dealDraft.deal_type === "LOAN" && (
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="mb-1 block text-xs text-text-muted">Loan start</label>
                        <input type="date" value={dealDraft.loan_start} onChange={(e) => setDealDraft((d) => ({ ...d, loan_start: e.target.value }))} className="w-full rounded-lg bg-surface px-3 py-1.5 text-sm text-text ring-1 ring-input-border focus:outline-none focus:ring-accent" />
                      </div>
                      <div>
                        <label className="mb-1 block text-xs text-text-muted">Loan end</label>
                        <input type="date" value={dealDraft.loan_end} onChange={(e) => setDealDraft((d) => ({ ...d, loan_end: e.target.value }))} className="w-full rounded-lg bg-surface px-3 py-1.5 text-sm text-text ring-1 ring-input-border focus:outline-none focus:ring-accent" />
                      </div>
                      <div>
                        <label className="mb-1 block text-xs text-text-muted">Loan fee (€)</label>
                        <CurrencyInput value={dealDraft.loan_fee} onChange={(v) => setDealDraft((d) => ({ ...d, loan_fee: v }))} className="w-full rounded-lg bg-surface px-3 py-1.5 text-sm text-text ring-1 ring-input-border focus:outline-none focus:ring-accent" />
                      </div>
                      <div>
                        <label className="mb-1 block text-xs text-text-muted">Option to buy (€)</label>
                        <CurrencyInput value={dealDraft.option_to_buy} onChange={(v) => setDealDraft((d) => ({ ...d, option_to_buy: v }))} className="w-full rounded-lg bg-surface px-3 py-1.5 text-sm text-text ring-1 ring-input-border focus:outline-none focus:ring-accent" />
                      </div>
                      <div className="col-span-2">
                        <label className="mb-1 block text-xs text-text-muted">Sell-on % (decimal, e.g. 0.05 = 5%)</label>
                        <input type="number" step="0.01" min={0} max={1} value={dealDraft.sell_on_pct} onChange={(e) => setDealDraft((d) => ({ ...d, sell_on_pct: e.target.value }))} className="w-full rounded-lg bg-surface px-3 py-1.5 text-sm text-text ring-1 ring-input-border focus:outline-none focus:ring-accent" />
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
                    <dt className="text-text-muted">Type</dt>
                    <dd className="text-text">{dealTypeLabel(deal.deal_type)}</dd>
                    {deal.loan_start && (
                      <><dt className="text-text-muted">Loan start</dt><dd className="text-text">{formatDate(deal.loan_start)}</dd></>
                    )}
                    {deal.loan_end && (
                      <><dt className="text-text-muted">Loan end</dt><dd className="text-text">{formatDate(deal.loan_end)}</dd></>
                    )}
                    {deal.loan_fee != null && (
                      <><dt className="text-text-muted">Loan fee</dt><dd className="text-text">{formatCurrency(deal.loan_fee)}</dd></>
                    )}
                    {deal.option_to_buy != null && (
                      <><dt className="text-text-muted">Option to buy</dt><dd className="text-text">{formatCurrency(deal.option_to_buy)}</dd></>
                    )}
                    {deal.obligation_to_buy && (
                      <><dt className="text-text-muted">Obligation to buy</dt><dd className="text-warning-text">Yes{deal.obligation_conditions ? ` — ${deal.obligation_conditions}` : ""}</dd></>
                    )}
                    {deal.sell_on_pct != null && (
                      <><dt className="text-text-muted">Sell-on %</dt><dd className="text-text">{(deal.sell_on_pct * 100).toFixed(1)}%</dd></>
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
                      className="mt-3 text-xs text-text-muted hover:text-accent transition-colors"
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
                    <div key={c.id} className="rounded-lg bg-surface-inset px-3 py-2.5 flex items-center justify-between gap-3">
                      <div className="min-w-0">
                        <p className="text-xs font-semibold text-text-secondary capitalize">
                          {c.clause_type.toLowerCase()} clause
                        </p>
                        <p className="text-xs text-text-muted truncate">{c.trigger_description}</p>
                      </div>
                      <div className="text-right shrink-0">
                        <p className="text-sm font-semibold text-text">{formatCurrency(c.amount)}</p>
                        {c.cap != null && (
                          <p className="text-[13px] text-text-muted">cap {formatCurrency(c.cap)}</p>
                        )}
                      </div>
                      <span className={`text-[11px] px-1.5 py-0.5 rounded font-semibold ${
                        c.status === "PAID"      ? "bg-success/15 text-success-text" :
                        c.status === "TRIGGERED" ? "bg-warning-fill/15 text-warning-text"    :
                                                    "bg-surface-inset text-text-muted"
                      }`}>{c.status}</span>
                    </div>
                  ))}
                </div>
              )}
              {canEditDealStructure && !addingClause && (
                <button
                  onClick={() => setAddingClause(true)}
                  className="text-xs text-text-muted hover:text-accent transition-colors"
                >
                  + Add clause
                </button>
              )}
              {addingClause && (
                <div className="rounded-lg bg-surface-inset px-4 py-3 ring-1 ring-border space-y-2">
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="mb-1 block text-xs text-text-muted">Type</label>
                      <select
                        value={clauseDraft.clause_type}
                        onChange={(e) => setClauseDraft((d) => ({ ...d, clause_type: e.target.value }))}
                        className="w-full rounded-lg bg-surface px-2.5 py-1.5 text-sm text-text ring-1 ring-input-border focus:outline-none focus:ring-accent"
                      >
                        {["APPEARANCES", "GOALS", "PROMOTION", "RESALE", "OTHER"].map((t) => (
                          <option key={t} value={t}>{t.charAt(0) + t.slice(1).toLowerCase()}</option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="mb-1 block text-xs text-text-muted">Amount (€)</label>
                      <CurrencyInput
                        value={clauseDraft.amount}
                        onChange={(v) => setClauseDraft((d) => ({ ...d, amount: v }))}
                        className="w-full rounded-lg bg-surface px-2.5 py-1.5 text-sm text-text ring-1 ring-input-border focus:outline-none focus:ring-accent"
                      />
                    </div>
                  </div>
                  <div>
                    <label className="mb-1 block text-xs text-text-muted">Trigger description</label>
                    <input
                      type="text"
                      value={clauseDraft.trigger_description}
                      onChange={(e) => setClauseDraft((d) => ({ ...d, trigger_description: e.target.value }))}
                      placeholder="e.g. Player makes 10+ appearances"
                      className="w-full rounded-lg bg-surface px-2.5 py-1.5 text-sm text-text placeholder-text-muted ring-1 ring-input-border focus:outline-none focus:ring-accent"
                    />
                  </div>
                  <div>
                    <label className="mb-1 block text-xs text-text-muted">Cap (€, optional)</label>
                    <CurrencyInput
                      value={clauseDraft.cap}
                      onChange={(v) => setClauseDraft((d) => ({ ...d, cap: v }))}
                      className="w-full rounded-lg bg-surface px-2.5 py-1.5 text-sm text-text ring-1 ring-input-border focus:outline-none focus:ring-accent"
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
                      <span className="text-text-muted">{formatDate(inst.due_date)}</span>
                      <span className="font-semibold text-text">{formatCurrency(inst.amount)}</span>
                      <span className={inst.paid ? "text-success-text text-xs" : "text-text-muted text-xs"}>
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
                  className="text-xs text-text-muted hover:text-accent transition-colors"
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
                        className="flex-1 rounded-lg bg-surface px-2.5 py-1.5 text-sm text-text ring-1 ring-input-border focus:outline-none focus:ring-accent"
                      />
                      <CurrencyInput
                        placeholder="Amount (€)"
                        value={row.amount}
                        onChange={(v) => setInstalmentRows((rows) => rows.map((r, j) => j === i ? { ...r, amount: v } : r))}
                        className="flex-1 rounded-lg bg-surface px-2.5 py-1.5 text-sm text-text placeholder-text-muted ring-1 ring-input-border focus:outline-none focus:ring-accent"
                      />
                      <button
                        onClick={() => setInstalmentRows((rows) => rows.filter((_, j) => j !== i))}
                        className="px-1 text-text-muted hover:text-danger-text transition-colors text-xs"
                        title="Remove"
                      >
                        ✕
                      </button>
                    </div>
                  ))}
                  <div className="text-xs text-text-muted pt-1">
                    Total: <span className="text-text font-semibold">{formatCurrency(instalmentRows.reduce((s, r) => s + (Number(r.amount) || 0), 0))}</span>
                    {" / "}
                    <span className="text-text-secondary">{formatCurrency(deal.agreed_fee)} agreed fee</span>
                  </div>
                  <div className="flex items-center gap-3 flex-wrap pt-1">
                    <button
                      onClick={() => setInstalmentRows((rows) => [...rows, { due_date: "", amount: "" }])}
                      className="text-xs text-text-muted hover:text-accent transition-colors"
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
                  <><dt className="text-text-muted">Commission %</dt><dd className="text-text">{(deal.agent_commission_pct * 100).toFixed(2)}%</dd></>
                )}
                {deal.agent_commission_amount != null && (
                  <><dt className="text-text-muted">Commission amount</dt><dd className="text-text">{formatCurrency(deal.agent_commission_amount)}</dd></>
                )}
                {deal.commission_payer && (
                  <><dt className="text-text-muted">Paid by</dt><dd className="text-text capitalize">{deal.commission_payer.toLowerCase()}</dd></>
                )}
              </dl>
            </Panel>
          ) : null}

          {/* Personal terms consent status (TRA-60) */}
          {deal.personal_terms ? (
            <Panel title="Personal Terms">
              <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
                {deal.personal_terms.wage_weekly != null && (
                  <><dt className="text-text-muted">Proposed wage</dt><dd className="text-text">{formatWage(deal.personal_terms.wage_weekly)}</dd></>
                )}
                {deal.personal_terms.signing_bonus != null && (
                  <><dt className="text-text-muted">Signing bonus</dt><dd className="text-text">{formatCurrency(deal.personal_terms.signing_bonus)}</dd></>
                )}
                {deal.personal_terms.length_years != null && (
                  <><dt className="text-text-muted">Contract length</dt><dd className="text-text">{deal.personal_terms.length_years} yr{deal.personal_terms.length_years !== 1 ? "s" : ""}</dd></>
                )}
                <dt className="text-text-muted">Player consent</dt>
                <dd className={
                  deal.personal_terms.player_consent === "AGREED"   ? "text-success-text font-semibold" :
                  deal.personal_terms.player_consent === "DECLINED" ? "text-danger-text font-semibold"     :
                                                                        "text-warning-text"
                }>{deal.personal_terms.player_consent}</dd>
              </dl>
              {isAgent && deal.personal_terms.player_consent === "PENDING" && !deal.personal_terms.player_has_account && (
                <div className="mt-3">
                  <p className="mb-1.5 text-[11px] text-text-muted">
                    Player has no account yet — you may respond on their behalf
                  </p>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="primary"
                      size="sm"
                      loading={personalTermsConsentMutation.isPending}
                      onClick={() => personalTermsConsentMutation.mutate("AGREED")}
                    >
                      Accept for player
                    </Button>
                    <Button
                      variant="danger"
                      size="sm"
                      loading={personalTermsConsentMutation.isPending}
                      onClick={() => personalTermsConsentMutation.mutate("DECLINED")}
                    >
                      Decline for player
                    </Button>
                  </div>
                </div>
              )}
            </Panel>
          ) : canSetPersonalTerms && id ? (
            <SetPersonalTermsForm dealId={id} />
          ) : null}

          {/* Medical check (TRA-61) — staff sets it; every participant can see it */}
          {id && <MedicalCheckPanel dealId={id} medicalCheck={deal.medical_check} isStaff={isStaff} />}

          <Panel title="Deal Notes">
            {deal.deal_notes.length === 0 ? (
              <p className="text-sm text-text-muted pb-2">No notes yet.</p>
            ) : (
              <div className="space-y-3 mb-4">
                {deal.deal_notes.map((note) => (
                  <div
                    key={note.id}
                    className="rounded-lg bg-surface-inset px-4 py-3"
                  >
                    <div className="flex items-center justify-between mb-1">
                      <p className="text-xs font-semibold text-text-secondary">
                        {note.author_club?.name ?? "System"}
                      </p>
                      <p className="text-[13px] text-text-muted">
                        {formatDate(note.created_at)}
                      </p>
                    </div>
                    <p className="text-sm text-text-secondary">{note.body}</p>
                  </div>
                ))}
              </div>
            )}
            {isParty && isActive && canDealWrite && <NoteForm dealId={deal.id} />}
          </Panel>

          <Panel title="Activity Timeline">
            <DealTimeline dealId={deal.id} />
          </Panel>
        </div>
      </div>

      {/* Deal room: message rail + documents (TRA-81/82) */}
      {(isParty || isAgent || isPlayer) && id && (
        <DealRoomPanel
          dealId={id}
          canWrite={!isParty || canDealWrite}
          viewerSide={viewerSide}
          negotiationId={atAgentNegotiation && negotiation ? negotiation.id : null}
          myClubName={myClubName}
          theirClubName={theirClubName}
        />
      )}
    </div>
  );
}

// ── Deal timeline (real audit log — visible to every deal participant) ────────

const AUDIT_DOT: Record<string, "success" | "accent" | "danger"> = {
  DEAL_CREATED: "success",
  DEAL_COMPLETED: "success",
  DEAL_COLLAPSED: "danger",
};

function DealTimeline({ dealId }: { dealId: string }) {
  const { data: events = [], isLoading } = useQuery<import("../../types/api").AuditEvent[]>({
    queryKey: ["deals", dealId, "audit-log"],
    queryFn: () => api.get(`/deals/${dealId}/audit-log`).then((r) => r.data),
  });

  const dotClass: Record<"success" | "accent" | "danger", string> = {
    success: "bg-success",
    accent:  "bg-accent",
    danger:  "bg-danger",
  };

  if (isLoading) {
    return <Spinner size="sm" />;
  }
  if (events.length === 0) {
    return <p className="text-sm text-text-muted">No activity yet.</p>;
  }

  return (
    <div className="relative pl-4">
      {/* Vertical line */}
      <div className="absolute left-[7px] top-2 bottom-2 w-px bg-rule" />

      <div className="space-y-5">
        {events.map((ev) => (
          <div key={ev.id} className="relative flex gap-3">
            <div className={`mt-1 h-3 w-3 shrink-0 rounded-full ring-2 ring-surface ${dotClass[AUDIT_DOT[ev.action] ?? "accent"]}`} />
            <div className="min-w-0">
              <div className="flex items-baseline gap-2">
                <span className="text-sm font-medium text-text">{ev.description ?? ev.action}</span>
                <span className="text-[13px] text-text-muted shrink-0">
                  {new Date(ev.created_at).toLocaleString("en-GB", {
                    day: "numeric", month: "short", year: "numeric",
                    hour: "2-digit", minute: "2-digit",
                  })}
                </span>
              </div>
              {ev.actor_label && (
                <p className="mt-0.5 text-xs text-text-muted">{ev.actor_label}</p>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
