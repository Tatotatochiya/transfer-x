import { Link } from "react-router-dom";

import Spinner from "../../components/ui/Spinner";
import { useDeadline, type DeadlineItem } from "../../hooks/useDeadline";
import { useDeadlineCountdown } from "../../hooks/useDeadlineCountdown";
import { formatCompactCurrency, formatDateTime } from "../../lib/utils";

/**
 * Deadline day (Q4 plan, Phase 2): every open transfer against the window's
 * close, with what each is waiting on and whose move it is. The club's
 * moves come first, then those at risk. Shown in Lite or the full app,
 * whichever the person uses (`lite` sizes it for Lite).
 */

const OWNER: Record<string, string> = {
  you: "Your move", either: "Your move", them: "Their move", player: "The player", agent: "The agent", staff: "TransferX staff",
};

function Countdown({ closesAt, lite }: { closesAt: string; lite: boolean }) {
  const c = useDeadlineCountdown(closesAt);
  const colour = c.state === "danger" || c.state === "expired" ? "text-danger-text" : c.state === "warning" ? "text-warning-text" : "text-text";
  return (
    <span className={`font-extrabold tabular-nums ${colour} ${lite ? "text-[2rem] sm:text-[2.5rem]" : "text-2xl"}`}>
      {c.state === "expired" ? "Closed" : c.label}
    </span>
  );
}

function liteLink(item: DeadlineItem): string {
  // In Lite, an offer waiting on the club opens its Lite card; the rest open the full page.
  return item.kind === "offer" && item.needs_you ? `/lite/offers/${item.id}` : item.link;
}

function Row({ item, lite }: { item: DeadlineItem; lite: boolean }) {
  const who = item.next_step ? OWNER[item.next_step.owner] ?? item.next_step.owner : null;
  const mine = item.needs_you;
  return (
    <li className={`flex flex-wrap items-center gap-x-4 gap-y-2 bg-surface ring-1 ${mine ? "ring-2 ring-accent" : "ring-border"} ${
      lite ? "rounded-[20px] px-5 py-4" : "rounded-xl px-4 py-3"}`}>
      <div className="min-w-0 flex-1 basis-56">
        <p className={`font-extrabold text-text ${lite ? "text-[1.25rem]" : "text-sm"}`}>
          {item.player_name}
          <span className={`ml-2 font-semibold text-text-muted ${lite ? "text-[1rem]" : "text-xs"}`}>
            {item.side === "BUYING" ? "Buying" : "Selling"}
            {item.counterparty ? (item.side === "BUYING" ? ` from ${item.counterparty}` : ` to ${item.counterparty}`) : ""}
            {item.amount != null ? ` · ${formatCompactCurrency(item.amount)}` : ""}
          </span>
        </p>
        <p className={`text-text-secondary ${lite ? "text-[1.0625rem]" : "text-sm"}`}>
          {item.stage}{item.next_step ? ` · next: ${item.next_step.label}` : ""}
        </p>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {who && (
          <span className={`rounded-full px-2.5 py-0.5 font-semibold ${mine ? "bg-accent-bg text-accent" : "bg-surface-inset text-text-secondary"} ${
            lite ? "text-[0.9375rem]" : "text-xs"}`}>{who}</span>
        )}
        {item.at_risk && (
          <span className={`rounded-full bg-danger-bg px-2.5 py-0.5 font-semibold text-danger-text ${lite ? "text-[0.9375rem]" : "text-xs"}`}>
            At risk · {item.steps_left} step{item.steps_left === 1 ? "" : "s"} left
          </span>
        )}
        <Link
          to={lite ? liteLink(item) : item.link}
          className={`flex items-center rounded-xl font-bold no-underline ${mine ? "bg-accent text-white" : "text-text ring-1 ring-border hover:ring-accent"} ${
            lite ? "min-h-[3.25rem] px-5 text-[1.0625rem]" : "min-h-11 px-3 text-sm lg:min-h-0 lg:py-1.5"}`}
        >
          {mine ? "Do it now" : "Open"}
        </Link>
      </div>
    </li>
  );
}

export default function DeadlinePage({ lite = false }: { lite?: boolean }) {
  const { data, isLoading, isError } = useDeadline();
  const h1 = lite ? "text-[2rem] sm:text-[2.375rem]" : "text-2xl";
  const body = lite ? "text-[1.125rem]" : "text-sm";

  if (isLoading) return <div className="flex justify-center py-16"><Spinner size="lg" /></div>;
  if (isError || !data) return <p className={`${body} text-danger-text`}>We couldn&rsquo;t load deadline day. Try again in a moment.</p>;

  const { window: w, items, counts } = data;
  return (
    <div className={`flex flex-col ${lite ? "gap-6" : "gap-4"}`}>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className={`font-extrabold tracking-[-0.02em] text-text ${h1}`}>Deadline day</h1>
          <p className={`text-text-secondary ${body}`}>
            {w.state === "open" && w.closes_at
              ? `${w.name ?? "The window"} closes ${formatDateTime(w.closes_at)}.`
              : w.state === "closed"
                ? `The window is closed.${w.opens_at ? ` ${w.name ?? "The next one"} opens ${formatDateTime(w.opens_at)}.` : ""}`
                : "No transfer window is set."}
          </p>
        </div>
        {w.state === "open" && w.closes_at && <Countdown closesAt={w.closes_at} lite={lite} />}
      </div>

      {w.state === "open" && (
        <p className={`text-text-secondary ${body}`}>
          <strong className="text-text">{counts.open}</strong> open
          {" · "}<strong className="text-accent">{counts.needs_you}</strong> waiting on you
          {" · "}<strong className="text-danger-text">{counts.at_risk}</strong> at risk
          {counts.talking ? ` · ${counts.talking} more still at the talking stage` : ""}
        </p>
      )}

      {items.length === 0 ? (
        <p className={`rounded-xl bg-surface px-5 py-6 text-text ring-1 ring-border ${body}`}>
          No transfers are open{w.state === "open" ? " before the window closes" : ""}.
        </p>
      ) : (
        <ul className={`flex flex-col ${lite ? "gap-3" : "gap-2"}`} aria-label="Open transfers">
          {items.map((i) => <Row key={`${i.kind}:${i.id}`} item={i} lite={lite} />)}
        </ul>
      )}

      {w.state === "open" && (
        <p className={`text-text-muted ${lite ? "text-[0.9375rem]" : "text-xs"}`}>
          &ldquo;At risk&rdquo; is a rough guide: fewer than {data.hours_per_step} hours left for each step still to do
          (agreeing the fee, personal terms, paperwork, signing). It shows what to chase, not what will fail.
        </p>
      )}
    </div>
  );
}
