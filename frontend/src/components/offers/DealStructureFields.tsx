import type { Offer } from "../../types/api";
import type { ClauseType } from "../../types/enums";
import CurrencyInput from "../ui/CurrencyInput";
import { formatCurrency } from "../../lib/utils";

/**
 * The payment schedule, add-ons and sell-on of a permanent offer.
 *
 * These are what decide a deal's real value ("£40m + £10m add-ons, over three
 * years, 15% sell-on"), and they used to be set in the deal room only after
 * the seller had accepted — by either club alone. They are proposed and
 * countered here instead, then copied onto the deal at acceptance.
 *
 * Collapsed until used, so a plain "£X on completion" offer stays one field.
 */

export interface StructureDraft {
  instalments: { due_date: string; amount: string }[];
  clauses: { clause_type: ClauseType; trigger_description: string; amount: string; cap: string }[];
  /** A percentage, 0–100, as typed; the API takes a fraction. */
  sellOn: string;
}

export const emptyStructure = (): StructureDraft => ({ instalments: [], clauses: [], sellOn: "" });

const str = (v: number | string | null | undefined) => (v == null ? "" : String(Number(v)));

export function structureFromOffer(o: Offer): StructureDraft {
  return {
    instalments: (o.instalments ?? []).map((i) => ({ due_date: i.due_date, amount: str(i.amount) })),
    clauses: (o.clauses ?? []).map((c) => ({
      clause_type: c.clause_type,
      trigger_description: c.trigger_description,
      amount: str(c.amount),
      cap: str(c.cap),
    })),
    sellOn: o.sell_on_pct != null ? String(Math.round(Number(o.sell_on_pct) * 1000) / 10) : "",
  };
}

/** Why the draft cannot be sent, or null. The server checks the same rules. */
export function structureError(d: StructureDraft, fee: number | null): string | null {
  if (d.instalments.some((i) => !i.due_date || !(Number(i.amount) > 0))) {
    return "Every payment in the schedule needs a date and an amount.";
  }
  if (d.instalments.length > 0) {
    const total = d.instalments.reduce((s, i) => s + Number(i.amount), 0);
    if (fee == null || Math.round(total) !== Math.round(fee)) {
      return `The payment schedule totals ${formatCurrency(total)} — it must add up to the fee.`;
    }
  }
  if (d.clauses.some((c) => !c.trigger_description.trim() || !(Number(c.amount) > 0))) {
    return "Every add-on needs a trigger and an amount.";
  }
  if (d.sellOn && !(Number(d.sellOn) > 0 && Number(d.sellOn) <= 100)) {
    return "Sell-on must be between 0 and 100%.";
  }
  return null;
}

export function structureBody(d: StructureDraft) {
  return {
    instalments: d.instalments.map((i) => ({ due_date: i.due_date, amount: Number(i.amount) })),
    clauses: d.clauses.map((c) => ({
      clause_type: c.clause_type,
      trigger_description: c.trigger_description.trim(),
      amount: Number(c.amount),
      ...(c.cap ? { cap: Number(c.cap) } : {}),
    })),
    sell_on_pct: d.sellOn ? Number(d.sellOn) / 100 : null,
  };
}

const CLAUSE_TYPES: { value: ClauseType; label: string }[] = [
  { value: "APPEARANCES", label: "Appearances" },
  { value: "GOALS", label: "Goals" },
  { value: "PROMOTION", label: "Promotion" },
  { value: "OTHER", label: "Other" },
];

const INPUT =
  "w-full rounded-lg bg-surface px-3 py-2 text-sm text-text placeholder-text-muted ring-1 ring-input-border focus:outline-none focus:ring-accent transition-colors";

