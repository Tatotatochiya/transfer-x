import { useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import api from "../../lib/api";
import type { Player, PlayerDetail } from "../../types/api";
import Badge from "../ui/Badge";
import ClubLink from "../ui/ClubLink";
import FormBadge from "./FormBadge";
import { positionVariant, playerStatusVariant, playerStatusLabel } from "../../lib/badges";
import AddToShortlistButton from "../scouting/AddToShortlistButton";
import { useCompare } from "../../context/CompareContext";

interface PlayerCardProps {
  player: Player;
  formScore?: number | null;
  formTrend?: number | null;
}

const positionBg: Record<string, string> = {
  GK:  "bg-amber-500/20 text-amber-400",
  DEF: "bg-blue-500/20 text-blue-400",
  MID: "bg-emerald-500/20 text-emerald-400",
  FWD: "bg-red-500/20 text-red-400",
};

export default function PlayerCard({ player, formScore, formTrend }: PlayerCardProps) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { toggle, has } = useCompare();
  const avatarBg = player.position ? (positionBg[player.position] ?? "bg-slate-700 text-slate-400") : "bg-slate-700 text-slate-400";
  const comparing = has(player.id);

  function prefetch() {
    queryClient.prefetchQuery({
      queryKey: ["players", "market", player.id],
      queryFn: () => api.get<PlayerDetail>(`/players/market/${player.id}`).then((r) => r.data),
      staleTime: 60_000,
    });
  }

  return (
    <div
      onMouseEnter={prefetch}
      onClick={() => navigate(`/players/market/${player.id}`)}
      className={`cursor-pointer rounded-xl ring-1 hover:ring-emerald-500/40 hover:bg-slate-800/80 transition-all duration-150 p-3 group ${
        comparing ? "bg-slate-800 ring-emerald-500/30" : "bg-slate-900 ring-white/[0.07]"
      }`}
    >
      <div className="flex items-start gap-3">
        {/* Avatar */}
        <div className="shrink-0">
          {player.photo_url ? (
            <img
              src={player.photo_url}
              alt={player.name}
              loading="lazy"
              className="h-12 w-12 rounded-full object-cover object-top ring-1 ring-white/10"
            />
          ) : (
            <div className={`h-12 w-12 rounded-full flex items-center justify-center text-lg font-black ring-1 ring-white/10 ${avatarBg}`}>
              {player.name[0]?.toUpperCase()}
            </div>
          )}
        </div>

        {/* Info */}
        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-1">
            <p className="truncate text-sm font-semibold text-white group-hover:text-emerald-400 transition-colors leading-tight">
              {player.name}
            </p>
            {player.position && (
              <Badge variant={positionVariant(player.position)} className="shrink-0 !text-[10px] !px-1.5 !py-0">
                {player.position}
              </Badge>
            )}
          </div>

          <p className="mt-0.5 truncate text-xs text-slate-500">
            <ClubLink
              id={player.current_club?.id}
              worldTeamId={player.world_team?.id}
              name={player.current_club?.name ?? player.world_team?.name ?? player.team_name}
              fallback="Free Agent"
            />
          </p>

          {(player.age || player.nationality) && (
            <p className="mt-0.5 text-xs text-slate-600 truncate">
              {[player.age ? `${player.age}y` : null, player.nationality]
                .filter(Boolean)
                .join(" · ")}
            </p>
          )}
        </div>
      </div>

      {/* Footer row */}
      <div className="mt-2.5 flex items-center justify-between gap-2">
        <div className="flex items-center gap-1.5">
          {/* Status */}
          {(player.current_club || player.world_team || player.team_name) ? (
            <Badge variant="info" className="!text-[10px] !px-1.5 !py-0">Contracted</Badge>
          ) : (
            <Badge variant={playerStatusVariant(player.status)} className="!text-[10px] !px-1.5 !py-0">
              {playerStatusLabel(player.status)}
            </Badge>
          )}

          {/* Open to offers */}
          {player.open_to_offers && (
            <span className="flex items-center gap-0.5 rounded-full bg-emerald-500/15 px-1.5 py-0.5 ring-1 ring-emerald-500/30">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
              <span className="text-[9px] font-semibold text-emerald-400">Open</span>
            </span>
          )}
        </div>

        <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
          {formScore != null && (
            <FormBadge score={formScore} trend={formTrend} size="sm" />
          )}
          {/* Compare toggle */}
          <button
            onClick={() => toggle(player.id)}
            title={comparing ? "Remove from comparison" : "Add to comparison"}
            className={`rounded p-0.5 transition-colors ${comparing ? "text-emerald-400" : "text-slate-600 hover:text-slate-300"}`}
          >
            <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
          </button>
          <AddToShortlistButton playerId={player.id} size="compact" />
        </div>
      </div>
    </div>
  );
}
