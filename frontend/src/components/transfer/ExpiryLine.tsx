import { useDeadlineCountdown } from "../../hooks/useDeadlineCountdown";

/** "Mon 1 Sep 2026, 23:00", in the viewer's own time. */
export function expiryWhen(iso: string): string {
  return new Date(iso).toLocaleString("en-GB", {
    weekday: "short", day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

/**
 * When an offer or deal runs out, and a live countdown to it (product ADR
 * 0014: by default, when the buying club's transfer window closes). Red in
 * the last day. The countdown ticks every second, so it is not announced:
 * the exact time is.
 */
export default function ExpiryLine({ at, label }: {
  at: string;
  /** "Offer expires", "Collapses unless completed by" */
  label: string;
}) {
  const left = useDeadlineCountdown(at);
  const lastDay = new Date(at).getTime() - Date.now() < 86_400_000;
  const passed = left.state === "expired";
  return (
    <p className={`flex flex-wrap items-baseline gap-x-2 text-small ${lastDay ? "text-danger-text" : "text-text-secondary"}`}>
      <span>
        <span className="font-semibold">{label}</span>{" "}
        <time dateTime={at}>{expiryWhen(at)}</time>
      </span>
      <span role="timer" aria-live="off" className={`font-semibold tabular-nums ${lastDay ? "" : "text-text"}`}>
        {passed ? "Time's up" : `${left.label} left`}
      </span>
    </p>
  );
}
