import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import api from "../../lib/api";
import { useAuthStore } from "../../store/auth";
import Button from "../../components/ui/Button";
import Icon from "../../components/layout/Icon";
import type { IconName } from "../../components/layout/Icon";
import type { TokenResponse, User } from "../../types/api";

type ActorType = "CLUB" | "AGENT" | "PLAYER";

const INPUT_CLS =
  "w-full rounded-lg bg-surface px-3 py-2.5 text-sm text-text placeholder-text-muted ring-1 ring-input-border focus:outline-none focus:ring-accent transition-colors";

const LABEL_CLS = "mb-1.5 block text-sm font-medium text-text-secondary";

interface TypeCardProps {
  type: ActorType;
  icon: IconName;
  title: string;
  description: string;
  selected: boolean;
  onSelect: () => void;
}

function TypeCard({ icon, title, description, selected, onSelect }: TypeCardProps) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className={`flex flex-col items-start gap-1 rounded-xl p-4 text-left ring-1 transition-all ${
        selected
          ? "bg-accent-bg ring-accent text-text"
          : "bg-surface ring-input-border text-text-muted hover:ring-accent hover:text-text"
      }`}
    >
      <Icon name={icon} className={`h-5 w-5 mb-1 ${selected ? "text-accent" : ""}`} />
      <span className="text-sm font-semibold text-text">{title}</span>
      <span className="text-xs leading-snug">{description}</span>
    </button>
  );
}

