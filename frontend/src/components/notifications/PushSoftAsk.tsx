import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import api from "../../lib/api";
import { trackClick } from "../../lib/analytics";
import {
  canAsk,
  countSession,
  readAskRecord,
  recordDismissal,
  subscribe,
  usePushState,
  useRefreshPush,
} from "../../lib/push";
import { useAuth } from "../../hooks/useAuth";
import { useFocusTrap } from "../../hooks/useFocusTrap";
import { useToast } from "../../context/ToastContext";
import type { Notification, Paginated, UnreadCount } from "../../types/api";
import InstallGuide from "./InstallGuide";

/**
 * "Get offers on this phone" (mobile notifications §7.3, 5a): a bottom sheet
 * the first time a club member on a phone or tablet sees something that is
 * their move, when this device could get notifications but doesn't.
 *
 * Never in the first session; after "Not now", again in 14 days, at most
 * three times (lib/push canAsk). Opening the Home Screen app for the first
 * time (?source=homescreen) asks straight away. Settings always has the
 * same switch.
 */

function useNarrow(): boolean {
  const query = "(max-width: 1023px)";
  const [narrow, setNarrow] = useState(() => typeof window.matchMedia === "function" && window.matchMedia(query).matches);
  useEffect(() => {
    if (typeof window.matchMedia !== "function") return;
    const mq = window.matchMedia(query);
    const on = () => setNarrow(mq.matches);
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, []);
  return narrow;
}

/** The sheet's opening line, from the notification that prompted it. */
export function askBody(n: Notification | null): string {
  const tail = "We can tell you about the next one straight away, so you can reply before the deadline.";
  if (n?.type === "OFFER_RECEIVED" && n.player) {
    // `club` is never an anonymous buyer (the API leaves it out), so a named
    // club here is one the seller may see.
    return n.club ? `${n.club.name} just made an offer for ${n.player.name}. ${tail}`
      : `There's a new offer for ${n.player.name}. ${tail}`;
  }
  return "We can tell you straight away when an offer or approval needs you, so you can reply before the deadline.";
}

const FROM_HOME_SCREEN = new URLSearchParams(window.location.search).get("source") === "homescreen";

export default function PushSoftAsk() {
  const { isAuthenticated, userType } = useAuth();
  const narrow = useNarrow();
  const { addToast } = useToast();
  const refresh = useRefreshPush();
  const active = isAuthenticated && userType === "CLUB" && narrow;
  const { data: state } = usePushState(active);
  const [sessions] = useState(countSession);
  const askable = active && (state === "default" || state === "needs-install")
    && canAsk({ record: readAskRecord(), sessions, now: Date.now(), fromHomeScreen: FROM_HOME_SCREEN });

  // Re-checked whenever the bell's unread count changes (same cache entry).
  const { data: unread } = useQuery<UnreadCount>({
    queryKey: ["notifications", "unread-count"],
    queryFn: () => api.get<UnreadCount>("/notifications/unread-count").then((r) => r.data),
    enabled: askable,
    staleTime: 60_000,
  });
  const { data: latest } = useQuery<Paginated<Notification>>({
    queryKey: ["notifications", "soft-ask", unread?.count ?? 0],
    queryFn: () => api.get<Paginated<Notification>>("/notifications", { params: { page_size: 5 } }).then((r) => r.data),
    enabled: askable && !FROM_HOME_SCREEN && (unread?.count ?? 0) > 0,
  });
  const trigger = latest?.items.find((n) => !n.is_read && n.tier === "YOUR_MOVE") ?? null;

  const [open, setOpen] = useState(false);
  const [blocked, setBlocked] = useState(false);
  const [guide, setGuide] = useState(false);
  const [busy, setBusy] = useState(false);
  const shown = useRef(false); // once per page load

  useEffect(() => {
    if (shown.current || !askable || !(FROM_HOME_SCREEN || trigger)) return;
    shown.current = true;
    setOpen(true);
    trackClick("push_ask_shown", window.location.pathname);
  }, [askable, trigger]);

  function notNow() {
    recordDismissal();
    trackClick("push_ask_dismissed", window.location.pathname);
    setOpen(false);
  }
  const close = () => setOpen(false);
  const ref = useFocusTrap(open, blocked ? close : notNow);

  // Called straight from the tap: iOS asks for permission only from a gesture.
  async function turnOn() {
    if (state === "needs-install") {
      setOpen(false);
      setGuide(true);
      return;
    }
    setBusy(true);
    try {
      const result = await subscribe();
      if (result === "granted-subscribed") {
        addToast("Notifications are on for this phone", "success");
        setOpen(false);
      } else if (result === "denied") {
        setBlocked(true);
      } else {
        notNow();
      }
    } catch {
      addToast("Couldn't turn notifications on. You can try again in Settings.", "error");
      setOpen(false);
    } finally {
      setBusy(false);
      refresh();
    }
  }

  return (
    <>
      {open && (
        <div className="fixed inset-0 z-[60] flex items-end bg-ink/35" onClick={blocked ? close : notNow}>
          <div
            ref={ref as React.RefObject<HTMLDivElement>}
            role="dialog"
            aria-modal="true"
            aria-labelledby="push-ask-title"
            onClick={(e) => e.stopPropagation()}
            className="flex w-full flex-col gap-3 rounded-t-[26px] bg-surface px-5 pb-[26px] pt-[22px] shadow-xl"
          >
            <span aria-hidden className="mx-auto -mt-2.5 mb-1 h-[5px] w-10 rounded-full bg-border" />
            <h2 id="push-ask-title" className="text-xl font-bold text-text">Get offers on this phone</h2>
            {blocked ? (
              <>
                <p className="text-sm leading-normal text-text-secondary">
                  Notifications are blocked for TransferX. Turn them on in your phone's Settings, then come back.
                </p>
                <button type="button" onClick={close} className="h-12 w-full rounded-xl bg-surface-inset text-[15px] font-semibold text-text">
                  Close
                </button>
              </>
            ) : (
              <>
                <p className="text-sm leading-normal text-text-secondary">{askBody(trigger)}</p>
                <ul className="space-y-1 text-sm text-text">
                  <li>• Offers and approvals: straight away</li>
                  <li>• Everything else: in the app, when you look</li>
                </ul>
                <button
                  type="button"
                  onClick={turnOn}
                  disabled={busy}
                  className="mt-1 h-12 w-full rounded-xl bg-accent text-[15px] font-semibold text-white disabled:opacity-60"
                >
                  Turn on notifications
                </button>
                <button type="button" onClick={notNow} className="h-11 w-full text-[15px] font-semibold text-text-secondary">
                  Not now
                </button>
              </>
            )}
          </div>
        </div>
      )}
      <InstallGuide open={guide} onClose={() => setGuide(false)} />
    </>
  );
}
