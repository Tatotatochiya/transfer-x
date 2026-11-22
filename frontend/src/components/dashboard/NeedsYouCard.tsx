import { useState } from "react";
import { Link } from "react-router-dom";

import FallbackImage from "../ui/FallbackImage";
import Button, { buttonClasses } from "../ui/Button";
import { formatCompactCurrency } from "../../lib/utils";
import { useDeadlineCountdown } from "../../hooks/useDeadlineCountdown";
import type { DashboardItem } from "../../types/api";

const ACTION: Record<DashboardItem["kind"], string> = {
  approval: "Review",
  offer: "Respond",
  deal: "Open",
  enquiry: "Reply",
};

const FALLBACK_TITLE: Record<DashboardItem["kind"], string> = {
  approval: "Approval request",
  offer: "Offer",
  deal: "Deal",
  enquiry: "Enquiry",
};

const CAP = 5;

function Deadline({ deadline }: { deadline: string | null }) {
  const result = useDeadlineCountdown(deadline);
  if (!deadline) return null;
  return (
    <span className={`tabular-nums ${result.state === "danger" || result.state === "expired" ? "font-semibold text-danger-text" : "text-text-secondary"}`}>
      {result.state === "expired" ? "Expired" : result.label}
    </span>
  );
}

/** One counted row: the whole row opens it; from 640px the verb shows as a button. */
function NeedsYouRow({ item }: { item: DashboardItem }) {
  const name = item.player_name ?? FALLBACK_TITLE[item.kind];
  return (
    <li>
      <Link to={item.link} className="flex items-center gap-3 px-4 py-3 transition-colors hover:bg-surface-inset sm:px-5">
        <FallbackImage src={item.player_photo_url} name={name} sizeClass="h-9 w-9 text-caption"
          colorClass="bg-surface-inset text-text-secondary" />
        <span className="min-w-0 flex-1">
          <span className="flex items-baseline justify-between gap-3">
            <span className="truncate text-body font-semibold text-text">{name}</span>
            {item.amount != null && (
              <span className="shrink-0 text-body font-semibold tabular-nums text-text sm:hidden">
                {formatCompactCurrency(item.amount)}
              </span>
            )}
          </span>
          <span className="block text-small sm:truncate">
            <span className="font-semibold text-danger-text">{item.reason}</span>
            {item.club_name && <span className="hidden text-text-secondary sm:inline"> · {item.club_name}</span>}
          </span>
          {item.club_name && <span className="block truncate text-small text-text-secondary sm:hidden">{item.club_name}</span>}
        </span>
        <span className="hidden shrink-0 text-right text-small sm:block">
          {item.amount != null && (
            <span className="block text-body font-semibold tabular-nums text-text">{formatCompactCurrency(item.amount)}</span>
          )}
          <Deadline deadline={item.deadline} />
        </span>
        <span className={`hidden shrink-0 sm:inline-flex ${buttonClasses("primary", "sm")}`}>{ACTION[item.kind]}</span>
        <span aria-hidden="true" className="shrink-0 text-section text-text-muted sm:hidden">›</span>
      </Link>
    </li>
  );
}

/** An uncounted housekeeping row under "Also". */
function AlsoRow({ children, action }: { children: React.ReactNode; action?: React.ReactNode }) {
  return (
    <li className="flex flex-wrap items-center gap-x-3 gap-y-2 px-4 py-2.5 sm:px-5">
      <span className="min-w-0 flex-1 text-small text-text-secondary">{children}</span>
      {action && <span className="flex shrink-0 items-center gap-2">{action}</span>}
    </li>
  );
}

export interface ExpiringRow {
  player_id: string;
  player_name: string;
  days_remaining: number;
}

/**
 * The Dashboard's to-do list (feature_spec/club-dashboard §4.2). The counted
 * rows are exactly the server's `waiting_on_you`, the same list the sidebar's
 * Transfers and Approvals badges count, in the server's order. Housekeeping
 * sits under "Also" and is never counted.
 */
