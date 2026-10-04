import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import api from "../../lib/api";
import { useAuthStore } from "../../store/auth";
import type { TokenResponse, User } from "../../types/api";
import Button from "../../components/ui/Button";
import Icon from "../../components/layout/Icon";
import Spinner from "../../components/ui/Spinner";
import { getApiError, formatDateTime } from "../../lib/utils";
import NameFields from "../../components/auth/NameFields";

interface PlayerInvitationPreview {
  player_name: string;
  /** His club's name, "your agent …", or "TransferX". */
  invited_by: string;
  email: string;
  expires_at: string;
}

/**
 * How a player joins TransferX: by invitation from the club that owns him, or
 * for a free agent from his agent or TransferX (product ADR 0007). His account accepts personal terms, so it
 * is never self-claimed. This page, reached from the emailed link, sets a
 * password and creates the account linked to his player record. Mirrors
 * JoinClubPage.
 */
export default function JoinPlayerPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const { setTokens, setUser } = useAuthStore();

  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPw, setConfirmPw] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const { data: preview, isLoading, isError } = useQuery<PlayerInvitationPreview>({
    queryKey: ["player-invitations", token],
    queryFn: () => api.get<PlayerInvitationPreview>(`/auth/player-invitations/${token}`).then((r) => r.data),
    enabled: token.length > 0,
    retry: false,
  });

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!firstName.trim() || !lastName.trim()) {
      setError("Enter your first and last name.");
      return;
    }
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
      const { data } = await api.post<TokenResponse>(`/auth/player-invitations/${token}/accept`, { password, first_name: firstName.trim(), last_name: lastName.trim() });
      setTokens(data.access_token, data.refresh_token);
      const { data: me } = await api.get<User>("/auth/me");
      setUser(me);
      navigate("/player/profile", { replace: true });
    } catch (err) {
      setError(getApiError(err, "This invitation is no longer valid."));
      setSubmitting(false);
    }
  }

  const invalid = !token || isError;
  const inputClass =
    "w-full rounded-lg bg-surface px-3 py-2.5 text-sm text-text placeholder-text-muted ring-1 ring-input-border focus:outline-none focus:ring-accent transition-colors";

  return (
    <div className="flex min-h-screen items-center justify-center bg-page px-4">
      <div className="w-full max-w-[400px]">
        <div className="mb-8 text-center">
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-accent-bg">
            <Icon name="bolt" className="h-7 w-7 text-accent" />
          </div>
          <p className="text-xs font-semibold uppercase tracking-widest text-accent">TransferX</p>
          <h1 className="mt-2 text-2xl font-semibold text-text">Your TransferX account</h1>
        </div>

        <div className="rounded-xl bg-surface p-8 ring-1 ring-border">
          {isLoading ? (
            <div className="flex justify-center py-8"><Spinner size="lg" /></div>
          ) : invalid ? (
            <div className="text-center">
              <p className="text-sm font-medium text-danger-text">
                This invitation link is invalid, expired, or has already been used.
              </p>
              <p className="mt-2 text-sm text-text-muted">Ask whoever invited you — your club, your agent or TransferX — for a new one.</p>
              <Button variant="secondary" size="sm" className="mt-5" onClick={() => navigate("/login")}>
                Go to sign in
              </Button>
            </div>
          ) : preview ? (
            <>
              <div className="mb-6 rounded-lg bg-surface-inset px-4 py-3.5 ring-1 ring-border">
                <p className="text-sm font-semibold text-text">{preview.player_name}</p>
                <p className="text-[13px] text-text-muted">
                  Invited by {preview.invited_by}. With your account you review and accept the personal
                  terms clubs offer you.
                </p>
                <p className="mt-0.5 text-[13px] text-text-muted">Expires {formatDateTime(preview.expires_at)}</p>
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
                <NameFields first={firstName} last={lastName} onFirst={setFirstName} onLast={setLastName} />
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
                    className={inputClass}
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
                    className={inputClass}
                    placeholder="••••••••"
                  />
                </div>
                <Button type="submit" variant="primary" size="lg" loading={submitting} className="w-full mt-2">
                  Create my account
                </Button>
              </form>
            </>
          ) : null}
        </div>
      </div>
    </div>
  );
}
