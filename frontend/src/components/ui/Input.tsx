import { useId } from "react";

interface InputProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, "className"> {
  label?: string;
  error?: string;
  /** Class applied to the wrapping div, not the <input> itself. */
  wrapperClassName?: string;
}

/**
 * Self-contained form field — label, input, and error message, matching the
 * Form archetype in docs/design_handoff_transferx/SCREENS.md. Replaces the
 * hand-repeated `rounded-lg bg-slate-800 ...` class string duplicated across
 * dozens of pages.
 */
export default function Input({ label, error, wrapperClassName = "", id, ...props }: InputProps) {
  const generatedId = useId();
  const inputId = id ?? generatedId;

  return (
    <div className={wrapperClassName}>
      {label && (
        <label htmlFor={inputId} className="mb-1.5 block text-sm font-semibold text-text-secondary">
          {label}
        </label>
      )}
      <input
        id={inputId}
        {...props}
        className={`w-full rounded-lg border bg-surface px-3 py-2.5 text-sm text-text placeholder:text-text-muted transition-colors focus:outline-none focus:ring-2 ${
          error
            ? "border-danger focus:border-danger focus:ring-danger/20"
            : "border-input-border focus:border-accent focus:ring-accent/20"
        }`}
      />
      {error && <p className="mt-1 text-xs text-danger-text-alt">{error}</p>}
    </div>
  );
}
