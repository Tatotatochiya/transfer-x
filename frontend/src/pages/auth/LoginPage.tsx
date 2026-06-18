import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
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
      navigate(me.user_type === "AGENT" ? "/agent/dashboard" : "/dashboard", { replace: true });
    } catch (err) {
      console.error("Login error:", err);
      setError("Invalid email or password.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-950 px-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="mb-8 text-center">
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-emerald-500/20">
            <Icon name="bolt" className="h-7 w-7 text-emerald-400" />
          </div>
          <p className="text-xs font-semibold uppercase tracking-widest text-emerald-400">TransferX</p>
          <h1 className="mt-2 text-2xl font-semibold text-white">Sign in</h1>
          <p className="mt-1 text-sm text-slate-500">Welcome back. Please enter your credentials.</p>
        </div>

        {/* Card */}
        <div className="rounded-xl bg-slate-900 p-8 ring-1 ring-white/[0.08]">
          {error && (
            <div className="mb-4 rounded-lg bg-red-500/10 px-4 py-3 text-sm text-red-400 ring-1 ring-red-500/30">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="email" className="mb-1.5 block text-sm font-medium text-slate-300">
                Email
              </label>
              <input
                id="email"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full rounded-lg bg-slate-800 px-3 py-2.5 text-sm text-white placeholder-slate-500 ring-1 ring-white/10 focus:outline-none focus:ring-emerald-500 transition-colors"
                placeholder="you@club.com"
              />
            </div>

            <div>
              <label htmlFor="password" className="mb-1.5 block text-sm font-medium text-slate-300">
                Password
              </label>
              <input
                id="password"
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full rounded-lg bg-slate-800 px-3 py-2.5 text-sm text-white placeholder-slate-500 ring-1 ring-white/10 focus:outline-none focus:ring-emerald-500 transition-colors"
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

        <p className="mt-6 text-center text-sm text-slate-500">
          New to TransferX?{" "}
          <Link to="/register" className="text-emerald-400 hover:underline">
            Create an account
          </Link>
        </p>
      </div>
    </div>
  );
}
