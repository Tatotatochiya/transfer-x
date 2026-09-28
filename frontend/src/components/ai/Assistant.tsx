/**
 * The workflow assistant's UI pieces (backend/app/ai/assist.py).
 *
 * Every panel here only advises. A suggestion is applied through the page's
 * normal, confirmed form — the advisor's "Use these terms" opens the counter
 * form pre-filled — and the server audits that it was used.
 */
import { useState } from "react";

import { getApiError } from "../../lib/utils";
import { formatCompactCurrency } from "../../lib/utils";
import {
  useAIStatus,
  useDealNextSteps,
  useNegotiationSummary,
  useOfferAdvice,
} from "../../hooks/useAssistant";
import type { Deal, Offer, SuggestedTerms, TermsWarning } from "../../types/api";
import Spinner from "../ui/Spinner";

// ── Shell ─────────────────────────────────────────────────────────────────────

export function AIPanel({
  title,
  action,
  children,
  className = "",
}: {
  title: string;
  action?: React.ReactNode;
  children?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={`rounded-xl bg-surface p-4 ring-1 ring-role-agent-text/25 ${className}`}>
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm font-semibold text-text">
          <span className="text-role-agent-text">✦</span> {title}
        </p>
        {action}
      </div>
      {children && <div className="mt-3">{children}</div>}
    </div>
  );
}

function AskButton({ onClick, label, loading }: { onClick: () => void; label: string; loading?: boolean }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={loading}
      className="shrink-0 rounded-lg bg-role-agent-text/10 px-3 py-1.5 text-xs font-semibold text-role-agent-text ring-1 ring-role-agent-text/30 hover:bg-role-agent-text/20 disabled:opacity-50 transition-colors"
    >
      {loading ? <Spinner size="sm" /> : label}
    </button>
  );
}

function Loading({ text }: { text: string }) {
  return (
    <p className="flex items-center gap-2 text-xs text-text-muted">
      <Spinner size="sm" /> {text}
    </p>
  );
}

function ErrorText({ error }: { error: unknown }) {
  return <p className="text-xs text-danger-text">{getApiError(error, "The assistant could not answer — try again.")}</p>;
}

function Bullets({ items, className = "text-text-secondary" }: { items: string[]; className?: string }) {
  if (!items.length) return null;
  return (
    <ul className={`mt-1 list-disc space-y-1 pl-4 text-[13px] leading-snug ${className}`}>
      {items.map((t, i) => <li key={i}>{t}</li>)}
    </ul>
  );
}

// ── Terms warnings (rule-based, no model) ────────────────────────────────────

const SEVERITY_CLASS: Record<TermsWarning["severity"], string> = {
  high: "bg-danger-bg text-danger-text ring-danger-border",
  medium: "bg-warning-bg text-warning-text ring-warning-fill/20",
  low: "bg-surface-inset text-text-secondary ring-border",
};

export function TermsWarnings({ warnings, title = "Check these terms" }: { warnings: TermsWarning[] | undefined; title?: string }) {
  if (!warnings?.length) return null;
  return (
    <div className="space-y-1.5">
      <p className="text-xs font-semibold text-text-muted">
        <span className="text-role-agent-text">✦</span> {title}
      </p>
      {warnings.map((w) => (
        <p key={w.code} className={`rounded-lg px-3 py-2 text-[13px] leading-snug ring-1 ${SEVERITY_CLASS[w.severity]}`}>
          {w.message}
        </p>
      ))}
    </div>
  );
}

// ── Counter-offer advisor ────────────────────────────────────────────────────

const REC_LABEL: Record<string, { label: string; className: string }> = {
  accept: { label: "Accept", className: "bg-success/15 text-success-text ring-success/30" },
  counter: { label: "Counter", className: "bg-accent-bg text-accent ring-accent/30" },
  reject: { label: "Reject", className: "bg-danger-bg text-danger-text ring-danger-border" },
  wait: { label: "Wait for their move", className: "bg-surface-inset text-text-secondary ring-border" },
};

function describeTerms(t: SuggestedTerms): string {
  const parts: string[] = [];
  if (t.fee_amount != null) parts.push(`fee ${formatCompactCurrency(t.fee_amount)}`);
  if (t.loan_fee != null) parts.push(`loan fee ${formatCompactCurrency(t.loan_fee)}`);
  if (t.wage_weekly != null) parts.push(`wage ${formatCompactCurrency(t.wage_weekly)}/wk`);
  if (t.contract_years != null) parts.push(`${t.contract_years}-year contract`);
  if (t.sell_on_pct != null) parts.push(`${Math.round(t.sell_on_pct * 100)}% sell-on`);
  if (t.wage_split_pct != null) parts.push(`they pay ${Math.round(t.wage_split_pct * 100)}% of wages`);
  if (t.option_to_buy != null) parts.push(`option to buy ${formatCompactCurrency(t.option_to_buy)}`);
  return parts.join(", ");
}

