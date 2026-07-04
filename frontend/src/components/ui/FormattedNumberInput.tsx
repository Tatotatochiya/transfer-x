interface FormattedNumberInputProps {
  value: string;
  onChange: (raw: string) => void;
  className?: string;
  placeholder?: string;
}

function formatWithCommas(raw: string): string {
  if (raw === "") return "";
  const [intPart, decPart] = raw.split(".");
  const withCommas = intPart.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  return decPart !== undefined ? `${withCommas}.${decPart}` : withCommas;
}

/**
 * Text input for money amounts that displays thousands separators as the
 * user types (e.g. "1,200,000"), while `onChange` always receives the plain
 * numeric string (no commas) — a drop-in replacement for the raw-string
 * state every `<input type="number">` money field in this codebase already uses.
 */
export default function FormattedNumberInput({
  value,
  onChange,
  className = "",
  placeholder,
}: FormattedNumberInputProps) {
  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    const raw = e.target.value.replace(/,/g, "");
    if (raw === "" || /^\d*\.?\d{0,2}$/.test(raw)) {
      onChange(raw);
    }
  }

  return (
    <input
      type="text"
      inputMode="decimal"
      value={formatWithCommas(value)}
      onChange={handleChange}
      placeholder={placeholder}
      className={className}
    />
  );
}
