import { useState } from "react";
import { Link } from "react-router-dom";
import type { ActiveDealStub, FairValueSignal, Player, PlayerDetail } from "../../types/api";
import Badge from "../ui/Badge";
import FairValueBadge from "./FairValueBadge";
import FormBadge from "./FormBadge";
import { formatCurrency } from "../../lib/utils";

const POSITION_ORDER = ["GK", "DEF", "MID", "FWD"];

const POSITION_COLOUR: Record<string, string> = {
  GK: "bg-amber-500/20 text-amber-300",
  DEF: "bg-blue-500/20 text-blue-300",
  MID: "bg-emerald-500/20 text-emerald-300",
  FWD: "bg-red-500/20 text-red-300",
};

// Accept both Player (world teams) and PlayerDetail (registered clubs, which adds active_contract + active_deal)
interface Props {
  players: (Player & { active_contract?: PlayerDetail["active_contract"]; active_deal?: ActiveDealStub | null })[];
  showContractDetails?: boolean;
  /** Map of player_id → form_score for displaying form badges */
  formScores?: Record<string, { score: number; trend: number | null }>;
  /** Map of player_id → fair-value signal (TRA-92). Market-facing, same as the
   * public player profile — never gated behind showContractDetails. */
  fairValues?: Record<string, FairValueSignal>;
  /** When provided, shows an interactive toggle for each player's open_to_offers flag */
  onToggleOpenToOffers?: (playerId: string, next: boolean) => void;
  /** Set of player IDs currently being toggled (shows loading state) */
  togglingIds?: Set<string>;
  /** When provided, renders an editable Valuation cell */
  onSetValuation?: (playerId: string, value: number | null) => void;
}

function PositionBreakdown({ players }: { players: PlayerDetail[] }) {
  const counts = POSITION_ORDER.reduce<Record<string, number>>((acc, pos) => {
    acc[pos] = players.filter((p) => p.position === pos).length;
    return acc;
  }, {});
  const total = players.length;

  return (
    <div className="mb-5 flex flex-wrap items-center gap-4 rounded-xl bg-slate-800/60 px-5 py-3">
      <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
        Squad ({total})
      </span>
      {POSITION_ORDER.map((pos) => (
        <span key={pos} className="flex items-center gap-1.5 text-sm">
          <span className={`rounded px-1.5 py-0.5 text-xs font-bold ${POSITION_COLOUR[pos]}`}>
            {pos}
          </span>
          <span className="text-white">{counts[pos]}</span>
        </span>
      ))}
    </div>
  );
}

