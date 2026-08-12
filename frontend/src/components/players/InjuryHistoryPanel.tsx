import { useQuery } from "@tanstack/react-query";
import api from "../../lib/api";
import type { PlayerInjury } from "../../types/api";
import Spinner from "../ui/Spinner";

const INJURY_SEVERITY: Record<string, { cls: string; label: string }> = {
  default: { cls: "bg-warning-fill/10 text-warning-text ring-warning-fill/20", label: "" },
  muscle:  { cls: "bg-warning-fill/10 text-warning-text ring-warning-fill/20", label: "" },
  knee:    { cls: "bg-danger/10 text-danger-text ring-danger/20", label: "" },
  ankle:   { cls: "bg-danger/10 text-danger-text ring-danger/20", label: "" },
  hamstring: { cls: "bg-warning-fill/10 text-warning-text ring-warning-fill/20", label: "" },
};

function injuryStyle(type: string | null) {
  if (!type) return INJURY_SEVERITY.default;
  const lower = type.toLowerCase();
  for (const key of Object.keys(INJURY_SEVERITY)) {
    if (lower.includes(key)) return INJURY_SEVERITY[key];
  }
  return INJURY_SEVERITY.default;
}

function InjuryRow({ inj }: { inj: PlayerInjury }) {
  const year = inj.fixture_date ? new Date(inj.fixture_date).getFullYear() : null;
  const month = inj.fixture_date
    ? new Date(inj.fixture_date).toLocaleDateString("en-GB", { month: "short" })
    : null;
  const style = injuryStyle(inj.injury_type);

  return (
    <div className="grid grid-cols-[56px_1fr] gap-3 py-3 border-b border-rule-faint last:border-0">
      {/* Date */}
      <div className="text-right">
        {year && <p className="text-sm font-bold text-text tabular-nums">{year}</p>}
        {month && <p className="text-[11px] text-text-muted">{month}</p>}
      </div>

      {/* Injury detail */}
      <div className="min-w-0 space-y-1">
        <div className="flex items-center gap-2 flex-wrap">
          {inj.injury_type && (
            <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ring-1 ${style.cls}`}>
              {inj.injury_type}
            </span>
          )}
          {inj.games_absent != null && (
            <span className="text-xs text-text-muted">
              {inj.games_absent} game{inj.games_absent !== 1 ? "s" : ""} missed
            </span>
          )}
        </div>
        <div className="flex items-center gap-2 text-[11px] text-text-muted">
          {inj.league_name && <span>{inj.league_name}</span>}
          {inj.league_name && inj.season && <span>·</span>}
          {inj.season && <span>Season {inj.season}</span>}
        </div>
      </div>
    </div>
  );
}

interface Props {
  playerId: string;
}

export default function InjuryHistoryPanel({ playerId }: Props) {
  const { data: injuries, isLoading, isError } = useQuery<PlayerInjury[]>({
    queryKey: ["players", playerId, "injuries"],
    queryFn: () =>
      api.get<PlayerInjury[]>(`/players/market/${playerId}/injuries`).then((r) => r.data),
    staleTime: 1000 * 60 * 60,
  });

  if (isLoading) {
    return <div className="flex justify-center py-6"><Spinner /></div>;
  }

  if (isError) {
    return (
      <div className="rounded-xl bg-danger-bg px-4 py-3 text-sm text-danger-text ring-1 ring-danger-border">
        Could not load injury history.
      </div>
    );
  }

  if (!injuries || injuries.length === 0) {
    return (
      <div className="rounded-xl bg-success/10 px-4 py-3 text-sm text-success-text ring-1 ring-success/20">
        No injury history on record.
      </div>
    );
  }

  const totalGames = injuries.reduce((s, i) => s + (i.games_absent ?? 0), 0);

  return (
    <div>
      <div className="mb-3 flex items-center gap-3">
        <span className="text-xs text-text-muted">{injuries.length} recorded</span>
        {totalGames > 0 && (
          <span className="text-xs text-text-muted">· {totalGames} games missed total</span>
        )}
      </div>
      {injuries.map((inj, i) => (
        <InjuryRow key={i} inj={inj} />
      ))}
    </div>
  );
}
