import { useState } from "react";
import type { PlayerForm, PlayerStats } from "../../types/api";
import type { PlayerPosition } from "../../types/enums";
import FormBadge from "./FormBadge";

const LEAGUE_NAMES: Record<string, string> = {
  "39":  "Premier League",
  "61":  "Ligue 1",
  "78":  "Bundesliga",
  "135": "Serie A",
  "140": "La Liga",
  "45":  "FA Cup",
  "48":  "League Cup",
  "2":   "Champions League",
  "667": "Europa Conference",
  "15":  "Club World Cup",
  "528": "UEFA Super Cup",
};

interface Props {
  stats: PlayerStats[];
  form: PlayerForm | null;
  position?: PlayerPosition | null;
}

// ── Primitives ────────────────────────────────────────────────────────────────

type StatBoxAccent = "emerald" | "blue" | "amber" | "slate" | "red" | "violet";

const accentCls: Record<StatBoxAccent, { bg: string; value: string }> = {
  emerald: { bg: "bg-emerald-500/10 ring-emerald-500/20", value: "text-emerald-400" },
  blue:    { bg: "bg-blue-500/10 ring-blue-500/20",       value: "text-blue-400" },
  amber:   { bg: "bg-amber-500/10 ring-amber-500/20",     value: "text-amber-400" },
  slate:   { bg: "bg-slate-800/70 ring-white/[0.06]",     value: "text-white" },
  red:     { bg: "bg-red-500/10 ring-red-500/20",         value: "text-red-400" },
  violet:  { bg: "bg-violet-500/10 ring-violet-500/20",   value: "text-violet-400" },
};

function StatBox({
  label,
  value,
  sub,
  accent = "slate",
}: {
  label: string;
  value: string | number | null | undefined;
  sub?: string;
  accent?: StatBoxAccent;
}) {
  const cls = accentCls[accent];
  return (
    <div className={`flex flex-col items-center rounded-xl px-3 py-3 min-w-0 ring-1 ${cls.bg}`}>
      <span className={`text-2xl font-bold tabular-nums leading-none ${cls.value}`}>
        {value != null && value !== "" ? value : <span className="text-slate-600">—</span>}
      </span>
      {sub && <span className="mt-0.5 text-[10px] text-slate-500">{sub}</span>}
      <span className="mt-1 text-[11px] text-slate-500 text-center leading-tight">{label}</span>
    </div>
  );
}

function StatRow({
  label,
  value,
  highlight,
}: {
  label: string;
  value: string | number | null | undefined;
  highlight?: string;
}) {
  if (value == null) return null;
  return (
    <div className="flex items-center justify-between py-1.5 border-b border-white/[0.04] last:border-0">
      <span className="text-sm text-slate-400">{label}</span>
      <span className={`text-sm font-semibold tabular-nums ${highlight ?? "text-white"}`}>{value}</span>
    </div>
  );
}

type SectionTheme = "default" | "emerald" | "blue" | "red" | "amber" | "violet";

const sectionThemeCls: Record<SectionTheme, { wrapper: string; bar: string; title: string }> = {
  default: { wrapper: "bg-slate-800/40 ring-white/[0.06]",      bar: "bg-slate-600",   title: "text-slate-500" },
  emerald: { wrapper: "bg-emerald-500/[0.07] ring-emerald-500/20", bar: "bg-emerald-500", title: "text-emerald-500" },
  blue:    { wrapper: "bg-blue-500/[0.07] ring-blue-500/20",       bar: "bg-blue-500",    title: "text-blue-500" },
  red:     { wrapper: "bg-red-500/[0.07] ring-red-500/20",         bar: "bg-red-500",     title: "text-red-500" },
  amber:   { wrapper: "bg-amber-500/[0.07] ring-amber-500/20",     bar: "bg-amber-500",   title: "text-amber-500" },
  violet:  { wrapper: "bg-violet-500/[0.07] ring-violet-500/20",   bar: "bg-violet-500",  title: "text-violet-500" },
};

function Section({
  title,
  theme = "default",
  children,
}: {
  title: string;
  theme?: SectionTheme;
  children: React.ReactNode;
}) {
  const cls = sectionThemeCls[theme];
  return (
    <div className={`rounded-xl px-4 py-3 ring-1 ${cls.wrapper}`}>
      <div className="mb-2.5 flex items-center gap-2">
        <span className={`h-2.5 w-2.5 rounded-sm ${cls.bar}`} />
        <p className={`text-[11px] font-bold uppercase tracking-wider ${cls.title}`}>{title}</p>
      </div>
      {children}
    </div>
  );
}

// ── Derived metrics ───────────────────────────────────────────────────────────

function pct(made: number | null, total: number | null): string | null {
  if (made == null || total == null || total === 0) return null;
  return `${Math.round((made / total) * 100)}%`;
}

// ── Position-specific stat groups ─────────────────────────────────────────────

