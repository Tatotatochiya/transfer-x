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

  const isDanger = pending?.options.danger || pending?.options.variant === "danger";

  return (
    <ConfirmContext.Provider value={{ confirm }}>
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
            <div className="mt-5 flex justify-end gap-3">
              <Button variant="ghost" size="sm" onClick={() => handleChoice(false)}>
                Cancel
              </Button>
              <Button
                variant={isDanger ? "danger" : "primary"}
                size="sm"
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
