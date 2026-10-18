import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import api from "../../lib/api";
import type { Deal } from "../../types/api";
import Button from "../ui/Button";
import { useAskReason } from "../../context/ConfirmContext";
import { useToast } from "../../context/ToastContext";
import { formatDateTime, getApiError } from "../../lib/utils";

/**
 * TransferX staff stepping into a stuck deal (backend admin/deal_tools.py).
 * Each tool goes through the deal's own rules, asks why, is in the admin
 * audit log, and tells both clubs what staff did and why. Shown on the deal
 * page to staff only.
 */

type Tool = "advance" | "paperwork" | "medical" | "deadline" | "complete" | "collapse";

const PAPERWORK_FOR: Record<string, { step: string; label: string }> = {
  agreement_buyer: { step: "buyer_signs_agreement", label: "Buying club signed the agreement" },
  agreement_seller: { step: "seller_signs_agreement", label: "Selling club signed the agreement" },
  registration: { step: "registration_submitted", label: "Registration submitted" },
};

function toLocalInput(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export default function DealStaffTools({ deal }: { deal: Deal }) {
  const queryClient = useQueryClient();
  const askReason = useAskReason();
  const { addToast } = useToast();
  const [until, setUntil] = useState(() => toLocalInput(new Date(Date.now() + 7 * 86_400_000)));

  const run = useMutation({
    mutationFn: ({ tool, body }: { tool: Tool; body: Record<string, unknown> }) =>
      api.post(`/admin/deals/${deal.id}/${tool}`, body).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["deals", deal.id] });
      queryClient.invalidateQueries({ queryKey: ["admin", "deals"] });
      addToast("Done. Both clubs have been told why.", "success");
    },
    onError: (err) => addToast(getApiError(err, "That couldn't be done."), "error"),
  });

  const open = deal.status === "IN_PROGRESS" || deal.status === "PENDING_COMPLETION";
  if (!open) {
    return (
      <div className="rounded-xl bg-surface-inset px-4 py-3 text-sm text-text-muted ring-1 ring-border">
        Staff tools: this deal is {deal.status.toLowerCase().replace("_", " ")}, so there&rsquo;s nothing to change.
      </div>
    );
  }

  async function act(tool: Tool, title: string, message: string, confirmLabel: string, body: Record<string, unknown> = {}, danger = false) {
    const reason = await askReason({
      title, message: `${message} Both clubs are told, with your reason, and it's in the audit log.`,
      reasonLabel: "Why?", placeholder: "e.g. Both clubs confirmed by phone", confirmLabel, danger,
    });
    if (reason) run.mutate({ tool, body: { ...body, reason } });
  }

  const outstanding = deal.stage === "PAPERWORK"
    ? deal.paperwork.filter((s) => !s.done && s.key !== "medical" && PAPERWORK_FOR[s.key])
    : [];
  const medicalOpen = deal.stage === "PAPERWORK" || deal.stage === "CONFIRMED";
  const awaitingCompletion = deal.status === "PENDING_COMPLETION";

  return (
    <section aria-label="Staff tools" className="rounded-xl bg-surface p-4 ring-1 ring-warning-fill/40">
      <p className="text-xs font-semibold uppercase tracking-wider text-warning-text">Staff tools</p>
      <p className="mt-1 text-sm text-text-secondary">
        For a deal that has stuck. Each step follows the deal&rsquo;s own rules and needs a reason.
      </p>

      <div className="mt-3 flex flex-col gap-3 text-sm">
        {deal.stage !== "PAPERWORK" && deal.stage !== "CONFIRMED" && (
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="text-text">Move the deal on a stage</span>
            <Button size="sm" variant="secondary" disabled={run.isPending}
              onClick={() => act("advance", "Move this deal on", "The deal moves to its next stage for both clubs.", "Move on")}>
              Move on
            </Button>
          </div>
        )}

        {outstanding.length > 0 && (
          <div>
            <p className="text-text">Record paperwork for a club</p>
            <div className="mt-1.5 flex flex-wrap gap-2">
              {outstanding.map((s) => (
                <Button key={s.key} size="sm" variant="secondary" disabled={run.isPending}
                  onClick={() => act("paperwork", PAPERWORK_FOR[s.key].label,
                    `Tick "${s.label}" for the ${s.owner === "buyer" ? "buying" : "selling"} club, as if it had done it.`,
                    "Record it", { step: PAPERWORK_FOR[s.key].step })}>
                  {PAPERWORK_FOR[s.key].label}
                </Button>
              ))}
            </div>
          </div>
        )}

        {medicalOpen && (
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="text-text">
              Medical{deal.medical_check ? `: ${deal.medical_check.status.toLowerCase()}` : ": not recorded"}
            </span>
            <span className="flex gap-2">
              <Button size="sm" variant="secondary" disabled={run.isPending}
                onClick={() => act("medical", "Record the medical as passed", "A pass can finish the paperwork.", "Record pass", { outcome: "PASSED" })}>
                Passed
              </Button>
              <Button size="sm" variant="danger" disabled={run.isPending}
                onClick={() => act("medical", "Record the medical as failed", "A failed medical blocks the deal.", "Record fail", { outcome: "FAILED" }, true)}>
                Failed
              </Button>
            </span>
          </div>
        )}

        {awaitingCompletion && (
          <div>
            <p className="text-text">
              Completion deadline{deal.sla_deadline ? `: ${formatDateTime(deal.sla_deadline)}` : ""}
            </p>
            <div className="mt-1.5 flex flex-wrap items-center gap-2">
              <input
                type="datetime-local"
                aria-label="New completion deadline"
                value={until}
                onChange={(e) => setUntil(e.target.value)}
                className="rounded-lg bg-surface px-2 py-1.5 text-sm text-text ring-1 ring-input-border"
              />
              <Button size="sm" variant="secondary" disabled={run.isPending || !until}
                onClick={() => act("deadline", "Move the completion deadline", `The new deadline is ${new Date(until).toLocaleString("en-GB")}.`,
                  "Move deadline", { until: new Date(until).toISOString() })}>
                Move deadline
              </Button>
            </div>
          </div>
        )}

        <div className="flex flex-wrap gap-2 border-t border-rule pt-3">
          <Button size="sm" variant="secondary" disabled={run.isPending}
            onClick={() => act("complete", "Complete this transfer",
              "The fee settles and the player joins the buying club now, skipping any steps left. Use it only when they happened outside TransferX. This can't be undone.",
              "Complete transfer", {}, true)}>
            Complete transfer
          </Button>
          <Button size="sm" variant="danger" disabled={run.isPending}
            onClick={() => act("collapse", "Collapse this deal",
              "The deal ends for both clubs. The buyer's committed budget is released and any listing it came from reopens. This can't be undone.",
              "Collapse deal", {}, true)}>
            Collapse deal
          </Button>
        </div>
      </div>
    </section>
  );
}
