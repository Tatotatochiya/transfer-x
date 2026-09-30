import { useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

import { liteMoney } from "../../lib/liteMoney";
import type { OfferMoney, TermsWarning } from "../../types/api";

/**
 * The Lite action card (docs/feature_spec/lite-mode README "Screen 5"): the
 * "normal confirmed form" of ADR 0006. It only describes an action; the page
 * using it calls the existing offer endpoints on confirm. Every figure in the
 * money panel comes from POST /ai/offer-check's `money` block, never from
 * the model and never computed here.
 */

export const HALF_M = 500_000;

/** A value that settles `ms` after it stops changing (the money check). */
export function useDebounced<T>(value: T, ms = 250): T {
  const [settled, setSettled] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setSettled(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return settled;
}

type Tone = "ready" | "received" | "approval";
const PILL: Record<Tone, string> = {
  ready: "bg-accent-bg text-accent",
  received: "bg-danger-bg text-danger-text",
  approval: "bg-warning-bg text-warning-text",
};

export function ActionCardShell({
  pill, tone, title, children, money,
}: { pill: string; tone: Tone; title: string; children: ReactNode; money: ReactNode }) {
  return (
    <div className="grid overflow-hidden rounded-3xl bg-surface ring-1 ring-border lg:grid-cols-[minmax(0,1fr)_400px]">
      <div className="flex flex-col gap-5 px-6 py-7 sm:px-8">
        <span className={`self-start rounded-full px-3 py-1 text-[0.8125rem] font-extrabold uppercase tracking-wide ${PILL[tone]}`}>
          {pill}
        </span>
        <h1 className="text-[1.75rem] font-extrabold leading-tight tracking-[-0.02em] text-text sm:text-[1.875rem]">{title}</h1>
        {children}
      </div>
      <aside className="flex flex-col gap-5 border-t border-border bg-surface-inset px-6 py-7 sm:px-7 lg:border-l lg:border-t-0">
        {money}
      </aside>
    </div>
  );
}

export function FactRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4 border-b border-border py-3 text-[1.125rem] last:border-b-0">
      <span className="text-text-muted">{label}</span>
      <span className="text-right font-semibold text-text">{children}</span>
    </div>
  );
}

export function FeeStepper({ value, onChange, label }: { value: number; onChange: (v: number) => void; label: string }) {
  const [text, setText] = useState(String(value / 1_000_000));
  useEffect(() => setText(String(value / 1_000_000)), [value]);
  const step = (d: number) => onChange(Math.max(HALF_M, value + d));
  const btn =
    "flex h-14 w-14 shrink-0 items-center justify-center rounded-xl bg-surface text-[1.75rem] font-bold text-text ring-1 ring-border hover:ring-accent focus:outline-none focus-visible:ring-2 focus-visible:ring-accent disabled:opacity-40";
  return (
    <div className="flex items-center gap-3">
      <button type="button" className={btn} onClick={() => step(-HALF_M)} disabled={value <= HALF_M} aria-label="£0.5m less">−</button>
      <label className="flex min-w-0 flex-1 items-center justify-center gap-1 rounded-xl bg-surface px-3 ring-1 ring-border focus-within:ring-2 focus-within:ring-accent">
        <span className="text-[1.75rem] font-extrabold text-text">£</span>
        <input
          aria-label={label}
          inputMode="decimal"
          value={text}
          onChange={(e) => {
            setText(e.target.value);
            const m = Number(e.target.value);
            if (Number.isFinite(m) && m > 0) onChange(Math.round(m * 1_000_000));
          }}
          className="h-14 w-24 min-w-0 bg-transparent text-center text-[1.75rem] font-extrabold text-text focus:outline-none"
        />
        <span className="text-[1.75rem] font-extrabold text-text">m</span>
      </label>
      <button type="button" className={btn} onClick={() => step(HALF_M)} aria-label="£0.5m more">+</button>
    </div>
  );
}

/** Warnings other than the budget ones, which the money panel already shows. */
export function Notes({ warnings }: { warnings: TermsWarning[] | undefined }) {
  const notes = (warnings ?? []).filter(
    (w) => w.severity !== "low" && w.code !== "over_transfer_budget" && w.code !== "over_wage_budget",
  );
  if (!notes.length) return null;
  return (
    <ul className="flex flex-col gap-2 rounded-xl bg-warning-bg px-4 py-3 text-base text-warning-text">
      {notes.map((w) => <li key={w.code}>{w.message}</li>)}
    </ul>
  );
}

