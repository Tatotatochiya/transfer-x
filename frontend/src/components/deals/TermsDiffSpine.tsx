import { useQuery } from "@tanstack/react-query";
import api from "../../lib/api";
import type { DealTermsVersion, TermsDiff } from "../../types/api";
import type { DealType } from "../../types/enums";
import Card from "../ui/Card";
import ResponsiveTable, { type ResponsiveColumn } from "../ui/ResponsiveTable";
import { dealTypeLabel } from "../../lib/badges";
import { formatCurrency, formatDate } from "../../lib/utils";

// ── Terms diff — the spine of the screen ──────────────────────────────────────

const TERMS_FIELD_LABELS: Record<string, string> = {
  agreed_fee: "Agreed fee",
  agreed_wage_weekly: "Weekly wage",
  deal_type: "Deal type",
  loan_start: "Loan start",
  loan_end: "Loan end",
  loan_fee: "Loan fee",
  option_to_buy: "Option to buy",
  obligation_to_buy: "Obligation to buy",
  obligation_conditions: "Obligation conditions",
  sell_on_pct: "Sell-on %",
};

const CURRENCY_FIELDS = new Set(["agreed_fee", "agreed_wage_weekly", "loan_fee", "option_to_buy"]);

function formatTermValue(field: string, value: unknown): string {
  if (value == null || value === "") return "—";
  if (field === "sell_on_pct") return `${(Number(value) * 100).toFixed(1)}%`;
  if (CURRENCY_FIELDS.has(field)) return formatCurrency(Number(value));
  if (typeof value === "boolean") return value ? "Yes" : "No";
  // Without this the diff spine prints the raw enum ("FREE_TRANSFER").
  if (field === "deal_type") return dealTypeLabel(value as DealType);
  return String(value);
}

interface DiffRow { field: string; oldValue: unknown; newValue: unknown }

export default function TermsDiffSpine({ dealId, isBuyer }: { dealId: string; isBuyer: boolean }) {
  const { data: versions = [], isLoading } = useQuery<DealTermsVersion[]>({
    queryKey: ["deals", dealId, "versions"],
    queryFn: () => api.get<DealTermsVersion[]>(`/deals/${dealId}/versions`).then((r) => r.data),
  });

  const { data: diff } = useQuery<TermsDiff>({
    queryKey: ["deals", dealId, "versions", "diff"],
    queryFn: () => api.get<TermsDiff>(`/deals/${dealId}/versions/diff`).then((r) => r.data),
    enabled: versions.length >= 2,
  });

  if (isLoading) return null;
  if (versions.length === 0 || !diff || diff.changes.length === 0) return null;

  const latest = [...versions].sort((a, b) => b.version_number - a.version_number)[0];
  const unchangedCount = Math.max(0, Object.keys(latest.terms_snapshot ?? {}).length - diff.changes.length);

  const rows: DiffRow[] = diff.changes.map((c) => ({ field: c.field, oldValue: c.old_value, newValue: c.new_value }));

  // DECISIONS.md item 5: no present-value model exists — nominal difference
  // only, never an invented discount rate. "Effect on you" only applies to
  // currency fields; everything else has no clean monetary framing.
  function effect(row: DiffRow): { text: string; className: string } {
    if (!CURRENCY_FIELDS.has(row.field)) return { text: "—", className: "text-text-muted" };
    const oldN = Number(row.oldValue ?? 0);
    const newN = Number(row.newValue ?? 0);
    const delta = newN - oldN;
    if (delta === 0) return { text: "No change", className: "text-text-muted" };
    // A higher fee/wage/loan-fee/option is worse for the buyer, better for the seller.
    const worseForMe = isBuyer ? delta > 0 : delta < 0;
    const magnitude = formatCurrency(Math.abs(delta));
    return {
      text: `${worseForMe ? "−" : "+"}${magnitude}`,
      className: worseForMe ? "text-danger-text" : "text-success-text",
    };
  }

  const netDelta = rows
    .filter((r) => CURRENCY_FIELDS.has(r.field))
    .reduce((sum, r) => {
      const delta = Number(r.newValue ?? 0) - Number(r.oldValue ?? 0);
      return sum + (isBuyer ? -delta : delta);
    }, 0);

  const columns: ResponsiveColumn<DiffRow>[] = [
    { key: "term", header: "Term", priority: 1, render: (r) => (
      <span className="font-medium text-text">{TERMS_FIELD_LABELS[r.field] ?? r.field}</span>
    ) },
    { key: "old", header: `Agreed (v${(latest.version_number - 1)})`, priority: 3, render: (r) => (
      <span className="text-text-muted line-through">{formatTermValue(r.field, r.oldValue)}</span>
    ) },
    { key: "new", header: `Proposed (v${latest.version_number})`, priority: 2, render: (r) => (
      <span className="font-bold text-text">{formatTermValue(r.field, r.newValue)}</span>
    ) },
    { key: "effect", header: "Effect on you", priority: 4, className: "text-right", render: (r) => {
      const e = effect(r);
      return <span className={`font-semibold ${e.className}`}>{e.text}</span>;
    } },
  ];

  return (
    <Card noPadding className="mb-6">
      <div className="border-b border-rule px-5 py-4">
        <p className="text-sm font-bold text-text">
          Terms — version {latest.version_number} proposed by {latest.changed_by_label ?? "the deal"}
        </p>
        <p className="mt-0.5 text-xs text-text-muted">
          {diff.changes.length} term{diff.changes.length === 1 ? "" : "s"} changed
          {unchangedCount > 0 && ` · ${unchangedCount} unchanged`}
          {" · sent "}{formatDate(latest.created_at)}
        </p>
      </div>
      <div className="p-5">
        <ResponsiveTable
          columns={columns}
          rows={rows}
          rowKey={(r) => r.field}
          renderCard={(r) => {
            const e = effect(r);
            return (
              <div className="px-4 py-3">
                <p className="text-sm font-semibold text-text">{TERMS_FIELD_LABELS[r.field] ?? r.field}</p>
                <div className="mt-1 flex items-center justify-between text-sm">
                  <span className="text-text-muted line-through">{formatTermValue(r.field, r.oldValue)}</span>
                  <span className="font-bold text-text">{formatTermValue(r.field, r.newValue)}</span>
                </div>
                <p className={`mt-0.5 text-right text-xs font-semibold ${e.className}`}>{e.text}</p>
              </div>
            );
          }}
        />
      </div>
      {netDelta !== 0 && (
        <div className="border-t border-rule px-5 py-3">
          <p className="text-xs text-text-muted">
            Net change against version {latest.version_number - 1}:{" "}
            <span className={netDelta < 0 ? "text-danger-text font-semibold" : "text-success-text font-semibold"}>
              {netDelta < 0 ? "−" : "+"}{formatCurrency(Math.abs(netDelta))}
            </span>{" "}
            to you over the life of the deal.
          </p>
        </div>
      )}
    </Card>
  );
}

