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
    <div className="flex min-h-screen items-center justify-center bg-page px-4">
      <div className="w-full max-w-[400px]">
        <div className="mb-8 text-center">
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-accent-bg">
            <Icon name="bolt" className="h-7 w-7 text-accent" />
          </div>
          <p className="text-xs font-semibold uppercase tracking-widest text-accent">TransferX</p>
          <h1 className="mt-2 text-2xl font-semibold text-text">Join your club's team</h1>
        </div>

        <div className="rounded-xl bg-surface p-8 ring-1 ring-border">
          {isLoading ? (
            <div className="flex justify-center py-8"><Spinner size="lg" /></div>
          ) : invalid ? (
            <div className="text-center">
              <p className="text-sm font-medium text-danger-text">
                This invitation link is invalid, expired, or has already been used.
              </p>
              <p className="mt-2 text-sm text-text-muted">
                Ask your club owner to send you a new invitation.
              </p>
              <Button variant="secondary" size="sm" className="mt-5" onClick={() => navigate("/login")}>
                Go to sign in
              </Button>
            </div>
          ) : preview ? (
            <>
              {/* Invitation card */}
              <div className="mb-6 flex items-center gap-4 rounded-lg bg-surface-inset px-4 py-3.5 ring-1 ring-border">
                <div className="flex h-12 w-12 shrink-0 items-center justify-center overflow-hidden rounded-xl bg-surface">
                  {preview.club_crest_url ? (
                    <img src={preview.club_crest_url} alt="" className="h-full w-full object-contain p-1.5" />
                  ) : (
                    <span className="text-lg font-bold text-text-muted">
                      {preview.club_name[0]?.toUpperCase()}
                    </span>
                  )}
                </div>
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold text-text">{preview.club_name}</p>
                  <p className="text-xs text-text-muted">
                    invites you to join as{" "}
                    <span className="font-medium text-accent">
                      {ROLE_LABELS[preview.role] ?? preview.role}
                    </span>
                  </p>
                  <p className="mt-0.5 text-[11px] text-text-muted">
                    Expires {formatDateTime(preview.expires_at)}
                  </p>
                </div>
              </div>

              {error && (
                <div className="mb-4 rounded-lg bg-danger-bg px-4 py-3 text-sm text-danger-text ring-1 ring-danger-border">
                  {error}
                </div>
              )}

              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label className="mb-1.5 block text-sm font-medium text-text-secondary">Email</label>
                  <input
                    type="email"
                    value={preview.email}
                    disabled
                    className="w-full rounded-lg bg-surface-inset px-3 py-2.5 text-sm text-text-muted ring-1 ring-input-border"
                  />
                </div>
                <div>
                  <label htmlFor="pw" className="mb-1.5 block text-sm font-medium text-text-secondary">
                    Choose a password
                  </label>
                  <input
                    id="pw"
                    type="password"
                    autoComplete="new-password"
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="w-full rounded-lg bg-surface px-3 py-2.5 text-sm text-text placeholder-text-muted ring-1 ring-input-border focus:outline-none focus:ring-accent transition-colors"
                    placeholder="At least 8 characters"
                  />
                </div>
                <div>
                  <label htmlFor="pw2" className="mb-1.5 block text-sm font-medium text-text-secondary">
                    Confirm password
                  </label>
                  <input
                    id="pw2"
                    type="password"
                    autoComplete="new-password"
                    required
                    value={confirmPw}
                    onChange={(e) => setConfirmPw(e.target.value)}
                    className="w-full rounded-lg bg-surface px-3 py-2.5 text-sm text-text placeholder-text-muted ring-1 ring-input-border focus:outline-none focus:ring-accent transition-colors"
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
