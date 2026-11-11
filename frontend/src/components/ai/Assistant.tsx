/**
 * The workflow assistant's UI pieces (backend/app/ai/assist.py).
 *
 * Every panel here only advises. A suggestion is applied through the page's
 * normal, confirmed form — the advisor's "Use these terms" opens the counter
 * form pre-filled — and the server audits that it was used.
 */
import { useState } from "react";
import { Link } from "react-router-dom";

import { getApiError } from "../../lib/utils";
import { formatCompactCurrency } from "../../lib/utils";
import {
  useAIStatus,
  useBriefing,
  useNegotiationSummary,
  useOfferAdvice,
  usePotentialBuyers,
} from "../../hooks/useAssistant";
import type { Offer, SuggestedTerms, TermsWarning } from "../../types/api";
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
    <div className={`rounded-xl bg-surface p-4 ring-1 ring-ai-ring ${className}`}>
      <div className="flex items-center justify-between gap-3">
        <p className="text-body font-semibold text-text">
          <span className="text-ai-text">✦</span> {title}
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
      className="shrink-0 rounded-lg bg-ai-bg px-3 py-1.5 text-caption font-semibold text-ai-text ring-1 ring-ai-ring hover:brightness-95 disabled:opacity-50 transition-colors"
    >
      {loading ? <Spinner size="sm" /> : label}
    </button>
  );
}

function Loading({ text }: { text: string }) {
  return (
    <p className="flex items-center gap-2 text-small text-text-muted">
      <Spinner size="sm" /> {text}
    </p>
  );
}

function ErrorText({ error }: { error: unknown }) {
  return <p className="text-small text-danger-text">{getApiError(error, "The assistant could not answer — try again.")}</p>;
}

function Bullets({ items, className = "text-text-secondary" }: { items: string[]; className?: string }) {
  if (!items.length) return null;
  return (
    <ul className={`mt-1 list-disc space-y-1 pl-4 text-caption leading-snug ${className}`}>
      {items.map((t, i) => <li key={i}>{t}</li>)}
    </ul>
  );
}

// ── Terms warnings (rule-based, no model) ────────────────────────────────────

const SEVERITY_CLASS: Record<TermsWarning["severity"], string> = {
  high: "bg-danger-bg text-danger-text ring-danger-border",
  medium: "bg-warning-bg text-warning-text ring-warning-ring",
  low: "bg-surface-inset text-text-secondary ring-border",
};

export function TermsWarnings({ warnings, title = "Check these terms" }: { warnings: TermsWarning[] | undefined; title?: string }) {
  if (!warnings?.length) return null;
  return (
    <div className="space-y-1.5">
      <p className="text-caption font-semibold text-text-muted">
        <span className="text-ai-text">✦</span> {title}
      </p>
      {warnings.map((w) => (
        <p key={w.code} className={`rounded-lg px-3 py-2 text-caption leading-snug ring-1 ${SEVERITY_CLASS[w.severity]}`}>
          {w.message}
        </p>
      ))}
    </div>
  );
}

// ── Counter-offer advisor ────────────────────────────────────────────────────

