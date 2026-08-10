import { createPortal } from "react-dom";
import { useFocusTrap } from "../../hooks/useFocusTrap";

export type ModalSize = "sm" | "md" | "lg" | "xl";

const sizeClasses: Record<ModalSize, string> = {
  sm: "max-w-sm",
  md: "max-w-md",
  lg: "max-w-lg",
  xl: "max-w-xl",
};

interface ModalProps {
  open: boolean;
  onClose: () => void;
  title?: string;
  size?: ModalSize;
  children: React.ReactNode;
  className?: string;
}

/**
 * Canonical modal primitive — backdrop + centered panel, portalled to
 * <body> so it can't be clipped by an ancestor's overflow/z-index. Escape,
 * Tab-trapping, body-scroll-lock and return-focus-on-close all come from
 * useFocusTrap, shared with the mobile nav drawer.
 */
export default function Modal({ open, onClose, title, size = "md", children, className = "" }: ModalProps) {
  const panelRef = useFocusTrap(open, onClose);

  if (!open) return null;

  return createPortal(
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4" onClick={onClose}>
      <div className="absolute inset-0 bg-ink/60 backdrop-blur-sm" />
      <div
        ref={panelRef as React.RefObject<HTMLDivElement>}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        tabIndex={-1}
        onClick={(e) => e.stopPropagation()}
        className={`relative w-full ${sizeClasses[size]} rounded-2xl bg-surface shadow-2xl ring-1 ring-border ${className}`}
      >
        {title && (
          <div className="border-b border-rule px-6 py-4">
            <h3 className="text-base font-bold text-text">{title}</h3>
          </div>
        )}
        {children}
      </div>
    </div>,
    document.body
  );
}