export default function SquadTable({ players, showContractDetails = false, formScores, fairValues, onToggleOpenToOffers, togglingIds, onSetValuation }: Props) {
  const [editingValuationId, setEditingValuationId] = useState<string | null>(null);
  const [valuationDraft, setValuationDraft] = useState("");

  function startEditValuation(playerId: string, current: number | null) {
    setEditingValuationId(playerId);
    setValuationDraft(current != null ? String(current) : "");
  }

  function commitValuation(playerId: string) {
    if (!onSetValuation) return;
    const trimmed = valuationDraft.trim();
    const parsed = trimmed === "" ? null : Number(trimmed.replace(/[^0-9.]/g, ""));
    onSetValuation(playerId, parsed != null && !isNaN(parsed) ? parsed : null);
    setEditingValuationId(null);
  }

  if (players.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-slate-500">No players in squad.</p>
    );
  }

  // Group by position for visual separation
  const groups = POSITION_ORDER.map((pos) => ({
    pos,
    players: players.filter((p) => p.position === pos),
  })).filter((g) => g.players.length > 0);

  // Catch-all for players without a position
  const unpositioned = players.filter((p) => !p.position);
  if (unpositioned.length > 0) groups.push({ pos: "—", players: unpositioned });

  return (
    <div>
      <PositionBreakdown players={players} />

      <div className="overflow-x-auto rounded-xl ring-1 ring-white/[0.06]">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-800 text-xs font-semibold uppercase tracking-wider text-slate-500">
              <th className="px-4 py-3 text-left">Pos</th>
              <th className="px-4 py-3 text-left">Player</th>
              <th className="px-4 py-3 text-left">Age</th>
              <th className="px-4 py-3 text-left">Nationality</th>
              <th className="px-4 py-3 text-left">Status</th>
              {formScores && <th className="px-4 py-3 text-center">Form</th>}
              {fairValues && <th className="px-4 py-3 text-left">Fair Value</th>}
              {onToggleOpenToOffers && (
                <th className="px-4 py-3 text-center">Open to offers</th>
              )}
              {showContractDetails && (
                <>
                  <th className="px-4 py-3 text-right">Wage / wk</th>
                  <th className="px-4 py-3 text-left">Contract ends</th>
                  <th className="px-4 py-3 text-right">Mkt Value</th>
                  <th className="px-4 py-3 text-right">Valuation</th>
                </>
              )}
            </tr>
          </thead>
          <tbody>
            {groups.map(({ pos, players: group }) =>
              group.map((player, idx) => (
                <tr
                  key={player.id}
                  className={`border-b border-slate-800/60 transition-colors hover:bg-slate-800/40 ${
                    idx === 0 && pos !== "—" ? "border-t-2 border-t-slate-700" : ""
                  }`}
                >
                  {/* Position */}
                  <td className="px-4 py-3">
                    {player.position ? (
                      <span
                        className={`rounded px-1.5 py-0.5 text-xs font-bold ${
                          POSITION_COLOUR[player.position] ?? "bg-slate-700 text-slate-300"
                        }`}
                      >
                        {player.position}
                      </span>
                    ) : (
                      <span className="text-slate-500">—</span>
                    )}
                  </td>

                  {/* Name + photo */}
                  <td className="px-4 py-3">
                    <Link
                      to={`/players/market/${player.id}`}
                      className="flex items-center gap-2.5 font-medium text-white hover:text-emerald-400 transition-colors"
                    >
                      {player.photo_url ? (
                        <img
                          loading="lazy"
                          src={player.photo_url}
                          alt={player.name}
                          className="h-7 w-7 rounded-full object-cover ring-1 ring-white/10"
                        />
                      ) : (
                        <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-slate-700 text-xs font-bold text-slate-400">
                          {player.name[0]?.toUpperCase()}
                        </div>
                      )}
                      {player.name}
                    </Link>
                    {player.open_to_offers && !onToggleOpenToOffers && (
                      <span className="ml-9 mt-0.5 block text-xs text-emerald-400">
                        Open to offers
                      </span>
                    )}
                  </td>

                  {/* Age */}
                  <td className="px-4 py-3 text-slate-300">{player.age ?? "—"}</td>

                  {/* Nationality */}
                  <td className="px-4 py-3 text-slate-400">{player.nationality ?? "—"}</td>

                  {/* Status — vendor players have status=FREE_AGENT in DB but display as Contracted when team affiliation is set */}
                  <td className="px-4 py-3">
                    <div className="flex flex-col gap-1">
                      {(player.current_club || player.world_team || player.team_name) ? (
                        <Badge variant="info">Contracted</Badge>
                      ) : (
                        <Badge variant={player.status === "FREE_AGENT" ? "warning" : "info"}>
                          {player.status === "FREE_AGENT" ? "Free Agent" : "Contracted"}
                        </Badge>
                      )}
                      {player.active_deal?.status === "IN_PROGRESS" && (
                        <span className="inline-flex items-center gap-1 rounded-full bg-amber-500/15 px-2 py-0.5 text-[10px] font-semibold text-amber-400 ring-1 ring-amber-500/30 w-fit">
                          <span className="h-1.5 w-1.5 rounded-full bg-amber-400 animate-pulse" />
                          Transfer pending
                        </span>
                      )}
                      {player.active_deal?.status === "COMPLETED" && (
                        <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/15 px-2 py-0.5 text-[10px] font-semibold text-emerald-400 ring-1 ring-emerald-500/20 w-fit">
                          Transferred
                        </span>
                      )}
                    </div>
                  </td>

                  {/* Form score */}
                  {formScores && (
                    <td className="px-4 py-3 text-center">
                      {formScores[player.id] != null ? (
                        <FormBadge
                          score={formScores[player.id].score}
                          trend={formScores[player.id].trend}
                        />
                      ) : (
                        <span className="text-xs text-slate-600">—</span>
                      )}
                    </td>
                  )}

                  {/* Fair value (TRA-92) — market-facing model estimate */}
                  {fairValues && (
                    <td className="px-4 py-3">
                      {fairValues[player.id] ? (
                        <FairValueBadge signal={fairValues[player.id]} compact />
                      ) : (
                        <span className="text-xs text-slate-600">—</span>
                      )}
                    </td>
                  )}

                  {/* Open to offers toggle (owner view) */}
                  {onToggleOpenToOffers && (
                    <td className="px-4 py-3 text-center">
                      <button
                        disabled={togglingIds?.has(player.id) || player.active_deal?.status === "IN_PROGRESS"}
                        title={player.active_deal?.status === "IN_PROGRESS" ? "Cannot change while a transfer deal is in progress" : undefined}
                        onClick={() => onToggleOpenToOffers(player.id, !player.open_to_offers)}
                        className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors focus:outline-none disabled:opacity-50 ${
                          player.open_to_offers ? "bg-emerald-500" : "bg-slate-600"
                        }`}
                        aria-label={player.open_to_offers ? "Disable open to offers" : "Enable open to offers"}
                      >
                        <span
                          className={`pointer-events-none inline-block h-4 w-4 rounded-full bg-white shadow ring-0 transition-transform ${
                            player.open_to_offers ? "translate-x-4" : "translate-x-0"
                          }`}
                        />
                      </button>
                    </td>
                  )}

                  {/* Contract details (owner view) */}
                  {showContractDetails && (
                    <>
                      <td className="px-4 py-3 text-right text-slate-300">
                        {player.active_contract?.wage_weekly
                          ? formatCurrency(player.active_contract.wage_weekly)
                          : <span className="text-slate-600">—</span>}
                      </td>
                      <td className="px-4 py-3 text-slate-400">
                        {player.active_contract?.end_date
                          ? new Date(player.active_contract.end_date).toLocaleDateString("en-GB", {
                              month: "short",
                              year: "numeric",
                            })
                          : <span className="text-slate-600">—</span>}
                      </td>
                      <td className="px-4 py-3 text-right text-sm font-semibold tabular-nums text-slate-300">
                        {player.market_value != null
                          ? formatCurrency(player.market_value)
                          : <span className="text-slate-600 font-normal">—</span>}
                      </td>
                      <td className="px-4 py-3 text-right">
                        {onSetValuation && player.active_contract ? (
                          editingValuationId === player.id ? (
                            <input
                              autoFocus
                              type="text"
                              value={valuationDraft}
                              onChange={(e) => setValuationDraft(e.target.value)}
                              onBlur={() => commitValuation(player.id)}
                              onKeyDown={(e) => {
                                if (e.key === "Enter") commitValuation(player.id);
                                if (e.key === "Escape") setEditingValuationId(null);
                              }}
                              placeholder="e.g. 5000000"
                              className="w-28 rounded bg-slate-800 px-2 py-1 text-right text-xs text-white ring-1 ring-emerald-500/50 focus:outline-none"
                            />
                          ) : (
                            <button
                              onClick={() => startEditValuation(player.id, player.active_contract?.club_valuation ?? null)}
                              className="group text-right"
                              title="Click to set valuation"
                            >
                              {player.active_contract.club_valuation != null ? (
                                <span className="text-slate-300 group-hover:text-emerald-400 transition-colors">
                                  {formatCurrency(player.active_contract.club_valuation)}
                                </span>
                              ) : (
                                <span className="text-slate-600 group-hover:text-slate-400 transition-colors">
                                  Set value
                                </span>
                              )}
                            </button>
                          )
                        ) : (
                          player.active_contract?.club_valuation != null
                            ? <span className="text-slate-300">{formatCurrency(player.active_contract.club_valuation)}</span>
                            : <span className="text-slate-600">—</span>
                        )}
                      </td>
                    </>
                  )}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
