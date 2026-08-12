import type { InputHTMLAttributes } from "react";

interface CurrencyInputProps
  extends Omit<InputHTMLAttributes<HTMLInputElement>, "type" | "value" | "onChange"> {
  value: string;
  onChange: (raw: string) => void;
}

function formatWithCommas(raw: string): string {
  if (raw === "") return "";
  const [intPart, decPart] = raw.split(".");
  const withCommas = intPart.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  return decPart !== undefined ? `${withCommas}.${decPart}` : withCommas;
}

/**
 * A text input that shows thousand separators (and up to 2 decimal places)
 * while the user types. `value`/`onChange` work with raw numeric strings (no
 * commas), so they're compatible with existing parseFloat() calls.
 */
export default function CurrencyInput({ value, onChange, ...props }: CurrencyInputProps) {
  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    const raw = e.target.value.replace(/,/g, "");
    if (raw === "" || /^\d*\.?\d{0,2}$/.test(raw)) {
      onChange(raw);
    }
  }

  return (
    <input
      {...props}
      type="text"
      inputMode="decimal"
      value={formatWithCommas(value)}
      onChange={handleChange}
    />
  );
}
