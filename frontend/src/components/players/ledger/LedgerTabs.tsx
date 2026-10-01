import { useState, type ReactNode } from "react";

import type { LedgerInjury, LedgerSeason, LedgerStats, PlayerLedger } from "../../../types/api";
import { ClubCell, MUTED, SeasonLedger, type LedgerRowSpec } from "./SeasonLedger";

/**
 * The profile's three tabs over one ledger (HANDOFF.md "Tab contents"):
 * Overview (column sets: Output, Passing, Defending), Career (with transfers
 * under their season) and Injuries (summary tiles, injuries under their
 * season). All figures come from GET /players/market/{id}/ledger.
 */

const n = (v: number) => v.toLocaleString("en-GB");
const per90 = (v: number, minutes: number) => (minutes > 0 ? ((v / minutes) * 90).toFixed(2) : "—");
const pct = (won: number, total: number) => (total > 0 ? `${Math.round((won / total) * 100)}%` : "—");
const rating = (r: number | null) => (r == null ? "—" : r.toFixed(2));
const appsStarts = (s: LedgerStats) => `${s.apps} (${s.starts})`;

export type StatSet = "output" | "passing" | "defending";

const SETS: Record<StatSet, { label: string; headers: string[]; cells: (s: LedgerStats) => ReactNode[] }> = {
  output: {
    label: "Output",
    headers: ["Apps", "Min", "G", "A", "G+A/90", "Shots/90", "Rating"],
    cells: (s) => [appsStarts(s), n(s.minutes), s.goals, s.assists, per90(s.goals + s.assists, s.minutes),
      per90(s.shots, s.minutes), rating(s.rating)],
  },
  passing: {
    label: "Passing",
    headers: ["Apps", "Min", "Key p.", "KP/90", "Pass %", "Assists", "Rating"],
    cells: (s) => [appsStarts(s), n(s.minutes), s.key_passes, per90(s.key_passes, s.minutes),
      s.pass_accuracy == null ? "—" : `${Math.round(s.pass_accuracy)}%`, s.assists, rating(s.rating)],
  },
  defending: {
    label: "Defending",
    headers: ["Apps", "Min", "Tackles", "Int.", "Tkl+Int/90", "Duels %", "YC"],
    cells: (s) => [appsStarts(s), n(s.minutes), s.tackles, s.interceptions,
      per90(s.tackles + s.interceptions, s.minutes), pct(s.duels_won, s.duels_total), s.yellow_cards],
  },
};
const OVERVIEW_TEMPLATE = "86px minmax(150px,2fr) repeat(7, minmax(52px,1fr))";
const FIVE_TEMPLATE = "86px minmax(150px,2fr) repeat(5, minmax(52px,1fr))";

const rowId = (s: LedgerSeason) => `${s.season}:${s.club}`;

function useExpanded(initial: string[]) {
  const [set, setSet] = useState(() => new Set(initial));
  return [set, (id: string) => setSet((prev) => {
    const next = new Set(prev);
    if (next.has(id)) next.delete(id); else next.add(id);
    return next;
  })] as const;
}

// ── Overview ──────────────────────────────────────────────────────────────────

export function OverviewLedger({ ledger, statSet, onStatSet }: {
  ledger: PlayerLedger; statSet: StatSet; onStatSet: (s: StatSet) => void;
}) {
  // The current season starts open; the rest folded.
  const [expanded, toggle] = useExpanded(ledger.seasons.slice(0, 1).map(rowId));
  const set = SETS[statSet];
  const clubs = new Set(ledger.seasons.map((s) => s.club)).size;
  const rows: LedgerRowSpec[] = ledger.seasons.map((s) => ({
    id: rowId(s), season: s.label,
    club: <ClubCell name={s.club} logo={s.club_logo} loan={s.is_loan} />,
    cells: set.cells(s.totals),
    sub: s.competitions.length > 1 ? s.competitions.map((c) => ({
      id: `${rowId(s)}:${c.name}`, club: c.name, cells: set.cells(c),
    })) : undefined,
  }));
  return (
    <div className="flex flex-col gap-3.5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex gap-0.5 rounded-lg bg-surface-inset p-[3px]" role="tablist" aria-label="Statistics">
          {(Object.keys(SETS) as StatSet[]).map((k) => (
            <button
              key={k}
              role="tab"
              aria-selected={statSet === k}
              onClick={() => onStatSet(k)}
              className={`rounded-md px-2.5 py-1 text-xs font-semibold transition-colors ${
                statSet === k ? "bg-surface text-text shadow-sm ring-1 ring-border" : "text-text-muted hover:text-text"
              }`}
            >
              {SETS[k].label}
            </button>
          ))}
        </div>
        <span className="text-xs text-text-muted">Apps (starts) · per 90 where noted · tap a season for competitions</span>
      </div>
      <SeasonLedger
        headers={set.headers} template={OVERVIEW_TEMPLATE} rows={rows} expanded={expanded} onToggle={toggle} highlightLast
        footer={ledger.career ? { label: "Career", sub: `${clubs} club${clubs === 1 ? "" : "s"}`, cells: set.cells(ledger.career) } : undefined}
        empty="No club seasons on record yet."
      />
      <FormStrip form={ledger.form} />
      {ledger.internationals.length > 0 && <Internationals seasons={ledger.internationals} set={set} />}
    </div>
  );
}

