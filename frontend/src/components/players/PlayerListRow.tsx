import { useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import api from "../../lib/api";
import type { FairValueSignal, Player, PlayerDetail } from "../../types/api";
import Badge from "../ui/Badge";
import ClubLink from "../ui/ClubLink";
import FormBadge from "./FormBadge";
import { positionVariant, playerStatusVariant, playerStatusLabel } from "../../lib/badges";
import AddToShortlistButton from "../scouting/AddToShortlistButton";
import { useCompare } from "../../context/CompareContext";
import { formatCompactCurrency, formatCurrency } from "../../lib/utils";
import { BAND_COLOUR, BAND_PHRASE } from "./FairValueBadge";

interface PlayerListRowProps {
  player: Player;
  formScore?: number | null;
  formTrend?: number | null;
  fairValueSignal?: FairValueSignal | null;
  /** Hide the Make offer / Shortlist actions for viewers who can't act (agents, players, logged out). */
  canAct?: boolean;
}

export default function PlayerListRow({ player, formScore, formTrend, fairValueSignal, canAct = true }: PlayerListRowProps) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { toggle, has } = useCompare();
  const comparing = has(player.id);
  // The server resolves the reference price (an open fixed-price listing's
  // asking price, else the legacy market_value — D7 excludes auctions), so it
  // arrives on the divergence. `market_value` is the fallback for a player with
  // an asking price but no model row to diverge from.
  const divergence = fairValueSignal?.divergence ?? null;
  const asking = divergence?.reference_price ?? player.market_value ?? null;
  const bargain = divergence?.band === "WELL_BELOW" || divergence?.band === "BELOW";

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
    <div
      onMouseEnter={prefetch}
      onClick={() => navigate(`/players/market/${player.id}`)}
      className={`cursor-pointer rounded-[14px] bg-surface ring-1 px-5 py-4 transition-all hover:ring-accent ${
        bargain ? "ring-success/25" : "ring-border"
      }`}
    >
      <div className="flex flex-wrap items-center gap-5">
        {/* Avatar + identity */}
        <div className="flex flex-1 basis-[200px] items-center gap-3 min-w-0">
          {player.photo_url ? (
            <img src={player.photo_url} alt={player.name} loading="lazy" className="h-11 w-11 shrink-0 rounded-full object-cover object-top ring-1 ring-border" />
          ) : (
            <div className="h-11 w-11 shrink-0 rounded-full bg-surface-inset flex items-center justify-center text-sm font-bold text-text-muted ring-1 ring-border">
              {player.name[0]?.toUpperCase()}
            </div>
          )}
          <div className="min-w-0">
            <p className="flex items-center gap-1.5 truncate text-base font-semibold text-text">
              {player.name}
              {player.position && <Badge variant={positionVariant(player.position)} className="!text-[10px]">{player.position}</Badge>}
            </p>
            <p className="truncate text-[13px] text-text-muted">
              <ClubLink id={player.current_club?.id} worldTeamId={player.world_team?.id} name={player.current_club?.name ?? player.world_team?.name ?? player.team_name} fallback="Free Agent" />
              {(player.age || player.nationality) && ` · ${[player.age ? `${player.age}y` : null, player.nationality].filter(Boolean).join(" · ")}`}
            </p>
          </div>
        </div>

        {/* Value — the model leads, because it is the figure a row actually has:
            ~30% of players carry a model valuation and 0% carry the legacy
            `market_value` this cell used to label "asking", so "Asking vs fair
            value" compared a number that usually exists against one that never
            does, and bailed entirely when the second was missing. Same two
            aligned rows as the squad table, and the 14px/600 weight goes to
            whichever figure answers "what would he cost" — the asking price
            where there is one, the model otherwise.

            The asking row is simply absent when there is none, unlike the
            squad's "yours": you cannot set another club's price, so an empty
            row would be inert rather than an invitation.

            Colour is directional here, the opposite call from the squad cell's
            magnitude banding — this is someone else's asking price and you are
            the buyer, so below-model is genuinely good news. That is what
            BAND_COLOUR already encodes, shared with the grid view's badge
            rather than re-derived (the private version this replaced also broke
            D5's copy rule by saying "fair value" instead of "model"). */}
        <div className="basis-[170px] shrink">
          <div className="flex items-baseline gap-x-1.5">
            <span className="w-[46px] shrink-0 text-[13px] text-text-muted">model</span>
            {fairValueSignal ? (
              <span
                className={`tabular-nums ${asking == null ? "text-sm font-semibold text-text" : "text-[13px] text-text-secondary"}`}
                title={`${formatCurrency(fairValueSignal.fair_value)} · ${fairValueSignal.confidence.toLowerCase()} confidence · range ${formatCompactCurrency(fairValueSignal.fair_value_low)}–${formatCompactCurrency(fairValueSignal.fair_value_high)}`}
              >
                {formatCompactCurrency(fairValueSignal.fair_value)}
              </span>
            ) : (
              <span
                className="text-[13px] text-text-muted"
                title="No model valuation. The model needs a position, vendor stats and 450+ minutes played, and never estimates without them."
              >
                —
              </span>
            )}
          </div>

          {asking != null && (
            <div className="flex flex-wrap items-baseline gap-x-1.5">
              <span className="w-[46px] shrink-0 text-[13px] text-text-muted">asking</span>
              <span className="text-sm font-semibold text-text tabular-nums">{formatCompactCurrency(asking)}</span>
              {divergence && (
                <span
                  className={`text-[13px] font-semibold tabular-nums ${BAND_COLOUR[divergence.band]}`}
                  title={`${BAND_PHRASE[divergence.band]} — the asking price is ${Math.abs(Math.round(divergence.pct))}% ${divergence.pct >= 0 ? "above" : "below"} the model`}
                >
                  {divergence.pct >= 0 ? "▲" : "▼"} {Math.abs(Math.round(divergence.pct))}%
                </span>
              )}
            </div>
          )}
        </div>

        {/* Form */}
        <div className="shrink-0 basis-[96px]">
          {formScore != null ? <FormBadge score={formScore} trend={formTrend} /> : <span className="text-xs text-text-muted">—</span>}
        </div>

        {/* Wage */}
        <div className="shrink-0 basis-[110px]">
          <p className="text-[11px] text-text-muted">Wage / wk</p>
          <p className="text-sm font-semibold text-text">{player.wage_weekly != null ? formatCurrency(player.wage_weekly) : "—"}</p>
        </div>

        {/* Status */}
        <div className="hidden shrink-0 items-center gap-1.5 sm:flex">
          <Badge variant={displayStatus.variant}>{displayStatus.label}</Badge>
          {player.open_to_offers && (
            <span className="flex items-center gap-0.5 rounded-full bg-success/15 px-1.5 py-0.5 ring-1 ring-success/30" title="Open to offers">
              <span className="h-1.5 w-1.5 rounded-full bg-success animate-pulse" />
              <span className="text-[9px] font-semibold text-success-text">Open</span>
            </span>
          )}
        </div>

        {/* Actions */}
        <div className="flex shrink-0 items-center gap-2" onClick={(e) => e.stopPropagation()}>
          {canAct && (
            <button
              onClick={() => navigate(`/players/market/${player.id}`)}
              className="rounded-lg bg-accent px-3.5 py-1.5 text-xs font-semibold text-white hover:bg-accent-hover transition-colors"
            >
              Make offer
            </button>
          )}
          <AddToShortlistButton playerId={player.id} size="compact" />
          <button
            onClick={() => toggle(player.id)}
            title={comparing ? "Remove from comparison" : "Compare"}
            className={`rounded p-1 transition-colors ${comparing ? "text-accent" : "text-text-muted hover:text-text-secondary"}`}
          >
            <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}