export default function RegisterPage() {
  const navigate = useNavigate();
  const { setTokens, setUser } = useAuthStore();

  const [actorType, setActorType] = useState<ActorType>("CLUB");
  const [email, setEmail]         = useState("");
  const [password, setPassword]   = useState("");

  // Agent fields
  const [displayName, setDisplayName] = useState("");
  const [agencyName, setAgencyName]   = useState("");
  const [country, setCountry]         = useState("");
  const [licenceNo, setLicenceNo]     = useState("");

  const [error, setError]     = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // Reset type-specific state when switching
  useEffect(() => {
    setError(null);
  }, [actorType]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    setLoading(true);
    try {
      const body: Record<string, unknown> = { email, password, user_type: actorType };

      if (actorType === "AGENT") {
        body.display_name = displayName;
        body.agency_name  = agencyName;
        body.country      = country;
        if (licenceNo.trim()) body.licence_no = licenceNo.trim();
      }

      const { data: tokens } = await api.post<TokenResponse>("/auth/register", body);
      setTokens(tokens.access_token, tokens.refresh_token);
      const { data: me } = await api.get<User>("/auth/me");
      setUser(me);

      const dest = actorType === "AGENT" ? "/agent/dashboard" : "/dashboard";
      navigate(dest, { replace: true });
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        "Registration failed. Please check your details and try again.";
      setError(typeof msg === "string" ? msg : "Registration failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-page px-4 py-12">
      {/* Wider than the 400px auth archetype — the three-column role
          selector genuinely needs the room; cramping it wasn't worth it. */}
      <div className="w-full max-w-lg">
        {/* Logo */}
        <div className="mb-8 text-center">
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-accent-bg">
            <Icon name="bolt" className="h-7 w-7 text-accent" />
          </div>
          <p className="text-xs font-semibold uppercase tracking-widest text-accent">TransferX</p>
          <h1 className="mt-2 text-2xl font-semibold text-text">Create an account</h1>
          <p className="mt-1 text-sm text-text-muted">Choose your role to get started.</p>
        </div>

        <div className="rounded-xl bg-surface p-8 ring-1 ring-border">
          {error && (
            <div className="mb-4 rounded-lg bg-danger-bg px-4 py-3 text-sm text-danger-text ring-1 ring-danger-border">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-5">
            {/* Actor type selector */}
            <div>
              <p className={LABEL_CLS}>I am a…</p>
              <div className="grid grid-cols-3 gap-2">
                <TypeCard
                  type="CLUB"
                  icon="shield"
                  title="Club"
                  description="Buy, sell, and manage players"
                  selected={actorType === "CLUB"}
                  onSelect={() => setActorType("CLUB")}
                />
                <TypeCard
                  type="AGENT"
                  icon="briefcase"
                  title="Agent"
                  description="Represent players in deals"
                  selected={actorType === "AGENT"}
                  onSelect={() => setActorType("AGENT")}
                />
                <TypeCard
                  type="PLAYER"
                  icon="user"
                  title="Player"
                  description="Manage your career"
                  selected={actorType === "PLAYER"}
                  onSelect={() => setActorType("PLAYER")}
                />
              </div>
            </div>

            {/* Clubs join by invitation only (product decision, 2026-09-27):
                public sign-up let anyone claim to be any club. The Club card
                stays — most visitors are clubs — and explains how to join
                rather than offering a form the server would refuse. */}
            {actorType === "CLUB" ? (
              <div className="rounded-lg bg-surface-inset px-4 py-4 ring-1 ring-border">
                <p className="text-sm font-semibold text-text">Clubs join TransferX by invitation</p>
                <p className="mt-1 text-[13px] text-text-muted">
                  Every club on TransferX is invited and verified by our team, so the club you deal with is
                  the club it says it is. Contact TransferX to be invited; if you already have been, use
                  the link in your invitation email.
                </p>
              </div>
            ) : actorType === "PLAYER" ? (
              /* Players join by invitation from their club (2026-09-28): a
                 player account accepts personal terms, so it is never claimed
                 by searching for a name. */
              <div className="rounded-lg bg-surface-inset px-4 py-4 ring-1 ring-border">
                <p className="text-sm font-semibold text-text">Players join by invitation from their club</p>
                <p className="mt-1 text-[13px] text-text-muted">
                  Your account lets you review and accept the personal terms clubs offer you, so it is set up
                  by the club you play for. Ask your club to invite you, then use the link in your invitation
                  email. Your agent can also accept terms on your behalf.
                </p>
              </div>
            ) : (<>
            {/* Common fields */}
            <div>
              <label htmlFor="email" className={LABEL_CLS}>Email</label>
              <input
                id="email"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className={INPUT_CLS}
                placeholder="you@example.com"
              />
            </div>
            <div>
              <label htmlFor="password" className={LABEL_CLS}>Password</label>
              <input
                id="password"
                type="password"
                autoComplete="new-password"
                required
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className={INPUT_CLS}
                placeholder="Min. 8 characters"
              />
            </div>

            {/* Agent-specific */}
            {actorType === "AGENT" && (
              <div className="space-y-4">
                <div>
                  <label htmlFor="display_name" className={LABEL_CLS}>Your name</label>
                  <input
                    id="display_name"
                    type="text"
                    required
                    value={displayName}
                    onChange={(e) => setDisplayName(e.target.value)}
                    className={INPUT_CLS}
                    placeholder="Full name"
                  />
                </div>
                <div>
                  <label htmlFor="agency_name" className={LABEL_CLS}>Agency name</label>
                  <input
                    id="agency_name"
                    type="text"
                    required
                    value={agencyName}
                    onChange={(e) => setAgencyName(e.target.value)}
                    className={INPUT_CLS}
                    placeholder="e.g. Elite Sports Management"
                  />
                </div>
                <div>
                  <label htmlFor="country" className={LABEL_CLS}>Country</label>
                  <input
                    id="country"
                    type="text"
                    required
                    value={country}
                    onChange={(e) => setCountry(e.target.value)}
                    className={INPUT_CLS}
                    placeholder="e.g. England"
                  />
                </div>
                <div>
                  <label htmlFor="licence_no" className={LABEL_CLS}>
                    FIFA licence no. <span className="text-text-muted">(optional)</span>
                  </label>
                  <input
                    id="licence_no"
                    type="text"
                    value={licenceNo}
                    onChange={(e) => setLicenceNo(e.target.value)}
                    className={INPUT_CLS}
                    placeholder="e.g. FIFA-2024-001234"
                  />
                </div>
              </div>
            )}

            <Button type="submit" variant="primary" size="lg" loading={loading} className="w-full mt-2">
              Create account
            </Button>
            </>)}
          </form>
        </div>

        <p className="mt-6 text-center text-sm text-text-muted">
          Already have an account?{" "}
          <Link to="/login" className="text-accent hover:underline">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
