import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import api from "../../lib/api";
import { useAuth } from "../../hooks/useAuth";
import { useDeadlineCountdown } from "../../hooks/useDeadlineCountdown";
import { formatDateTime } from "../../lib/utils";
import Icon from "../layout/Icon";
import type { Club, TransferWindowStatus } from "../../types/api";

/**
 * Small, always-visible countdown to the transfer window opening or closing —
 * lives in the top bar (both desktop and mobile) so every page carries it.
 * Scoped to the current club's association (country) when known, so a club in
 * England sees England's window rather than an unrelated global one.
 */
export default function TransferWindowCountdown() {
  const { isAuthenticated, isClub, isSuperuser } = useAuth();
  const [hover, setHover] = useState(false);

  const { data: club } = useQuery<Club>({
    queryKey: ["clubs", "me"],
    queryFn: () => api.get<Club>("/clubs/me").then((r) => r.data),
    enabled: isAuthenticated && isClub,
    staleTime: 60_000,
  });
  const association = club?.country ?? null;

  const { data: windowStatus } = useQuery<TransferWindowStatus>({
    queryKey: ["transfer-window", "status", association],
    queryFn: () =>
      api
        .get<TransferWindowStatus>("/transfers/window/status", { params: { association: association ?? undefined } })
        .then((r) => r.data),
    staleTime: 60_000,
    refetchInterval: 60_000,
  });

  const isOpen = windowStatus?.is_open ?? false;
  const target = isOpen ? windowStatus?.current_window?.closes_at : windowStatus?.next_window?.opens_at;
  const countdown = useDeadlineCountdown(target);

  if (!windowStatus) return null;

  let dotColour = "bg-slate-500";
  let text = "Open market";
  let tooltip = association
    ? `No transfer window configured for ${association} or globally — transfers are unrestricted.`
    : "No transfer window configured — transfers are unrestricted.";

  if (windowStatus.enforced) {
    if (isOpen && windowStatus.current_window) {
      dotColour = "bg-emerald-400";
      text = countdown.state === "expired" ? "Closing…" : `Closes ${countdown.label}`;
      tooltip = `${windowStatus.current_window.name} is open — closes ${formatDateTime(windowStatus.current_window.closes_at)}`;
    } else if (windowStatus.next_window) {
      dotColour = "bg-red-400";
      text = countdown.state === "expired" ? "Opening…" : `Opens ${countdown.label}`;
      tooltip = `Window closed — ${windowStatus.next_window.name} opens ${formatDateTime(windowStatus.next_window.opens_at)}`;
    } else {
      dotColour = "bg-red-400";
      text = "Window closed";
      tooltip = "Transfer window is closed — no upcoming window scheduled.";
    }
  }

  const pill = (
    <div
      className="relative flex items-center gap-1.5 rounded-full bg-slate-900/80 px-2.5 py-1 text-xs ring-1 ring-white/[0.08] backdrop-blur"
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
    >
      <Icon name="clock" className="h-3.5 w-3.5 text-slate-400 shrink-0" />
      <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${dotColour} ${windowStatus.enforced && isOpen ? "animate-pulse" : ""}`} />
      <span className="font-medium tabular-nums text-slate-200 whitespace-nowrap">{text}</span>

      {hover && (
        <div className="pointer-events-none absolute right-0 top-full z-50 mt-2 w-56 rounded-md bg-slate-800 px-3 py-2 text-xs text-slate-300 shadow-xl ring-1 ring-white/10">
          {tooltip}
          {isSuperuser && <div className="mt-1 text-[10px] text-emerald-400">Click to manage windows →</div>}
        </div>
      )}
    </div>
  );

  if (isSuperuser) {
    return (
      <Link to="/admin/windows" className="no-underline">
        {pill}
      </Link>
    );
  }
  return pill;
}
