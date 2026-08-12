import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import api from "../../lib/api";
import { useAuthStore } from "../../store/auth";
import Button from "../../components/ui/Button";
import Icon from "../../components/layout/Icon";
import type { IconName } from "../../components/layout/Icon";
import type { Paginated, Player, TokenResponse, User } from "../../types/api";

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

  // Club fields
  const [clubName, setClubName] = useState("");

  // Agent fields
  const [displayName, setDisplayName] = useState("");
  const [agencyName, setAgencyName]   = useState("");
  const [country, setCountry]         = useState("");
  const [licenceNo, setLicenceNo]     = useState("");

  // Player claim fields
  const [playerSearch, setPlayerSearch]     = useState("");
  const [searchResults, setSearchResults]   = useState<Player[]>([]);
  const [searching, setSearching]           = useState(false);
  const [selectedPlayer, setSelectedPlayer] = useState<Player | null>(null);

  const [error, setError]     = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (actorType !== "PLAYER" || playerSearch.length < 2) {
      setSearchResults([]);
      return;
    }
    const timer = setTimeout(async () => {
      setSearching(true);
      try {
        const { data } = await api.get<Paginated<Player>>("/players/market", {
          params: { search: playerSearch, page_size: 8 },
        });
        setSearchResults(data.items);
      } catch {
        setSearchResults([]);
      } finally {
        setSearching(false);
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [playerSearch, actorType]);

  // Reset type-specific state when switching
  useEffect(() => {
    setSelectedPlayer(null);
    setPlayerSearch("");
    setSearchResults([]);
    setError(null);
  }, [actorType]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (actorType === "PLAYER" && !selectedPlayer) {
      setError("Please search for and select your player record.");
      return;
    }

    setLoading(true);
    try {
      const body: Record<string, unknown> = { email, password, user_type: actorType };

      if (actorType === "CLUB" && clubName.trim()) {
        body.club_name = clubName.trim();
      } else if (actorType === "AGENT") {
        body.display_name = displayName;
        body.agency_name  = agencyName;
        body.country      = country;
        if (licenceNo.trim()) body.licence_no = licenceNo.trim();
      } else if (actorType === "PLAYER") {
        body.player_id = selectedPlayer!.id;
      }

      const { data: tokens } = await api.post<TokenResponse>("/auth/register", body);
      setTokens(tokens.access_token, tokens.refresh_token);
      const { data: me } = await api.get<User>("/auth/me");
      setUser(me);

      const dest = actorType === "AGENT" ? "/agent/dashboard"
                 : actorType === "PLAYER" ? "/player/profile"
                 : "/dashboard";
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

            {/* Club-specific */}
            {actorType === "CLUB" && (
              <div>
                <label htmlFor="club_name" className={LABEL_CLS}>
                  Club name <span className="text-text-muted">(optional)</span>
                </label>
                <input
                  id="club_name"
                  type="text"
                  value={clubName}
                  onChange={(e) => setClubName(e.target.value)}
                  className={INPUT_CLS}
                  placeholder="Defaults to your email prefix"
                />
              </div>
            )}

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

            {/* Player-specific */}
            {actorType === "PLAYER" && (
              <div>
                <label className={LABEL_CLS}>Find your player record</label>
                {selectedPlayer ? (
                  <div className="flex items-center justify-between rounded-lg bg-accent-bg px-4 py-3 ring-1 ring-accent">
                    <div>
                      <p className="text-sm font-medium text-text">{selectedPlayer.name}</p>
                      <p className="text-xs text-text-muted">{selectedPlayer.position ?? "Unknown position"}</p>
                    </div>
                    <button
                      type="button"
                      onClick={() => { setSelectedPlayer(null); setPlayerSearch(""); }}
                      className="text-xs text-text-muted hover:text-text transition-colors"
                    >
                      Change
                    </button>
                  </div>
                ) : (
                  <div className="relative">
                    <input
                      type="text"
                      value={playerSearch}
                      onChange={(e) => setPlayerSearch(e.target.value)}
                      className={INPUT_CLS}
                      placeholder="Search by name…"
                    />
                    {(searching || searchResults.length > 0) && (
                      <div className="absolute left-0 right-0 top-full z-10 mt-1 max-h-48 overflow-y-auto rounded-lg bg-surface py-1 ring-1 ring-border shadow-xl">
                        {searching ? (
                          <p className="px-4 py-2 text-xs text-text-muted">Searching…</p>
                        ) : searchResults.length === 0 ? (
                          <p className="px-4 py-2 text-xs text-text-muted">No players found</p>
                        ) : (
                          searchResults.map((p) => (
                            <button
                              key={p.id}
                              type="button"
                              onClick={() => { setSelectedPlayer(p); setSearchResults([]); }}
                              className="w-full px-4 py-2.5 text-left text-sm hover:bg-surface-inset transition-colors"
                            >
                              <span className="font-medium text-text">{p.name}</span>
                              {p.position && (
                                <span className="ml-2 text-xs text-text-muted">{p.position}</span>
                              )}
                            </button>
                          ))
                        )}
                      </div>
                    )}
                  </div>
                )}
                <p className="mt-1.5 text-xs text-text-muted">
                  Your account will be linked to this player record.
                </p>
              </div>
            )}

            <Button type="submit" variant="primary" size="lg" loading={loading} className="w-full mt-2">
              Create account
            </Button>
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
