import { createContext, useCallback, useContext, useRef, useState } from "react";
import Button from "../components/ui/Button";

interface ConfirmOptions {
  title?: string;
  message: string;
  confirmLabel?: string;
  variant?: "danger" | "primary";
}

interface ConfirmContextValue {
  confirm: (options: ConfirmOptions) => Promise<boolean>;
}

const ConfirmContext = createContext<ConfirmContextValue | null>(null);

interface PendingConfirm {
  options: ConfirmOptions;
  resolve: (value: boolean) => void;
}

export function ConfirmProvider({ children }: { children: React.ReactNode }) {
  const [pending, setPending] = useState<PendingConfirm | null>(null);
  const resolveRef = useRef<((value: boolean) => void) | null>(null);

  const confirm = useCallback((options: ConfirmOptions): Promise<boolean> => {
    return new Promise((resolve) => {
      resolveRef.current = resolve;
      setPending({ options, resolve });
    });
  }, []);

  const handleChoice = (value: boolean) => {
    pending?.resolve(value);
    setPending(null);
  };

  return (
    <ConfirmContext.Provider value={{ confirm }}>
      {children}
      {pending && (
        <div className="fixed inset-0 z-[9998] flex items-center justify-center p-4">
          {/* Backdrop */}
          <div
            className="absolute inset-0 bg-slate-950/80 backdrop-blur-sm"
            onClick={() => handleChoice(false)}
          />
          {/* Modal */}
          <div className="relative w-full max-w-sm rounded-2xl bg-slate-900 p-6 shadow-2xl ring-1 ring-white/[0.08]">
            {pending.options.title && (
              <h3 className="mb-2 text-base font-semibold text-white">
                {pending.options.title}
              </h3>
            )}
            <p className="text-sm text-slate-300">{pending.options.message}</p>
            <div className="mt-5 flex justify-end gap-3">
              <Button variant="ghost" size="sm" onClick={() => handleChoice(false)}>
                Cancel
              </Button>
              <Button
                variant={pending.options.variant === "danger" ? "danger" : "primary"}
                size="sm"
                onClick={() => handleChoice(true)}
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
