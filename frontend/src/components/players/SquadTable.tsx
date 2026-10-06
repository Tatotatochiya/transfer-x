import { useState } from "react";
import { Link } from "react-router-dom";
import type { ActiveDealStub, FairValueSignal, Player, PlayerDetail } from "../../types/api";
import { parseValuation } from "../../lib/money";
import { formatCompactCurrency, formatCurrency } from "../../lib/utils";
import PlayerLink from "../ui/PlayerLink";

/**
 * The squad as one compact table (docs/feature_spec/my-club-compact-squad):
 * a row per player (40px, or 48px "comfortable" and on touch screens),
 * column labels once, position groups as thin bands. Every field, rule and
 * action of the old card rows is kept; only the layout changed.
 */

const POSITION_TARGETS = [
  { pos: "GK", min: 2, label: "Goalkeepers" },
  { pos: "DEF", min: 4, label: "Defenders" },
  { pos: "MID", min: 4, label: "Midfielders" },
  { pos: "FWD", min: 3, label: "Forwards" },
];

const POSITION_COLOUR: Record<string, string> = {
  GK: "bg-pos-gk-bg text-pos-gk-text",
  DEF: "bg-pos-def-bg text-pos-def-text",
  MID: "bg-pos-mid-bg text-pos-mid-text",
  FWD: "bg-pos-fwd-bg text-pos-fwd-text",
};

/** Player · Contract · Wage/wk · Model · Yours · Form · Status. Shared by the
 *  header and every row so the two can't drift. */
export const SQUAD_COLS = "minmax(240px,2.4fr) 104px 72px 64px 104px 56px 150px";
/** Without contract details (another club's squad): Player · Form · Status. */
export const SQUAD_COLS_PUBLIC = "minmax(240px,1fr) 56px 150px";

export type SquadDensity = "compact" | "comfortable";

/** Where a player's sale has got to: the furthest selling card on the
 *  Transfers board (an enquiry, an offer, a bid, a deal at some stage, or
 *  just a listing). */
export interface InPlay {
  label: string;
  /** The board card's own line, e.g. "Offer sent · your reply". */
  detail: string;
  link: string;
  yourMove: boolean;
  /** Only a listing, nothing on it yet. */
  listingOnly: boolean;
}

type SquadPlayer = Player & { active_contract?: PlayerDetail["active_contract"]; active_deal?: ActiveDealStub | null };

interface Props {
  players: SquadPlayer[];
  showContractDetails?: boolean;
  formScores?: Record<string, { score: number; trend: number | null }>;
  fairValues?: Record<string, FairValueSignal>;
  /** Withdraw a player's listing — the "unlist" half of List / Unlist. */
  onUnlist?: (saleId: string, player: { id: string; name: string }) => void;
  unlistingIds?: Set<string>;
  onSetValuation?: (playerId: string, value: number | null) => void;
  /** Open listings right now, player id → listing id — drives the "Listed"
   *  chip and flag, and the row's link to the listing. */
  openListings?: Map<string, string>;
  /** When set, each row a writer sees gets a List action that calls this. */
  onList?: (player: { id: string; name: string }) => void;
  /** Why nothing can be listed right now (window closed) — disables List. */
  listBlockedReason?: string | null;
  /** Loans where this club is the *loanee*, keyed by player id. These players
   *  hold our registration and appear in the squad, but we do not own them:
   *  the server already refuses to let us list or sell them, and the row
   *  should not offer to either. */
  loanedIn?: Map<string, { endDate: string; parentClubName: string | null }>;
  /** Players with something going on (from the board's selling side), by
   *  player id: the row says how far it has got and links to it. */
  inPlay?: Map<string, InPlay>;
  /** Row height: 40px (default) or 48px. Touch screens always get 48px. */
  density?: SquadDensity;
  /** When set, the toolbar offers a Compact / Comfortable switch. */
  onDensityChange?: (density: SquadDensity) => void;
}

