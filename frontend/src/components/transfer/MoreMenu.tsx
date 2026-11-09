import { Fragment, useEffect, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";

const FOCUS = "focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-accent";
const ITEM = `flex min-h-12 w-full items-center rounded-lg px-2.5 text-left text-[15px] text-text no-underline hover:bg-surface-inset lg:min-h-10 lg:text-sm ${FOCUS}`;

export interface MoreMenuItem {
  label: string;
  /** A link, or an action. */
  to?: string;
  onSelect?: () => void;
  danger?: boolean;
  dividerBefore?: boolean;
}

/**
 * A transfer page's secondary actions (deal-room-focus §5.7,
 * offer-room-focus §5.10), kept away from the main action. Keyboard as the
 * account menu in Sidebar.tsx: arrows, Home/End, Escape returns focus to the
 * button; it closes on an outside click, Tab and a route change. With no
 * items the trigger is hidden.
 */
export default function MoreMenu({ items }: { items: MoreMenuItem[] }) {
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

  const menuItems = () => Array.from(menuRef.current?.querySelectorAll<HTMLElement>('[role="menuitem"]') ?? []);

  useEffect(() => {
    if (open && focusFirst.current) menuItems()[0]?.focus();
    focusFirst.current = false;
  }, [open]);

  if (items.length === 0) return null;

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
    const list = menuItems();
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
          {items.map((item, i) => (
            <Fragment key={item.label}>
              {item.dividerBefore && i > 0 && <div role="separator" className="my-1 h-px bg-rule" />}
              {item.to ? (
                <Link to={item.to} role="menuitem" tabIndex={-1} className={`${ITEM} ${item.danger ? "text-danger-text-alt" : ""}`}>
                  {item.label}
                </Link>
              ) : (
                <button
                  type="button"
                  role="menuitem"
                  tabIndex={-1}
                  onClick={() => { setOpen(false); item.onSelect?.(); }}
                  className={`${ITEM} ${item.danger ? "text-danger-text-alt" : ""}`}
                >
                  {item.label}
                </button>
              )}
            </Fragment>
          ))}
        </div>
      )}
    </div>
  );
}
