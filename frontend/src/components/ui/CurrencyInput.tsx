import type { InputHTMLAttributes } from "react";

interface CurrencyInputProps
  extends Omit<InputHTMLAttributes<HTMLInputElement>, "type" | "value" | "onChange"> {
  value: string;
  onChange: (raw: string) => void;
}

function formatWithCommas(raw: string): string {
  if (!raw) return "";
  const digits = raw.replace(/\D/g, "");
  if (!digits) return "";
  return parseInt(digits, 10).toLocaleString("en-GB");
}

/**
 * A text input that shows thousand separators while the user types.
 * `value` and `onChange` work with raw numeric strings (no commas),
 * so they're compatible with the existing parseFloat() calls.
 */
export default function CurrencyInput({ value, onChange, ...props }: CurrencyInputProps) {
  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    const raw = e.target.value.replace(/\D/g, "");
    onChange(raw);
  }

  return (
    <input
      {...props}
      type="text"
      inputMode="numeric"
      value={formatWithCommas(value)}
      onChange={handleChange}
    />
  );
}
