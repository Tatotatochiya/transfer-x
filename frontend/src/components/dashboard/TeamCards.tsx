import { Link } from "react-router-dom";

import { POSITION_TARGETS, type TeamSummary } from "./squadSummary";

function PositionBar({ byPosition }: { byPosition: TeamSummary["summary"]["byPosition"] }) {
  const total = POSITION_TARGETS.reduce((n, t) => n + byPosition[t.pos], 0);
  return (
    <div className="flex gap-1" aria-label="Players by position">
      {POSITION_TARGETS.map((t) => {
        const n = byPosition[t.pos];
        return (
          <span key={t.pos} title={`${t.label}: ${n}`}
            className="min-w-9 rounded-md bg-surface-inset px-1.5 py-1 text-center text-caption font-semibold text-text-secondary"
            style={{ flexGrow: total > 0 ? Math.max(n, 1) : 1, flexBasis: 0 }}>
            <span className="hidden sm:inline">{t.pos} </span>{n}
          </span>
        );
      })}
    </div>
  );
}

function Line({ label, children, tone = "text-text" }: { label: string; children: React.ReactNode; tone?: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3 text-small">
      <span className="text-text-secondary">{label}</span>
      <span className={`font-semibold tabular-nums ${tone}`}>{children}</span>
    </div>
  );
}

function TeamCard({ team, wide }: { team: TeamSummary; wide: boolean }) {
  const s = team.summary;
  const figures = (
    <div className="flex gap-6">
      <div>
        <p className="text-title font-bold tabular-nums text-text">{s.count}</p>
        <p className="text-small text-text-secondary">players</p>
      </div>
      <div>
        <p className="text-title font-bold tabular-nums text-text">{s.averageAge?.toFixed(1) ?? "—"}</p>
        <p className="text-small text-text-secondary">average age</p>
      </div>
    </div>
  );
  const lines = (
    <div className="space-y-1.5">
      <Line label="Contracts ending in 6 months" tone={s.endingSoon > 0 ? "text-warning-text" : "text-text"}>{s.endingSoon}</Line>
      <Line label="Aged 21 or under">{s.under21}</Line>
      <Line label="Squad needs" tone={s.gaps.length ? "text-danger-text" : "text-text"}>
        {s.gaps.length === 0 ? "Covered" : (
          <>Need {s.gaps.map((g, i) => (
            <span key={g.pos}>{i > 0 && ", "}
              <Link to={`/players/market?position=${g.pos}`} className="hover:underline">{g.need} {g.pos}</Link>
            </span>
          ))}</>
        )}
      </Line>
    </div>
  );
  return (
    <article className="min-w-0 rounded-2xl bg-surface p-4 ring-1 ring-border">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-body font-semibold text-text">{team.name}</h3>
        <Link to="/club" className="text-small font-semibold text-accent hover:underline">View →</Link>
      </div>
      <div className={wide ? "grid gap-4 xl:grid-cols-3 xl:items-center xl:gap-8" : "space-y-3"}>
        {figures}
        <PositionBar byPosition={s.byPosition} />
        {lines}
      </div>
    </article>
  );
}

/**
 * One card per team the viewer can see (feature_spec/club-dashboard §4.4,
 * product ADR 0013). Today every club has one team, its first team.
 */
export default function TeamCards({ teams }: { teams: TeamSummary[] }) {
  if (teams.length === 0) return null;
  const many = teams.length > 1;
  return (
    <section aria-labelledby="teams-heading">
      <div className="mb-2 flex items-center justify-between">
        <h2 id="teams-heading" className="text-section font-bold text-text">{many ? "Your teams" : "Your squad"}</h2>
        <Link to="/club" className="text-small font-semibold text-accent hover:underline">My Club →</Link>
      </div>
      {many ? (
        <div className="-mx-4 flex snap-x gap-3 overflow-x-auto px-4 pb-1 sm:mx-0 sm:grid sm:grid-cols-3 sm:overflow-visible sm:px-0">
          {teams.map((t) => (
            <div key={t.key} className="w-[250px] shrink-0 snap-start sm:w-auto"><TeamCard team={t} wide={false} /></div>
          ))}
        </div>
      ) : (
        <TeamCard team={teams[0]} wide />
      )}
    </section>
  );
}
