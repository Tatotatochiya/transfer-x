import { createContext, useCallback, useContext, useState } from "react";
import Button from "../components/ui/Button";

interface ConfirmOptions {
  title?: string;
  message: string;
  confirmLabel?: string;
  variant?: "danger" | "primary";
}

interface ReasonConfirmOptions {
  title?: string;
  message: string;
  confirmLabel?: string;
  reasonLabel?: string;
  reasonPlaceholder?: string;
}

interface ReasonConfirmResult {
  confirmed: boolean;
  reason: string;
}

interface ConfirmContextValue {
  confirm: (options: ConfirmOptions) => Promise<boolean>;
  confirmWithReason: (options: ReasonConfirmOptions) => Promise<ReasonConfirmResult>;
}

const ConfirmContext = createContext<ConfirmContextValue | null>(null);

type PendingState =
  | { kind: "simple"; options: ConfirmOptions; resolve: (value: boolean) => void }
  | { kind: "reason"; options: ReasonConfirmOptions; resolve: (value: ReasonConfirmResult) => void };

export function ConfirmProvider({ children }: { children: React.ReactNode }) {
  const [pending, setPending] = useState<PendingState | null>(null);
  const [reasonText, setReasonText] = useState("");

  const confirm = useCallback((options: ConfirmOptions): Promise<boolean> => {
    return new Promise((resolve) => {
      setPending({ kind: "simple", options, resolve });
    });
  }, []);

  const confirmWithReason = useCallback(
    (options: ReasonConfirmOptions): Promise<ReasonConfirmResult> => {
      return new Promise((resolve) => {
        setReasonText("");
        setPending({ kind: "reason", options, resolve });
      });
    },
    []
  );

  function handleSimpleChoice(value: boolean) {
    if (pending?.kind === "simple") pending.resolve(value);
    setPending(null);
  }

  function handleReasonChoice(confirmed: boolean) {
    if (pending?.kind === "reason") {
      pending.resolve({ confirmed, reason: confirmed ? reasonText.trim() : "" });
    }
    setPending(null);
    setReasonText("");
  }

  const reasonInvalid = pending?.kind === "reason" && !reasonText.trim();

  return (
    <ConfirmContext.Provider value={{ confirm, confirmWithReason }}>
      {children}
      {pending && (
        <div className="fixed inset-0 z-[9998] flex items-center justify-center p-4">
          {/* Backdrop */}
          <div
            className="absolute inset-0 bg-slate-950/80 backdrop-blur-sm"
            onClick={() => (pending.kind === "simple" ? handleSimpleChoice(false) : handleReasonChoice(false))}
          />
          {/* Modal */}
          <div className="relative w-full max-w-sm rounded-2xl bg-slate-900 p-6 shadow-2xl ring-1 ring-white/[0.08]">
            {pending.options.title && (
              <h3 className="mb-2 text-base font-semibold text-white">
                {pending.options.title}
              </h3>
            )}
            <p className="text-sm text-slate-300">{pending.options.message}</p>

            {pending.kind === "reason" && (
              <div className="mt-4">
                <label className="mb-1 block text-xs text-slate-400">
                  {pending.options.reasonLabel ?? "Reason (required)"}
                </label>
                <textarea
                  autoFocus
                  rows={3}
                  value={reasonText}
                  onChange={(e) => setReasonText(e.target.value)}
                  placeholder={pending.options.reasonPlaceholder ?? "Explain why — this is recorded in the audit trail"}
                  className="w-full resize-none rounded-lg bg-slate-800 px-3 py-2 text-sm text-white placeholder-slate-600 ring-1 ring-white/10 focus:outline-none focus:ring-amber-500"
                />
              </div>
            )}

            <div className="mt-5 flex justify-end gap-3">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => (pending.kind === "simple" ? handleSimpleChoice(false) : handleReasonChoice(false))}
              >
                Cancel
              </Button>
              <Button
                variant={pending.kind === "reason" || pending.options.variant === "danger" ? "danger" : "primary"}
                size="sm"
                disabled={reasonInvalid}
                onClick={() => (pending.kind === "simple" ? handleSimpleChoice(true) : handleReasonChoice(true))}
              >
                {pending.options.confirmLabel ?? "Confirm"}
              </Button>
            </div>
          </div>
        </div>
      )}
    </ConfirmContext.Provider>
  );
}

export function useConfirm() {
  const ctx = useContext(ConfirmContext);
  if (!ctx) throw new Error("useConfirm must be used within ConfirmProvider");
  return ctx.confirm;
}

export function useConfirmWithReason() {
  const ctx = useContext(ConfirmContext);
  if (!ctx) throw new Error("useConfirmWithReason must be used within ConfirmProvider");
  return ctx.confirmWithReason;
}