type ChipKey = "all" | "risk" | "inplay";

function monthsUntil(iso: string): number {
  return (new Date(iso).getTime() - Date.now()) / (30 * 86_400_000);
}

const monthYear = (iso: string) => new Date(iso).toLocaleDateString("en-GB", { month: "short", year: "numeric" });

// Ports the server's divergence banding (`backend/app/valuation/constants.py`)
// so a gap computed here lands where the API would have put it: −10..+10 is in
// line, ≤ −25 or ≥ +30 is a wide gap. Keep the two in step.
function valuationGap(pct: number): "in-line" | "notable" | "wide" {
  const p = Math.round(pct * 10) / 10; // the server bands the 1dp-rounded pct
  if (p <= -25 || p >= 30) return "wide";
  if (p <= -10 || p >= 10) return "notable";
  return "in-line";
}

const ROW_HEIGHT: Record<SquadDensity, string> = {
  compact: "h-10 pointer-coarse:h-12",
  comfortable: "h-12",
};

// A hit area that reaches 44px without making the 40px row taller.
const HIT = "-my-2 py-2";

// ── Player row ────────────────────────────────────────────────────────────────

function PlayerRow({
  player, showContractDetails, formScore, fairValue, listingId, loan, inPlay,
  onUnlist, unlisting, onSetValuation, onList, listBlockedReason, density, cols,
}: {
  player: SquadPlayer;
  showContractDetails: boolean;
  formScore?: { score: number; trend: number | null };
  fairValue?: FairValueSignal;
  listingId?: string;
  loan?: { endDate: string; parentClubName: string | null };
  inPlay?: InPlay;
  onUnlist?: (saleId: string, player: { id: string; name: string }) => void;
  unlisting?: boolean;
  onSetValuation?: (playerId: string, value: number | null) => void;
  onList?: (player: { id: string; name: string }) => void;
  listBlockedReason?: string | null;
  density: SquadDensity;
  cols: string;
}) {
  const [editingValuation, setEditingValuation] = useState(false);
  const [draft, setDraft] = useState("");

  const contractEnd = player.active_contract?.end_date;
  const contractMonths = contractEnd ? monthsUntil(contractEnd) : null;
  const contractColour = contractMonths == null ? "text-text-muted"
    : contractMonths < 6 ? "text-danger-text"
    : contractMonths < 12 ? "text-warning-text"
    : "text-text-secondary";

  // The fair-value model first, then the legacy vendor market_value (ADR 0002).
  const market = (fairValue ? Number(fairValue.fair_value) : null) ?? (player.market_value != null ? Number(player.market_value) : null);
  const valuation = player.active_contract?.club_valuation != null ? Number(player.active_contract.club_valuation) : null;
  const pct = market && valuation ? ((valuation - market) / market) * 100 : null;
  const gap = pct != null && valuationGap(pct) !== "in-line" ? { pct, wide: valuationGap(pct) === "wide" } : null;
  const wage = player.active_contract?.wage_weekly != null ? Number(player.active_contract.wage_weekly) : null;

  const flag = loan
    ? { label: "On loan", colour: "text-accent" }
    : player.active_deal?.status === "IN_PROGRESS"
    ? { label: "Transfer pending", colour: "text-warning-text" }
    : listingId
    ? { label: "Listed", colour: "text-accent" }
    : null;

  function commitValuation() {
    if (!onSetValuation) return;
    const value = parseValuation(draft);
    if (value !== undefined) onSetValuation(player.id, value); // not a figure: keep the old one
    setEditingValuation(false);
  }

  const meta = [player.age ? `${player.age}` : null, player.nationality].filter(Boolean).join(" · ");
  const editable = !!onSetValuation && !loan;
  const valuationButton = "rounded font-bold underline decoration-dotted decoration-1 underline-offset-[3px] transition-colors";

  return (
    <div
      role="row"
      style={{ gridTemplateColumns: cols }}
      className={`grid items-center gap-x-3 px-4 text-[13px] tabular-nums whitespace-nowrap shadow-[inset_0_-1px_0_var(--color-rule-faint)] transition-colors duration-150 hover:bg-surface-inset ${ROW_HEIGHT[density]}`}
    >
      {/* Player */}
      <div role="cell" className="flex min-w-0 items-center gap-2.5">
        {player.photo_url ? (
          <img src={player.photo_url} alt="" loading="lazy" className="h-[26px] w-[26px] shrink-0 rounded-full object-cover object-top ring-1 ring-border" />
        ) : (
          <span className={`flex h-[26px] w-[26px] shrink-0 items-center justify-center rounded-full text-xs font-bold ${player.position ? POSITION_COLOUR[player.position] : "bg-surface-inset text-text-muted"}`}>
            {player.name[0]?.toUpperCase()}
          </span>
        )}
        <PlayerLink id={player.id} name={player.name} title={player.name} className="min-w-0 truncate text-sm font-semibold text-text" />
        {meta && <span className="shrink-0 text-text-muted">{meta}</span>}
      </div>

      {showContractDetails && (
        <>
          {/* Contract */}
          <div role="cell" className={loan ? "text-text-secondary" : `font-semibold ${contractColour}`}>
            {loan ? `Loan · ${monthYear(loan.endDate)}` : contractEnd ? monthYear(contractEnd) : "—"}
          </div>

          {/* Wage/wk */}
          <div role="cell" className="text-right text-text">{wage ? formatCompactCurrency(wage) : "—"}</div>

          {/* Model */}
          <div role="cell" className="text-right">
            {market != null ? (
              <span
                className="text-text-secondary"
                title={fairValue ? `${formatCurrency(market)} · ${fairValue.confidence.toLowerCase()} confidence · range ${formatCompactCurrency(fairValue.fair_value_low)}–${formatCompactCurrency(fairValue.fair_value_high)}` : formatCurrency(market)}
              >
                {formatCompactCurrency(market)}
              </span>
            ) : (
              <span className="text-text-muted" title="No model valuation. The model needs a position, vendor stats and 450+ minutes played, and never estimates without them.">—</span>
            )}
          </div>

          {/* Yours: the club's own valuation, the gap to the model first */}
          <div role="cell" className="flex items-center justify-end gap-1.5">
            {loan ? (
              <span className="text-text-muted">—</span>
            ) : editingValuation ? (
              <input
                autoFocus
                type="text"
                inputMode="decimal"
                aria-label={`Your valuation of ${player.name}`}
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onBlur={commitValuation}
                onKeyDown={(e) => { if (e.key === "Enter") commitValuation(); if (e.key === "Escape") setEditingValuation(false); }}
                placeholder={market != null ? formatCompactCurrency(market) : "e.g. 18m"}
                className="w-16 rounded-md bg-surface px-1.5 py-[3px] text-right text-[13px] text-text ring-1 ring-inset ring-accent focus:outline-none"
              />
            ) : (
              <>
                {gap && valuation != null && (
                  <span
                    className={`font-semibold ${gap.wide ? "text-warning-text" : "text-text-secondary"}`}
                    title={`Your valuation is ${Math.abs(Math.round(gap.pct))}% ${gap.pct >= 0 ? "above" : "below"} the model${fairValue ? ` (${fairValue.confidence.toLowerCase()} confidence)` : ""}`}
                  >
                    {gap.pct >= 0 ? "▲" : "▼"}{Math.abs(Math.round(gap.pct))}%
                  </span>
                )}
                {valuation != null ? (
                  editable ? (
                    <button
                      type="button"
                      onClick={() => { setEditingValuation(true); setDraft(String(+(valuation / 1e6).toFixed(2)) + "m"); }}
                      title={`Edit — currently ${formatCurrency(valuation)}`}
                      className={`${HIT} ${valuationButton} text-text hover:text-accent`}
                    >
                      {formatCompactCurrency(valuation)}
                    </button>
                  ) : (
                    <span className="font-bold text-text">{formatCompactCurrency(valuation)}</span>
                  )
                ) : editable ? (
                  <button
                    type="button"
                    onClick={() => { setEditingValuation(true); setDraft(""); }}
                    title={market != null ? `Set your valuation — the model says ${formatCurrency(market)}` : "Set your valuation"}
                    className={`${HIT} ${valuationButton} font-semibold text-accent`}
                  >
                    + set
                  </button>
                ) : (
                  <span className="text-text-muted">—</span>
                )}
              </>
            )}
          </div>
        </>
      )}

      {/* Form */}
      <div role="cell" className="text-right">
        {formScore != null ? (
          <span className="font-semibold text-text">
            {formScore.score.toFixed(0)}
            {formScore.trend != null && formScore.trend > 0 && <span className="ml-[3px] text-success-text" aria-label="rising">▲</span>}
            {formScore.trend != null && formScore.trend < 0 && <span className="ml-[3px] text-danger-text" aria-label="falling">▼</span>}
          </span>
        ) : (
          <span className="text-text-muted">—</span>
        )}
      </div>

      {/* Status: on loan, listed (+ Unlist), transfer pending, List, or the flag */}
      <div role="cell" className="flex min-w-0 items-center justify-end gap-2">
        {/* Something beyond a bare listing (an enquiry, an offer, a deal):
            say how far it has got, and link to it. Unlisting a player with
            offers on him is a decision for the listing page, not a row. */}
        {!loan && inPlay && !inPlay.listingOnly ? (
          <InPlayLink inPlay={inPlay} />
        ) : loan ? (
          <span
            className="font-semibold text-accent"
            title={`On loan${loan.parentClubName ? ` from ${loan.parentClubName}` : ""} until ${new Date(loan.endDate).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" })}. He is not ours to sell.`}
          >
            On loan
          </span>
        ) : onUnlist ? (
          // A writer's row. List / Unlist wait for the listings to load
          // (onList is undefined until then), so a listed player is never
          // briefly offered "List".
          onList ? (
            listingId ? (
              <>
                <Link to={`/sales/${listingId}`} className={`${HIT} font-semibold text-accent hover:underline`}>Listed →</Link>
                <button
                  type="button"
                  disabled={unlisting}
                  onClick={() => onUnlist(listingId, { id: player.id, name: player.name })}
                  className={`${HIT} font-semibold text-text-muted hover:text-text disabled:opacity-50`}
                >
                  {unlisting ? "Unlisting…" : "Unlist"}
                </button>
              </>
            ) : player.active_deal?.status === "IN_PROGRESS" ? (
              <span className="font-semibold text-warning-text">Transfer pending</span>
            ) : (
              <button
                type="button"
                disabled={!!listBlockedReason}
                title={listBlockedReason ?? `List ${player.name} for sale`}
                onClick={() => onList({ id: player.id, name: player.name })}
                className="rounded-lg bg-surface px-2.5 py-[3px] text-[13px] font-semibold text-text-secondary ring-1 ring-inset ring-input-border hover:bg-surface-inset disabled:cursor-not-allowed disabled:opacity-50"
              >
                List
              </button>
            )
          ) : flag ? (
            <span className={`font-semibold ${flag.colour}`}>{flag.label}</span>
          ) : null
        ) : flag ? (
          <span className={`font-semibold ${flag.colour}`}>{flag.label}</span>
        ) : (
          <span className="text-text-muted">—</span>
        )}
      </div>
    </div>
  );
}

