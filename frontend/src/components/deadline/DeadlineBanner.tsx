import { Link } from "react-router-dom";

import { timeUntil, useDeadline } from "../../hooks/useDeadline";

/**
 * Shown on the Lite home and the dashboard once the window closes within
 * three days and the club has transfers open: the time left, how many wait
 * on the club, and a way into deadline-day mode.
 */
export default function DeadlineBanner({ lite = false }: { lite?: boolean }) {
  const { data } = useDeadline();
  if (!data?.window.deadline_mode || !data.window.closes_at || data.counts.open === 0) return null;
  const { open, needs_you: mine, at_risk: risky } = data.counts;
  const left = timeUntil(data.window.closes_at);
  return (
    <div
      role="status"
      className={`flex flex-wrap items-center gap-3 bg-danger-bg ring-1 ring-danger-border ${
        lite ? "rounded-[18px] px-5 py-4" : "mb-4 rounded-xl px-4 py-3"
      }`}
    >
      <span className="min-w-0 flex-1">
        <span className={`block font-extrabold text-danger-text ${lite ? "text-[1.25rem]" : "text-sm"}`}>
          Deadline day: the window closes in {left}
        </span>
        <span className={`block text-text-secondary ${lite ? "text-[1.0625rem]" : "text-sm"}`}>
          {open} transfer{open === 1 ? "" : "s"} still open
          {mine ? `, ${mine} waiting on you` : ""}
          {risky ? `, ${risky} at risk` : ""}.
        </span>
      </span>
      <Link
        to="/deadline"
        className={`flex items-center rounded-xl bg-danger font-bold text-white no-underline ${
          lite ? "min-h-[3.25rem] px-6 text-[1.0625rem]" : "min-h-11 px-4 text-sm lg:min-h-0 lg:py-2"
        }`}
      >
        Open deadline day
      </Link>
    </div>
  );
}
