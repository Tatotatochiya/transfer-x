import { useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import api from "../../lib/api";
import type { Fixture } from "../../types/api";
import Spinner from "../ui/Spinner";

const LEAGUE_NAMES: Record<string, string> = {
  "39":  "Premier League",
  "61":  "Ligue 1",
  "78":  "Bundesliga",
  "135": "Serie A",
  "140": "La Liga",
  "45":  "FA Cup",
  "48":  "League Cup",
  "2":   "UCL",
  "667": "UECL",
  "15":  "Club World Cup",
  "528": "UEFA Super Cup",
};

// ── Status badge ──────────────────────────────────────────────────────────────

function StatusBadge({ short, long }: { short: string; long: string | null }) {
  const isLive = ["1H", "HT", "2H", "ET", "BT", "P", "SUSP", "INT"].includes(short);
  const isFinished = ["FT", "AET", "PEN"].includes(short);

  if (isLive) {
    return (
      <span className="flex items-center gap-1 rounded-full bg-danger/15 px-2 py-0.5 text-[10px] font-bold text-danger-text ring-1 ring-danger/30">
        <span className="h-1.5 w-1.5 rounded-full bg-danger animate-pulse" />
        {short}
      </span>
    );
  }
  if (isFinished) {
    return (
      <span className="rounded-full bg-text-muted/15 px-2 py-0.5 text-[10px] font-bold text-text-muted">
        {short}
      </span>
    );
  }
  // Not started / postponed / cancelled
  return (
    <span className="rounded-full bg-surface-inset px-2 py-0.5 text-[10px] font-medium text-text-muted ring-1 ring-border">
      {short === "NS" ? "—" : short}
    </span>
  );
}

// ── Team display ──────────────────────────────────────────────────────────────

function TeamBadge({
  name,
  crest,
  isHighlighted,
  align,
  vendorId,
}: {
  name: string;
  crest: string | null;
  isHighlighted: boolean;
  align: "left" | "right";
  vendorId: number;
}) {
  const navigate = useNavigate();

  const handleClick = useCallback(async () => {
    try {
      const { data } = await api.get<{ id: string }>(`/world/teams/by-vendor/${vendorId}`);
      navigate(`/world/teams/${data.id}`);
    } catch {
      // Team not indexed — silently ignore
    }
  }, [vendorId, navigate]);

  return (
    <button
      type="button"
      onClick={handleClick}
      className={`flex items-center gap-2 min-w-0 cursor-pointer group ${align === "right" ? "flex-row-reverse" : ""}`}
    >
      {crest ? (
        <img src={crest} alt={name} className="h-6 w-6 shrink-0 object-contain" />
      ) : (
        <div className="h-6 w-6 shrink-0 rounded-full bg-surface-inset flex items-center justify-center text-[10px] font-bold text-text-muted">
          {name[0]?.toUpperCase()}
        </div>
      )}
      <span
        className={`truncate text-sm font-medium transition-colors group-hover:text-accent ${
          isHighlighted ? "text-text" : "text-text-muted"
        }`}
      >
        {name}
      </span>
    </button>
  );
}

// ── Single fixture row ────────────────────────────────────────────────────────

function FixtureRow({
  fixture,
  vendorTeamId,
}: {
  fixture: Fixture;
  vendorTeamId: number;
}) {
  const isFinished = ["FT", "AET", "PEN"].includes(fixture.status_short);
  const isHomeTeam = fixture.home_team_vendor_id === vendorTeamId;
  const kickoff = fixture.kickoff_at ? new Date(fixture.kickoff_at) : null;

  const dateStr = kickoff
    ? kickoff.toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" })
    : "TBC";
  const timeStr = kickoff
    ? kickoff.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" })
    : "";

  const leagueName = fixture.league_id ? (LEAGUE_NAMES[String(fixture.league_id)] ?? fixture.league_name ?? "") : fixture.league_name ?? "";

  return (
    <div className="rounded-xl bg-surface-inset px-4 py-3 ring-1 ring-border hover:ring-input-border transition-all">
      {/* Meta row */}
      <div className="mb-2 flex items-center justify-between text-[11px] text-text-muted">
        <span>{leagueName}{fixture.round ? ` · ${fixture.round}` : ""}</span>
        <span>{dateStr}{timeStr ? ` · ${timeStr}` : ""}</span>
      </div>

      {/* Match row */}
      <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-3">
        <TeamBadge
          name={fixture.home_team_name}
          crest={fixture.home_team_crest_url}
          isHighlighted={isHomeTeam}
          align="left"
          vendorId={fixture.home_team_vendor_id}
        />

        {/* Score / status */}
        <div className="flex flex-col items-center gap-0.5">
          {isFinished && fixture.home_goals != null && fixture.away_goals != null ? (
            <span className="text-lg font-bold tabular-nums text-text">
              {fixture.home_goals} – {fixture.away_goals}
            </span>
          ) : (
            <span className="text-lg font-bold text-text-muted">vs</span>
          )}
          <StatusBadge short={fixture.status_short} long={fixture.status_long} />
        </div>

        <TeamBadge
          name={fixture.away_team_name}
          crest={fixture.away_team_crest_url}
          isHighlighted={!isHomeTeam}
          align="right"
          vendorId={fixture.away_team_vendor_id}
        />
      </div>

      {fixture.venue_name && (
        <p className="mt-2 text-center text-[10px] text-text-muted">{fixture.venue_name}</p>
      )}
    </div>
  );
}

// ── Main panel ────────────────────────────────────────────────────────────────

interface Props {
  vendorTeamId: number;
}

export default function FixturesPanel({ vendorTeamId }: Props) {
  const { data: fixtures, isLoading, isError } = useQuery<Fixture[]>({
    queryKey: ["fixtures", "team", vendorTeamId],
    queryFn: () =>
      api
        .get<Fixture[]>(`/fixtures/team/${vendorTeamId}`, { params: { next: 5, last: 5 } })
        .then((r) => r.data),
    staleTime: 60_000 * 30, // 30 min — backend handles actual TTL
  });

  if (isLoading) {
    return (
      <div className="flex justify-center py-8">
        <Spinner />
      </div>
    );
  }

  if (isError || !fixtures) {
    return (
      <div className="rounded-xl bg-danger-bg px-4 py-3 text-sm text-danger-text ring-1 ring-danger-border">
        Could not load fixtures.
      </div>
    );
  }

  if (fixtures.length === 0) {
    return (
      <div className="rounded-xl bg-surface-inset px-4 py-4 text-sm text-text-muted ring-1 ring-border">
        No fixture data available.
      </div>
    );
  }

  // Split into past results and upcoming
  const now = new Date();
  const past = fixtures
    .filter((f) => {
      const kickoff = f.kickoff_at ? new Date(f.kickoff_at) : null;
      return ["FT", "AET", "PEN"].includes(f.status_short) || (kickoff && kickoff < now);
    })
    .slice(-5);
  const upcoming = fixtures
    .filter((f) => {
      const kickoff = f.kickoff_at ? new Date(f.kickoff_at) : null;
      return !["FT", "AET", "PEN"].includes(f.status_short) && (!kickoff || kickoff >= now);
    })
    .slice(0, 5);

  return (
    <div className="space-y-6">
      {past.length > 0 && (
        <div>
          <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-text-muted">
            Recent Results
          </p>
          <div className="space-y-2">
            {past.map((f) => (
              <FixtureRow key={f.fixture_vendor_id} fixture={f} vendorTeamId={vendorTeamId} />
            ))}
          </div>
        </div>
      )}

      {upcoming.length > 0 && (
        <div>
          <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-text-muted">
            Upcoming
          </p>
          <div className="space-y-2">
            {upcoming.map((f) => (
              <FixtureRow key={f.fixture_vendor_id} fixture={f} vendorTeamId={vendorTeamId} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
