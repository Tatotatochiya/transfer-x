import type { ActiveDealStub, PlayerDetail } from "../../types/api";
import Card from "../ui/Card";
import { formatCurrency } from "../../lib/utils";

type SquadPlayer = { active_contract?: PlayerDetail["active_contract"] } & {
  id: string; position: string | null; age: number | null; market_value?: number | null;
  active_deal?: ActiveDealStub | null;
};

const CLIFF_WINDOWS = [
  { label: "Under 6 months", maxMonths: 6 },
  { label: "6–12 months", maxMonths: 12 },
  { label: "12–24 months", maxMonths: 24 },
];

const AGE_BANDS = [
  { label: "Under 21", test: (a: number) => a < 21 },
  { label: "21–25", test: (a: number) => a >= 21 && a <= 25 },
  { label: "26–29", test: (a: number) => a >= 26 && a <= 29 },
  { label: "30+", test: (a: number) => a >= 30 },
];

const POSITION_ORDER = ["GK", "DEF", "MID", "FWD"];

function monthsUntil(iso: string): number {
  return (new Date(iso).getTime() - Date.now()) / (30 * 86_400_000);
}

function ContractCliff({ players }: { players: SquadPlayer[] }) {
  const withContract = players.filter((p) => p.active_contract?.end_date);
  const windows = CLIFF_WINDOWS.map((w, i) => {
    const prevMax = i === 0 ? 0 : CLIFF_WINDOWS[i - 1].maxMonths;
    const inWindow = withContract.filter((p) => {
      const m = monthsUntil(p.active_contract!.end_date!);
      return m >= prevMax && m < w.maxMonths;
    });
    const valueAtRisk = inWindow.reduce((sum, p) => sum + Number(p.market_value ?? 0), 0);
    return { ...w, count: inWindow.length, valueAtRisk };
  });

  return (
    <Card tier={4} noPadding>
      <div className="px-[18px] py-[13px]">
        <p className="text-[13px] font-semibold text-text-secondary">Contract cliff</p>
      </div>
      <div className="px-[18px] pb-3">
        {windows.map((w) => (
          <div key={w.label} className="flex items-center justify-between py-[9px]">
            <div className="min-w-0">
              <p className="text-[13px] text-text">{w.label}</p>
              <p className="text-[11px] text-text-muted">{w.count} player{w.count === 1 ? "" : "s"}</p>
            </div>
            <span className="shrink-0 text-[13px] font-semibold text-text">
              {w.valueAtRisk > 0 ? formatCurrency(w.valueAtRisk) : "—"}
            </span>
          </div>
        ))}
      </div>
    </Card>
  );
}

function WageBillByPosition({ players }: { players: SquadPlayer[] }) {
  const byPos = POSITION_ORDER.map((pos) => ({
    pos,
    total: players.filter((p) => p.position === pos).reduce((sum, p) => sum + Number(p.active_contract?.wage_weekly ?? 0), 0),
  }));
  const max = Math.max(...byPos.map((p) => p.total), 1);

  return (
    <Card tier={4} noPadding>
      <div className="px-[18px] py-[13px]">
        <p className="text-[13px] font-semibold text-text-secondary">Wage bill by position</p>
      </div>
      <div className="px-[18px] pb-3 space-y-2.5">
        {byPos.map((p) => (
          <div key={p.pos}>
            <div className="flex items-center justify-between text-[13px]">
              <span className="text-text">{p.pos}</span>
              <span className="font-semibold text-text">{formatCurrency(p.total)}</span>
            </div>
            <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-border-quiet">
              <div className="h-full bg-accent-soft" style={{ width: `${(p.total / max) * 100}%` }} />
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}

function AgeProfile({ players }: { players: SquadPlayer[] }) {
  const withAge = players.filter((p): p is SquadPlayer & { age: number } => p.age != null);
  const bands = AGE_BANDS.map((b) => ({ ...b, count: withAge.filter((p) => b.test(p.age)).length }));
  const max = Math.max(...bands.map((b) => b.count), 1);

  return (
    <Card tier={4} noPadding>
      <div className="px-[18px] py-[13px]">
        <p className="text-[13px] font-semibold text-text-secondary">Age profile</p>
      </div>
      <div className="px-[18px] pb-3 space-y-2">
        {bands.map((b) => (
          <div key={b.label} className="flex items-center gap-2.5">
            <span className="w-16 shrink-0 text-[11px] text-text-muted">{b.label}</span>
            <div className="h-4 flex-1 overflow-hidden rounded bg-border-quiet">
              <div className="h-full bg-accent" style={{ width: `${(b.count / max) * 100}%` }} />
            </div>
            <span className="w-4 shrink-0 text-right text-[11px] text-text-muted">{b.count}</span>
          </div>
        ))}
      </div>
    </Card>
  );
}

export default function SquadRail({ players }: { players: SquadPlayer[] }) {
  return (
    <div className="space-y-4">
      <ContractCliff players={players} />
      <WageBillByPosition players={players} />
      <AgeProfile players={players} />
    </div>
  );
}
