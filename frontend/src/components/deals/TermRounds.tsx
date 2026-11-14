import { useQuery } from "@tanstack/react-query";

import api from "../../lib/api";
import { formatCurrency, formatDate, formatWage } from "../../lib/utils";
import type { Deal, TermProposal } from "../../types/api";

const PAYER: Record<string, string> = { BUYER: "the buying club", SELLER: "the selling club", PLAYER: "the player" };

function commission(t: TermProposal["terms"]): string {
  const pct = t.commission_pct != null ? `${+(Number(t.commission_pct) * 100).toFixed(2)}%` : null;
  const amount = t.commission_amount != null ? formatCurrency(Number(t.commission_amount)) : null;
  const payer = t.commission_payer ? `paid by ${PAYER[t.commission_payer] ?? t.commission_payer.toLowerCase()}` : null;
  return [pct && amount ? `${pct} (${amount})` : pct ?? amount, payer].filter(Boolean).join(", ");
}

function personalTerms(t: TermProposal["terms"]): string {
  const wage = t.wage_weekly != null ? formatWage(Number(t.wage_weekly)) : null;
  const years = t.length_years != null ? `${t.length_years} year${t.length_years === 1 ? "" : "s"}` : null;
  const bonus = t.signing_bonus != null && Number(t.signing_bonus) > 0 ? `${formatCurrency(Number(t.signing_bonus))} signing bonus` : null;
  return [[wage, years].filter(Boolean).join(" for "), bonus].filter(Boolean).join(", ");
}

/** The buying club offers or counters; the agent or player asks, or comes back. */
function verb(r: TermProposal, i: number): string {
  if (r.side === "BUYER") return i === 0 && r.kind === "PERSONAL_TERMS" ? "offered" : "countered with";
  return i === 0 ? "asked for" : "came back with";
}

/**
 * The rounds of the stage's negotiation, oldest first (ADR 0012): who asked
 * for what, and each counter with its note. Shown once there's been a counter.
 */
export default function TermRounds({ deal }: { deal: Deal }) {
  const kind = deal.stage === "AGENT_NEGOTIATION" ? "COMMISSION" : deal.stage === "PERSONAL_TERMS" ? "PERSONAL_TERMS" : null;
  const { data } = useQuery<TermProposal[]>({
    queryKey: ["deals", deal.id, "term-proposals"],
    queryFn: () => api.get<TermProposal[]>(`/deals/${deal.id}/term-proposals`).then((r) => r.data),
    enabled: kind != null,
  });
  const rounds = (data ?? []).filter((r) => r.kind === kind);
  if (rounds.length < 2) return null;
  const P = deal.player?.name ?? "the player";
  const name = (side: TermProposal["side"]) =>
    side === "BUYER" ? deal.buyer_club?.name ?? "The buying club"
      : side === "AGENT" ? deal.agent?.display_name ?? "The agent"
        : `${P}'s side`;
  return (
    <div className="mt-4 border-t border-rule pt-3">
      <p className="text-small font-semibold text-text-secondary">The negotiation so far</p>
      <ol className="mt-1.5 space-y-1">
        {rounds.map((r, i) => (
          <li key={r.id} className="text-small text-text-secondary">
            <span className="font-semibold text-text">{name(r.side)}</span>{" "}
            {verb(r, i)} {kind === "COMMISSION" ? commission(r.terms) : personalTerms(r.terms)}
            <span className="text-text-muted"> · {formatDate(r.created_at)}</span>
            {r.note && <span className="text-text-muted"> “{r.note}”</span>}
          </li>
        ))}
      </ol>
    </div>
  );
}