function InPlayLink({ inPlay }: { inPlay: InPlay }) {
  return (
    <Link
      to={inPlay.link}
      title={inPlay.detail}
      className={`${HIT} flex min-w-0 items-center gap-1.5 font-semibold hover:underline ${inPlay.yourMove ? "text-accent" : "text-warning-text"}`}
    >
      {inPlay.yourMove && <span className="h-2 w-2 shrink-0 rounded-full bg-accent" aria-label="Your move" />}
      <span className="truncate">{inPlay.label}</span>
      <span aria-hidden>→</span>
    </Link>
  );
}

// ── Position group: a band, then its rows ─────────────────────────────────────

function PositionBand({ label, min, total }: { label: string; min: number; total: number }) {
  // total is the whole squad's count for this position, independent of the
  // active filter chip — depth coverage shouldn't flip to "priority gap"
  // just because a filter (e.g. "Contract risk") happens to hide everyone.
  const covered = total >= min;
  return (
    <div role="row" className="flex min-h-8 items-center gap-2.5 whitespace-nowrap bg-surface-quiet px-4 shadow-[inset_0_-1px_0_var(--color-rule)]">
      <span className="text-[13px] font-bold text-text">{label}</span>
      <span className={`text-[13px] font-semibold ${covered ? "text-success-text" : "text-danger-text"}`}>
        {total} of {min} minimum — {covered ? "covered" : "priority gap"}
      </span>
    </div>
  );
}

