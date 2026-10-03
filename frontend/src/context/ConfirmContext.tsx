import { createContext, useCallback, useContext, useRef, useState } from "react";
import Button from "../components/ui/Button";
import Modal from "../components/ui/Modal";

interface ConfirmOptions {
  title?: string;
  message: string;
  confirmLabel?: string;
  variant?: "danger" | "primary";
  /** Equivalent to variant: "danger" — some call sites use this instead. */
  danger?: boolean;
}

interface ReasonOptions extends ConfirmOptions {
  /** Label above the box, e.g. "Why are you cancelling this sale?" */
  reasonLabel?: string;
  placeholder?: string;
}

interface ConfirmContextValue {
  confirm: (options: ConfirmOptions) => Promise<boolean>;
  /** Like confirm, but asks why (at least 5 characters). Resolves to the
   *  reason, or null if cancelled. Admin actions record it in the audit trail. */
  askReason: (options: ReasonOptions) => Promise<string | null>;
}

const MIN_REASON = 5;

const ConfirmContext = createContext<ConfirmContextValue | null>(null);

interface PendingConfirm {
  options: ReasonOptions;
  resolve: (value: boolean) => void;
  withReason?: (reason: string | null) => void;
}

export function ConfirmProvider({ children }: { children: React.ReactNode }) {
  const [pending, setPending] = useState<PendingConfirm | null>(null);
  const resolveRef = useRef<((value: boolean) => void) | null>(null);

  const [reason, setReason] = useState("");

  const confirm = useCallback((options: ConfirmOptions): Promise<boolean> => {
    return new Promise((resolve) => {
      resolveRef.current = resolve;
      setPending({ options, resolve });
    });
  }, []);

  const askReason = useCallback((options: ReasonOptions): Promise<string | null> => {
    return new Promise((resolve) => {
      setReason("");
      setPending({ options, resolve: () => {}, withReason: resolve });
    });
  }, []);

  const trimmed = reason.trim().replace(/\s+/g, " ");
  const handleChoice = (value: boolean) => {
    if (pending?.withReason) pending.withReason(value ? trimmed : null);
    else pending?.resolve(value);
    setPending(null);
  };

  const isDanger = pending?.options.danger || pending?.options.variant === "danger";

  return (
    <ConfirmContext.Provider value={{ confirm, askReason }}>
      {children}
      <Modal open={pending !== null} onClose={() => handleChoice(false)} size="sm">
        {pending && (
          <div className="p-6">
            {pending.options.title && (
              <h3 className="mb-2 text-base font-bold text-text">
                {pending.options.title}
              </h3>
            )}
            <p className="text-sm text-text-secondary">{pending.options.message}</p>
            {pending.withReason && (
              <label className="mt-4 block">
                <span className="mb-1.5 block text-xs font-semibold text-text-secondary">
                  {pending.options.reasonLabel ?? "Reason"}
                </span>
                <textarea
                  autoFocus
                  rows={3}
                  maxLength={500}
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  placeholder={pending.options.placeholder ?? "Recorded in the audit log"}
                  className="w-full resize-none rounded-lg bg-surface px-3 py-2 text-sm text-text ring-1 ring-inset ring-input-border focus:outline-none focus:ring-accent"
                />
                <span className="mt-1 block text-xs text-text-muted">Recorded in the audit log, with your name.</span>
              </label>
            )}
            <div className="mt-5 flex justify-end gap-3">
              <Button variant="ghost" size="sm" onClick={() => handleChoice(false)}>
                Cancel
              </Button>
              <Button
                variant={isDanger ? "danger" : "primary"}
                size="sm"
                disabled={!!pending.withReason && trimmed.length < MIN_REASON}
                onClick={() => handleChoice(true)}
              >
                {pending.options.confirmLabel ?? "Confirm"}
              </Button>
            </div>
          </div>
        )}
      </Modal>
    </ConfirmContext.Provider>
  );
}

export function useConfirm() {
  const ctx = useContext(ConfirmContext);
  if (!ctx) throw new Error("useConfirm must be used within ConfirmProvider");
  return ctx.confirm;
}

export function useAskReason() {
  const ctx = useContext(ConfirmContext);
  if (!ctx) throw new Error("useAskReason must be used within ConfirmProvider");
  return ctx.askReason;
}