function Internationals({ seasons, set }: { seasons: LedgerSeason[]; set: (typeof SETS)[StatSet] }) {
  const [expanded, toggle] = useExpanded([]);
  return (
    <details className="rounded-lg ring-1 ring-border">
      <summary className="cursor-pointer px-3 py-2 text-sm font-semibold text-text-secondary">
        International ({seasons.reduce((a, s) => a + s.totals.apps, 0)} apps)
      </summary>
      <div className="px-1 pb-2">
        <SeasonLedger
          headers={set.headers} template={OVERVIEW_TEMPLATE} expanded={expanded} onToggle={toggle}
          rows={seasons.map((s) => ({
            id: rowId(s), season: s.label, club: <ClubCell name={s.club} logo={s.club_logo} />, cells: set.cells(s.totals),
            sub: s.competitions.length > 1 ? s.competitions.map((c) => ({ id: `${rowId(s)}:${c.name}`, club: c.name, cells: set.cells(c) })) : undefined,
          }))}
        />
      </div>
    </details>
  );
}

export function FormStrip({ form }: { form: PlayerLedger["form"] }) {
  if (form.score == null && form.recent.length === 0) return null;
  const trend = form.trend;
  return (
    <div className="flex flex-wrap items-center gap-4 rounded-lg bg-surface-inset px-3 py-2.5 ring-1 ring-border">
      <div>
        <p className="text-[11px] font-bold uppercase tracking-[0.06em] text-text-muted">Form score</p>
        <p className="text-xs text-text-muted">Last 5 games</p>
      </div>
      {form.score != null && (
        <p className="tabular-nums">
          <span className="text-xl font-extrabold text-success-text">{Math.round(form.score)}</span>
          {trend != null && trend !== 0 && (
            <span className={`ml-1.5 text-[13px] font-semibold ${trend > 0 ? "text-success-text" : "text-danger-text"}`}>
              {trend > 0 ? "▲" : "▼"} {Math.abs(Math.round(trend))}
            </span>
          )}
        </p>
      )}
      {form.recent.length > 0 && (
        <ul className="ml-auto flex flex-wrap gap-1.5" aria-label="Last five games">
          {[...form.recent].reverse().map((g, i) => (
            <li
              key={i}
              title={`${g.opponent ?? "?"}${g.competition ? ` · ${g.competition}` : ""}${g.date ? ` · ${new Date(g.date).toLocaleDateString("en-GB")}` : ""}${g.minutes != null ? ` · ${g.minutes} min` : ""}`}
              className="rounded-md bg-surface px-2 py-1 text-center ring-1 ring-border"
            >
              <span className={`block text-[13px] font-bold tabular-nums ${
                g.rating == null ? "text-text-muted" : g.rating >= 7.5 ? "text-success-text" : g.rating >= 7 ? "text-text" : "text-warning-text"
              }`}>
                {g.rating == null ? "—" : g.rating.toFixed(1)}
              </span>
              <span className="block text-[10px] uppercase text-text-muted">{(g.opponent ?? "?").replace(/[^A-Za-z]/g, "").slice(0, 3)}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// ── Career ────────────────────────────────────────────────────────────────────

export function CareerLedger({ ledger }: { ledger: PlayerLedger }) {
  const [expanded, toggle] = useExpanded([]);
  const cells = (s: LedgerStats) => [s.apps, s.starts, n(s.minutes), s.goals, s.assists];
  const placed = new Set<number>();
  const last = ledger.seasons.length - 1;
  const rows: LedgerRowSpec[] = ledger.seasons.map((s, idx) => {
    // Each move under the first row of its season.
    const moves = ledger.transfers
      .map((t, i) => ({ t, i }))
      .filter(({ t, i }) => t.season === s.season && !placed.has(i));
    moves.forEach(({ i }) => placed.add(i));
    // Moves from before the seasons on record go under the oldest one.
    const earlier = idx === last
      ? ledger.transfers.map((t, i) => ({ t, i })).filter(({ i }) => !placed.has(i) && !moves.some((m) => m.i === i))
      : [];
    return {
      id: rowId(s), season: s.label,
      club: <ClubCell name={s.club} logo={s.club_logo} loan={s.is_loan} />,
      cells: cells(s.totals),
      after: moves.length || earlier.length ? (
        <>
          {moves.map(({ t, i }) => <TransferRow key={i} move={t} />)}
          {earlier.length > 0 && (
            <p className="border-b border-rule-faint bg-surface-inset/60 py-1 pl-[30px] text-[11px] font-bold uppercase tracking-[0.05em] text-text-muted">
              Earlier moves
            </p>
          )}
          {earlier.map(({ t, i }) => <TransferRow key={i} move={t} />)}
        </>
      ) : undefined,
    };
  });
  const fees = ledger.transfers.filter((t) => t.fee && /\d/.test(t.fee)).length;
  return (
    <SeasonLedger
      headers={["Apps", "Starts", "Min", "G", "A"]} template={FIVE_TEMPLATE} rows={rows} expanded={expanded} onToggle={toggle}
      footer={ledger.career ? {
        label: "Career",
        sub: `${ledger.transfers.length} move${ledger.transfers.length === 1 ? "" : "s"}${fees ? ` · ${fees} fee${fees === 1 ? "" : "s"}` : ""}`,
        cells: cells(ledger.career),
      } : undefined}
      empty="No club seasons on record yet."
    />
  );
}

function TransferRow({ move }: { move: PlayerLedger["transfers"][number] }) {
  const loan = (move.type ?? "").toLowerCase() === "loan";
  const known = move.fee && move.fee.toLowerCase() !== "n/a";
  return (
    <div className="flex flex-wrap items-center gap-2.5 border-b border-rule-faint bg-surface-inset/60 py-1.5 pl-[30px] pr-2.5 text-xs text-text-secondary">
      <span className="w-[62px] font-bold tabular-nums text-text">
        {move.date ? new Date(move.date).toLocaleDateString("en-GB", { month: "short", year: "numeric" }) : "—"}
      </span>
      <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${loan ? "bg-warning-bg text-warning-text" : "bg-accent-bg text-accent"}`}>
        {loan ? "Loan" : "Transfer"}
      </span>
      <span className="min-w-0 truncate">
        {move.from ?? "—"} <span className="text-text-muted" aria-hidden="true">→</span>{" "}
        <span className="font-semibold text-text">{move.to ?? "—"}</span>
      </span>
      <span className={`ml-auto font-semibold tabular-nums ${known ? "text-success-text" : "text-text-muted"}`}>
        {loan ? "" : known ? move.fee : "Undisclosed"}
      </span>
    </div>
  );
}

// ── Injuries ──────────────────────────────────────────────────────────────────

export function InjuriesLedger({ ledger }: { ledger: PlayerLedger }) {
  const injuries = ledger.injuries;
  const seasons = ledger.seasons;
  const covered = new Set(seasons.map((s) => s.season));
  const periods = (injuries?.periods ?? []).filter((p) => covered.has(p.season));
  // Open the latest season with an injury that cost games.
  const firstHurt = seasons.find((s) => periods.some((p) => p.season === s.season && p.games_missed > 0));
  const [expanded, toggle] = useExpanded(firstHurt ? [rowId(firstHurt)] : []);
  if (!injuries) return <p className="text-sm text-text-muted">Sign in to see his injury record.</p>;

  // One season can have two rows (a mid-season move); injuries go on the first.
  const seen = new Set<string>();
  const rows: LedgerRowSpec[] = seasons.map((s) => {
    const first = !seen.has(s.season);
    seen.add(s.season);
    const by = first ? injuries.by_season[s.season] : undefined;
    const own = first ? periods.filter((p) => p.season === s.season) : [];
    return {
      id: rowId(s), season: s.label,
      club: <ClubCell name={s.club} logo={s.club_logo} loan={s.is_loan} />,
      cells: [
        by?.injuries ? by.injuries : MUTED,
        by?.games_missed ? <MissedCell games={by.games_missed} /> : MUTED,
        by?.availability == null ? MUTED : <AvailCell pct={by.availability} />,
        by?.longest ? `${by.longest} g` : MUTED,
        <span className="text-text-secondary">{s.totals.apps}</span>,
      ],
      sub: own.length ? own.map((p, i) => ({
        id: `${rowId(s)}:${i}`,
        season: new Date(p.start).toLocaleDateString("en-GB", { month: "short", year: "numeric" }),
        club: <InjuryPill injury={p} />,
        cells: ["", p.games_missed ? `${p.games_missed} g` : "—", "", "",
          p.end ? `to ${new Date(p.end).toLocaleDateString("en-GB", { day: "numeric", month: "short" })}` : "ongoing"],
      })) : undefined,
    };
  });

  const total = periods.length;
  const missed = periods.reduce((a, p) => a + p.games_missed, 0);
  const last = [...periods].sort((a, b) => b.start.localeCompare(a.start))[0];
  const longest = [...periods].sort((a, b) => b.games_missed - a.games_missed)[0];
  const known = seasons.map((s) => injuries.by_season[s.season]).filter((b) => b?.availability != null);
  const since = seasons.length ? seasons[seasons.length - 1].label : null;
  return (
    <div className="flex flex-col gap-3.5">
      <div className="grid grid-cols-2 gap-px overflow-hidden rounded-lg bg-border sm:grid-cols-4">
        <Tile label="Injuries" value={String(total)} sub={since ? `Since ${since}` : ""} />
        <Tile label="Games missed" value={String(missed)} sub={seasons.length ? `≈ ${Math.round(missed / new Set(seasons.map((s) => s.season)).size)} per season` : ""} />
        <Tile label="Last injury" value={last ? new Date(last.start).toLocaleDateString("en-GB", { month: "short", year: "numeric" }) : "—"}
          sub={last ? `${last.type ?? "Injury"}${last.games_missed ? ` · ${last.games_missed} games` : ""}` : "None on record"} />
        <Tile label="Longest" value={longest?.games_missed ? `${longest.games_missed} games` : "—"} danger={!!longest?.games_missed && longest.games_missed >= 10}
          sub={longest?.games_missed ? `${longest.type ?? "Injury"} · ${new Date(longest.start).getFullYear()}` : ""} />
      </div>
      <SeasonLedger
        headers={["Injuries", "Missed", "Avail.", "Longest", "Apps"]} template={FIVE_TEMPLATE} rows={rows}
        expanded={expanded} onToggle={toggle}
        footer={{
          label: "Career", sub: since ? `Since ${since}` : undefined,
          cells: [total || MUTED, missed ? <MissedCell games={missed} /> : MUTED,
            known.length ? <AvailCell pct={Math.round(known.reduce((a, b) => a + (b!.availability ?? 0), 0) / known.length)} /> : MUTED,
            longest?.games_missed ? `${longest.games_missed} g` : MUTED, ledger.career?.apps ?? 0],
        }}
        empty="No club seasons on record yet."
      />
      <p className="text-xs text-text-muted">
        Availability is the share of his clubs&rsquo; matches he wasn&rsquo;t missing through injury, where the match count is known.
        From API-Football&rsquo;s public injury records; this isn&rsquo;t medical data.
      </p>
    </div>
  );
}

function Tile({ label, value, sub, danger }: { label: string; value: string; sub: string; danger?: boolean }) {
  return (
    <div className="bg-surface px-3 py-2.5">
      <p className="text-[11px] font-bold uppercase tracking-[0.06em] text-text-muted">{label}</p>
      <p className={`text-[17px] font-bold tabular-nums ${danger ? "text-danger-text" : "text-text"}`}>{value}</p>
      <p className="truncate text-xs text-text-muted">{sub}</p>
    </div>
  );
}

function MissedCell({ games }: { games: number }) {
  return <span className={games >= 10 ? "text-danger-text" : "text-warning-text"}>{games} g</span>;
}

function AvailCell({ pct }: { pct: number }) {
  return <span className={pct >= 90 ? "text-success-text" : pct >= 75 ? "text-text" : "text-danger-text"}>{pct}%</span>;
}

function InjuryPill({ injury }: { injury: LedgerInjury }) {
  return (
    <span className={`inline-block max-w-full truncate rounded-full px-2 py-0.5 text-[11px] font-semibold ${
      injury.severe ? "bg-danger-bg text-danger-text" : "bg-warning-bg text-warning-text"
    }`}>
      {injury.type ?? "Injury"}
    </span>
  );
}