export function OfferAdvisor({
  offer,
  canCounter,
  onUseTerms,
}: {
  offer: Offer;
  canCounter: boolean;
  onUseTerms: (terms: SuggestedTerms) => void;
}) {
  const { data: status } = useAIStatus();
  const [asked, setAsked] = useState(false);
  const { data, isFetching, error } = useOfferAdvice(offer.id, offer.last_action_at, asked);
  if (!status?.available) return null;

  const rec = data ? REC_LABEL[data.recommendation] ?? REC_LABEL.wait : null;
  const modelRange = data?.facts.model_range;
  return (
    <AIPanel
      title="Offer advisor"
      action={!data && <AskButton label="What should we do?" onClick={() => setAsked(true)} loading={isFetching} />}
    >
      {!asked && !data && (
        <p className="text-xs text-text-muted">
          Weighs these terms against the fee model{offer.sale_id ? ", the guide price" : ""} and your position, and suggests a next move.
        </p>
      )}
      {isFetching && !data && <Loading text="Reading the negotiation…" />}
      {error != null && <ErrorText error={error} />}
      {data && rec && (
        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ${rec.className}`}>{rec.label}</span>
            {data.facts.fee_vs_model_pct != null && (
              <span className="text-xs text-text-muted">
                {data.facts.fee_vs_model_pct >= 0 ? "+" : ""}{Math.round(data.facts.fee_vs_model_pct)}% vs model
              </span>
            )}
            {modelRange && modelRange[0] != null && (
              <span className="text-xs text-text-muted">
                model {formatCompactCurrency(modelRange[0])}–{formatCompactCurrency(modelRange[1])}
              </span>
            )}
            {data.facts.competing_offers && (
              <span className="text-xs text-text-muted">
                {data.facts.competing_offers.count} other offer{data.facts.competing_offers.count === 1 ? "" : "s"}
              </span>
            )}
          </div>
          <p className="text-[13px] leading-snug text-text">{data.summary}</p>
          {data.suggested_terms && (
            <div className="rounded-lg bg-accent-bg px-3 py-2.5 ring-1 ring-accent/20">
              <p className="text-[13px] text-text">
                <span className="font-semibold">Suggested counter:</span> {describeTerms(data.suggested_terms)}
              </p>
              {canCounter && (
                <button
                  type="button"
                  onClick={() => onUseTerms(data.suggested_terms!)}
                  className="mt-2 rounded-lg bg-accent px-3 py-1.5 text-xs font-semibold text-white hover:bg-accent-hover transition-colors"
                >
                  Use these terms in a counter
                </button>
              )}
            </div>
          )}
          <Bullets items={data.reasons} />
          {data.watch_outs.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-text-muted">Watch out for</p>
              <Bullets items={data.watch_outs} />
            </div>
          )}
          <TermsWarnings warnings={data.checks} title="Rule checks on the current terms" />
          <p className="text-[11px] text-text-muted">
            Advice only — figures come from TransferX's data; you decide and act.
          </p>
        </div>
      )}
    </AIPanel>
  );
}

// ── Negotiation summary ──────────────────────────────────────────────────────

export function NegotiationSummaryPanel({ offer }: { offer: Offer }) {
  const { data: status } = useAIStatus();
  const [asked, setAsked] = useState(false);
  const rounds = offer.events?.filter((e) => e.event_type === "COUNTERED" || e.event_type === "IMPROVED").length ?? 0;
  const { data, isFetching, error } = useNegotiationSummary(offer.id, offer.last_action_at, asked);
  if (!status?.available || rounds < 1) return null;
  return (
    <AIPanel
      title="Where this negotiation stands"
      action={!data && <AskButton label="Summarise" onClick={() => setAsked(true)} loading={isFetching} />}
    >
      {isFetching && !data && <Loading text="Summarising…" />}
      {error != null && <ErrorText error={error} />}
      {data && (
        <div className="space-y-2">
          <p className="text-[13px] leading-snug text-text">{data.summary}</p>
          {data.gap && (
            <p className="text-xs"><span className="font-semibold text-text">Gap:</span> <span className="text-text-secondary">{data.gap}</span></p>
          )}
          <div className="grid gap-3 sm:grid-cols-2">
            {data.their_moves.length > 0 && (
              <div><p className="text-xs font-semibold text-text-muted">Their moves</p><Bullets items={data.their_moves} /></div>
            )}
            {data.your_moves.length > 0 && (
              <div><p className="text-xs font-semibold text-text-muted">Your moves</p><Bullets items={data.your_moves} /></div>
            )}
          </div>
        </div>
      )}
    </AIPanel>
  );
}

// ── Deal next steps ──────────────────────────────────────────────────────────

const OWNER_LABEL: Record<string, string> = {
  you: "You", them: "Them", either: "Either club", player: "The player", agent: "The agent", staff: "TransferX",
};

export function DealNextStepsPanel({ deal }: { deal: Deal }) {
  // Keyed on the deal's version so a step completed elsewhere refreshes it.
  const version = `${deal.updated_at}:${deal.stage}:${deal.personal_terms?.player_consent ?? ""}:${deal.medical_check?.status ?? ""}`;
  const { data } = useDealNextSteps(deal.id, version);
  if (!data || data.steps.length === 0) return null;
  const mine = data.steps.filter((s) => s.owner === "you" || s.owner === "either");
  return (
    <AIPanel title="Next steps" className="mb-6">
      {data.brief?.headline && <p className="mb-2 text-[13px] leading-snug text-text">{data.brief.headline}</p>}
      <ul className="space-y-1.5">
        {data.steps.map((s, i) => (
          <li key={i} className="flex items-start justify-between gap-3 text-[13px]">
            <span className={s.owner === "you" || s.owner === "either" ? "font-medium text-text" : "text-text-secondary"}>
              {s.label}
              {s.due && <span className="ml-1 text-text-muted">· by {s.due}</span>}
            </span>
            <span className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] font-semibold ring-1 ${
              s.owner === "you" ? "bg-accent-bg text-accent ring-accent/30" : "bg-surface-inset text-text-muted ring-border"
            }`}>
              {OWNER_LABEL[s.owner] ?? s.owner}
            </span>
          </li>
        ))}
      </ul>
      {data.brief && data.brief.advice.length > 0 && mine.length > 0 && <Bullets items={data.brief.advice} />}
      {data.idle_days != null && data.idle_days >= 5 && (
        <p className="mt-2 text-xs text-warning-text">No movement for {data.idle_days} days.</p>
      )}
    </AIPanel>
  );
}
