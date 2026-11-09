import type { ReactNode } from "react";

export type StatusCardTone = "you" | "wait" | "info" | "hold" | "done" | "collapsed" | "closed";

const TONE: Record<StatusCardTone, { ring: string; overline: string }> = {
  you: { ring: "ring-danger-ring", overline: "text-danger-text" },
  wait: { ring: "ring-border", overline: "text-text-secondary" },
  info: { ring: "ring-border", overline: "text-text-muted" },
  hold: { ring: "ring-warning-fill/40", overline: "text-warning-text" },
  done: { ring: "ring-success/30", overline: "text-success-text" },
  collapsed: { ring: "ring-danger-border", overline: "text-danger-text-alt" },
  closed: { ring: "ring-border", overline: "text-text-muted" },
};

/** The card's box alone: for a status card whose content is replaced (the offer page's inline counter). */
export function StatusCardFrame({ labelledBy, ring, children }: { labelledBy: string; ring: string; children: ReactNode }) {
  return (
    <section
      aria-labelledby={labelledBy}
      className={`rounded-xl bg-surface p-4 shadow-[0_1px_2px_rgba(16,24,40,0.06)] ring-1 sm:px-5 sm:py-[18px] ${ring}`}
    >
      {children}
    </section>
  );
}

/**
 * The one place a transfer page says what happens next and who does it,
 * shared by the deal room and the offer page (deal-room-focus §5.3,
 * offer-room-focus §5.1). Text on the left, an optional middle column
 * (`children`), the buttons on the right (`actions`), and anything that
 * spans the card underneath (`footer`). The headline takes focus after an
 * action succeeds, so it has tabIndex -1 and the id `headlineId`.
 */
export default function StatusCardShell({
  tone, overline, overlineClassName, meta, headline, headlineId, body, children, actions, footer,
}: {
  tone: StatusCardTone;
  overline: string;
  /** Overrides the tone's overline colour (an offer due within a day turns red). */
  overlineClassName?: string;
  meta?: string;
  headline: string;
  headlineId: string;
  body?: ReactNode;
  children?: ReactNode;
  actions?: ReactNode;
  footer?: ReactNode;
}) {
  const t = TONE[tone];
  return (
    <StatusCardFrame labelledBy={headlineId} ring={t.ring}>
      <div className="flex flex-col gap-4 sm:flex-row sm:flex-wrap sm:gap-5 lg:flex-nowrap lg:items-center lg:gap-7">
        <div className="min-w-0 sm:flex-[1_1_360px] lg:flex-1">
          <p className={`text-xs font-bold uppercase tracking-[0.05em] ${overlineClassName ?? t.overline}`}>
            {overline}
            {meta && (
              <span className={`text-[13px] font-semibold normal-case tracking-normal ${overlineClassName ?? "text-text-secondary"}`}>
                {" · "}{meta}
              </span>
            )}
          </p>
          <h2 id={headlineId} tabIndex={-1} className="mt-1.5 text-[19px] font-bold leading-snug text-text focus:outline-none lg:text-xl">
            {headline}
          </h2>
          {body}
        </div>
        {children}
        {actions && (
          <div className="flex flex-col gap-2 sm:flex-[0_0_220px] lg:w-[200px] lg:flex-none">
            {actions}
          </div>
        )}
      </div>
      {footer}
    </StatusCardFrame>
  );
}
