import { useState, type ReactNode } from "react";
import api from "../../lib/api";
import type { Deal, FairValueSignal } from "../../types/api";
import FairValueBadge from "../players/FairValueBadge";
import Money from "../ui/Money";
import { formatCurrency, formatDate, formatWage } from "../../lib/utils";

function Row({ label, value, note, span }: { label: string; value: ReactNode; note?: ReactNode; span?: boolean }) {
  return (
    <div className={`flex justify-between gap-3 border-t border-rule py-3 ${span ? "sm:col-span-2" : ""}`}>
      <span className="text-body text-text-secondary">{label}</span>
      <div className="min-w-0 text-right">
        <div className="text-body font-semibold text-text">{value}</div>
        {note && <div className="mt-0.5 text-caption text-text-muted">{note}</div>}
      </div>
    </div>
  );
}

function Disclosure({ id, open, onToggle, children }: { id: string; open: boolean; onToggle: () => void; children: ReactNode }) {
  return (
    <button
      type="button"
      aria-expanded={open}
      aria-controls={id}
      onClick={onToggle}
      className="inline-flex min-h-11 items-center gap-1 font-semibold text-accent lg:min-h-0"
    >
      {children} <span aria-hidden>{open ? "⌃" : "⌄"}</span>
    </button>
  );
}

const PAYER: Record<string, string> = { BUYER: "the buying club", SELLER: "the selling club", PLAYER: "the player" };

/**
 * Everything agreed on the deal, in one card (deal-room-focus §5.6): the old
 * Agreed terms, Deal structure, Add-ons, Payment schedule, Agent commission,
 * Personal terms and Medical panels. The schedule and add-ons open in place.
 */
