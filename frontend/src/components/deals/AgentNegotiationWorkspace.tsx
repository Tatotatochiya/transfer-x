import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import api from "../../lib/api";
import type { AgentNegotiation } from "../../types/api";
import Button from "../ui/Button";
import CurrencyInput from "../ui/CurrencyInput";
import NegotiationMessageThread from "./NegotiationMessageThread";
import { useToast } from "../../context/ToastContext";
import { formatCurrency, getApiError } from "../../lib/utils";

// ── Agreement status chip ─────────────────────────────────────────────────────

function AgreementChip({ label, status }: { label: string; status: string }) {
  const color =
    status === "AGREED"   ? "bg-success/15 text-success-text ring-success/30" :
    status === "DECLINED" ? "bg-danger/15 text-danger-text ring-danger/30"     :
                             "bg-surface-inset text-text-muted ring-border";
  return (
    <span className={`flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ${color}`}>
      {label}: {status === "AGREED" ? "agreed" : status === "DECLINED" ? "declined" : "waiting"}
    </span>
  );
}

// ── Agent negotiation workspace (TRA-128) ─────────────────────────────────────

/**
 * The agent's commission workspace at AGENT_NEGOTIATION (TRA-128): the terms
 * he proposes and the club-side thread. Moving the deal on lives in the
 * status card now (deal-room-focus row 19).
 */
export default function AgentNegotiationWorkspace({
  dealId,
  negotiation,
}: {
  dealId: string;
  negotiation: AgentNegotiation | null;
}) {
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
    <div>
      <div className="mb-3 flex items-center justify-between">
        <p className="text-xs font-semibold uppercase tracking-wider text-role-agent-text">
          Negotiation Workspace
        </p>
        <AgreementChip label="Club" status={negotiation?.club_agreement ?? "PENDING"} />
      </div>

      <div className="rounded-xl bg-surface-inset px-5 py-4 ring-1 ring-border">
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

      {/* Workspace footer: edit controls */}
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
      </div>
    </div>
  );
}

