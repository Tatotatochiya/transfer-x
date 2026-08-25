import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "../../lib/api";
import type { Loan } from "../../types/api";
import Button from "../ui/Button";
import { formatCurrency, getApiError } from "../../lib/utils";

/** Loans this club is a party to, in both directions.
 *
 *  **Out** — players we own who are away. They are deliberately absent from
 *  the squad table: during a loan the *loanee* holds the registration, so
 *  `current_club_id` is theirs and the squad endpoint correctly does not
 *  return them. Without this panel a player out on loan would simply vanish
 *  from the club that owns him.
 *
 *  **In** — players we have borrowed. They *are* in the squad (with an "On
 *  loan" chip and no sell affordance), so this group exists for one thing the
 *  squad row cannot carry: exercising an option to buy.
 */
export default function LoansPanel({ canAct }: { canAct: boolean }) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);
  const [confirming, setConfirming] = useState<string | null>(null);

  const { data: out = [] } = useQuery<Loan[]>({
    queryKey: ["clubs", "me", "loans", "out"],
    queryFn: () => api.get<Loan[]>("/clubs/me/loans?direction=out").then((r) => r.data),
    staleTime: 60_000,
  });
  const { data: incoming = [] } = useQuery<Loan[]>({
    queryKey: ["clubs", "me", "loans", "in"],
    queryFn: () => api.get<Loan[]>("/clubs/me/loans?direction=in").then((r) => r.data),
    staleTime: 60_000,
  });

  function invalidate() {
    setConfirming(null);
    setError(null);
    queryClient.invalidateQueries({ queryKey: ["clubs", "me", "loans", "out"] });
    queryClient.invalidateQueries({ queryKey: ["clubs", "me", "loans", "in"] });
    queryClient.invalidateQueries({ queryKey: ["clubs"] });
  }

  const recall = useMutation({
    mutationFn: (loanId: string) => api.post(`/loans/${loanId}/recall`),
    onSuccess: invalidate,
    onError: (e) => setError(getApiError(e)),
  });

  const exercise = useMutation({
    mutationFn: (loanId: string) =>
      api.post<Loan>(`/loans/${loanId}/exercise-option`).then((r) => r.data),
    onSuccess: (loan) => {
      invalidate();
      // The purchase is an ordinary deal from here — budget, medical,
      // paperwork — so send them to it rather than implying it is done.
      if (loan.conversion_deal_id) navigate(`/deals/${loan.conversion_deal_id}`);
    },
    onError: (e) => setError(getApiError(e)),
  });

  if (out.length === 0 && incoming.length === 0) return null;

  function returnDate(loan: Loan) {
    return new Date(loan.end_date).toLocaleDateString("en-GB", {
      day: "numeric", month: "short", year: "numeric",
    });
  }

  function optionChip(loan: Loan) {
    if (loan.option_to_buy == null) return null;
    return (
      <span
        className="rounded-full bg-surface-inset px-2 py-0.5 text-[13px] font-semibold text-text-secondary ring-1 ring-input-border"
        title={
          loan.obligation_to_buy
            ? `Must be bought for ${formatCurrency(loan.option_to_buy)} when the loan ends`
            : `May be bought for ${formatCurrency(loan.option_to_buy)}`
        }
      >
        {loan.obligation_to_buy ? "Obligation" : "Option"} {formatCurrency(loan.option_to_buy)}
      </span>
    );
  }

  return (
    <div className="mt-6 space-y-6">
      {error && (
        <p className="rounded-lg bg-danger-bg px-3 py-2 text-[13px] text-danger-text ring-1 ring-danger-border">
          {error}
        </p>
      )}

      {out.length > 0 && (
        <div>
          <div className="mb-2.5 flex items-baseline justify-between">
            <h3 className="text-sm font-semibold text-text">Out on loan</h3>
            <span className="text-[13px] text-text-muted">
              {out.length} {out.length === 1 ? "player" : "players"}
            </span>
          </div>
          <div className="space-y-2">
            {out.map((loan) => (
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
                  <p className="text-sm font-semibold text-text">{returnDate(loan)}</p>
                </div>

                {/* What this loan is still costing us. The parent keeps paying
                    whatever share it did not hand over, so a 100% split shows
                    a dash rather than a misleading £0. */}
                <div className="basis-[120px] shrink">
                  <p className="text-[11px] text-text-muted">They pay</p>
                  <p className="text-sm font-semibold text-text tabular-nums">
                    {loan.loanee_wage_share > 0
                      ? `${formatCurrency(loan.loanee_wage_share)}/wk`
                      : "—"}
                  </p>
                </div>

                <div className="flex shrink-0 items-center gap-2">
                  {optionChip(loan)}

                  {/* Once a purchase is running, that is the state that matters
                      — and recalling him would contradict a sale in progress. */}
                  {loan.conversion_deal_id ? (
                    <Link
                      to={`/deals/${loan.conversion_deal_id}`}
                      className="text-[13px] font-semibold text-accent no-underline hover:underline"
                    >
                      Being bought →
                    </Link>
                  ) : (
                    canAct && loan.recall_allowed && (
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
                    )
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {incoming.length > 0 && (
        <div>
          <div className="mb-2.5 flex items-baseline justify-between">
            <h3 className="text-sm font-semibold text-text">On loan to us</h3>
            <span className="text-[13px] text-text-muted">
              {incoming.length} {incoming.length === 1 ? "player" : "players"}
            </span>
          </div>
          <div className="space-y-2">
            {incoming.map((loan) => (
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
                    from {loan.parent_club?.name ?? "another club"}
                  </p>
                </div>

                <div className="basis-[130px] shrink">
                  <p className="text-[11px] text-text-muted">Goes back</p>
                  <p className="text-sm font-semibold text-text">{returnDate(loan)}</p>
                </div>

                <div className="basis-[120px] shrink">
                  <p className="text-[11px] text-text-muted">We pay</p>
                  <p className="text-sm font-semibold text-text tabular-nums">
                    {loan.loanee_wage_share > 0
                      ? `${formatCurrency(loan.loanee_wage_share)}/wk`
                      : "—"}
                  </p>
                </div>

                <div className="flex shrink-0 items-center gap-2">
                  {optionChip(loan)}

                  {loan.conversion_deal_id ? (
                    <Link
                      to={`/deals/${loan.conversion_deal_id}`}
                      className="text-[13px] font-semibold text-accent no-underline hover:underline"
                    >
                      Purchase in progress →
                    </Link>
                  ) : (
                    canAct && loan.option_to_buy != null && !loan.obligation_to_buy && (
                      confirming === loan.id ? (
                        <span className="flex items-center gap-1.5">
                          <Button
                            variant="primary"
                            size="sm"
                            onClick={() => exercise.mutate(loan.id)}
                            disabled={exercise.isPending}
                          >
                            {exercise.isPending
                              ? "Starting…"
                              : `Buy for ${formatCurrency(loan.option_to_buy)}`}
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
                          title={`Buy him outright for ${formatCurrency(loan.option_to_buy)}. This starts a normal transfer — budget, medical and paperwork still apply.`}
                        >
                          Exercise option
                        </Button>
                      )
                    )
                  )}

                  {/* An obligation needs no button: it fires on its own at the
                      end date, and pretending otherwise would suggest the club
                      still has a choice. */}
                  {loan.obligation_to_buy && !loan.conversion_deal_id && (
                    <span className="text-[13px] text-text-muted">
                      Completes automatically
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
