import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import api from "../../lib/api";
import Button from "../../components/ui/Button";
import Icon from "../../components/layout/Icon";
import Spinner from "../../components/ui/Spinner";
import { getApiError } from "../../lib/utils";

/**
 * Choose a new password with a one-time link from TransferX staff
 * (/reset-password?token=…). The link works once, for 24 hours. Setting the
 * password signs the person out on every device; they then sign in.
 */
export default function ResetPasswordPage() {
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const [password, setPassword] = useState("");
  const [confirmPw, setConfirmPw] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);

  const { data: preview, isLoading, isError } = useQuery<{ email: string; expires_at: string }>({
    queryKey: ["password-reset", token],
    queryFn: () => api.get(`/auth/password-reset/${token}`).then((r) => r.data),
    enabled: !!token,
    retry: false,
  });

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (password.length < 8) return setError("Use at least 8 characters.");
    if (password !== confirmPw) return setError("The two passwords don't match.");
    setSubmitting(true);
    try {
      await api.post("/auth/password-reset", { token, new_password: password });
      setDone(true);
    } catch (err) {
      setError(getApiError(err, "This link has expired or has already been used."));
    } finally {
      setSubmitting(false);
    }
  }

  const input = "w-full rounded-lg bg-surface px-3 py-2 text-sm text-text ring-1 ring-input-border focus:outline-none focus:ring-accent";

  return (
    <div className="flex min-h-screen items-center justify-center bg-page px-4">
      <div className="w-full max-w-[400px]">
        <div className="mb-8 text-center">
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-accent-bg">
            <Icon name="bolt" className="h-7 w-7 text-accent" />
          </div>
          <p className="text-xs font-semibold uppercase tracking-widest text-accent">TransferX</p>
          <h1 className="mt-2 text-2xl font-semibold text-text">Choose a new password</h1>
        </div>

        <div className="rounded-xl bg-surface p-8 ring-1 ring-border">
          {done ? (
            <div className="text-center">
              <p className="text-sm font-medium text-success-text">Your password has been changed.</p>
              <p className="mt-2 text-sm text-text-muted">You've been signed out on every device. Sign in with your new password.</p>
              <Link to="/login" className="mt-5 inline-block text-sm font-semibold text-accent hover:underline">Go to sign in</Link>
            </div>
          ) : isLoading ? (
            <div className="flex justify-center py-8"><Spinner size="lg" /></div>
          ) : !token || isError || !preview ? (
            <div className="text-center">
              <p className="text-sm font-medium text-danger-text">This link has expired or has already been used.</p>
              <p className="mt-2 text-sm text-text-muted">Ask TransferX for a new one.</p>
              <Link to="/login" className="mt-5 inline-block text-sm font-semibold text-accent hover:underline">Go to sign in</Link>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              <p className="text-sm text-text-secondary">For <span className="font-semibold text-text">{preview.email}</span></p>
              <div>
                <label htmlFor="pw" className="mb-1.5 block text-sm font-medium text-text-secondary">New password</label>
                <input id="pw" type="password" autoComplete="new-password" value={password}
                  onChange={(e) => setPassword(e.target.value)} className={input} />
                <p className="mt-1 text-xs text-text-muted">At least 8 characters.</p>
              </div>
              <div>
                <label htmlFor="pw2" className="mb-1.5 block text-sm font-medium text-text-secondary">Type it again</label>
                <input id="pw2" type="password" autoComplete="new-password" value={confirmPw}
                  onChange={(e) => setConfirmPw(e.target.value)} className={input} />
              </div>
              {error && <p className="text-sm text-danger-text">{error}</p>}
              <Button type="submit" variant="primary" className="w-full" loading={submitting}>Set password</Button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