function CoreGrid({ s }: { s: PlayerStats }) {
  const starterPct =
    s.appearances > 0 && s.lineups != null
      ? Math.round((s.lineups / s.appearances) * 100)
      : null;

  return (
    <div className="space-y-2">
      <div className="grid grid-cols-4 gap-2">
        <StatBox label="Goals"   value={s.goals}       accent="emerald" />
        <StatBox label="Assists" value={s.assists}      accent="blue" />
        <StatBox label="Apps"    value={s.appearances}  accent="slate"
                 sub={s.lineups != null ? `${s.lineups} starts` : undefined} />
        <StatBox label="Rating"  value={s.avg_rating != null ? Number(s.avg_rating).toFixed(1) : null} accent="amber" />
      </div>

      {/* Starter / sub usage bar */}
      {s.appearances > 0 && (s.lineups != null || s.substitutes_in != null) && (
        <div className="rounded-xl bg-slate-800/50 px-4 py-2.5 ring-1 ring-white/[0.05]">
          <div className="flex items-center justify-between text-[11px] text-slate-500 mb-1.5">
            <span>Usage</span>
            <span className="tabular-nums">
              {s.lineups ?? 0} starts · {s.substitutes_in ?? 0} sub appearances · {s.substitutes_bench ?? 0} on bench
            </span>
          </div>
          {starterPct != null && (
            <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-700">
              <div
                className="h-full rounded-full bg-emerald-500 transition-all"
                style={{ width: `${starterPct}%` }}
              />
            </div>
          )}
          {starterPct != null && (
            <div className="mt-1 flex justify-between text-[10px] text-slate-600">
              <span>Starter {starterPct}%</span>
              <span>Sub {100 - starterPct}%</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function GKStats({ s }: { s: PlayerStats }) {
  return (
    <Section title="Goalkeeping" theme="amber">
      <StatRow label="Saves"          value={s.saves}          highlight="text-amber-400" />
      <StatRow label="Goals Conceded" value={s.goals_conceded} highlight="text-red-400" />
      <StatRow label="Minutes"        value={s.minutes != null ? `${s.minutes.toLocaleString()} min` : null} />
    </Section>
  );
}

function DEFStats({ s }: { s: PlayerStats }) {
  const duelWin = pct(s.duels_won, s.duels_total);
  return (
    <div className="space-y-3">
      <Section title="Defending" theme="blue">
        <StatRow label="Tackles"         value={s.tackles_total}  highlight="text-blue-400" />
        <StatRow label="Interceptions"   value={s.interceptions}  highlight="text-blue-400" />
        <StatRow label="Blocks"          value={s.blocks}         highlight="text-blue-400" />
        <StatRow label="Duel Win %"      value={duelWin}          highlight="text-blue-300" />
        <StatRow label="Dribbled Past"   value={s.dribbles_past}  highlight="text-red-400" />
      </Section>
      <Section title="Discipline" theme="violet">
        <StatRow label="Yellow Cards"     value={s.yellow_cards}    highlight="text-amber-400" />
        <StatRow label="2nd Yellow"       value={s.cards_yellowred} highlight="text-amber-500" />
        <StatRow label="Red Cards"        value={s.red_cards}       highlight="text-red-400" />
        <StatRow label="Fouls Committed"  value={s.fouls_committed} />
      </Section>
    </div>
  );
}

function MIDStats({ s }: { s: PlayerStats }) {
  const dribblePct = pct(s.dribbles_success, s.dribbles_attempts);
  return (
    <div className="space-y-3">
      <Section title="Passing & Creativity" theme="emerald">
        <StatRow label="Key Passes"    value={s.key_passes}     highlight="text-emerald-400" />
        <StatRow label="Pass Accuracy" value={s.pass_accuracy != null ? `${s.pass_accuracy}%` : null} highlight="text-emerald-400" />
        <StatRow label="Dribbles"      value={dribblePct ? `${s.dribbles_success}/${s.dribbles_attempts} (${dribblePct})` : s.dribbles_success} />
      </Section>
      <Section title="Defending & Discipline" theme="blue">
        <StatRow label="Tackles"          value={s.tackles_total}   highlight="text-blue-400" />
        <StatRow label="Interceptions"    value={s.interceptions}   highlight="text-blue-400" />
        <StatRow label="Yellow Cards"     value={s.yellow_cards}    highlight="text-amber-400" />
        <StatRow label="Fouls Committed"  value={s.fouls_committed} />
      </Section>
    </div>
  );
}

function FWDStats({ s }: { s: PlayerStats }) {
  const shotAcc   = pct(s.shots_on_target, s.shots_total);
  const dribblePct = pct(s.dribbles_success, s.dribbles_attempts);
  return (
    <div className="space-y-3">
      <Section title="Attack" theme="red">
        <StatRow label="Shots"            value={s.shots_total} />
        <StatRow label="Shots on Target"  value={shotAcc ? `${s.shots_on_target}/${s.shots_total} (${shotAcc})` : s.shots_on_target} highlight="text-red-400" />
        <StatRow label="Dribbles"         value={dribblePct ? `${s.dribbles_success}/${s.dribbles_attempts} (${dribblePct})` : s.dribbles_success} />
        <StatRow label="Fouls Drawn"      value={s.fouls_drawn} />
      </Section>
      {((s.penalty_scored ?? 0) > 0 || (s.penalty_missed ?? 0) > 0 || (s.penalty_won ?? 0) > 0) && (
        <Section title="Penalties" theme="violet">
          <StatRow label="Won"    value={s.penalty_won}    highlight="text-emerald-400" />
          <StatRow label="Scored" value={s.penalty_scored} highlight="text-emerald-400" />
          <StatRow label="Missed" value={s.penalty_missed} highlight="text-red-400" />
        </Section>
      )}
    </div>
  );
}

// ── Form score block ──────────────────────────────────────────────────────────

function FormBlock({ form }: { form: PlayerForm }) {
  const score = Number(form.form_score);
  const trend = form.trend != null ? Number(form.trend) : null;
  const barColour =
    score >= 75 ? "bg-emerald-400"
    : score >= 55 ? "bg-green-400"
    : score >= 35 ? "bg-amber-400"
    : "bg-red-400";

  return (
    <div className="flex items-center justify-between rounded-xl bg-slate-800/70 px-5 py-4 ring-1 ring-white/[0.06]">
      <div>
        <p className="text-xs font-bold uppercase tracking-wider text-slate-400">Form Score</p>
        <p className="mt-0.5 text-xs text-slate-500">Last {form.games_considered} games</p>
      </div>
      <div className="flex items-center gap-3">
        <div className="hidden sm:block w-28 overflow-hidden rounded-full bg-slate-700 h-2">
          <div
            className={`h-full rounded-full transition-all ${barColour}`}
            style={{ width: `${Math.min(100, score)}%` }}
          />
        </div>
        <FormBadge score={score} trend={trend} size="md" />
      </div>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export default function StatsPanel({ stats, form, position }: Props) {
  // Sort once: prefer records with a team name, then by appearances desc
  const sorted = stats.length > 0
    ? [...stats].sort((a, b) => {
        const aHasTeam = a.team_name ? 1 : 0;
        const bHasTeam = b.team_name ? 1 : 0;
        if (bHasTeam !== aHasTeam) return bHasTeam - aHasTeam;
        return b.appearances - a.appearances;
      })
    : [];

  const [selectedIdx, setSelectedIdx] = useState(0);
  const primary = sorted[selectedIdx] ?? null;

  if (!primary && !form) {
    return (
      <div className="rounded-xl bg-slate-800/40 px-5 py-4 text-sm text-slate-500 ring-1 ring-white/[0.06]">
        No performance data available yet.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Season selector — tabs when multiple records exist */}
      {sorted.length > 1 && (
        <div className="flex flex-wrap gap-1.5">
          {sorted.map((s, i) => {
            const leagueName = s.league_id ? (LEAGUE_NAMES[s.league_id] ?? `League ${s.league_id}`) : null;
            const parts = [leagueName ?? s.team_name, s.season, s.position_played].filter(Boolean);
            const label = parts.join(" · ") || `Record ${i + 1}`;
            return (
              <button
                key={s.id}
                onClick={() => setSelectedIdx(i)}
                className={`rounded-lg px-3 py-1.5 text-xs font-medium ring-1 transition-colors ${
                  i === selectedIdx
                    ? "bg-emerald-500/15 text-emerald-400 ring-emerald-500/30"
                    : "bg-slate-800 text-slate-400 ring-white/[0.06] hover:text-white"
                }`}
              >
                {label}
              </button>
            );
          })}
        </div>
      )}

      {/* Season / team header when single record */}
      {primary && sorted.length === 1 && (
        <div className="flex items-center justify-between text-xs text-slate-500">
          <div className="flex items-center gap-2">
            <span className="font-medium text-slate-400">
              {primary.league_id ? (LEAGUE_NAMES[primary.league_id] ?? primary.team_name ?? "—") : (primary.team_name ?? "—")}
            </span>
            {primary.position_played && (
              <span className="rounded-full bg-slate-700 px-2 py-0.5 text-[10px] font-bold text-slate-300">
                {primary.position_played}
              </span>
            )}
          </div>
          <span>{primary.season ?? ""}</span>
        </div>
      )}

      {/* Core grid — goals / assists / apps / rating */}
      {primary && <CoreGrid s={primary} />}

      {/* Minutes */}
      {primary?.minutes != null && (
        <p className="text-right text-xs text-slate-600">
          {primary.minutes.toLocaleString()} minutes played
        </p>
      )}

      {/* Position-specific sections */}
      {primary && (
        <div className="space-y-3">
          {primary.saves != null && <GKStats s={primary} />}
          {(primary.shots_total != null || primary.shots_on_target != null || primary.fouls_drawn != null) && (
            <FWDStats s={primary} />
          )}
          {(primary.key_passes != null || primary.pass_accuracy != null || primary.dribbles_attempts != null) && (
            <MIDStats s={primary} />
          )}
          {(primary.tackles_total != null || primary.interceptions != null || primary.blocks != null) && (
            <DEFStats s={primary} />
          )}
        </div>
      )}

      {/* Form score */}
      {form && <FormBlock form={form} />}
    </div>
  );
}
