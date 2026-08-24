import { useState } from "react";
import { Link } from "react-router-dom";
import type { ActiveDealStub, FairValueSignal, Player, PlayerDetail } from "../../types/api";
import { formatCompactCurrency, formatCurrency } from "../../lib/utils";

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

type SquadPlayer = Player & { active_contract?: PlayerDetail["active_contract"]; active_deal?: ActiveDealStub | null };

interface Props {
  players: SquadPlayer[];
  showContractDetails?: boolean;
  formScores?: Record<string, { score: number; trend: number | null }>;
  fairValues?: Record<string, FairValueSignal>;
  onToggleOpenToOffers?: (playerId: string, next: boolean) => void;
  togglingIds?: Set<string>;
  onSetValuation?: (playerId: string, value: number | null) => void;
  /** Player IDs with an open listing right now — drives the "Listed" chip and flag. */
  listedPlayerIds?: Set<string>;
}

type ChipKey = "all" | "risk" | "listed" | "open";

function monthsUntil(iso: string): number {
  return (new Date(iso).getTime() - Date.now()) / (30 * 86_400_000);
}

// Ports the server's divergence banding (`backend/app/valuation/constants.py`)
// so a gap computed here lands where the API would have put it: −10..+10 is in
// line, ≤ −25 or ≥ +30 is a wide gap. Keep the two in step.
function valuationGap(pct: number): "in-line" | "notable" | "wide" {
  const p = Math.round(pct * 10) / 10; // the server bands the 1dp-rounded pct
  if (p <= -25 || p >= 30) return "wide";
  if (p <= -10 || p >= 10) return "notable";
  return "in-line";
}

// ── Player row ────────────────────────────────────────────────────────────────

