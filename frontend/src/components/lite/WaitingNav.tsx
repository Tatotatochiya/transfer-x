import { useRef, type ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useClubDashboard } from "../../hooks/useClubDashboard";
import type { DashboardItem } from "../../types/api";

/**
 * "Waiting on you · 2 of 3" with Previous and Next, through the Dashboard's
 * waiting list, so a director can work through everything from one push
 * (mobile notifications §7.3). Offers and approvals open their decision
 * sheet; anything else opens its own page. `SwipeNav` adds a swipe.
 */

function sheetHref(item: DashboardItem): string {
  if (item.kind === "offer") return `/lite/offers/${item.id}?from=push`;
  if (item.kind === "approval") return `/lite/approvals/${item.id}?from=push`;
  return item.link;
}

export function useWaitingNav(kind: DashboardItem["kind"], id: string) {
  const { data } = useClubDashboard(true);
  const items = data?.waiting_on_you ?? [];
  const i = items.findIndex((it) => it.kind === kind && it.id === id);
  const at = (step: number) => {
    if (items.length < 2) return null;
    const item = items[((i < 0 ? 0 : i) + step + items.length) % items.length];
    return item && !(item.kind === kind && item.id === id) ? sheetHref(item) : null;
  };
  return { index: i, total: items.length, prevHref: i >= 0 ? at(-1) : null, nextHref: i >= 0 ? at(1) : sheetHref(items[0] ?? ({} as DashboardItem)) };
}

export function WaitingHeader({ kind, id }: { kind: DashboardItem["kind"]; id: string }) {
  const { index, total, prevHref, nextHref } = useWaitingNav(kind, id);
  if (total === 0) return null;
  return (
    <div className="flex items-center justify-between gap-3">
      {prevHref ? (
        <Link to={prevHref} className="text-[1.0625rem] font-semibold text-text-secondary no-underline">‹ Previous</Link>
      ) : (
        <Link to="/lite" className="text-[1.0625rem] font-semibold text-text-secondary no-underline">‹ Home</Link>
      )}
      <span className="text-[1rem] font-semibold text-text-secondary">
        Waiting on you{index >= 0 ? ` · ${index + 1} of ${total}` : ` · ${total}`}
      </span>
      {nextHref ? <Link to={nextHref} className="text-[1.0625rem] font-bold text-accent no-underline">Next ›</Link> : <span />}
    </div>
  );
}

const SWIPE_PX = 70;

/** Swipe left for the next item, right for the previous one. A mostly
 *  vertical drag (scrolling) is ignored, and so are drags that start on a
 *  form control, so typing an amount never changes page. */
export function SwipeNav({ kind, id, enabled, children }: {
  kind: DashboardItem["kind"]; id: string; enabled: boolean; children: ReactNode;
}) {
  const navigate = useNavigate();
  const { prevHref, nextHref } = useWaitingNav(kind, id);
  const start = useRef<{ x: number; y: number } | null>(null);
  if (!enabled) return <>{children}</>;
  return (
    <div
      onTouchStart={(e) => {
        const t = e.target as HTMLElement;
        start.current = t.closest("input, textarea, select, button[aria-label*='less'], button[aria-label*='more']")
          ? null : { x: e.touches[0].clientX, y: e.touches[0].clientY };
      }}
      onTouchEnd={(e) => {
        const s = start.current;
        start.current = null;
        if (!s) return;
        const dx = e.changedTouches[0].clientX - s.x;
        const dy = e.changedTouches[0].clientY - s.y;
        if (Math.abs(dx) < SWIPE_PX || Math.abs(dx) < Math.abs(dy) * 1.5) return;
        const href = dx < 0 ? nextHref : prevHref;
        if (href) navigate(href);
      }}
    >
      {children}
    </div>
  );
}
