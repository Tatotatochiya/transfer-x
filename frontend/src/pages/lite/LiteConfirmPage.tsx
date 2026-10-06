import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";

import api from "../../lib/api";
import { getApiError } from "../../lib/utils";
import { liteMoney } from "../../lib/liteMoney";
import { timeLeft } from "../../lib/timeLeft";
import { useAuthStore } from "../../store/auth";
import Spinner from "../../components/ui/Spinner";

/**
 * A decision from an email (Lite L8, BACKEND §7). Opening this page changes
 * nothing; Confirm holds the action for 10 seconds like any Lite send.
 * Accepting or countering needs the email's recipient signed in; saying no
 * doesn't. Works without the app's chrome, since it may be the first page
 * someone sees after tapping a button in their inbox.
 */

interface View {
  state: "ready" | "used" | "expired" | "changed";
  action: "counter" | "accept" | "reject";
  amount: number | null;
  label: string;
  needs_sign_in: boolean;
  signed_in_as_recipient: boolean;
  card: {
    offer_id: string;
    player_name: string | null;
    other_club: string | null;
    fee: number | null;
    deal_type: "PERMANENT" | "LOAN";
    expires_at: string | null;
    your_valuation: number | null;
  };
}

const STATE_TEXT: Record<Exclude<View["state"], "ready">, string> = {
  used: "This link has already been used.",
  expired: "This link has expired.",
  changed: "This has changed since we emailed you.",
};

export default function LiteConfirmPage() {
  const { token = "" } = useParams();
  const [params] = useSearchParams();
  const location = useLocation();
  const navigate = useNavigate();
  const signedIn = useAuthStore((s) => !!s.accessToken || !!s.refreshToken);
  const action = params.get("action") ?? "";
  const amount = params.get("amount");

  const { data: view, isLoading, error } = useQuery<View>({
    queryKey: ["lite", "confirm", token, action, amount],
    queryFn: () => api.get<View>(`/lite/confirm/${token}`, { params: { action, ...(amount && { amount }) } }).then((r) => r.data),
    retry: false,
  });

  const [sentAt, setSentAt] = useState<number | null>(null);
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    if (!sentAt) return;
    const t = window.setInterval(() => setNow(Date.now()), 500);
    return () => window.clearInterval(t);
  }, [sentAt]);

  const confirm = useMutation({
    mutationFn: () => api.post<{ action_id: string }>(`/lite/confirm/${token}`, {
      action, ...(view?.amount != null && action === "counter" && { amount: view.amount }),
    }).then((r) => r.data),
    onSuccess: (r) => {
      // Signed in as the recipient: the usual Sent screen, with undo and progress.
      if (view?.signed_in_as_recipient) navigate(`/lite/actions/${r.action_id}`, { replace: true });
      else setSentAt(Date.now());
    },
  });
  const undo = useMutation({ mutationFn: () => api.post(`/lite/confirm/${token}/undo`) });

  const signIn = `/login?next=${encodeURIComponent(location.pathname + location.search)}`;
  const left = sentAt ? Math.max(0, 10 - Math.floor((now - sentAt) / 1000)) : 0;

  return (
    <div className="min-h-screen bg-page px-4 py-10">
      <div className="mx-auto max-w-lg">
        <p className="mb-6 text-lg font-extrabold text-text">TransferX</p>
        {isLoading ? (
          <div className="flex justify-center py-16"><Spinner size="lg" /></div>
        ) : error || !view ? (
          <div className="rounded-[20px] bg-surface p-6 ring-1 ring-border">
            <p className="text-[1.25rem] text-text">{getApiError(error, "This link isn't valid.")}</p>
            <Link to="/login" className="mt-4 inline-block text-[1.0625rem] font-bold text-accent">Open TransferX →</Link>
          </div>
        ) : (
          <div className="rounded-[20px] bg-surface p-6 ring-1 ring-border">
            <p className="text-[0.9375rem] font-semibold text-text-muted">
              {view.card.other_club ?? "A club"} · {view.card.deal_type === "LOAN" ? "loan" : "transfer"} offer
            </p>
            <h1 className="mt-1 text-[1.75rem] font-extrabold leading-tight text-text">{view.card.player_name ?? "Your player"}</h1>
            <dl className="mt-4 space-y-2 text-[1.125rem]">
              {view.card.fee != null && (
                <div className="flex justify-between"><dt className="text-text-secondary">Their offer</dt><dd className="font-bold text-text">{liteMoney(view.card.fee)}</dd></div>
              )}
              {view.card.your_valuation != null && (
                <div className="flex justify-between"><dt className="text-text-secondary">Your valuation</dt><dd className="font-bold text-text">{liteMoney(view.card.your_valuation)}</dd></div>
              )}
              {view.card.expires_at && (
                <div className="flex justify-between"><dt className="text-text-secondary">Time left</dt><dd className="text-text">{timeLeft(view.card.expires_at)?.text}</dd></div>
              )}
            </dl>

            {view.state !== "ready" ? (
              <div className="mt-6">
                <p className="text-[1.125rem] text-text">{STATE_TEXT[view.state]}</p>
                <Link to={signedIn ? `/lite/offers/${view.card.offer_id}` : `/login?next=${encodeURIComponent(`/lite/offers/${view.card.offer_id}`)}`}
                  className="mt-4 inline-flex min-h-[3.25rem] items-center rounded-[13px] bg-accent px-5 text-[1.0625rem] font-bold text-white no-underline">
                  See it in TransferX
                </Link>
              </div>
            ) : sentAt ? (
              <div className="mt-6" role="status">
                {undo.isSuccess ? (
                  <p className="text-[1.25rem] font-bold text-text">Cancelled. Nothing was sent.</p>
                ) : (
                  <>
                    <p className="text-[1.25rem] font-bold text-text">{left > 0 ? `Sending in ${left} seconds` : "Sent"}</p>
                    {left > 0 && (
                      <button type="button" onClick={() => undo.mutate()} disabled={undo.isPending}
                        className="mt-3 min-h-[3.25rem] rounded-[13px] px-5 text-[1.0625rem] font-bold text-text ring-1 ring-border">
                        Undo
                      </button>
                    )}
                    {undo.isError && <p className="mt-2 text-danger-text">{getApiError(undo.error)}</p>}
                  </>
                )}
              </div>
            ) : view.needs_sign_in && !signedIn ? (
              <div className="mt-6">
                <p className="text-[1.0625rem] text-text-secondary">This moves money, so sign in with the account this email was sent to first.</p>
                <Link to={signIn} className="mt-3 inline-flex min-h-[3.5rem] w-full items-center justify-center rounded-[14px] bg-accent text-[1.125rem] font-bold text-white no-underline">
                  Sign in to {view.label.toLowerCase()}
                </Link>
              </div>
            ) : (
              <div className="mt-6">
                <button type="button" onClick={() => confirm.mutate()} disabled={confirm.isPending}
                  className="min-h-[3.5rem] w-full rounded-[14px] bg-accent text-[1.125rem] font-bold text-white disabled:opacity-60">
                  {confirm.isPending ? "Sending…" : `Confirm: ${view.label}`}
                </button>
                <p className="mt-2 text-[0.9375rem] text-text-muted">You can undo for 10 seconds after confirming.</p>
                {confirm.isError && <p className="mt-2 text-danger-text">{getApiError(confirm.error)}</p>}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
