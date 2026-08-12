import { useEffect, useRef } from "react";

const FOCUSABLE =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

/**
 * Shared overlay behaviour for anything that opens on top of the page —
 * Escape closes it, Tab cycles only within it, body scroll locks while
 * it's open, and focus returns to whatever triggered it on close. Used by
 * Modal and the mobile nav drawer, per docs/design_handoff_transferx/RESPONSIVE.md
 * ("traps focus while open and returns focus to the hamburger on close").
 */
export function useFocusTrap(active: boolean, onClose: () => void) {
  const containerRef = useRef<HTMLElement>(null);
  const triggerRef = useRef<Element | null>(null);

  useEffect(() => {
    if (!active) return;

    triggerRef.current = document.activeElement;
    const container = containerRef.current;
    const focusables = () => Array.from(container?.querySelectorAll<HTMLElement>(FOCUSABLE) ?? []);
    focusables()[0]?.focus();

    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        onClose();
        return;
      }
      if (e.key !== "Tab") return;
      const items = focusables();
      if (items.length === 0) return;
      const first = items[0];
      const last = items[items.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    }
    document.addEventListener("keydown", handleKeyDown);

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = previousOverflow;
      (triggerRef.current as HTMLElement | null)?.focus?.();
    };
  }, [active, onClose]);

  return containerRef;
}