export default function DealStructureFields({
  value,
  onChange,
  fee,
}: {
  value: StructureDraft;
  onChange: (next: StructureDraft) => void;
  /** The fee being offered, so the schedule can show what is left to place. */
  fee: number | null;
}) {
  const set = (patch: Partial<StructureDraft>) => onChange({ ...value, ...patch });
  const scheduled = value.instalments.reduce((s, i) => s + (Number(i.amount) || 0), 0);
  const used = value.instalments.length > 0 || value.clauses.length > 0 || !!value.sellOn;

  return (
    <details open={used} className="rounded-lg bg-surface-inset px-4 py-3 ring-1 ring-border">
      <summary className="cursor-pointer text-sm font-semibold text-text-secondary">
        Payment schedule, add-ons &amp; sell-on{" "}
        <span className="font-normal text-text-muted">(optional)</span>
      </summary>

      <div className="mt-4 space-y-5">
        {/* Payment schedule */}
        <div>
          <p className="mb-1.5 text-[13px] font-semibold text-text-secondary">Payment</p>
          {value.instalments.length === 0 ? (
            <p className="text-[13px] text-text-muted">The whole fee is paid on completion.</p>
          ) : (
            <div className="space-y-2">
              {value.instalments.map((row, i) => (
                <div key={i} className="flex items-center gap-2">
                  <input
                    type="date"
                    aria-label={`Payment ${i + 1} due`}
                    value={row.due_date}
                    onChange={(e) => set({
                      instalments: value.instalments.map((r, j) => (j === i ? { ...r, due_date: e.target.value } : r)),
                    })}
                    className={INPUT}
                  />
                  <CurrencyInput
                    aria-label={`Payment ${i + 1} amount`}
                    placeholder="Amount (£)"
                    value={row.amount}
                    onChange={(v) => set({
                      instalments: value.instalments.map((r, j) => (j === i ? { ...r, amount: v } : r)),
                    })}
                    className={INPUT}
                  />
                  <button
                    type="button"
                    onClick={() => set({ instalments: value.instalments.filter((_, j) => j !== i) })}
                    className="min-h-11 px-2 text-sm text-text-muted hover:text-danger-text lg:min-h-0"
                    aria-label={`Remove payment ${i + 1}`}
                  >
                    ✕
                  </button>
                </div>
              ))}
              <p className="text-[13px] text-text-muted">
                {formatCurrency(scheduled)} of {fee != null ? formatCurrency(fee) : "the fee"} scheduled
              </p>
            </div>
          )}
          <button
            type="button"
            onClick={() => set({ instalments: [...value.instalments, { due_date: "", amount: "" }] })}
            className="mt-2 text-[13px] font-semibold text-accent hover:underline"
          >
            {value.instalments.length === 0 ? "Pay in instalments" : "+ Add a payment"}
          </button>
        </div>

        {/* Add-ons */}
        <div>
          <p className="mb-1.5 text-[13px] font-semibold text-text-secondary">Add-ons</p>
          {value.clauses.length === 0 && (
            <p className="text-[13px] text-text-muted">None. Add-ons are paid only if their trigger is met.</p>
          )}
          <div className="space-y-3">
            {value.clauses.map((c, i) => {
              const update = (patch: Partial<StructureDraft["clauses"][number]>) =>
                set({ clauses: value.clauses.map((r, j) => (j === i ? { ...r, ...patch } : r)) });
              return (
                <div key={i} className="grid grid-cols-1 gap-2 rounded-lg bg-surface p-3 ring-1 ring-border sm:grid-cols-2">
                  <select
                    aria-label="Add-on type"
                    value={c.clause_type}
                    onChange={(e) => update({ clause_type: e.target.value as ClauseType })}
                    className={INPUT}
                  >
                    {CLAUSE_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
                  </select>
                  <input
                    aria-label="Add-on trigger"
                    value={c.trigger_description}
                    onChange={(e) => update({ trigger_description: e.target.value })}
                    maxLength={300}
                    placeholder="e.g. After 50 league appearances"
                    className={INPUT}
                  />
                  <CurrencyInput
                    aria-label="Add-on amount"
                    value={c.amount}
                    onChange={(v) => update({ amount: v })}
                    placeholder="Amount (£)"
                    className={INPUT}
                  />
                  <div className="flex items-center gap-2">
                    <CurrencyInput
                      aria-label="Add-on cap"
                      value={c.cap}
                      onChange={(v) => update({ cap: v })}
                      placeholder="Cap (£, optional)"
                      className={INPUT}
                    />
                    <button
                      type="button"
                      onClick={() => set({ clauses: value.clauses.filter((_, j) => j !== i) })}
                      className="min-h-11 px-2 text-sm text-text-muted hover:text-danger-text lg:min-h-0"
                      aria-label="Remove add-on"
                    >
                      ✕
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
          <button
            type="button"
            onClick={() => set({
              clauses: [...value.clauses, { clause_type: "APPEARANCES", trigger_description: "", amount: "", cap: "" }],
            })}
            className="mt-2 text-[13px] font-semibold text-accent hover:underline"
          >
            + Add an add-on
          </button>
        </div>

        {/* Sell-on */}
        <div>
          <label className="mb-1.5 block text-[13px] font-semibold text-text-secondary">
            Sell-on <span className="font-normal text-text-muted">(optional)</span>
          </label>
          <div className="relative max-w-[160px]">
            <input
              type="number"
              min={0}
              max={100}
              step={0.5}
              value={value.sellOn}
              onChange={(e) => set({ sellOn: e.target.value })}
              placeholder="e.g. 15"
              className={`${INPUT} pr-8`}
            />
            <span className="absolute right-3 top-1/2 -translate-y-1/2 text-sm text-text-muted">%</span>
          </div>
          <p className="mt-1 text-[13px] text-text-muted">
            The share of a future fee his current club receives if you sell him on.
          </p>
        </div>
      </div>
    </details>
  );
}