export function MoneyPanel({ money, loading, what }: { money: OfferMoney | undefined; loading: boolean; what: string }) {
  if (!money || money.transfer_before == null) {
    return (
      <>
        <h2 className="text-base font-bold text-text">What this does to your money</h2>
        <p className="text-[1.0625rem] text-text-secondary">{loading ? "Working it out…" : "Your club has no budget on record."}</p>
      </>
    );
  }
  const total = money.transfer_budget ?? 0;
  const after = money.transfer_after ?? 0;
  const pct = (v: number) => `${total > 0 ? Math.max(0, Math.min(100, (v / total) * 100)) : 0}%`;
  const over = money.over_budget;
  return (
    <>
      <h2 className="text-base font-bold text-text">What this does to your money</h2>
      <div>
        <p className="text-[1.0625rem] text-text-secondary">Money left to spend</p>
        <p className="mt-1 flex flex-wrap items-baseline gap-x-3">
          <span className="text-[1.5rem] text-text-muted line-through">{liteMoney(money.transfer_before)}</span>
          <span className={`text-[2.125rem] font-extrabold ${over ? "text-danger-text" : "text-text"}`}>
            → {liteMoney(after)}
          </span>
        </p>
        {money.on_completion && (
          <p className="mt-1 text-base text-text-secondary">The fee comes in when the deal completes.</p>
        )}
      </div>
      {!money.on_completion && total > 0 && (
        <div>
          <div className="flex h-3 overflow-hidden rounded-full bg-border" aria-hidden="true">
            <span className="h-full bg-accent" style={{ width: pct(Math.max(0, after)) }} />
            <span
              className="h-full bg-[repeating-linear-gradient(45deg,var(--color-warning-fill)_0_6px,transparent_6px_12px)]"
              style={{ width: pct(Math.max(0, money.this_action)) }}
            />
          </div>
          <p className="mt-2 text-base text-text-secondary">
            Striped part is this {what}, of your {liteMoney(total)} budget
          </p>
        </div>
      )}
      {money.wage_before_weekly != null && money.wage_after_weekly != null && (
        <div>
          <p className="text-[1.0625rem] text-text-secondary">Spare for wages</p>
          <p className={`mt-1 text-[1.25rem] font-bold ${money.over_wage ? "text-danger-text" : "text-text"}`}>
            {liteMoney(money.wage_before_weekly)} → {liteMoney(money.wage_after_weekly)} a week
          </p>
        </div>
      )}
      {over && (
        <p role="alert" className="rounded-xl bg-danger-bg px-4 py-3 text-[1.0625rem] font-semibold text-danger-text">
          {money.over_transfer ? "This is more than you have left to spend." : "This is more than you have left for wages."}
        </p>
      )}
      <p className="mt-auto text-[0.9375rem] text-text-muted">
        From your club's budget on TransferX, worked out now.{money.on_completion ? "" : " Nothing is held until you confirm."}
      </p>
    </>
  );
}

/** What happened, once the action has been sent. */
export function Done({ title, body, links }: { title: string; body: string; links: { to: string; label: string }[] }) {
  return (
    <div className="flex flex-col items-start gap-5 rounded-3xl bg-surface px-6 py-8 ring-1 ring-border sm:px-8">
      <span className="flex h-16 w-16 items-center justify-center rounded-full bg-success-text/10 text-[2rem] font-extrabold text-success-text" aria-hidden="true">
        ✓
      </span>
      <h1 className="text-[1.75rem] font-extrabold tracking-[-0.02em] text-text sm:text-[2.25rem]">{title}</h1>
      <p className="text-[1.1875rem] text-text-secondary">{body}</p>
      <div className="flex w-full flex-col gap-3 sm:w-auto sm:flex-row">
        {links.map((l, i) => (
          <Link
            key={l.to}
            to={l.to}
            className={`flex min-h-[3.5rem] items-center justify-center rounded-xl px-6 text-[1.0625rem] font-bold no-underline ${
              i === 0 ? "bg-accent text-white" : "text-text ring-1 ring-border hover:ring-accent"
            }`}
          >
            {l.label}
          </Link>
        ))}
      </div>
    </div>
  );
}

export const primaryBtn =
  "min-h-[4rem] flex-1 rounded-xl bg-accent px-6 text-[1.125rem] font-bold text-white hover:bg-accent-hover focus:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50";
export const secondaryBtn =
  "min-h-[4rem] rounded-xl px-6 text-[1.125rem] font-bold text-text ring-1 ring-border hover:ring-accent focus:outline-none focus-visible:ring-2 focus-visible:ring-accent disabled:cursor-not-allowed disabled:opacity-50";
export const dangerBtn =
  "min-h-[4rem] rounded-xl px-6 text-[1.125rem] font-bold text-danger-text ring-1 ring-danger-border hover:bg-danger-bg focus:outline-none focus-visible:ring-2 focus-visible:ring-danger disabled:cursor-not-allowed disabled:opacity-50";
export const textBtn =
  "min-h-[3.25rem] rounded-xl px-4 text-[1.0625rem] font-semibold text-text-secondary hover:text-text focus:outline-none focus-visible:ring-2 focus-visible:ring-accent";
