import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "../../lib/api";
import { liteMoney } from "../../lib/liteMoney";
import { getApiError } from "../../lib/utils";
import { useLiteHome } from "../../hooks/useLite";
import { CLUB_DASHBOARD_KEY } from "../../hooks/useClubDashboard";
import Spinner from "../../components/ui/Spinner";
import { textBtn } from "../../components/lite/ActionCard";

/**
 * Screen 6 (Lite L6): sent, with undo and plain progress.
 *
 * The action was confirmed and is held for 10 seconds (architecture ADR
 * 0007). The undo bar counts down from `execute_at`; undoing in time means
 * nothing was sent. Then "Where this deal is" follows it in five plain
 * steps, from the server, so it never disagrees with the deal page.
 */

export interface ProgressStep {
  label: string;
  state: "done" | "current" | "future" | "ended";
  hint: string | null;
}

export interface HeldActionView {
  id: string;
  kind: "bid" | "counter" | "accept" | "reject";
  status: "HELD" | "EXECUTED" | "CANCELLED" | "FAILED";
  execute_at: string;
  result: { offer_id?: string; deal_id?: string; approval_id?: string } | null;
  error: string | null;
  progress: { title: string; subline: string; steps: ProgressStep[]; seconds_left: number | null; deal_id?: string };
}

const WINDOW_MS = 10_000;

