import { useFxStore } from "../../store/fx";
import { usePreferencesStore } from "../../store/preferences";
import { formatCompactCurrency, formatCurrency, formatEstimate } from "../../lib/utils";

/** A £ amount, with "≈ €21.1m" after it when the user asked for estimates in
 *  another currency (Account settings). The £ figure is what's agreed. */
export default function Money({
  value,
  compact = false,
  format,
  className = "",
}: {
  value: number | string | null | undefined;
  compact?: boolean;
  /** Overrides how the £ figure is written (e.g. liteMoney). */
  format?: (v: number | null | undefined) => string;
  className?: string;
}) {
  const n = value == null || value === "" ? null : Number(value);
  const pounds = (format ?? (compact ? formatCompactCurrency : formatCurrency))(n);
  return (
    <span className={className}>
      {pounds}
      <Estimate value={n} />
    </span>
  );
}

/** Just the "≈ €21.1m" part, for a £ figure written elsewhere. */
export function Estimate({ value }: { value: number | string | null | undefined }) {
  const currency = usePreferencesStore((s) => s.currency);
  const rates = useFxStore((s) => s.rates);
  const asOf = useFxStore((s) => s.asOf);
  const source = useFxStore((s) => s.source);
  const estimate = formatEstimate(value, currency, rates);
  if (!estimate) return null;
  const basis = source === "ECB" && asOf ? `the ECB rate of ${asOf}` : "an approximate rate";
  return (
    <span
      className="ml-1 whitespace-nowrap text-[0.8em] font-normal text-text-muted"
      title={`Estimate at ${basis}. Amounts are agreed in pounds.`}
    >
      {estimate}
    </span>
  );
}
