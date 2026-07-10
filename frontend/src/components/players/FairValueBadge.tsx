import type { FairValueSignal } from "../../types/api";
import type { ValuationBand } from "../../types/enums";
import { formatDate } from "../../lib/utils";
import ValuationBreakdownPopover from "./ValuationBreakdownPopover";

interface Props {
  signal: FairValueSignal | null | undefined;
  /** Label for the reference price in the full strip (e.g. "Agreed fee"). */
  referenceLabel?: string;
  /** Card form: a single pill instead of the full strip. */
  compact?: boolean;
}

// D5 copy rules: only these phrases, always "model" — never a verdict.
const BAND_PHRASE: Record<ValuationBand, string> = {
  WELL_BELOW: "Well below model",
  BELOW: "Below model",
  IN_LINE: "In line with model",
  ABOVE: "Above model",
  WELL_ABOVE: "Well above model",
};

const BAND_COLOUR: Record<ValuationBand, string> = {
  WELL_BELOW: "text-emerald-500",
  BELOW: "text-emerald-400",
  IN_LINE: "text-slate-400",
  ABOVE: "text-amber-400",
  WELL_ABOVE: "text-rose-400",
};

function compactMoney(value: number): string {
  const n = Number(value);
  if (n >= 1_000_000) return `£${(n / 1_000_000).toFixed(1)}m`;
  return `£${Math.round(n / 1_000)}k`;
}

function signedPct(pct: number): string {
  const rounded = Math.round(Number(pct));
  return `${rounded >= 0 ? "+" : "−"}${Math.abs(rounded)}%`;
}

function isStale(asOf: string): boolean {
  return Date.now() - new Date(asOf).getTime() > 60 * 86_400_000;
}

/** The fair-value signal (TRA-92). Renders nothing when `signal` is absent —
 *  never a placeholder value. */
export default function FairValueBadge({ signal, referenceLabel, compact = false }: Props) {
  if (!signal) return null;

  const low = signal.confidence === "LOW";
  const divergence = signal.divergence;
  const bandColour = divergence ? BAND_COLOUR[divergence.band] : "text-slate-400";

  if (compact) {
    return (
      <span
        className={`inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 text-[10px] font-semibold tabular-nums ring-1 ${
          low
            ? "bg-slate-800/60 text-slate-500 ring-white/[0.06]"
            : "bg-slate-800 text-slate-300 ring-white/[0.1]"
        }`}
        title={`Model fair value ${compactMoney(signal.fair_value)} (${signal.confidence} confidence)`}
      >
        Model {compactMoney(signal.fair_value)}
        {divergence && (
          <span className={low ? "text-slate-500" : bandColour}>
            · {signedPct(divergence.pct)}
          </span>
        )}
      </span>
    );
  }

  return (
    <div
      className={`flex flex-wrap items-center gap-x-2 gap-y-1 text-xs tabular-nums ${
        low ? "opacity-70" : ""
      }`}
    >
      {divergence && (
        <>
          <span className="text-slate-300">
            {referenceLabel ?? "Asking"} {compactMoney(divergence.reference_price)}
          </span>
          <span className="text-slate-700">·</span>
        </>
      )}
      <span className="font-semibold text-slate-200">Model {compactMoney(signal.fair_value)}</span>
      <span className="text-slate-500">
        (range {compactMoney(signal.fair_value_low)}–{compactMoney(signal.fair_value_high)})
      </span>
      {divergence && (
        <>
          <span className="text-slate-700">·</span>
          <span className={`font-semibold ${low ? "text-slate-500" : bandColour}`}>
            {signedPct(divergence.pct)} {BAND_PHRASE[divergence.band].toLowerCase()}
          </span>
        </>
      )}
      <span
        className={`rounded-full px-1.5 py-0.5 text-[10px] font-semibold ring-1 ${
          low
            ? "bg-slate-800/60 text-slate-500 ring-white/[0.06]"
            : "bg-slate-800 text-slate-400 ring-white/[0.08]"
        }`}
      >
        {low ? "Low confidence" : `${signal.confidence} confidence`}
      </span>
      {isStale(signal.as_of) && (
        <span className="text-amber-400/80">as of {formatDate(signal.as_of)}</span>
      )}
      <ValuationBreakdownPopover signal={signal} />
    </div>
  );
}
