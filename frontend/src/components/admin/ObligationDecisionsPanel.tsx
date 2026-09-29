import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import api from "../../lib/api";
import { formatCurrency, formatDate, getApiError } from "../../lib/utils";
import { useConfirm } from "../../context/ConfirmContext";
import type { Loan } from "../../types/api";
import Button from "../ui/Button";

const WORD: Record<string, string> = { MET: "met", NOT_MET: "not met" };

/**
 * Conditional obligations to buy that the two clubs could not settle — past
 * the loan's end, with an answer missing or the clubs disagreeing (loan spec
 * deviation 30). TransferX decides: met starts the purchase, not met returns
 * the player. The reason is shown to both clubs and kept in the audit.
 */
export default function ObligationDecisionsPanel() {
  const queryClient = useQueryClient();
  const confirm = useConfirm();
  const [reasons, setReasons] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);

  const { data: loans = [] } = useQuery<Loan[]>({
    queryKey: ["admin", "loans", "obligations-awaiting"],
    queryFn: () => api.get<Loan[]>("/admin/loans/obligations-awaiting").then((r) => r.data),
  });

  const decide = useMutation({
    mutationFn: ({ id, met }: { id: string; met: boolean }) =>
      api.post(`/admin/loans/${id}/obligation-decision`, { met, reason: reasons[id] ?? "" }).then((r) => r.data),
    onSuccess: () => {
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["admin", "loans", "obligations-awaiting"] });
    },
    onError: (e) => setError(getApiError(e, "Could not record the decision.")),
  });

  if (loans.length === 0) return null;

  return (
    <div className="mb-6 rounded-xl bg-warning-bg px-5 py-4 ring-1 ring-warning-fill/20">
      <p className="text-sm font-semibold text-warning-text">
        Conditional obligations awaiting a decision ({loans.length})
      </p>
      <p className="mt-0.5 text-[13px] text-warning-text/80">
        These loans have ended, and the clubs have not both confirmed whether the obligation&rsquo;s conditions were
        met. Your decision is final: met starts the purchase, not met returns the player.
      </p>
      {error && <p className="mt-2 text-xs text-danger-text">{error}</p>}
      <ul className="mt-3 space-y-3">
        {loans.map((loan) => (
          <li key={loan.id} className="rounded-lg bg-surface px-4 py-3 ring-1 ring-border">
            <p className="text-sm text-text">
              <span className="font-semibold">{loan.player?.name ?? "Player"}</span> — {loan.parent_club?.name} → {loan.loanee_club?.name},
              ended {formatDate(loan.end_date)}, obligation {formatCurrency(loan.option_to_buy)}
            </p>
            <p className="mt-0.5 text-[13px] text-text-secondary">Conditions: {loan.obligation_conditions}</p>
            <p className="mt-0.5 text-[13px] text-text-muted">
              {loan.parent_club?.name}: {WORD[loan.parent_obligation_answer ?? ""] ?? "no answer"} ·{" "}
              {loan.loanee_club?.name}: {WORD[loan.loanee_obligation_answer ?? ""] ?? "no answer"}
            </p>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <input
                value={reasons[loan.id] ?? ""}
                onChange={(e) => setReasons((r) => ({ ...r, [loan.id]: e.target.value }))}
                placeholder="Reason (both clubs see it)"
                className="min-w-0 flex-1 rounded-lg bg-surface px-3 py-1.5 text-sm text-text ring-1 ring-input-border focus:outline-none focus:ring-accent"
              />
              {([true, false] as const).map((met) => (
                <Button
                  key={String(met)}
                  size="sm"
                  variant={met ? "primary" : "danger"}
                  disabled={!(reasons[loan.id] ?? "").trim() || decide.isPending}
                  onClick={async () => {
                    const ok = await confirm({
                      title: met ? "Decide the conditions were met?" : "Decide the conditions were not met?",
                      message: met
                        ? `The purchase of ${loan.player?.name ?? "the player"} starts now. Both clubs are told why.`
                        : `The loan ends and ${loan.player?.name ?? "the player"} returns to ${loan.parent_club?.name ?? "his club"}. Both clubs are told why.`,
                      confirmLabel: met ? "Start the purchase" : "Return him",
                      variant: met ? "primary" : "danger",
                    });
                    if (ok) decide.mutate({ id: loan.id, met });
                  }}
                >
                  {met ? "Met" : "Not met"}
                </Button>
              ))}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
