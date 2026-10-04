import { useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import api from "../../lib/api";
import { getApiError } from "../../lib/utils";
import { liteMoney } from "../../lib/liteMoney";
import { timeLeft } from "../../lib/timeLeft";
import { useClubCapabilities } from "../../hooks/useClubCapabilities";
import { CLUB_DASHBOARD_KEY } from "../../hooks/useClubDashboard";
import { ActionCardShell, Done, FactRow } from "../../components/lite/ActionCard";
import { SwipeNav, WaitingHeader } from "../../components/lite/WaitingNav";
import Spinner from "../../components/ui/Spinner";
import type { PendingApproval } from "../../types/api";

/**
 * The approval decision sheet (mobile notifications, phase 4 follow-up): an
 * approval push on a phone opens this. What is asked, who asked, the budget
 * after and the time left, with Approve and Decline. Approving carries out
 * the action straight away, so it asks once more first.
 */

const STATUS_TEXT: Record<string, string> = {
  APPROVED_EXECUTED: "Already approved.",
  APPROVED_FAILED: "Approved, but it couldn't be carried out.",
  REJECTED: "Already declined.",
  CANCELLED: "Withdrawn by the person who asked.",
  EXPIRED: "This approval has expired.",
};

export default function LiteApprovalPage() {
  const { id = "" } = useParams();
  const [params] = useSearchParams();
  const fromPush = params.get("from") === "push";
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { can } = useClubCapabilities();
  const [mode, setMode] = useState<"answer" | "approve" | "decline">("answer");
  const [reason, setReason] = useState("");
  const [done, setDone] = useState<"approved" | "declined" | null>(null);

  const { data: a, isLoading, error } = useQuery<PendingApproval>({
    queryKey: ["approvals", id],
    queryFn: () => api.get<PendingApproval>(`/clubs/me/approvals/${id}`).then((r) => r.data),
    enabled: !!id,
  });
  const after = () => {
    void qc.invalidateQueries({ queryKey: CLUB_DASHBOARD_KEY });
    void qc.invalidateQueries({ queryKey: ["approvals"] });
  };
  const approve = useMutation({
    mutationFn: () => api.post(`/clubs/me/approvals/${id}/approve`),
    onSuccess: () => { setDone("approved"); after(); },
  });
  const decline = useMutation({
    mutationFn: () => api.post(`/clubs/me/approvals/${id}/reject`, { reason: reason.trim() || null }),
    onSuccess: () => { setDone("declined"); after(); },
  });

  if (isLoading) return <div className="flex justify-center py-20"><Spinner size="lg" /></div>;
  if (error || !a) return <p className="text-[1.125rem] text-text">{getApiError(error, "That approval isn't there any more.")}</p>;

  if (done) {
    return (
      <Done
        title={done === "approved" ? "Approved" : "Declined"}
        body={done === "approved"
          ? `It's been carried out${a.requested_by_name ? `, and ${a.requested_by_name} has been told` : ""}.`
          : `${a.requested_by_name ?? "They"} will be told${reason.trim() ? ", with your reason" : ""}.`}
        links={[{ to: "/lite", label: "Back to home" }, { to: "/club/approvals", label: "All approvals" }]}
      />
    );
  }

  const pending = a.status === "PENDING";
  const canDecide = can("APPROVE_ACTIONS");
  const left = timeLeft(a.expires_at);
  const who = a.requested_by_name ?? a.requested_by_email ?? "Someone";
  const btn = "min-h-[3.5rem] rounded-[14px] px-6 text-[1.125rem] font-bold";
  const busy = approve.isPending || decline.isPending;
  const err = approve.error ?? decline.error;

  return (
    <SwipeNav kind="approval" id={a.id} enabled={fromPush}>
      <div className="flex flex-col gap-4">
        {fromPush && <WaitingHeader kind="approval" id={a.id} />}
        <ActionCardShell
          pill="Approval needed"
          tone="approval"
          title={a.summary ?? `Approve ${liteMoney(Number(a.amount))}?`}
          money={
            <div className="flex flex-col gap-1">
              <FactRow label="Amount">{liteMoney(Number(a.amount))}</FactRow>
              {a.budget_after != null && <FactRow label="Budget after">{liteMoney(Number(a.budget_after))}</FactRow>}
            </div>
          }
        >
          <div className="flex flex-col">
            <FactRow label="Asked by">{who}</FactRow>
            {a.player_name && a.player_id && (
              <FactRow label="Player"><Link to={`/players/market/${a.player_id}`} className="text-accent">{a.player_name}</Link></FactRow>
            )}
            {pending && left && (
              <FactRow label="Time left"><span className={left.urgent ? "font-bold text-danger-text" : ""}>{left.text}</span></FactRow>
            )}
          </div>

          {!pending ? (
            <p className="text-[1.125rem] text-text">{STATUS_TEXT[a.status] ?? a.status}</p>
          ) : !canDecide ? (
            <p className="text-[1.125rem] text-text-secondary">Waiting for the owner or sporting director to decide.</p>
          ) : mode === "answer" ? (
            <div className="flex flex-wrap gap-3">
              <button type="button" className={`${btn} bg-accent text-white`} onClick={() => setMode("approve")}>Approve</button>
              <button type="button" className={`${btn} text-text ring-1 ring-border`} onClick={() => setMode("decline")}>Decline</button>
            </div>
          ) : mode === "approve" ? (
            <div className="flex flex-col gap-3">
              <p className="text-[1.125rem] text-text">This carries it out now, in your club&rsquo;s name. There&rsquo;s no undo.</p>
              <div className="flex flex-wrap gap-3">
                <button type="button" disabled={busy} className={`${btn} bg-accent text-white disabled:opacity-60`} onClick={() => approve.mutate()}>
                  {approve.isPending ? "Approving…" : "Yes, approve"}
                </button>
                <button type="button" className={`${btn} text-text`} onClick={() => setMode("answer")}>Back</button>
              </div>
            </div>
          ) : (
            <form className="flex flex-col gap-3" onSubmit={(e) => { e.preventDefault(); decline.mutate(); }}>
              <label className="text-[1.0625rem] text-text-secondary">
                Why not? <span className="text-text-muted">(optional, {who} sees it)</span>
                <textarea value={reason} onChange={(e) => setReason(e.target.value)} rows={2} maxLength={500}
                  className="mt-1 w-full rounded-xl bg-surface px-4 py-3 text-[1.125rem] text-text ring-1 ring-input-border focus:outline-none focus:ring-accent" />
              </label>
              <div className="flex flex-wrap gap-3">
                <button type="submit" disabled={busy} className={`${btn} bg-danger text-white disabled:opacity-60`}>
                  {decline.isPending ? "Declining…" : "Decline"}
                </button>
                <button type="button" className={`${btn} text-text`} onClick={() => setMode("answer")}>Back</button>
              </div>
            </form>
          )}
          {err && <p className="text-[1.0625rem] text-danger-text">{getApiError(err)}</p>}
          <button type="button" className="self-start text-[1.0625rem] font-semibold text-text-secondary" onClick={() => navigate("/club/approvals")}>
            See all approvals
          </button>
        </ActionCardShell>
      </div>
    </SwipeNav>
  );
}
