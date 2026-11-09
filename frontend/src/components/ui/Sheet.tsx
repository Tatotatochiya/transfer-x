import { useEffect, useId, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";

const FOCUSABLE =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

/**
 * A form that opens over the page on phones and tablets (offer-room-focus
 * §5.6): full height below 640px, a 560px centred dialog from 640px. The
 * header and footer stay put while the body scrolls, so the footer's submit
 * button is always on screen.
 *
 * It traps focus as Modal does, but leaves keys alone while focus is outside
 * it, so a confirm opened on top of it (Discard your counter?) works.
 * On open, focus goes to the element marked `data-autofocus`, else the first
 * control; on close it returns to whatever opened the sheet.
 */
export default function Sheet({ open, onClose, title, subtitle, footer, children }: {
  open: boolean;
  onClose: () => void;
  title: string;
  subtitle?: ReactNode;
  footer: ReactNode;
  children: ReactNode;
}) {
  const panelRef = useRef<HTMLDivElement>(null);
  const titleId = useId();
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    if (!open) return;
    const opener = document.activeElement as HTMLElement | null;
    const panel = panelRef.current;
    const focusables = () => Array.from(panel?.querySelectorAll<HTMLElement>(FOCUSABLE) ?? []);
    (panel?.querySelector<HTMLElement>("[data-autofocus]") ?? focusables()[0])?.focus();

    function inside() {
      const a = document.activeElement;
      return !a || a === document.body || !!panel?.contains(a);
    }
    function onKeyDown(e: KeyboardEvent) {
      if (!inside()) return;
      if (e.key === "Escape") {
        e.preventDefault();
        onCloseRef.current();
        return;
      }
      if (e.key !== "Tab") return;
      const items = focusables();
      if (items.length === 0) return;
      const first = items[0];
      const last = items[items.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    }
    document.addEventListener("keydown", onKeyDown);
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = overflow;
      if (opener && document.contains(opener)) opener.focus();
    };
  }, [open]);

  if (!open) return null;

  return createPortal(
    <div className="fixed inset-0 z-[90] sm:flex sm:items-center sm:justify-center sm:p-4">
      <div className="absolute inset-0 hidden bg-ink/40 sm:block" onClick={() => onClose()} aria-hidden />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="relative flex h-full w-full flex-col bg-surface sm:h-auto sm:max-h-[90vh] sm:w-[560px] sm:rounded-2xl sm:shadow-2xl sm:ring-1 sm:ring-border"
      >
        <div className="flex shrink-0 items-start gap-3 border-b border-rule px-4 pb-3 pt-[max(12px,env(safe-area-inset-top))] sm:px-5 sm:pt-4">
          <div className="min-w-0 flex-1">
            <h2 id={titleId} className="text-lg font-bold text-text">{title}</h2>
            {subtitle && <p className="mt-0.5 text-sm text-text-secondary">{subtitle}</p>}
          </div>
          <button
            type="button"
            aria-label="Close without sending"
            onClick={() => onClose()}
            className="-mr-2 flex h-11 w-11 shrink-0 items-center justify-center rounded-lg text-xl text-text-muted hover:bg-surface-inset hover:text-text"
          >
            ×
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4 sm:px-5">{children}</div>
        <div className="shrink-0 border-t border-rule bg-surface px-4 pt-3 pb-[max(16px,env(safe-area-inset-bottom))] shadow-[0_-4px_12px_rgba(16,24,40,0.06)] sm:rounded-b-2xl sm:px-5">
          {footer}
        </div>
      </div>
    </div>,
    document.body,
  );
}
