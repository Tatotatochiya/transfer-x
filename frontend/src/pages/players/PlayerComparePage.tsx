import { useNavigate, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import api from "../../lib/api";
import type { PlayerDetail, PlayerForm, PlayerStats } from "../../types/api";
import Badge from "../../components/ui/Badge";
import FormBadge from "../../components/players/FormBadge";
import Spinner from "../../components/ui/Spinner";
import ClubLink from "../../components/ui/ClubLink";
import { positionVariant } from "../../lib/badges";

// ── Stat comparison row ────────────────────────────────────────────────────────

function CompareRow({
  label,
  a,
  b,
  higherIsBetter = true,
}: {
  label: string;
  a: number | null | undefined;
  b: number | null | undefined;
  higherIsBetter?: boolean;
}) {
  const aVal = a != null ? Number(a) : null;
  const bVal = b != null ? Number(b) : null;

  const aBetter = aVal != null && bVal != null && (higherIsBetter ? aVal > bVal : aVal < bVal);
  const bBetter = aVal != null && bVal != null && (higherIsBetter ? bVal > aVal : bVal < aVal);

  const cellCls = (better: boolean) =>
    `text-sm tabular-nums font-semibold px-4 py-2 text-center ${better ? "text-success-text" : "text-text-secondary"}`;

  return (
    <tr className="border-b border-rule-faint">
      <td className={cellCls(aBetter)}>{aVal != null ? aVal : <span className="text-text-muted">—</span>}</td>
      <td className="px-4 py-2 text-center text-xs text-text-muted">{label}</td>
      <td className={cellCls(bBetter)}>{bVal != null ? bVal : <span className="text-text-muted">—</span>}</td>
    </tr>
  );
}

// ── Player column header ───────────────────────────────────────────────────────

function PlayerHeader({ player, form }: { player: PlayerDetail; form: PlayerForm | null }) {
  const club = player.current_club?.name ?? player.world_team?.name ?? player.team_name;
  const crest = player.current_club?.crest_url ?? player.world_team?.crest_url;

  return (
    <div className="flex flex-col items-center gap-2 p-4 text-center">
      {player.photo_url ? (
        <img src={player.photo_url} alt={player.name} className="h-16 w-16 rounded-full object-cover object-top ring-2 ring-border" />
      ) : (
        <div className="h-16 w-16 rounded-full bg-surface-inset flex items-center justify-center text-2xl font-black text-text-muted">
          {player.name[0]?.toUpperCase()}
        </div>
      )}
      <div>
        <p className="text-base font-bold text-text">{player.name}</p>
        {club && (
          <p className="mt-0.5 flex items-center justify-center gap-1 text-xs text-text-muted">
            {crest && <img src={crest} alt="" className="h-3.5 w-3.5 object-contain" />}
            <ClubLink
              id={player.current_club?.id}
              worldTeamId={player.world_team?.id}
              name={club}
            />
          </p>
        )}
      </div>
      <div className="flex flex-wrap justify-center gap-1">
        {player.position && <Badge variant={positionVariant(player.position)}>{player.position}</Badge>}
        {player.age && <span className="text-xs text-text-muted">{player.age}y</span>}
        {player.nationality && <span className="text-xs text-text-muted">{player.nationality}</span>}
        {form && <FormBadge score={Number(form.form_score)} trend={form.trend != null ? Number(form.trend) : null} />}
      </div>
    </div>
  );
}

// ── Section divider ────────────────────────────────────────────────────────────

function SectionRow({ label, colour }: { label: string; colour: string }) {
  return (
    <tr>
      <td colSpan={3} className={`px-4 py-2 text-[10px] font-bold uppercase tracking-wider ${colour} bg-surface-inset`}>
        {label}
      </td>
    </tr>
  );
}

// ── Main page ──────────────────────────────────────────────────────────────────

export default function PlayerComparePage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const idA = params.get("a");
  const idB = params.get("b");

  const fetchPlayer = (id: string | null) =>
    id ? api.get<PlayerDetail>(`/players/market/${id}`).then((r) => r.data) : Promise.resolve(null);

  const fetchStats = (id: string | null) =>
    id
      ? api.get<PlayerStats[]>(`/players/${id}/stats`).then((r) => r.data).catch(() => [] as PlayerStats[])
      : Promise.resolve([] as PlayerStats[]);

  const fetchForm = (id: string | null) =>
    id
      ? api.get<PlayerForm>(`/players/${id}/form`).then((r) => r.data).catch(() => null)
      : Promise.resolve(null);

  const { data: playerA, isLoading: loadA } = useQuery({ queryKey: ["players", "market", idA], queryFn: () => fetchPlayer(idA), enabled: !!idA });
  const { data: playerB, isLoading: loadB } = useQuery({ queryKey: ["players", "market", idB], queryFn: () => fetchPlayer(idB), enabled: !!idB });
  const { data: statsA = [] } = useQuery({ queryKey: ["players", idA, "stats"], queryFn: () => fetchStats(idA), enabled: !!idA });
  const { data: statsB = [] } = useQuery({ queryKey: ["players", idB, "stats"], queryFn: () => fetchStats(idB), enabled: !!idB });
  const { data: formA = null } = useQuery({ queryKey: ["players", idA, "form"], queryFn: () => fetchForm(idA), enabled: !!idA });
  const { data: formB = null } = useQuery({ queryKey: ["players", idB, "form"], queryFn: () => fetchForm(idB), enabled: !!idB });

  if (!idA || !idB) {
    return (
      <div className="py-20 text-center text-text-muted">
        Select two players from the market to compare.{" "}
        <button onClick={() => navigate("/players/market")} className="text-accent hover:underline">Browse players</button>
      </div>
    );
  }

  if (loadA || loadB) {
    return <div className="flex justify-center py-20"><Spinner size="lg" /></div>;
  }

  if (!playerA || !playerB) {
    return (
      <div className="rounded-xl bg-danger-bg px-5 py-4 text-sm text-danger-text ring-1 ring-danger-border">
        One or both players could not be found.{" "}
        <button onClick={() => navigate(-1)} className="underline">Go back</button>
      </div>
    );
  }

  // Pick primary stats row (most appearances)
  const primaryA = statsA.length > 0 ? [...statsA].sort((a, b) => b.appearances - a.appearances)[0] : null;
  const primaryB = statsB.length > 0 ? [...statsB].sort((a, b) => b.appearances - a.appearances)[0] : null;

  return (
    <div>
      <button
        onClick={() => navigate(-1)}
        className="mb-6 flex items-center gap-1.5 text-sm text-text-muted hover:text-text transition-colors"
      >
        ← Back
      </button>

      <h1 className="mb-6 text-2xl font-bold text-text">Player Comparison</h1>

      <div className="rounded-2xl bg-surface ring-1 ring-border overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-rule">
              <th className="w-1/2"><PlayerHeader player={playerA} form={formA} /></th>
              <th className="w-0 px-2 text-xs text-text-muted font-normal">vs</th>
              <th className="w-1/2"><PlayerHeader player={playerB} form={formB} /></th>
            </tr>
          </thead>
          <tbody>
            <SectionRow label="Overview" colour="text-text-muted" />
            <CompareRow label="Age" a={playerA.age} b={playerB.age} higherIsBetter={false} />

            {(primaryA || primaryB) && (
              <>
                <SectionRow label="Key Stats" colour="text-success-text" />
                <CompareRow label="Goals"       a={primaryA?.goals}       b={primaryB?.goals} />
                <CompareRow label="Assists"     a={primaryA?.assists}     b={primaryB?.assists} />
                <CompareRow label="Appearances" a={primaryA?.appearances} b={primaryB?.appearances} />
                <CompareRow label="Avg Rating"  a={primaryA?.avg_rating}  b={primaryB?.avg_rating} />
                <CompareRow label="Minutes"     a={primaryA?.minutes}     b={primaryB?.minutes} />
              </>
            )}

            {(primaryA?.shots_total != null || primaryB?.shots_total != null) && (
              <>
                <SectionRow label="Attack" colour="text-danger-text" />
                <CompareRow label="Shots"          a={primaryA?.shots_total}      b={primaryB?.shots_total} />
                <CompareRow label="Shots on Target" a={primaryA?.shots_on_target} b={primaryB?.shots_on_target} />
                <CompareRow label="Key Passes"     a={primaryA?.key_passes}       b={primaryB?.key_passes} />
              </>
            )}

            {(primaryA?.tackles_total != null || primaryB?.tackles_total != null) && (
              <>
                <SectionRow label="Defending" colour="text-accent" />
                <CompareRow label="Tackles"       a={primaryA?.tackles_total}  b={primaryB?.tackles_total} />
                <CompareRow label="Interceptions" a={primaryA?.interceptions}  b={primaryB?.interceptions} />
                <CompareRow label="Blocks"        a={primaryA?.blocks}         b={primaryB?.blocks} />
              </>
            )}

            {(primaryA?.saves != null || primaryB?.saves != null) && (
              <>
                <SectionRow label="Goalkeeping" colour="text-warning-text" />
                <CompareRow label="Saves"          a={primaryA?.saves}          b={primaryB?.saves} />
                <CompareRow label="Goals Conceded" a={primaryA?.goals_conceded} b={primaryB?.goals_conceded} higherIsBetter={false} />
              </>
            )}

            {(formA || formB) && (
              <>
                <SectionRow label="Form" colour="text-role-agent-text" />
                <CompareRow label="Form Score" a={formA ? Number(formA.form_score) : null} b={formB ? Number(formB.form_score) : null} />
              </>
            )}

            <SectionRow label="Discipline" colour="text-role-club-text" />
            <CompareRow label="Yellow Cards"     a={primaryA?.yellow_cards}    b={primaryB?.yellow_cards}    higherIsBetter={false} />
            <CompareRow label="Red Cards"        a={primaryA?.red_cards}       b={primaryB?.red_cards}       higherIsBetter={false} />
            <CompareRow label="Fouls Committed"  a={primaryA?.fouls_committed} b={primaryB?.fouls_committed} higherIsBetter={false} />
          </tbody>
        </table>
      </div>

      <p className="mt-3 text-xs text-text-muted text-center">
        Green values indicate the better stat. Stats from highest-appearance season.
      </p>
    </div>
  );
}
