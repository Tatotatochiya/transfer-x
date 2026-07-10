import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import api from "../../lib/api";
import { useAuthStore } from "../../store/auth";
import type { InvitationPreview, TokenResponse, User } from "../../types/api";
import Button from "../../components/ui/Button";
import Icon from "../../components/layout/Icon";
import Spinner from "../../components/ui/Spinner";
import { getApiError, formatDateTime } from "../../lib/utils";

const ROLE_LABELS: Record<string, string> = {
  SPORTING_DIRECTOR: "Sporting Director",
  MANAGER: "Manager",
  SCOUT: "Scout",
  READONLY: "Read-only",
};

/**
 * TRA-86 (D6): staff invitation acceptance — provisioning via an emailed
 * link, not open signup. The login page stays login-only; this page only
 * works with a live single-use token.
 */
export default function AcceptInvitePage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const { setTokens, setUser } = useAuthStore();

  const [password, setPassword] = useState("");
  const [confirmPw, setConfirmPw] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const { data: preview, isLoading, isError } = useQuery<InvitationPreview>({
    queryKey: ["invitations", token],
    queryFn: () => api.get<InvitationPreview>(`/auth/invitations/${token}`).then((r) => r.data),
    enabled: token.length > 0,
    retry: false,
  });

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    if (password !== confirmPw) {
      setError("Passwords do not match.");
      return;
    }
    setSubmitting(true);
    try {
      const { data } = await api.post<TokenResponse>(`/auth/invitations/${token}/accept`, {
        password,
      });
      setTokens(data.access_token, data.refresh_token);
      const { data: me } = await api.get<User>("/auth/me");
      setUser(me);
      navigate("/dashboard", { replace: true });
    } catch (err) {
      setError(getApiError(err, "This invitation is no longer valid."));
      setSubmitting(false);
    }
  }

  const invalid = !token || isError;

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-950 px-4">
      <div className="w-full max-w-md">
        <div className="mb-8 text-center">
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-emerald-500/20">
            <Icon name="bolt" className="h-7 w-7 text-emerald-400" />
          </div>
          <p className="text-xs font-semibold uppercase tracking-widest text-emerald-400">TransferX</p>
          <h1 className="mt-2 text-2xl font-semibold text-white">Join your club's team</h1>
        </div>

        <div className="rounded-xl bg-slate-900 p-8 ring-1 ring-white/[0.08]">
          {isLoading ? (
            <div className="flex justify-center py-8"><Spinner size="lg" /></div>
          ) : invalid ? (
            <div className="text-center">
              <p className="text-sm font-medium text-red-400">
                This invitation link is invalid, expired, or has already been used.
              </p>
              <p className="mt-2 text-sm text-slate-500">
                Ask your club owner to send you a new invitation.
              </p>
              <Button variant="secondary" size="sm" className="mt-5" onClick={() => navigate("/login")}>
                Go to sign in
              </Button>
            </div>
          ) : preview ? (
            <>
              {/* Invitation card */}
              <div className="mb-6 flex items-center gap-4 rounded-lg bg-slate-800/60 px-4 py-3.5 ring-1 ring-white/[0.06]">
                <div className="flex h-12 w-12 shrink-0 items-center justify-center overflow-hidden rounded-xl bg-slate-700">
                  {preview.club_crest_url ? (
                    <img src={preview.club_crest_url} alt="" className="h-full w-full object-contain p-1.5" />
                  ) : (
                    <span className="text-lg font-bold text-slate-400">
                      {preview.club_name[0]?.toUpperCase()}
                    </span>
                  )}
                </div>
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold text-white">{preview.club_name}</p>
                  <p className="text-xs text-slate-400">
                    invites you to join as{" "}
                    <span className="font-medium text-emerald-400">
                      {ROLE_LABELS[preview.role] ?? preview.role}
                    </span>
                  </p>
                  <p className="mt-0.5 text-[11px] text-slate-600">
                    Expires {formatDateTime(preview.expires_at)}
                  </p>
                </div>
              </div>

              {error && (
                <div className="mb-4 rounded-lg bg-red-500/10 px-4 py-3 text-sm text-red-400 ring-1 ring-red-500/30">
                  {error}
                </div>
              )}

              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label className="mb-1.5 block text-sm font-medium text-slate-300">Email</label>
                  <input
                    type="email"
                    value={preview.email}
                    disabled
                    className="w-full rounded-lg bg-slate-800/50 px-3 py-2.5 text-sm text-slate-400 ring-1 ring-white/10"
                  />
                </div>
                <div>
                  <label htmlFor="pw" className="mb-1.5 block text-sm font-medium text-slate-300">
                    Choose a password
                  </label>
                  <input
                    id="pw"
                    type="password"
                    autoComplete="new-password"
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="w-full rounded-lg bg-slate-800 px-3 py-2.5 text-sm text-white placeholder-slate-500 ring-1 ring-white/10 focus:outline-none focus:ring-emerald-500 transition-colors"
                    placeholder="At least 8 characters"
                  />
                </div>
                <div>
                  <label htmlFor="pw2" className="mb-1.5 block text-sm font-medium text-slate-300">
                    Confirm password
                  </label>
                  <input
                    id="pw2"
                    type="password"
                    autoComplete="new-password"
                    required
                    value={confirmPw}
                    onChange={(e) => setConfirmPw(e.target.value)}
                    className="w-full rounded-lg bg-slate-800 px-3 py-2.5 text-sm text-white placeholder-slate-500 ring-1 ring-white/10 focus:outline-none focus:ring-emerald-500 transition-colors"
                    placeholder="••••••••"
                  />
                </div>
                <Button type="submit" variant="primary" size="lg" loading={submitting} className="w-full mt-2">
                  Join {preview.club_name}
                </Button>
              </form>
            </>
          ) : null}
        </div>
      </div>
    </div>
  );
}