export default function NeedsYouCard({
  items, myPendingApprovals = 0, expiring = [], onList, setup, onOpenSetup, namePrompt,
}: {
  items: DashboardItem[];
  /** For someone who doesn't approve: their own requests waiting on an approver. */
  myPendingApprovals?: number;
  /** Contracts ending within 60 days, not listed. */
  expiring?: ExpiringRow[];
  /** Given only with MARKET_WRITE. */
  onList?: (row: ExpiringRow) => void;
  setup?: { done: number; total: number } | null;
  onOpenSetup?: () => void;
  namePrompt?: { show: boolean; dismiss: () => void };
}) {
  const [all, setAll] = useState(false);
  const count = items.length;
  const shown = all ? items : items.slice(0, CAP);
  const expiringShown = expiring.slice(0, 2);
  const hasAlso = myPendingApprovals > 0 || expiring.length > 0 || !!setup || !!namePrompt?.show;

  return (
    <section id="needs-you" aria-labelledby="needs-you-heading"
      className={`scroll-mt-24 overflow-hidden rounded-2xl bg-surface ring-1 ${count > 0 ? "ring-danger-ring" : "ring-border"}`}>
      <div className="flex items-center gap-2 px-4 pt-4 pb-2 sm:px-5">
        {count > 0 && <span aria-hidden="true" className="h-2 w-2 rounded-full bg-danger" />}
        <h2 id="needs-you-heading" className="text-section font-bold text-text">Needs you</h2>
        <span className="text-caption font-semibold tabular-nums text-text-muted" data-testid="needs-you-count">{count}</span>
        {count > 1 && <span className="ml-auto hidden text-small text-text-muted sm:inline">Most urgent first</span>}
      </div>

      {count === 0 ? (
        <p className="px-4 pb-3 text-body text-text-secondary sm:px-5">Nothing needs you right now.</p>
      ) : (
        <ul className="divide-y divide-rule-faint">
          {shown.map((item) => <NeedsYouRow key={`${item.kind}-${item.id}`} item={item} />)}
        </ul>
      )}
      {count > CAP && !all && (
        <button type="button" onClick={() => setAll(true)}
          className="px-4 py-2 text-small font-semibold text-accent hover:underline sm:px-5">
          Show all {count}
        </button>
      )}

      {hasAlso && (
        <>
          <p className="border-t border-rule px-4 pt-3 text-caption font-semibold text-text-muted sm:px-5">Also</p>
          <ul className="pb-1.5">
            {myPendingApprovals > 0 && (
              <AlsoRow action={<Link to="/club/approvals" className="text-small font-semibold text-accent hover:underline">View</Link>}>
                {myPendingApprovals} of your request{myPendingApprovals === 1 ? " is" : "s are"} awaiting approval
              </AlsoRow>
            )}
            {expiringShown.map((c) => (
              <AlsoRow key={c.player_id}
                action={onList && <Button size="sm" variant="secondary" onClick={() => onList(c)}>List</Button>}>
                {c.player_name}&rsquo;s contract ends in {c.days_remaining} day{c.days_remaining === 1 ? "" : "s"}
              </AlsoRow>
            ))}
            {expiring.length > expiringShown.length && (
              <AlsoRow>
                <Link to="/club" className="font-semibold text-accent hover:underline">
                  +{expiring.length - expiringShown.length} more contract{expiring.length - expiringShown.length === 1 ? "" : "s"} ending
                </Link>
              </AlsoRow>
            )}
            {setup && (
              <AlsoRow action={<Button size="sm" variant="secondary" onClick={onOpenSetup}>Continue</Button>}>
                Finish setting up your club · {setup.done} of {setup.total}
              </AlsoRow>
            )}
            {namePrompt?.show && (
              <AlsoRow action={<>
                <Link to="/account#name" className={buttonClasses("secondary", "sm")}>Add name</Link>
                <button type="button" onClick={namePrompt.dismiss} className="text-small text-text-muted hover:text-text">Not now</button>
              </>}>
                Add your name so your team sees who did what
              </AlsoRow>
            )}
          </ul>
        </>
      )}
    </section>
  );
}