const REC_LABEL: Record<string, { label: string; className: string }> = {
  accept: { label: "Accept", className: "bg-success-bg text-success-text ring-success-ring" },
  counter: { label: "Counter", className: "bg-accent-bg text-accent ring-accent-ring" },
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
        <p className="text-small text-text-muted">
          Weighs these terms against the fee model{offer.sale_id ? ", the guide price" : ""} and your position, and suggests a next move.
        </p>
      )}
      {isFetching && !data && <Loading text="Reading the negotiation…" />}
      {error != null && <ErrorText error={error} />}
      {data && rec && (
        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className={`rounded-full px-2.5 py-0.5 text-caption font-semibold ring-1 ${rec.className}`}>{rec.label}</span>
            {data.facts.fee_vs_model_pct != null && (
              <span className="text-small text-text-muted">
                {data.facts.fee_vs_model_pct >= 0 ? "+" : ""}{Math.round(data.facts.fee_vs_model_pct)}% vs model
              </span>
            )}
            {modelRange && modelRange[0] != null && (
              <span className="text-small text-text-muted">
                model {formatCompactCurrency(modelRange[0])}–{formatCompactCurrency(modelRange[1])}
              </span>
            )}
            {data.facts.competing_offers && (
              <span className="text-small text-text-muted">
                {data.facts.competing_offers.count} other offer{data.facts.competing_offers.count === 1 ? "" : "s"}
              </span>
            )}
          </div>
          <p className="text-small leading-snug text-text">{data.summary}</p>
          {data.suggested_terms && (
            <div className="rounded-lg bg-accent-bg px-3 py-2.5 ring-1 ring-accent-ring">
              <p className="text-small text-text">
                <span className="font-semibold">Suggested counter:</span> {describeTerms(data.suggested_terms)}
              </p>
              {canCounter && (
                <button
                  type="button"
                  onClick={() => onUseTerms(data.suggested_terms!)}
                  className="mt-2 rounded-lg bg-accent px-3 py-1.5 text-caption font-semibold text-on-accent hover:bg-accent-hover transition-colors"
                >
                  Use these terms in a counter
                </button>
              )}
            </div>
          )}
          <Bullets items={data.reasons} />
          {data.watch_outs.length > 0 && (
            <div>
              <p className="text-caption font-semibold text-text-muted">Watch out for</p>
              <Bullets items={data.watch_outs} />
            </div>
          )}
          <TermsWarnings warnings={data.checks} title="Rule checks on the current terms" />
          <p className="text-small text-text-muted">
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
          <p className="text-small leading-snug text-text">{data.summary}</p>
          {data.gap && (
            <p className="text-small"><span className="font-semibold text-text">Gap:</span> <span className="text-text-secondary">{data.gap}</span></p>
          )}
          <div className="grid gap-3 sm:grid-cols-2">
            {data.their_moves.length > 0 && (
              <div><p className="text-caption font-semibold text-text-muted">Their moves</p><Bullets items={data.their_moves} /></div>
            )}
            {data.your_moves.length > 0 && (
              <div><p className="text-caption font-semibold text-text-muted">Your moves</p><Bullets items={data.your_moves} /></div>
            )}
          </div>
        </div>
      )}
    </AIPanel>
  );
}

// ── Morning briefing ─────────────────────────────────────────────────────────

export function BriefingCard() {
  const { data: status } = useAIStatus();
  const [asked, setAsked] = useState(false);
  const { data, isFetching, error } = useBriefing(!!status?.available && asked);
  if (!status?.available) return null;
  return (
    <AIPanel
      title="Today's briefing"
      className="mb-6"
      action={!data && <AskButton label="Brief me" onClick={() => setAsked(true)} loading={isFetching} />}
    >
      {!asked && <p className="text-small text-text-muted">A short summary of what needs you today and what changed overnight.</p>}
      {isFetching && !data && <Loading text="Preparing your briefing…" />}
      {error != null && <ErrorText error={error} />}
      {data && (
        <div className="space-y-2">
          <p className="text-small leading-snug text-text">{data.headline}</p>
          {data.focus && (
            <p className="rounded-lg bg-accent-bg px-3 py-2 text-caption leading-snug text-text ring-1 ring-accent-ring">
              <span className="font-semibold">Focus today:</span> {data.focus}
            </p>
          )}
          <Bullets items={data.points} />
        </div>
      )}
    </AIPanel>
  );
}

// ── Who might want him ───────────────────────────────────────────────────────

export function PotentialBuyersPanel({ playerId }: { playerId: string }) {
  const [asked, setAsked] = useState(false);
  const { data, isFetching, error } = usePotentialBuyers(playerId, asked);
  return (
    <AIPanel
      title="Who might want him?"
      action={!data && <AskButton label="Find clubs" onClick={() => setAsked(true)} loading={isFetching} />}
    >
      {!asked && <p className="text-small text-text-muted">Clubs on TransferX whose squads look short in his position, from public squad information.</p>}
      {isFetching && !data && <Loading text="Looking at squads…" />}
      {error != null && <ErrorText error={error} />}
      {data && (
        <div className="space-y-2">
          {data.summary && <p className="text-small leading-snug text-text">{data.summary}</p>}
          <ul className="space-y-2">
            {data.clubs.map((c) => (
              <li key={c.club_id} className="text-small leading-snug">
                <Link to={`/clubs/${c.club_id}`} className="font-semibold text-text hover:text-accent">{c.club}</Link>
                <span className="text-text-secondary"> — {c.reason}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </AIPanel>
  );
}