function Stepper({ steps }: { steps: ProgressStep[] }) {
  return (
    <ol className="flex flex-col">
      {steps.map((s, i) => {
        const last = i === steps.length - 1;
        const node =
          s.state === "done" ? "bg-accent text-white"
            : s.state === "current" ? "bg-surface ring-[3px] ring-accent"
              : s.state === "ended" ? "bg-danger-bg text-danger-text ring-2 ring-danger-border"
                : "bg-surface ring-2 ring-border";
        return (
          <li key={i} className="flex gap-4" aria-current={s.state === "current" ? "step" : undefined}>
            <div className="flex flex-col items-center">
              <span className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-sm font-extrabold ${node}`}>
                {s.state === "done" ? "✓" : s.state === "current" ? <span className="h-2.5 w-2.5 rounded-full bg-accent" /> : s.state === "ended" ? "!" : null}
              </span>
              {!last && <span className={`w-[3px] flex-1 min-h-6 ${s.state === "done" ? "bg-accent" : "bg-border"}`} />}
            </div>
            <div className={`pb-6 ${last ? "pb-0" : ""}`}>
              <p className={`text-[1.125rem] leading-8 ${
                s.state === "current" ? "font-bold text-text" : s.state === "future" ? "text-text-muted" : s.state === "ended" ? "font-semibold text-danger-text" : "text-text"
              }`}>
                {s.label}
              </p>
              {s.hint && <p className="text-[1rem] text-text-secondary">{s.hint}</p>}
            </div>
          </li>
        );
      })}
    </ol>
  );
}

/** "Bid sent. Changed your mind?  [Undo · 8s]" with a bar running down. */
function UndoBar({ executeAt, onUndo, busy }: { executeAt: string; onUndo: () => void; busy: boolean }) {
  const end = new Date(executeAt).getTime();
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 200);
    return () => clearInterval(t);
  }, []);
  const left = Math.max(0, end - now);
  const seconds = Math.ceil(left / 1000);
  const gone = left <= 0;
  return (
    <div
      role="status"
      className={`fixed bottom-6 left-1/2 z-50 w-[min(620px,calc(100vw-2rem))] -translate-x-1/2 overflow-hidden rounded-[18px] bg-ink text-white shadow-2xl transition-all duration-200 ease-out ${
        gone ? "pointer-events-none translate-y-8 opacity-0" : "opacity-100"
      }`}
    >
      <div className="flex items-center justify-between gap-4 px-5 py-3.5">
        <span className="text-[1.125rem] font-semibold">Sent. Changed your mind?</span>
        <button
          type="button"
          onClick={onUndo}
          disabled={busy || gone}
          className="min-h-[3.25rem] shrink-0 rounded-xl bg-white px-5 text-[1.0625rem] font-extrabold text-ink disabled:opacity-60"
        >
          Undo · {seconds}s
        </button>
      </div>
      <div className="h-[5px] bg-white/15">
        <div className="h-full bg-white transition-[width] duration-200 ease-linear" style={{ width: `${(left / WINDOW_MS) * 100}%` }} />
      </div>
    </div>
  );
}

export default function LiteSentPage() {
  const { actionId } = useParams<{ actionId: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const back = (location.state as { back?: string } | null)?.back ?? "/lite";
  const queryClient = useQueryClient();
  const { data: home } = useLiteHome();
  const [cancelled, setCancelled] = useState(false);

  const { data, error, isLoading } = useQuery<HeldActionView>({
    queryKey: ["lite", "action", actionId],
    queryFn: () => api.get<HeldActionView>(`/lite/actions/${actionId}`).then((r) => r.data),
    enabled: !!actionId && !cancelled,
    // Quickly while held (the bar, then the step moving on), slowly after.
    refetchInterval: (q) => (q.state.data?.status === "HELD" ? 1000 : 15_000),
  });

  // Once sent, the home, the offers list and the dashboard all changed.
  const status = data?.status;
  useEffect(() => {
    if (status && status !== "HELD") {
      queryClient.invalidateQueries({ queryKey: ["lite", "home"] });
      queryClient.invalidateQueries({ queryKey: CLUB_DASHBOARD_KEY });
    }
  }, [status, queryClient]);

  const undo = useMutation({
    mutationFn: () => api.post<HeldActionView>(`/lite/actions/${actionId}/undo`).then((r) => r.data),
    onSuccess: () => {
      setCancelled(true);
      // "Cancelled. Nothing was sent." for 3 seconds, then back to the card, still filled in.
      setTimeout(() => navigate(back, { replace: true }), 3000);
    },
  });

  if (cancelled) {
    return (
      <div className="flex flex-col items-start gap-4 rounded-3xl bg-surface px-6 py-8 ring-1 ring-border sm:px-8" role="status">
        <h1 className="text-[1.75rem] font-extrabold text-text sm:text-[2.25rem]">Cancelled. Nothing was sent.</h1>
        <p className="text-[1.1875rem] text-text-secondary">Taking you back to the card…</p>
      </div>
    );
  }
  if (isLoading) return <div className="flex justify-center py-16"><Spinner size="lg" /></div>;
  if (error || !data) {
    return (
      <div className="flex flex-col items-start gap-4">
        <h1 className="text-[1.75rem] font-extrabold text-text">We couldn't find that</h1>
        <p className="text-[1.25rem] text-text-secondary">{getApiError(error, "It may belong to someone else.")}</p>
        <Link to="/lite" className="text-[1.125rem] font-bold text-accent">Back to home</Link>
      </div>
    );
  }

  const failed = data.status === "FAILED";
  const money = home?.money;
  const dealId = data.result?.deal_id ?? data.progress.deal_id;
  const offerId = data.result?.offer_id;

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_340px]">
      <div className="flex flex-col gap-6">
        <header className="flex flex-col items-start gap-4">
          <span
            aria-hidden="true"
            className={`flex h-16 w-16 items-center justify-center rounded-full text-[2rem] font-extrabold ${failed ? "bg-danger-bg text-danger-text" : "bg-success-text/10 text-success-text"}`}
          >
            {failed ? "!" : "✓"}
          </span>
          <h1 className="text-[1.75rem] font-extrabold tracking-[-0.02em] text-text sm:text-[2.25rem]">{data.progress.title}</h1>
          <p className="text-[1.1875rem] text-text-secondary">{data.progress.subline}</p>
        </header>

        <section className="rounded-3xl bg-surface px-6 py-6 ring-1 ring-border sm:px-8">
          <h2 className="mb-5 text-[1.25rem] font-bold text-text">Where this deal is</h2>
          <Stepper steps={data.progress.steps} />
        </section>
      </div>

      <aside className="flex flex-col gap-4">
        {money && (
          <section className="rounded-3xl bg-surface px-6 py-5 ring-1 ring-border">
            <p className="text-[1rem] font-semibold text-text-secondary">Your transfer budget</p>
            <p className="mt-1 text-[1.75rem] font-extrabold text-text">
              {liteMoney(money.transfer_remaining)} <span className="text-[1.0625rem] font-semibold text-text-muted">of {liteMoney(money.transfer_budget)}</span>
            </p>
            <div className="mt-3 h-2.5 overflow-hidden rounded-full bg-surface-inset">
              <div className="h-full rounded-full bg-accent" style={{ width: `${Math.max(0, Math.min(100, (money.transfer_remaining / Math.max(1, money.transfer_budget)) * 100))}%` }} />
            </div>
            <p className="mt-3 text-[0.9375rem] text-text-muted">
              {data.status === "HELD" ? "Nothing is held until it's sent." : "Money held for an offer is released if it's turned down or withdrawn."}
            </p>
          </section>
        )}
        <Link to="/lite" className="flex min-h-[3.75rem] items-center justify-center rounded-xl bg-accent px-6 text-[1.125rem] font-bold text-white no-underline">
          Back to home
        </Link>
        {dealId ? (
          <Link to={`/deals/${dealId}`} className="flex min-h-[3.5rem] items-center justify-center rounded-xl px-6 text-[1.0625rem] font-bold text-text no-underline ring-1 ring-border hover:ring-accent">
            Open the deal
          </Link>
        ) : offerId && data.status === "EXECUTED" ? (
          <Link to={`/offers/${offerId}`} className="flex min-h-[3.5rem] items-center justify-center rounded-xl px-6 text-[1.0625rem] font-bold text-text no-underline ring-1 ring-border hover:ring-accent">
            See the full offer
          </Link>
        ) : failed ? (
          <button type="button" className={textBtn} onClick={() => navigate(back)}>Back to the card</button>
        ) : null}
        {undo.isError && <p className="text-[1rem] text-danger-text">{getApiError(undo.error, "Too late to undo.")}</p>}
      </aside>

      {data.status === "HELD" && <UndoBar executeAt={data.execute_at} onUndo={() => undo.mutate()} busy={undo.isPending} />}
    </div>
  );
}

/** Confirm a card: hold the action and open the Sent screen. `back` is the
 *  card's own URL with its values, where Undo returns. */
export async function holdAndOpen(
  navigate: ReturnType<typeof useNavigate>,
  body: { kind: HeldActionView["kind"]; payload: Record<string, unknown>; ai_assisted?: boolean },
  back: string,
): Promise<void> {
  const { data } = await api.post<HeldActionView>("/lite/actions", body);
  navigate(`/lite/actions/${data.id}`, { state: { back } });
}