function PlayerRow({
  player, showContractDetails, formScore, fairValue, isListed,
  onToggleOpenToOffers, toggling, onSetValuation,
}: {
  player: SquadPlayer;
  showContractDetails: boolean;
  formScore?: { score: number; trend: number | null };
  fairValue?: FairValueSignal;
  isListed: boolean;
  onToggleOpenToOffers?: (playerId: string, next: boolean) => void;
  toggling?: boolean;
  onSetValuation?: (playerId: string, value: number | null) => void;
}) {
  const [editingValuation, setEditingValuation] = useState(false);
  const [draft, setDraft] = useState("");

  const contractEnd = player.active_contract?.end_date;
  const contractMonths = contractEnd ? monthsUntil(contractEnd) : null;
  const contractColour = contractMonths == null ? "text-text-muted"
    : contractMonths < 6 ? "text-danger-text"
    : contractMonths < 12 ? "text-warning-text"
    : "text-text-secondary";

  // Prefer the fair-value model (real, ~30% coverage today) over the legacy
  // vendor market_value field (currently 0% populated — enrichment is a
  // documented no-op with no source configured) — same source order as B6's
  // contract-cliff value-at-risk (ADR 0002), applied here too since the model
  // figure was being computed and passed in but never actually displayed.
  const market = (fairValue ? Number(fairValue.fair_value) : null) ?? player.market_value ?? null;
  const valuation = player.active_contract?.club_valuation ?? null;
  const pct = market && valuation ? ((valuation - market) / market) * 100 : null;
  // Only a real gap is worth pixels; narrowing here also keeps the JSX free of
  // non-null assertions.
  const gap =
    pct != null && valuationGap(pct) !== "in-line"
      ? { pct, wide: valuationGap(pct) === "wide" }
      : null;

  const flag = player.active_deal?.status === "IN_PROGRESS"
    ? { label: "Transfer pending", colour: "text-warning-text" }
    : isListed
    ? { label: "Listed", colour: "text-accent" }
    : player.open_to_offers
    ? { label: "Open to offers", colour: "text-success-text" }
    : null;

  function commitValuation() {
    if (!onSetValuation) return;
    const parsed = draft.trim() === "" ? null : Number(draft.replace(/[^0-9.]/g, ""));
    onSetValuation(player.id, parsed != null && !isNaN(parsed) ? parsed : null);
    setEditingValuation(false);
  }

  return (
    <div className="rounded-xl bg-surface ring-1 ring-border px-5 py-3.5">
      <div className="flex flex-wrap items-center gap-[18px]">
        {/* Avatar */}
        <div className="shrink-0">
          {player.photo_url ? (
            <img src={player.photo_url} alt={player.name} loading="lazy" className="h-[38px] w-[38px] rounded-full object-cover ring-1 ring-border" />
          ) : (
            <div className={`flex h-[38px] w-[38px] items-center justify-center rounded-full text-sm font-bold ${player.position ? POSITION_COLOUR[player.position] : "bg-surface-inset text-text-muted"}`}>
              {player.name[0]?.toUpperCase()}
            </div>
          )}
        </div>

        {/* Identity */}
        <div className="flex-1 basis-[170px] min-w-0">
          <Link to={`/players/market/${player.id}`} className="text-[15px] font-semibold text-text hover:text-accent transition-colors">
            {player.name}
          </Link>
          <p className="text-xs text-text-muted">
            {[player.age ? `${player.age}y` : null, player.nationality].filter(Boolean).join(" · ") || "—"}
          </p>
        </div>

        {/* Contract */}
        {showContractDetails && (
          <div className="basis-[120px] shrink">
            <p className="text-[11px] text-text-muted">Contract ends</p>
            <p className={`text-sm font-semibold ${contractColour}`}>
              {contractEnd ? new Date(contractEnd).toLocaleDateString("en-GB", { month: "short", year: "numeric" }) : "—"}
            </p>
          </div>
        )}

        {/* Wage */}
        {showContractDetails && (
          <div className="basis-[90px] shrink">
            <p className="text-[11px] text-text-muted">Wage / wk</p>
            <p className="text-sm font-semibold text-text">
              {player.active_contract?.wage_weekly ? formatCurrency(player.active_contract.wage_weekly) : "—"}
            </p>
          </div>
        )}

        {/* Valuation — two aligned rows, the model's figure always on top and the
            club's own beneath it, so the figures line up as a column you can
            scan down the squad. Replaced a uniform three-line widget that spent
            most of its space on the rows with the least to say: `club_valuation`
            is only ever set by hand, so a row nobody had valued still rendered
            an empty comparison bar and a "set yours" hint.

            The model row renders even when there is no model figure, because
            that absence is itself information rather than a hole —
            `valuation/service.py:51` refuses a row for a player under 450
            minutes, with no position, or with no vendor stats, "never a made-up
            number", so a dash here reads as fringe/injured/new rather than as a
            bug. The 14px/600 weight goes to whichever figure is the club's best
            answer — its own valuation where one exists, the model's otherwise —
            so the cell always carries exactly one value-sized figure like the
            Contract and Wage cells beside it.

            Colour tracks the *size* of the gap, not its direction: for a player
            you already own, carrying him above or below the model are both
            merely facts, and D5's copy rule is that the model never renders a
            verdict. */}
        {showContractDetails && (
          <div className="hidden md:block basis-[170px] shrink">
            {/* Model — always present, dash and all. */}
            <div className="flex items-baseline gap-x-1.5">
              <span className="w-[38px] shrink-0 text-[13px] text-text-muted">model</span>
              {market != null ? (
                <span
                  className={`tabular-nums ${valuation == null ? "text-sm font-semibold text-text" : "text-[13px] text-text-secondary"}`}
                  title={fairValue ? `${formatCurrency(market)} · ${fairValue.confidence.toLowerCase()} confidence · range ${formatCompactCurrency(fairValue.fair_value_low)}–${formatCompactCurrency(fairValue.fair_value_high)}` : formatCurrency(market)}
                >
                  {formatCompactCurrency(market)}
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

            {/* The club's own. */}
            {editingValuation ? (
              <input
                autoFocus type="text" inputMode="numeric" value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onBlur={commitValuation}
                onKeyDown={(e) => { if (e.key === "Enter") commitValuation(); if (e.key === "Escape") setEditingValuation(false); }}
                placeholder={market != null ? formatCompactCurrency(market) : "Amount"}
                className="mt-0.5 w-full rounded bg-surface-inset px-1.5 py-1 text-[13px] text-text ring-1 ring-accent focus:outline-none"
              />
            ) : valuation == null ? (
              <div className="flex items-baseline gap-x-1.5">
                <span className="w-[38px] shrink-0 text-[13px] text-text-muted">yours</span>
                {onSetValuation ? (
                  // Deliberately the same weight as the edit affordance below
                  // rather than a full button: a 44px button (rule 6) would add
                  // 26px to the *majority* of rows, and it would be the only
                  // rule-6-compliant control in a table whose open-to-offers
                  // toggle is 20×36px. The negative margin buys hit area
                  // without costing row height. Touch targets here need a
                  // table-wide decision, not one compliant outlier.
                  <button
                    onClick={() => { setEditingValuation(true); setDraft(""); }}
                    title={market != null ? `Set your valuation — the model says ${formatCurrency(market)}` : "Set your valuation"}
                    className="-my-1 rounded px-1.5 py-1 text-[13px] font-semibold text-accent underline decoration-dotted decoration-1 underline-offset-[3px] transition-colors hover:bg-surface-inset"
                  >
                    + set
                  </button>
                ) : (
                  <span className="text-[13px] text-text-muted">—</span>
                )}
              </div>
            ) : (
              <div className="flex flex-wrap items-baseline gap-x-1.5">
                <span className="w-[38px] shrink-0 text-[13px] text-text-muted">yours</span>
                {onSetValuation ? (
                  <button
                    onClick={() => { setEditingValuation(true); setDraft(String(valuation)); }}
                    title={`Edit — currently ${formatCurrency(valuation)}`}
                    className="text-sm font-semibold text-text underline decoration-dotted decoration-1 underline-offset-[3px] transition-colors hover:text-accent"
                  >
                    {formatCompactCurrency(valuation)}
                  </button>
                ) : (
                  <span className="text-sm font-semibold text-text tabular-nums">{formatCompactCurrency(valuation)}</span>
                )}
                {gap && (
                  <span
                    className={`text-[13px] font-semibold tabular-nums ${gap.wide ? "text-warning-text" : "text-text-secondary"}`}
                    title={`Your valuation is ${Math.abs(Math.round(gap.pct))}% ${gap.pct >= 0 ? "above" : "below"} the model${fairValue ? ` (${fairValue.confidence.toLowerCase()} confidence)` : ""}`}
                  >
                    {gap.pct >= 0 ? "▲" : "▼"} {Math.abs(Math.round(gap.pct))}%
                  </span>
                )}
              </div>
            )}
          </div>
        )}

        {/* Flag / open-to-offers toggle */}
        <div className="flex shrink-0 basis-[110px] justify-end">
          {onToggleOpenToOffers ? (
            <button
              disabled={toggling || player.active_deal?.status === "IN_PROGRESS"}
              title={player.active_deal?.status === "IN_PROGRESS" ? "Cannot change while a transfer is in progress" : undefined}
              onClick={() => onToggleOpenToOffers(player.id, !player.open_to_offers)}
              className={`relative inline-flex h-5 w-9 shrink-0 rounded-full transition-colors disabled:opacity-50 ${player.open_to_offers ? "bg-success" : "bg-border"}`}
              aria-label={player.open_to_offers ? "Disable open to offers" : "Enable open to offers"}
            >
              <span className={`pointer-events-none inline-block h-4 w-4 translate-y-0.5 rounded-full bg-white shadow transition-transform ${player.open_to_offers ? "translate-x-[18px]" : "translate-x-0.5"}`} />
            </button>
          ) : flag ? (
            <span className={`text-xs font-semibold ${flag.colour}`}>{flag.label}</span>
          ) : (
            <span className="text-xs text-text-muted">—</span>
          )}
        </div>
      </div>

      {/* Form score, shown as a secondary line to avoid crowding the primary row */}
      {formScore != null && (
        <p className="mt-1.5 text-[11px] text-text-muted">Form {formScore.score.toFixed(0)}{formScore.trend != null && (formScore.trend > 0 ? " ↑" : formScore.trend < 0 ? " ↓" : "")}</p>
      )}
    </div>
  );
}

// ── Position group ────────────────────────────────────────────────────────────

function PositionGroup({
  pos, label, min, total, players, ...rowProps
}: {
  pos: string; label: string; min: number; total: number; players: SquadPlayer[];
} & Omit<Parameters<typeof PlayerRow>[0], "player" | "isListed" | "toggling" | "formScore" | "fairValue">
  & { listedPlayerIds: Set<string>; formScores?: Record<string, { score: number; trend: number | null }>; fairValues?: Record<string, FairValueSignal>; togglingIds?: Set<string> }) {
  // total is the whole squad's count for this position, independent of the
  // active filter chip — depth coverage shouldn't flip to "priority gap"
  // just because a filter (e.g. "Contract risk") happens to hide everyone.
  const covered = total >= min;

  return (
    <div className="mb-[22px]">
      <div className="mb-2.5 flex items-center gap-2.5">
        <h3 className="text-[15px] font-bold text-text">{label}</h3>
        <span className={`text-[13px] font-semibold ${covered ? "text-success-text" : "text-danger-text"}`}>
          {total} of {min} minimum — {covered ? "covered" : "priority gap"}
        </span>
      </div>
      {players.length === 0 ? (
        <p className="text-sm text-text-muted">
          {total === 0 ? `No ${label.toLowerCase()} in the squad.` : `No ${label.toLowerCase()} match this filter.`}
        </p>
      ) : (
        <div className="space-y-2">
          {players.map((p) => (
            <PlayerRow
              key={p.id}
              player={p}
              showContractDetails={rowProps.showContractDetails}
              formScore={rowProps.formScores?.[p.id]}
              fairValue={rowProps.fairValues?.[p.id]}
              isListed={rowProps.listedPlayerIds.has(p.id)}
              onToggleOpenToOffers={rowProps.onToggleOpenToOffers}
              toggling={rowProps.togglingIds?.has(p.id)}
              onSetValuation={rowProps.onSetValuation}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// ── Main ──────────────────────────────────────────────────────────────────────

export default function SquadTable({
  players, showContractDetails = false, formScores, fairValues,
  onToggleOpenToOffers, togglingIds, onSetValuation, listedPlayerIds,
}: Props) {
  const [chip, setChip] = useState<ChipKey>("all");
  const listed = listedPlayerIds ?? new Set<string>();

  if (players.length === 0) {
    return <p className="py-8 text-center text-sm text-text-muted">No players in squad.</p>;
  }

  const counts = {
    all: players.length,
    risk: players.filter((p) => p.active_contract?.end_date && monthsUntil(p.active_contract.end_date) < 12).length,
    listed: players.filter((p) => listed.has(p.id)).length,
    open: players.filter((p) => p.open_to_offers).length,
  };

  const filtered = players.filter((p) => {
    if (chip === "risk") return p.active_contract?.end_date && monthsUntil(p.active_contract.end_date) < 12;
    if (chip === "listed") return listed.has(p.id);
    if (chip === "open") return p.open_to_offers;
    return true;
  });

  const groups = POSITION_TARGETS.map((t) => ({
    ...t,
    total: players.filter((p) => p.position === t.pos).length,
    players: filtered.filter((p) => p.position === t.pos),
  }));
  const unpositioned = filtered.filter((p) => !p.position);

  const chips: { key: ChipKey; label: string }[] = [
    { key: "all", label: `All ${counts.all}` },
    { key: "risk", label: `Contract risk ${counts.risk}` },
    { key: "listed", label: `Listed ${counts.listed}` },
    { key: "open", label: `Open to offers ${counts.open}` },
  ];

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap gap-2">
          {chips.map((c) => (
            <button
              key={c.key}
              onClick={() => setChip(c.key)}
              className={`rounded-lg px-3.5 py-1.5 text-[13px] font-semibold transition-colors ${
                chip === c.key ? "bg-ink text-white" : "bg-surface text-text-secondary ring-1 ring-input-border hover:ring-accent"
              }`}
            >
              {c.label}
            </button>
          ))}
        </div>
        <span className="text-[13px] text-text-muted">Sorted by contract risk</span>
      </div>

      {groups.map((g) => (
        <PositionGroup
          key={g.pos}
          pos={g.pos}
          label={g.label}
          min={g.min}
          total={g.total}
          players={[...g.players].sort((a, b) => {
            const am = a.active_contract?.end_date ? monthsUntil(a.active_contract.end_date) : Infinity;
            const bm = b.active_contract?.end_date ? monthsUntil(b.active_contract.end_date) : Infinity;
            return am - bm;
          })}
          showContractDetails={showContractDetails}
          formScores={formScores}
          fairValues={fairValues}
          onToggleOpenToOffers={onToggleOpenToOffers}
          togglingIds={togglingIds}
          onSetValuation={onSetValuation}
          listedPlayerIds={listed}
        />
      ))}

      {unpositioned.length > 0 && (
        <PositionGroup
          pos="—"
          label="Unpositioned"
          min={0}
          total={players.filter((p) => !p.position).length}
          players={unpositioned}
          showContractDetails={showContractDetails}
          formScores={formScores}
          fairValues={fairValues}
          onToggleOpenToOffers={onToggleOpenToOffers}
          togglingIds={togglingIds}
          onSetValuation={onSetValuation}
          listedPlayerIds={listed}
        />
      )}
    </div>
  );
}
