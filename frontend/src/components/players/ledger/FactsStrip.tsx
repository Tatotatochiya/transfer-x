import { useState, type ReactNode } from "react";

import { formatCurrency } from "../../../lib/utils";
import type { FairValueSignal, PlayerDetail } from "../../../types/api";

/**
 * The facts strip (HANDOFF.md §4): model value, market value, contract, wage,
 * release clause (or, for the player's own club, its private valuation,
 * editable here), and form. Another club never sees his contract wage: the
 * API withholds it, and the strip shows the public estimate instead.
 */

const money = (raw: number | string | null | undefined, currency?: string | null) => {
  // Decimal fields arrive as strings ("196500.00").
  if (raw == null || raw === "" || Number.isNaN(Number(raw))) return "—";
  const v = Number(raw);
  const sym = currency === "EUR" ? "€" : currency === "USD" ? "$" : "£";
  return v >= 1e6 ? `${sym}${+(v / 1e6).toFixed(1)}m` : `${sym}${Math.round(v / 1e3)}k`;
};
const monthYear = (iso: string) => new Date(iso).toLocaleDateString("en-GB", { month: "short", year: "numeric" });

function timeLeft(iso: string): string {
  const end = new Date(iso);
  const now = new Date();
  let months = (end.getFullYear() - now.getFullYear()) * 12 + end.getMonth() - now.getMonth();
  if (months <= 0) return "Ending";
  const years = Math.floor(months / 12);
  months %= 12;
  return [years ? `${years} yr` : "", months ? `${months} mo` : ""].filter(Boolean).join(" ") + " left";
}

function Cell({ label, value, sub, valueClass = "text-text" }: { label: string; value: ReactNode; sub?: ReactNode; valueClass?: string }) {
  return (
    <div className="flex min-w-0 flex-col gap-0.5 px-3.5 py-2.5 shadow-[-1px_0_0_var(--color-rule-faint)]">
      <span className="text-[11px] font-bold uppercase tracking-[0.06em] text-text-muted">{label}</span>
      <span className={`truncate text-[15px] font-bold tabular-nums ${valueClass}`}>{value}</span>
      {sub != null && <span className="truncate text-xs text-text-muted">{sub}</span>}
    </div>
  );
}

const SOURCE: Record<string, string> = { TRANSFERMARKT: "Transfermarkt", ETV: "Estimated", MANUAL: "Club", CAPOLOGY: "Capology" };

export default function FactsStrip({
  player, fairValue, form, isMyPlayer, valuationPending, onSaveValuation,
}: {
  player: PlayerDetail;
  fairValue: FairValueSignal | null;
  form: { score: number | null; trend: number | null };
  isMyPlayer: boolean;
  valuationPending: boolean;
  onSaveValuation: (value: number | null) => void;
}) {
  const contract = player.active_contract;
  const end = contract?.end_date ?? player.contract_expiry ?? null;
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");

  const ownWage = isMyPlayer && contract?.wage_weekly != null;
  const wage = ownWage ? contract!.wage_weekly : player.wage_weekly;
  const wageSub = ownWage ? "Contract" : player.wage_weekly != null
    ? `${SOURCE[player.wage_source ?? ""] ?? "Estimate"} est.` : "No public estimate";

  const save = () => {
    const parsed = draft.trim() === "" ? null : Number(draft.replace(/[^0-9.]/g, ""));
    onSaveValuation(parsed != null && !Number.isNaN(parsed) ? (parsed < 1000 ? parsed * 1e6 : parsed) : null);
    setEditing(false);
  };

  return (
    <div className="grid grid-cols-[repeat(auto-fit,minmax(150px,1fr))] overflow-hidden rounded-[10px] bg-surface ring-1 ring-border">
      <Cell label="Model value" value={fairValue ? money(fairValue.fair_value) : "—"}
        sub={fairValue ? `Range ${money(fairValue.fair_value_low)}–${money(fairValue.fair_value_high)}` : "Not enough recent data"} />
      <Cell label="Market value" value={money(player.market_value, player.market_value_currency)}
        sub={player.market_value != null ? [SOURCE[player.valuation_source ?? ""] ?? null,
          player.valuation_as_of ? monthYear(player.valuation_as_of) : null].filter(Boolean).join(" · ") || undefined : undefined} />
      <Cell label="Contract" value={end ? monthYear(end) : "—"}
        sub={isMyPlayer && contract?.start_date ? `Started ${monthYear(contract.start_date)}` : end ? timeLeft(end) : undefined} />
      <Cell label="Wage" value={wage != null ? `${money(wage, ownWage ? undefined : player.wage_currency)}/wk` : "Not public"}
        valueClass={wage != null ? "text-success-text" : "text-text"} sub={wageSub} />
      {isMyPlayer ? (
        <div className="flex min-w-0 flex-col gap-0.5 px-3.5 py-2.5 shadow-[-1px_0_0_var(--color-rule-faint)]">
          <span className="text-[11px] font-bold uppercase tracking-[0.06em] text-text-muted">Club valuation</span>
          {editing ? (
            <form className="flex items-center gap-1" onSubmit={(e) => { e.preventDefault(); save(); }}>
              <input
                autoFocus
                aria-label="Club valuation in millions of pounds"
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Escape") setEditing(false); }}
                placeholder="e.g. 22"
                className="w-20 rounded-md bg-surface-inset px-2 py-0.5 text-sm tabular-nums text-text ring-1 ring-input-border focus:outline-none focus:ring-accent"
              />
              <span className="text-xs text-text-muted">m</span>
              <button type="submit" disabled={valuationPending} className="text-xs font-semibold text-accent">Save</button>
            </form>
          ) : (
            <button
              type="button"
              onClick={() => {
                setDraft(contract?.club_valuation != null ? String(+(contract.club_valuation / 1e6).toFixed(2)) : "");
                setEditing(true);
              }}
              disabled={!contract}
              title={contract ? "Edit your valuation" : "Record his contract first"}
              className={contract?.club_valuation != null
                ? "truncate text-left text-[15px] font-bold tabular-nums text-text hover:text-accent disabled:cursor-default disabled:hover:text-text"
                : "self-start rounded-md bg-accent-bg px-2 py-0.5 text-[13px] font-semibold text-accent ring-1 ring-accent/30 hover:bg-accent/15 disabled:cursor-not-allowed disabled:opacity-60"}
            >
              {contract?.club_valuation != null
                ? <>{formatCurrency(contract.club_valuation)} <span aria-hidden="true">✎</span></>
                : "Set valuation"}
            </button>
          )}
          <span className="truncate text-xs text-text-muted">
            {contract ? "Only your club sees this" : "Needs his contract on record"}
          </span>
        </div>
      ) : (
        <Cell label="Release clause" value={contract?.release_clause != null ? money(contract.release_clause) : "None"}
          sub={contract?.release_clause != null ? "Can be triggered" : "Not on record"} />
      )}
      <Cell label="Form"
        value={form.score == null ? "—" : (
          <>
            {Math.round(form.score)}{" "}
            {form.trend != null && form.trend !== 0 && <span aria-label={form.trend > 0 ? "rising" : "falling"}>{form.trend > 0 ? "▲" : "▼"}</span>}
          </>
        )}
        valueClass={form.score == null ? "text-text" : form.score >= 60 ? "text-success-text" : form.score >= 40 ? "text-text" : "text-warning-text"}
        sub="Last 5 games" />
    </div>
  );
}
