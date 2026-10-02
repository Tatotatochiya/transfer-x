import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import axios from "axios";
import api from "../../lib/api";
import { useAuth } from "../../hooks/useAuth";
import Button from "../../components/ui/Button";
import Icon from "../../components/layout/Icon";

export default function LoginPage() {
  const navigate = useNavigate();
  const { login } = useAuth();

  const [email, setEmail]       = useState("");
  const [password, setPassword] = useState("");
  const [error, setError]       = useState<string | null>(null);
  const [loading, setLoading]   = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const me = await login(email, password);
      let dest = me.user_type === "AGENT" ? "/agent/dashboard"
               : me.user_type === "PLAYER" ? "/player/profile"
               : "/dashboard";
      // TransferX staff start on the admin panel, whatever their account type.
      if (me.is_superuser) dest = "/admin";
      // Club members with Lite mode on land on the Lite home. If the
      // preference can't be read, the full app is the safe default.
      else if (me.user_type === "CLUB") {
        const prefs = await api.get<{ lite_mode: boolean }>("/users/me/preferences").then((r) => r.data).catch(() => null);
        if (prefs?.lite_mode) dest = "/lite";
      }
      navigate(dest, { replace: true });
    } catch (err) {
      console.error("Login error:", err);
      if (axios.isAxiosError(err) && !err.response) {
        setError("Can't reach the server. Check your connection and try again.");
      } else {
        // The server says when a username is shared by two accounts.
        const detail = axios.isAxiosError(err) ? err.response?.data?.detail : undefined;
        setError(typeof detail === "string" && detail.includes("email address")
          ? detail
          : "Invalid email, username or password.");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-page px-4">
      <div className="w-full max-w-[400px]">
        {/* Logo */}
        <div className="mb-8 text-center">
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-accent-bg">
            <Icon name="bolt" className="h-7 w-7 text-accent" />
          </div>
          <p className="text-xs font-semibold uppercase tracking-widest text-accent">TransferX</p>
          <h1 className="mt-2 text-2xl font-semibold text-text">Sign in</h1>
          <p className="mt-1 text-sm text-text-muted">Welcome back. Please enter your credentials.</p>
        </div>

        {/* Card */}
        <div className="rounded-xl bg-surface p-8 ring-1 ring-border">
          {error && (
            <div className="mb-4 rounded-lg bg-danger-bg px-4 py-3 text-sm text-danger-text ring-1 ring-danger-border">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              {/* A username is the part of the email before the "@". */}
              <label htmlFor="email" className="mb-1.5 block text-sm font-medium text-text-secondary">
                Email or username
              </label>
              <input
                id="email"
                type="text"
                autoComplete="username"
                autoCapitalize="none"
                spellCheck={false}
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full rounded-lg bg-surface px-3 py-2.5 text-sm text-text placeholder-text-muted ring-1 ring-input-border focus:outline-none focus:ring-accent transition-colors"
                placeholder="you@club.com or you"
              />
            </div>

            <div>
              <label htmlFor="password" className="mb-1.5 block text-sm font-medium text-text-secondary">
                Password
              </label>
              <input
                id="password"
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full rounded-lg bg-surface px-3 py-2.5 text-sm text-text placeholder-text-muted ring-1 ring-input-border focus:outline-none focus:ring-accent transition-colors"
                placeholder="••••••••"
              />
            </div>

            <Button
              type="submit"
              variant="primary"
              size="lg"
              loading={loading}
              className="w-full mt-2"
            >
              Sign in
            </Button>
          </form>
        </div>

        <p className="mt-6 text-center text-sm text-text-muted">
          New to TransferX?{" "}
          <Link to="/register" className="text-accent hover:underline">
            Create an account
          </Link>
        </p>
      </div>
    </div>
  );
}
