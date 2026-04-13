import { useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import api from "../../lib/api";
import type { Player, PlayerDetail, PlayerStats } from "../../types/api";
import Badge from "../ui/Badge";
import ClubLink from "../ui/ClubLink";
import FormBadge from "./FormBadge";
import { positionVariant, playerStatusVariant, playerStatusLabel } from "../../lib/badges";
import AddToShortlistButton from "../scouting/AddToShortlistButton";
import { useCompare } from "../../context/CompareContext";

interface PlayerListRowProps {
  player: Player;
  formScore?: number | null;
  formTrend?: number | null;
  stats?: PlayerStats | null;
}

export default function PlayerListRow({ player, formScore, formTrend, stats }: PlayerListRowProps) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { toggle, has } = useCompare();
  const comparing = has(player.id);

  function prefetch() {
    queryClient.prefetchQuery({
      queryKey: ["players", "market", player.id],
      queryFn: () => api.get<PlayerDetail>(`/players/market/${player.id}`).then((r) => r.data),
      staleTime: 60_000,
    });
  }

  const displayStatus = (player.current_club || player.world_team || player.team_name)
    ? { variant: "info" as const, label: "Contracted" }
    : { variant: playerStatusVariant(player.status), label: playerStatusLabel(player.status) };

  return (
    <tr
      onMouseEnter={prefetch}
      onClick={() => navigate(`/players/market/${player.id}`)}
      className={`cursor-pointer border-b border-white/[0.04] hover:bg-slate-800/60 transition-colors ${comparing ? "bg-slate-800/40" : ""}`}
    >
      {/* Player */}
      <td className="px-3 py-2.5">
        <div className="flex items-center gap-2.5">
          {player.photo_url ? (
            <img
              src={player.photo_url}
              alt={player.name}
              loading="lazy"
              className="h-8 w-8 shrink-0 rounded-full object-cover object-top ring-1 ring-white/10"
            />
          ) : (
            <div className="h-8 w-8 shrink-0 rounded-full bg-slate-700 flex items-center justify-center text-xs font-bold text-slate-400 ring-1 ring-white/10">
              {player.name[0]?.toUpperCase()}
            </div>
          )}
          <div className="min-w-0">
            <p className="truncate text-sm font-medium text-white">{player.name}</p>
            {(player.age || player.nationality) && (
              <p className="text-xs text-slate-600 truncate">
                {[player.age ? `${player.age}y` : null, player.nationality].filter(Boolean).join(" · ")}
              </p>
            )}
          </div>
        </div>
      </td>

      {/* Position */}
      <td className="px-3 py-2.5 hidden sm:table-cell">
        {player.position ? (
          <Badge variant={positionVariant(player.position)}>{player.position}</Badge>
        ) : (
          <span className="text-xs text-slate-600">—</span>
        )}
      </td>

      {/* Club */}
      <td className="px-3 py-2.5 hidden md:table-cell">
        <div className="flex items-center gap-1.5 max-w-[180px]">
          {(player.current_club?.crest_url ?? player.world_team?.crest_url) ? (
            <img
              src={(player.current_club?.crest_url ?? player.world_team?.crest_url)!}
              alt=""
              loading="lazy"
              className="h-4 w-4 shrink-0 object-contain"
            />
          ) : (player.current_club || player.world_team || player.team_name) ? (
            <span className="h-4 w-4 shrink-0 rounded-full bg-slate-700 flex items-center justify-center text-[9px] font-bold text-slate-500">
              {(player.current_club?.name ?? player.world_team?.name ?? player.team_name ?? "?")[0]?.toUpperCase()}
            </span>
          ) : null}
          <span className="text-sm text-slate-400 truncate">
            <ClubLink
              id={player.current_club?.id}
              worldTeamId={player.world_team?.id}
              name={player.current_club?.name ?? player.world_team?.name ?? player.team_name}
              fallback="Free Agent"
            />
          </span>
        </div>
      </td>

      {/* Status */}
      <td className="px-3 py-2.5 hidden sm:table-cell">
        <div className="flex items-center gap-1.5">
          <Badge variant={displayStatus.variant}>{displayStatus.label}</Badge>
          {player.open_to_offers && (
            <span className="flex items-center gap-0.5 rounded-full bg-emerald-500/15 px-1.5 py-0.5 ring-1 ring-emerald-500/30" title="Open to offers">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
              <span className="text-[9px] font-semibold text-emerald-400">Open</span>
            </span>
          )}
        </div>
      </td>

      {/* Form */}
      <td className="px-3 py-2.5">
        {formScore != null ? (
          <FormBadge score={formScore} trend={formTrend} size="sm" />
        ) : (
          <span className="text-xs text-slate-700">—</span>
        )}
      </td>

      {/* Goals */}
      <td className="px-3 py-2.5 hidden lg:table-cell text-sm tabular-nums text-slate-300">
        {stats?.goals ?? <span className="text-slate-700">—</span>}
      </td>

      {/* Assists */}
      <td className="px-3 py-2.5 hidden lg:table-cell text-sm tabular-nums text-slate-300">
        {stats?.assists ?? <span className="text-slate-700">—</span>}
      </td>

      {/* Apps */}
      <td className="px-3 py-2.5 hidden xl:table-cell text-sm tabular-nums text-slate-300">
        {stats?.appearances ?? <span className="text-slate-700">—</span>}
      </td>

      {/* Rating */}
      <td className="px-3 py-2.5 hidden xl:table-cell text-sm tabular-nums text-slate-300">
        {stats?.avg_rating != null
          ? Number(stats.avg_rating).toFixed(1)
          : <span className="text-slate-700">—</span>}
      </td>

      {/* Actions */}
      <td className="px-2 py-2.5" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center gap-1">
          <button
            onClick={() => toggle(player.id)}
            title={comparing ? "Remove from comparison" : "Compare"}
            className={`rounded p-1 transition-colors ${comparing ? "text-emerald-400" : "text-slate-600 hover:text-slate-300"}`}
          >
            <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
          </button>
          <AddToShortlistButton playerId={player.id} size="compact" />
        </div>
      </td>
    </tr>
  );
}