export default function DealTermsCard({
  deal, isPlayer, isBuyer, fairValue, canRecordMedical, onRecordMedical, scheduleOpen, onToggleSchedule,
}: {
  deal: Deal;
  isPlayer: boolean;
  isBuyer: boolean;
  fairValue: FairValueSignal | null;
  canRecordMedical: boolean;
  onRecordMedical: () => void;
  scheduleOpen: boolean;
  onToggleSchedule: () => void;
}) {
  const [addonsOpen, setAddonsOpen] = useState(false);
  const loan = deal.deal_type === "LOAN";
  const terms = deal.personal_terms;
  const P = deal.player?.name ?? "the player";
  const wage = deal.agreed_wage_weekly ?? terms?.wage_weekly ?? null;
  const wageFromProposal = deal.agreed_wage_weekly == null && terms?.wage_weekly != null;
  const years = deal.contract_length_years ?? terms?.length_years ?? null;
  const bonus = deal.signing_bonus ?? terms?.signing_bonus ?? null;
  const medical = deal.medical_check;

  async function openEvidence(e: React.MouseEvent) {
    e.preventDefault();
    const res = await api.get(
      `/deals/${deal.id}/attachments/${terms!.consent_evidence_attachment_id}/download`,
      { responseType: "blob" },
    );
    window.open(URL.createObjectURL(res.data), "_blank");
  }

  return (
    <section aria-labelledby="deal-terms-heading" className="rounded-xl bg-surface px-4 pb-4 pt-3.5 ring-1 ring-border sm:px-5">
      <h3 id="deal-terms-heading" className="mb-1 text-section font-bold text-text">Agreed terms</h3>
      <div className="grid sm:grid-cols-2 sm:gap-x-8">
        <Row
          label={loan ? "Loan fee" : "Fee"}
          value={<Money value={deal.agreed_fee} />}
          note={!isPlayer && fairValue ? <FairValueBadge signal={fairValue} referenceLabel="Agreed fee" /> : undefined}
        />

        {loan && (
          <>
            <Row label="Loan period" value={`${formatDate(deal.loan_start)} – ${formatDate(deal.loan_end)}`} />
            <Row label="Wage share" value={(() => {
              const pct = Math.round(Number(deal.wage_split_pct ?? 1) * 100);
              const w = deal.agreed_wage_weekly != null ? Number(deal.agreed_wage_weekly) : null;
              return w != null
                ? `${pct}% — ${formatCurrency(Math.round(w * pct / 100))}/wk of ${formatCurrency(w)}/wk`
                : `${pct}% of his wage`;
            })()} />
            <Row
              label="Purchase"
              value={<span className={deal.obligation_to_buy ? "text-warning-text" : undefined}>
                {deal.option_to_buy != null
                  ? `${deal.obligation_to_buy ? "Obligation" : "Option"} to buy at ${formatCurrency(deal.option_to_buy)}`
                  : "None — he returns at the end"}
              </span>}
            />
            {deal.obligation_to_buy && deal.obligation_conditions && <Row label="Conditional on" value={deal.obligation_conditions} />}
            <Row label="Early recall" value={deal.recall_allowed ? "His club may recall him" : "Not allowed"} />
          </>
        )}

        {!loan && (
          <Row
            label="Payment"
            value={deal.instalments.length === 0 ? "On completion" : (
              <Disclosure id="deal-schedule" open={scheduleOpen} onToggle={onToggleSchedule}>
                {deal.instalments.length} instalments
              </Disclosure>
            )}
          />
        )}
        {!loan && scheduleOpen && deal.instalments.length > 0 && (
          <ul id="deal-schedule" className="space-y-1.5 border-t border-rule py-3 sm:col-span-2">
            {deal.instalments.map((inst) => (
              <li key={inst.id} className="flex items-center justify-between gap-3 text-body">
                <span className="text-text-secondary">{formatDate(inst.due_date)}</span>
                <span className="font-semibold text-text">{formatCurrency(inst.amount)}</span>
                <span className={inst.paid ? "text-success-text" : "text-text-muted"}>
                  {inst.paid ? `Paid ${inst.paid_at ? formatDate(inst.paid_at) : ""}` : "Pending"}
                </span>
              </li>
            ))}
          </ul>
        )}

        {deal.sell_on_pct != null && <Row label="Sell-on" value={`${(Number(deal.sell_on_pct) * 100).toFixed(1)}%`} />}

        {wage != null && (
          <Row
            label="Wage"
            value={formatWage(Number(wage))}
            note={<>
              {years != null && <span>{years}-year contract</span>}
              {wageFromProposal && terms?.player_consent !== "AGREED" && (
                <span className="block text-warning-text">Proposed · waiting for {P}</span>
              )}
            </>}
          />
        )}
        {bonus != null && <Row label="Signing bonus" value={formatCurrency(bonus)} />}

        {(deal.agent_commission_pct != null || deal.agent_commission_amount != null) && (
          <Row
            label="Agent commission"
            value={[
              deal.agent_commission_pct != null ? `${(Number(deal.agent_commission_pct) * 100).toFixed(1)}%` : null,
              deal.agent_commission_amount != null ? formatCurrency(Number(deal.agent_commission_amount)) : null,
            ].filter(Boolean).join(" · ")}
            note={deal.commission_payer ? `Paid by ${PAYER[deal.commission_payer] ?? deal.commission_payer.toLowerCase()}` : undefined}
          />
        )}

        {deal.clauses.length > 0 && (
          <Row
            label="Add-ons"
            value={<Disclosure id="deal-addons" open={addonsOpen} onToggle={() => setAddonsOpen((v) => !v)}>
              {deal.clauses.length} add-on{deal.clauses.length === 1 ? "" : "s"}
            </Disclosure>}
          />
        )}
        {addonsOpen && deal.clauses.length > 0 && (
          <ul id="deal-addons" className="space-y-2 border-t border-rule py-3 sm:col-span-2">
            {deal.clauses.map((c) => (
              <li key={c.id} className="flex items-center justify-between gap-3 rounded-lg bg-surface-inset px-3 py-2.5">
                <div className="min-w-0">
                  <p className="text-body font-semibold capitalize text-text-secondary">{c.clause_type.toLowerCase()}</p>
                  <p className="truncate text-caption text-text-muted">{c.trigger_description}</p>
                </div>
                <div className="shrink-0 text-right">
                  <p className="text-body font-semibold text-text">{formatCurrency(c.amount)}</p>
                  {c.cap != null && <p className="text-caption text-text-muted">cap {formatCurrency(c.cap)}</p>}
                </div>
                <span className={`shrink-0 rounded px-1.5 py-0.5 text-caption font-semibold ${
                  c.status === "PAID" ? "bg-success-bg text-success-text"
                    : c.status === "TRIGGERED" ? "bg-warning-bg text-warning-text"
                    : "bg-surface-inset text-text-secondary"
                }`}>{c.status === "PAID" ? "Paid" : c.status === "TRIGGERED" ? "Triggered" : "Pending"}</span>
              </li>
            ))}
          </ul>
        )}

        {terms && (
          <Row
            label="Player consent"
            value={terms.player_consent === "AGREED" ? <span className="text-success-text">Agreed</span>
              : terms.player_consent === "DECLINED" ? <span className="text-danger-text">Declined</span>
              : <span className="text-warning-text">Waiting</span>}
            note={<>
              {terms.player_consent === "AGREED" && terms.agreed_at && <span>{formatDate(terms.agreed_at)}</span>}
              {isBuyer && terms.consent_evidence_attachment_id && (
                <a
                  href={`${api.defaults.baseURL ?? ""}/deals/${deal.id}/attachments/${terms.consent_evidence_attachment_id}/download`}
                  onClick={openEvidence}
                  className="block font-semibold text-accent hover:underline"
                >
                  View signed copy
                </a>
              )}
            </>}
          />
        )}

        {(medical || canRecordMedical) && (
          <Row
            label="Medical"
            value={!medical ? <span className="text-text-muted">Not recorded yet</span>
              : medical.status === "PASSED" ? <span className="text-success-text">Passed</span>
              : medical.status === "FAILED" ? <span className="text-danger-text">Failed</span>
              : <span className="text-warning-text">In progress</span>}
            note={<>
              {medical && <span>{formatDate(medical.updated_at)}</span>}
              {medical?.notes && <span className="block">{medical.notes}</span>}
              {canRecordMedical && (
                <button type="button" onClick={onRecordMedical} className="block min-h-11 w-full text-right font-semibold text-accent hover:underline lg:min-h-0">
                  {!medical || medical.status === "PENDING" ? "Record result" : "Change"}
                </button>
              )}
            </>}
          />
        )}
      </div>
      <p className="mt-2 text-small text-text-muted">
        Agreed on the offer and fixed for this deal. To change them, collapse the deal and re-approach.
      </p>
    </section>
  );
}