// ── Loading ───────────────────────────────────────────────────────────────────

/** Eight static grey rows the height of the real ones (no shimmer). */
export function SquadTableSkeleton() {
  return (
    <div aria-busy="true" aria-label="Loading squad" className="overflow-hidden rounded-xl bg-surface ring-1 ring-border">
      <div className="h-[34px] bg-surface-header shadow-[inset_0_-1px_0_var(--color-rule)]" />
      {Array.from({ length: 8 }, (_, i) => (
        <div key={i} className="flex h-10 items-center px-4 shadow-[inset_0_-1px_0_var(--color-rule-faint)]">
          <div className="h-3 w-full rounded bg-surface-inset" />
        </div>
      ))}
    </div>
  );
}

// ── Main ──────────────────────────────────────────────────────────────────────

export default function SquadTable({
  players, showContractDetails = false, formScores, fairValues,
  onUnlist, unlistingIds, onSetValuation, openListings, loanedIn, inPlay, onList, listBlockedReason,
  density = "compact", onDensityChange,
}: Props) {
  const [chip, setChip] = useState<ChipKey>("all");
  const listed = openListings ?? new Map<string, string>();
  const isInPlay = (p: SquadPlayer) => listed.has(p.id) || !!inPlay?.has(p.id) || p.active_deal?.status === "IN_PROGRESS";

  if (players.length === 0) {
    return <p className="py-8 text-center text-sm text-text-muted">No players in squad.</p>;
  }

  const counts = {
    all: players.length,
    risk: players.filter((p) => p.active_contract?.end_date && monthsUntil(p.active_contract.end_date) < 12).length,
    inplay: players.filter(isInPlay).length,
  };

  const filtered = players.filter((p) => {
    if (chip === "risk") return p.active_contract?.end_date && monthsUntil(p.active_contract.end_date) < 12;
    if (chip === "inplay") return isInPlay(p);
    return true;
  });

  // Contract months ascending; no contract last.
  const byContract = (a: SquadPlayer, b: SquadPlayer) => {
    const am = a.active_contract?.end_date ? monthsUntil(a.active_contract.end_date) : Infinity;
    const bm = b.active_contract?.end_date ? monthsUntil(b.active_contract.end_date) : Infinity;
    return am - bm;
  };

  const groups = POSITION_TARGETS.map((t) => ({
    key: t.pos, label: t.label, min: t.min,
    total: players.filter((p) => p.position === t.pos).length,
    players: filtered.filter((p) => p.position === t.pos).sort(byContract),
  }));
  const unpositioned = filtered.filter((p) => !p.position);
  if (unpositioned.length > 0) {
    groups.push({
      key: "none", label: "Unpositioned", min: 0,
      total: players.filter((p) => !p.position).length,
      players: [...unpositioned].sort(byContract),
    });
  }

  const chips: { key: ChipKey; label: string }[] = [
    { key: "all", label: `All ${counts.all}` },
    { key: "risk", label: `Contract risk ${counts.risk}` },
    { key: "inplay", label: `In play ${counts.inplay}` },
  ];

  const cols = showContractDetails ? SQUAD_COLS : SQUAD_COLS_PUBLIC;
  const headers = showContractDetails
    ? ["Player", "Contract", "Wage/wk", "Model", "Yours", "Form", "Status"]
    : ["Player", "Form", "Status"];
  const rightFrom = showContractDetails ? 2 : 1; // Wage/wk onwards (or Form onwards) align right

  return (
    <div className="flex flex-col gap-3.5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap gap-2">
          {chips.map((c) => (
            <button
              key={c.key}
              onClick={() => setChip(c.key)}
              aria-pressed={chip === c.key}
              className={`whitespace-nowrap rounded-[20px] px-3 py-[5px] text-[13px] font-semibold transition-colors ${
                chip === c.key ? "bg-ink text-white" : "bg-surface text-text-secondary ring-1 ring-inset ring-input-border hover:ring-accent"
              }`}
            >
              {c.label}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-3">
          <span className="whitespace-nowrap text-[13px] text-text-muted">Sorted by contract risk</span>
          {onDensityChange && (
            <div role="group" aria-label="Row height" className="flex rounded-lg bg-surface-inset p-0.5">
              {(["compact", "comfortable"] as const).map((d) => (
                <button
                  key={d}
                  type="button"
                  aria-pressed={density === d}
                  onClick={() => onDensityChange(d)}
                  className={`rounded-md px-2 py-0.5 text-xs font-semibold capitalize transition-colors ${
                    density === d ? "bg-surface text-text shadow-sm" : "text-text-muted hover:text-text"
                  }`}
                >
                  {d}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="overflow-x-auto rounded-xl bg-surface ring-1 ring-border">
        <div role="table" aria-label="Squad" className={showContractDetails ? "min-w-[860px]" : "min-w-[520px]"}>
          <div
            role="row"
            style={{ gridTemplateColumns: cols }}
            className="grid h-[34px] items-center gap-x-3 bg-surface-header px-4 text-[11px] font-semibold uppercase tracking-[0.04em] text-text-muted shadow-[inset_0_-1px_0_var(--color-rule)]"
          >
            {headers.map((h, i) => (
              <span key={h} role="columnheader" className={i >= rightFrom ? "text-right" : ""}>{h}</span>
            ))}
          </div>

          {groups.map((g) => (
            <div key={g.key} role="rowgroup">
              <PositionBand label={g.label} min={g.min} total={g.total} />
              {g.players.length === 0 ? (
                <div role="row" className={`flex items-center px-4 text-[13px] text-text-muted shadow-[inset_0_-1px_0_var(--color-rule-faint)] ${ROW_HEIGHT[density]}`}>
                  {g.total === 0 ? `No ${g.label.toLowerCase()} in the squad.` : `No ${g.label.toLowerCase()} match this filter.`}
                </div>
              ) : (
                g.players.map((p) => (
                  <PlayerRow
                    key={p.id}
                    player={p}
                    showContractDetails={showContractDetails}
                    formScore={formScores?.[p.id]}
                    fairValue={fairValues?.[p.id]}
                    listingId={listed.get(p.id)}
                    inPlay={inPlay?.get(p.id)}
                    loan={loanedIn?.get(p.id)}
                    onUnlist={onUnlist}
                    unlisting={unlistingIds?.has(p.id)}
                    onSetValuation={onSetValuation}
                    onList={onList}
                    listBlockedReason={listBlockedReason}
                    density={density}
                    cols={cols}
                  />
                ))
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
