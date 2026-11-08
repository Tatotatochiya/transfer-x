import { useEffect, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { askAboutPath } from "../../lib/ask";

const FOCUS = "focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-accent";
const ITEM = `flex min-h-12 w-full items-center rounded-lg px-2.5 text-left text-[15px] text-text no-underline hover:bg-surface-inset lg:min-h-10 lg:text-sm ${FOCUS}`;

/**
 * The deal room's secondary actions (deal-room-focus §5.7): asking TransferX
 * about the deal, and collapsing it, kept away from the main action (D6).
 * Keyboard as the account menu in Sidebar.tsx: arrows, Home/End, Escape
 * returns focus to the button; it closes on an outside click, Tab and a
 * route change.
 */
export default function DealMoreMenu({ dealId, playerName, canAsk, canCollapse, onCollapse }: {
  dealId: string;
  playerName: string;
  canAsk: boolean;
  canCollapse: boolean;
  onCollapse: () => void;
}) {
  const [open, setOpen] = useState(false);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const focusFirst = useRef(false);
  const location = useLocation();

  useEffect(() => { setOpen(false); }, [location.pathname]);

  useEffect(() => {
    if (!open) return;
    function onDown(e: MouseEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  const items = () => Array.from(menuRef.current?.querySelectorAll<HTMLElement>('[role="menuitem"]') ?? []);

  useEffect(() => {
    if (open && focusFirst.current) items()[0]?.focus();
    focusFirst.current = false;
  }, [open]);

  if (!canAsk && !canCollapse) return null;

  function close() {
    setOpen(false);
    buttonRef.current?.focus();
  }

  function onButtonKeyDown(e: React.KeyboardEvent) {
    if (e.key === "ArrowUp" || e.key === "ArrowDown") {
      e.preventDefault();
      focusFirst.current = true;
      setOpen(true);
    } else if (e.key === "Escape" && open) {
      e.stopPropagation();
      close();
    }
  }

  function onMenuKeyDown(e: React.KeyboardEvent) {
    const list = items();
    const i = list.indexOf(document.activeElement as HTMLElement);
    const go = (n: number) => { e.preventDefault(); list[(n + list.length) % list.length]?.focus(); };
    if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); close(); }
    else if (e.key === "ArrowDown") go(i + 1);
    else if (e.key === "ArrowUp") go(i - 1);
    else if (e.key === "Home") go(0);
    else if (e.key === "End") go(list.length - 1);
    else if (e.key === "Tab") setOpen(false);
  }

  return (
    <div ref={wrapperRef} className="relative">
      <button
        ref={buttonRef}
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={(e) => { focusFirst.current = e.detail === 0; setOpen((o) => !o); }}
        onKeyDown={onButtonKeyDown}
        className="min-h-11 rounded-lg bg-surface px-3.5 text-[15px] font-semibold text-text-secondary ring-1 ring-inset ring-input-border hover:text-text lg:min-h-10 lg:text-sm"
      >
        More ⋯
      </button>
      {open && (
        <div
          ref={menuRef}
          role="menu"
          aria-label="More actions"
          onKeyDown={onMenuKeyDown}
          className="absolute right-0 top-[calc(100%+6px)] z-50 w-64 rounded-xl bg-surface p-1.5 shadow-xl ring-1 ring-border"
        >
          {canAsk && (
            <Link to={askAboutPath("deal", dealId, playerName)} role="menuitem" tabIndex={-1} className={ITEM}>
              Ask TransferX about this deal
            </Link>
          )}
          {canAsk && canCollapse && <div role="separator" className="my-1 h-px bg-rule" />}
          {canCollapse && (
            <button
              type="button"
              role="menuitem"
              tabIndex={-1}
              onClick={() => { setOpen(false); onCollapse(); }}
              className={`${ITEM} text-danger-text-alt`}
            >
              Collapse deal…
            </button>
          )}
        </div>
      )}
    </div>
  );
}
