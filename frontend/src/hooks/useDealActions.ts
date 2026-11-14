import { useMutation, useQueryClient } from "@tanstack/react-query";
import api from "../lib/api";
import type { Deal } from "../types/api";
import { useToast } from "../context/ToastContext";
import { getApiError } from "../lib/utils";

export type MedicalStatus = "PENDING" | "PASSED" | "FAILED";
export interface PersonalTermsValues { wage_weekly: number | null; signing_bonus: number | null; length_years: number | null; note?: string | null }
/** An answer; a decline ends the transfer, with an optional reason the other side sees. */
export interface Answer { agreement: "AGREED" | "DECLINED"; reason?: string | null }
export interface CommissionCounter { commission_pct: number; commission_payer: "BUYER" | "SELLER" | "PLAYER"; note?: string | null }

/**
 * Every write on a deal, in one place (deal-room-focus §5.8). Moved from the
 * deal page and its inline components unchanged: the same endpoints,
 * payloads, invalidations and toasts.
 */
export function useDealActions(dealId: string | undefined, opts: { onDone?: () => void } = {}) {
  const queryClient = useQueryClient();
  const { addToast } = useToast();
  const done = () => opts.onDone?.();

  const advance = useMutation({
    mutationFn: () => api.post<Deal>(`/deals/${dealId}/advance`).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["deals", dealId] });
      addToast("Deal advanced to next stage.", "success");
      done();
    },
    onError: (err) => addToast(getApiError(err, "Failed to advance deal."), "error"),
  });

  const collapse = useMutation({
    mutationFn: (reason?: string) =>
      api.post<Deal>(`/deals/${dealId}/collapse`, { reason: reason?.trim() || null }).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["deals", dealId] });
      queryClient.invalidateQueries({ queryKey: ["deals"] });
      addToast("Deal collapsed.", "warning");
      done();
    },
    onError: (err) => addToast(getApiError(err, "Failed to collapse deal."), "error"),
  });

  const paperwork = useMutation({
    mutationFn: (step: "sign-agreement" | "submit-registration") =>
      api.post<Deal>(`/deals/${dealId}/paperwork/${step}`).then((r) => r.data),
    onSuccess: (updated) => {
      queryClient.invalidateQueries({ queryKey: ["deals"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      addToast(
        updated.stage === "CONFIRMED" ? "Paperwork complete — the transfer is ready to execute." : "Done.",
        "success",
      );
      done();
    },
    onError: (err: unknown) => addToast(getApiError(err, "Could not complete that step."), "error"),
  });

  const recordMedical = useMutation({
    mutationFn: (v: { status: MedicalStatus; notes: string | null }) =>
      api.put(`/deals/${dealId}/medical-check`, v).then((r) => r.data),
    onSuccess: (_, v) => {
      // A passed medical can be the step that completes the paperwork and
      // confirms the deal, so refresh everything that shows its stage.
      queryClient.invalidateQueries({ queryKey: ["deals"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      const choice = { PASSED: "passed", FAILED: "failed", PENDING: "still in progress" }[v.status];
      addToast(`Medical recorded: ${choice}.`, "success");
      done();
    },
    onError: (err: unknown) => addToast(getApiError(err, "Failed to save medical check."), "error"),
  });

  const commissionRespond = useMutation({
    mutationFn: (a: Answer) =>
      api.post(`/deals/${dealId}/agent-negotiation/club-respond`, a).then((r) => r.data),
    onSuccess: (_, a) => {
      queryClient.invalidateQueries({ queryKey: ["deals", dealId] });
      addToast(a.agreement === "AGREED" ? "Proposal accepted." : "Declined. The transfer has ended.", a.agreement === "AGREED" ? "success" : "warning");
      done();
    },
    onError: (err: unknown) => addToast(getApiError(err, "Failed to respond."), "error"),
  });

  // ADR 0012: the buying club counters the agent's commission; the agent
  // accepts the counter or proposes again.
  const commissionCounter = useMutation({
    mutationFn: (v: CommissionCounter) =>
      api.post(`/deals/${dealId}/agent-negotiation/club-counter`, v).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["deals", dealId] });
      addToast("Counter sent to the agent.", "success");
      done();
    },
    onError: (err: unknown) => addToast(getApiError(err, "Failed to send the counter."), "error"),
  });

  const agentAccept = useMutation({
    mutationFn: () => api.post(`/deals/${dealId}/agent-negotiation/agent-accept`).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["deals", dealId] });
      addToast("Counter accepted. The commission is agreed.", "success");
      done();
    },
    onError: (err: unknown) => addToast(getApiError(err, "Failed to accept."), "error"),
  });

  // The buying club answering the player side's terms.
  const termsRespond = useMutation({
    mutationFn: (a: Answer) => api.post(`/deals/${dealId}/personal-terms/club-respond`, a).then((r) => r.data),
    onSuccess: (_, a) => {
      queryClient.invalidateQueries({ queryKey: ["deals", dealId] });
      addToast(a.agreement === "AGREED" ? "Terms agreed." : "Declined. The transfer has ended.", a.agreement === "AGREED" ? "success" : "warning");
      done();
    },
    onError: (err: unknown) => addToast(getApiError(err, "Failed to respond."), "error"),
  });

  const setPersonalTerms = useMutation({
    mutationFn: (v: PersonalTermsValues) => api.put(`/deals/${dealId}/personal-terms`, v).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["deals", dealId] });
      addToast("Personal terms sent.", "success");
      done();
    },
    onError: (err: unknown) => addToast(getApiError(err, "Failed to set personal terms."), "error"),
  });

  // Responding for a player with no account: his mandated agent, or the
  // buying club when he has no agent either.
  const playerConsent = useMutation({
    mutationFn: (a: Answer) =>
      api.post(`/deals/${dealId}/personal-terms/player-consent`, a).then((r) => r.data),
    onSuccess: (_, { agreement }) => {
      queryClient.invalidateQueries({ queryKey: ["deals", dealId] });
      addToast(
        agreement === "AGREED" ? "Accepted on behalf of the player." : "Declined on behalf of the player.",
        agreement === "AGREED" ? "success" : "warning",
      );
      done();
    },
    onError: (err: unknown) => addToast(getApiError(err, "Failed to respond."), "error"),
  });

  // The buying club recording a player's agreement (ADR 0006) attaches the
  // signed terms: uploaded to its private deal-room channel, then referenced
  // by the consent so the record rests on a document, not the club's word.
  const recordAgreement = useMutation({
    mutationFn: async (file: File) => {
      const form = new FormData();
      form.append("file", file);
      form.append("audience", "BUYER_ONLY");
      const { data: attachment } = await api.post<{ id: string }>(`/deals/${dealId}/attachments`, form);
      return api.post(`/deals/${dealId}/personal-terms/player-consent`, {
        agreement: "AGREED",
        evidence_attachment_id: attachment.id,
      }).then((r) => r.data);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["deals", dealId] });
      addToast("Agreement recorded with the signed terms.", "success");
      done();
    },
    onError: (err: unknown) => addToast(getApiError(err, "Could not record the agreement."), "error"),
  });

  return {
    advance, collapse, paperwork, recordMedical, commissionRespond, commissionCounter, agentAccept,
    setPersonalTerms, termsRespond, playerConsent, recordAgreement,
  };
}

export type DealActions = ReturnType<typeof useDealActions>;
