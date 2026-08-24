import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "../../lib/api";
import type { Loan } from "../../types/api";
import Button from "../ui/Button";
import { formatCurrency, getApiError } from "../../lib/utils";

/** Players this club owns who are away on loan.
 *
 *  They are deliberately absent from the squad table: during a loan the
 *  *loanee* holds the registration, so `current_club_id` is theirs and the
 *  squad endpoint correctly does not return them. Without this panel a player
 *  out on loan would simply vanish from the club that owns him.
 */
export default function LoansPanel({ canAct }: { canAct: boolean }) {
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [confirming, setConfirming] = useState<string | null>(null);

  const { data: loans = [] } = useQuery<Loan[]>({
    queryKey: ["clubs", "me", "loans", "out"],
    queryFn: () => api.get<Loan[]>("/clubs/me/loans?direction=out").then((r) => r.data),
    staleTime: 60_000,
  });

  const recall = useMutation({
    mutationFn: (loanId: string) => api.post(`/loans/${loanId}/recall`),
    onSuccess: () => {
      setConfirming(null);
      setError(null);
      // The player rejoins the squad, and his wage comes back onto the books.
      queryClient.invalidateQueries({ queryKey: ["clubs", "me", "loans", "out"] });
      queryClient.invalidateQueries({ queryKey: ["clubs"] });
    },
    onError: (e) => setError(getApiError(e)),
  });

  if (loans.length === 0) return null;

  return (
    <div className="mt-6">
      <div className="mb-2.5 flex items-baseline justify-between">
        <h3 className="text-sm font-semibold text-text">Out on loan</h3>
        <span className="text-[13px] text-text-muted">
          {loans.length} {loans.length === 1 ? "player" : "players"}
        </span>
      </div>

      {error && (
        <p className="mb-2.5 rounded-lg bg-danger-bg px-3 py-2 text-[13px] text-danger-text ring-1 ring-danger-border">
          {error}
        </p>
      )}

      <div className="space-y-2">
        {loans.map((loan) => (
          <div
            key={loan.id}
            className="flex flex-wrap items-center gap-4 rounded-xl bg-surface px-5 py-3.5 ring-1 ring-border"
          >
            <div className="flex-1 basis-[180px] min-w-0">
              <Link
                to={`/players/market/${loan.player_id}`}
                className="text-[15px] font-semibold text-text transition-colors hover:text-accent"
              >
                {loan.player?.name ?? "Player"}
              </Link>
              <p className="text-[13px] text-text-muted">
                at {loan.loanee_club?.name ?? "another club"}
              </p>
            </div>

            <div className="basis-[130px] shrink">
              <p className="text-[11px] text-text-muted">Returns</p>
              <p className="text-sm font-semibold text-text">
                {new Date(loan.end_date).toLocaleDateString("en-GB", {
                  day: "numeric", month: "short", year: "numeric",
                })}
              </p>
            </div>

            {/* What this loan is still costing us. The parent keeps paying
                whatever share it did not hand over, so a 100% split shows
                nothing rather than a misleading £0 line. */}
            <div className="basis-[120px] shrink">
              <p className="text-[11px] text-text-muted">They pay</p>
              <p className="text-sm font-semibold text-text tabular-nums">
                {loan.loanee_wage_share > 0
                  ? `${formatCurrency(loan.loanee_wage_share)}/wk`
                  : "—"}
              </p>
            </div>

            <div className="flex shrink-0 items-center gap-2">
              {loan.option_to_buy != null && (
                <span
                  className="rounded-full bg-surface-inset px-2 py-0.5 text-[13px] font-semibold text-text-secondary ring-1 ring-input-border"
                  title={
                    loan.obligation_to_buy
                      ? `They must buy him for ${formatCurrency(loan.option_to_buy)} when the loan ends`
                      : `They may buy him for ${formatCurrency(loan.option_to_buy)}`
                  }
                >
                  {loan.obligation_to_buy ? "Obligation" : "Option"} {formatCurrency(loan.option_to_buy)}
                </span>
              )}

              {canAct && loan.recall_allowed && (
                confirming === loan.id ? (
                  <span className="flex items-center gap-1.5">
                    <Button
                      variant="danger"
                      size="sm"
                      onClick={() => recall.mutate(loan.id)}
                      disabled={recall.isPending}
                    >
                      {recall.isPending ? "Recalling…" : "Confirm recall"}
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => setConfirming(null)}>
                      Cancel
                    </Button>
                  </span>
                ) : (
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => { setError(null); setConfirming(loan.id); }}
                    title="End the loan early and bring him back now"
                  >
                    Recall
                  </Button>
                )
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
