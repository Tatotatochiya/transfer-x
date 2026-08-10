import { useId } from "react";

interface SelectProps extends Omit<React.SelectHTMLAttributes<HTMLSelectElement>, "className"> {
  label?: string;
  error?: string;
  children: React.ReactNode;
  /** Class applied to the wrapping div, not the <select> itself. */
  wrapperClassName?: string;
}

/** Matches Input's visual language — same field shape, native <option> children. */
export default function Select({ label, error, children, wrapperClassName = "", id, ...props }: SelectProps) {
  const generatedId = useId();
  const selectId = id ?? generatedId;

  return (
    <div className={wrapperClassName}>
      {label && (
        <label htmlFor={selectId} className="mb-1.5 block text-sm font-semibold text-text-secondary">
          {label}
        </label>
      )}
      <select
        id={selectId}
        {...props}
        className={`w-full rounded-lg border bg-surface px-3 py-2.5 text-sm text-text transition-colors focus:outline-none focus:ring-2 ${
          error
            ? "border-danger focus:border-danger focus:ring-danger/20"
            : "border-input-border focus:border-accent focus:ring-accent/20"
        }`}
      >
        {children}
      </select>
      {error && <p className="mt-1 text-xs text-danger-text-alt">{error}</p>}
    </div>
  );
}
