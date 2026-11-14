import { useState } from "react";
import { Link } from "react-router-dom";
import type { Deal } from "../../types/api";
import Button from "../ui/Button";
import CurrencyInput from "../ui/CurrencyInput";
import { useConfirm } from "../../context/ConfirmContext";
import type { DealActions } from "../../hooks/useDealActions";
import { formatCurrency, getApiError } from "../../lib/utils";
import StatusCardShell from "../transfer/StatusCardShell";
import type { DealStatusView, StatusAction } from "./dealStatus";
import EndTransferDialog from "./EndTransferDialog";
import TermRounds from "./TermRounds";

const INPUT = "w-full min-h-12 lg:min-h-0 rounded-lg bg-surface px-3 py-2 text-body text-text ring-1 ring-input-border focus:outline-none focus:ring-accent";

interface Props {
  view: DealStatusView;
  deal: Deal;
  viewerSide: "buyer" | "seller" | null;
  actions: DealActions;
  onOpenMessages: () => void;
  onShowSchedule: () => void;
  onRecordMedical: () => void;
  /** Chasing whoever holds the move (MoveReminder), shown under the card's actions. */
  reminder?: React.ReactNode;
}

const NOTE_MAX = 200;

function NoteField({ id, value, onChange }: { id: string; value: string; onChange: (v: string) => void }) {
  return (
    <div className="sm:col-span-3">
      <label htmlFor={id} className="mb-1 block text-small font-medium text-text-secondary">Note to the other side <span className="text-text-muted">(optional)</span></label>
      <input id={id} value={value} maxLength={NOTE_MAX} onChange={(e) => onChange(e.target.value)} className={INPUT} />
    </div>
  );
}

/** Proposing the player's personal terms, or countering them, inside the card (ADRs 0001, 0012). */
function ProposeTermsForm({ actions, onCancel, initial, submitLabel }: {
  actions: DealActions; onCancel: () => void;
  /** The terms on the table, when countering them. */
  initial?: { wage: number | null; bonus: number | null; years: number | null };
  submitLabel: string;
}) {
  const [wage, setWage] = useState(initial?.wage != null ? String(Math.round(initial.wage)) : "");
  const [bonus, setBonus] = useState(initial?.bonus ? String(Math.round(initial.bonus)) : "");
  const [years, setYears] = useState(initial?.years != null ? String(initial.years) : "");
  const [note, setNote] = useState("");
  return (
    <div className="mt-4 grid gap-3 border-t border-rule pt-4 sm:grid-cols-3">
      <div>
        <label htmlFor="pt-wage" className="mb-1 block text-small font-medium text-text-secondary">Weekly wage (£)</label>
        <CurrencyInput id="pt-wage" value={wage} onChange={setWage} className={INPUT} />
      </div>
      <div>
        <label htmlFor="pt-bonus" className="mb-1 block text-small font-medium text-text-secondary">Signing bonus (£)</label>
        <CurrencyInput id="pt-bonus" value={bonus} onChange={setBonus} className={INPUT} />
      </div>
      <div>
        <label htmlFor="pt-years" className="mb-1 block text-small font-medium text-text-secondary">Contract length (years)</label>
        <input id="pt-years" type="number" min={1} max={10} value={years} onChange={(e) => setYears(e.target.value)} className={INPUT} />
      </div>
      {initial && <NoteField id="pt-note" value={note} onChange={setNote} />}
      <div className="flex flex-wrap gap-2 sm:col-span-3">
        <Button
          variant="primary"
          size="lg"
          loading={actions.setPersonalTerms.isPending}
          disabled={wage === "" || years === ""}
          onClick={() => actions.setPersonalTerms.mutate({
            wage_weekly: wage !== "" ? Number(wage) : null,
            signing_bonus: bonus !== "" ? Number(bonus) : null,
            length_years: years !== "" ? Number(years) : null,
            note: note.trim() || null,
          })}
        >
          {submitLabel}
        </Button>
        <Button variant="ghost" size="lg" onClick={onCancel}>Cancel</Button>
      </div>
    </div>
  );
}

/** The buying club's counter to the agent's commission (ADR 0012). */
function CommissionCounterForm({ actions, onCancel, initialPayer }: {
  actions: DealActions; onCancel: () => void; initialPayer: "BUYER" | "SELLER" | "PLAYER";
}) {
  const [pct, setPct] = useState("");
  const [payer, setPayer] = useState(initialPayer);
  const [note, setNote] = useState("");
  const value = Number(pct);
  const valid = pct !== "" && value >= 0 && value < 100;
  return (
    <div className="mt-4 grid gap-3 border-t border-rule pt-4 sm:grid-cols-3">
      <div>
        <label htmlFor="cc-pct" className="mb-1 block text-small font-medium text-text-secondary">Commission (% of the fee)</label>
        <input id="cc-pct" type="number" min={0} max={99} step={0.5} value={pct} onChange={(e) => setPct(e.target.value)} className={INPUT} />
      </div>
      <div>
        <label htmlFor="cc-payer" className="mb-1 block text-small font-medium text-text-secondary">Paid by</label>
        <select id="cc-payer" value={payer} onChange={(e) => setPayer(e.target.value as typeof payer)} className={INPUT}>
          <option value="BUYER">The buying club</option>
          <option value="SELLER">The selling club</option>
          <option value="PLAYER">The player</option>
        </select>
      </div>
      <NoteField id="cc-note" value={note} onChange={setNote} />
      <div className="flex flex-wrap gap-2 sm:col-span-3">
        <Button
          variant="primary"
          size="lg"
          loading={actions.commissionCounter.isPending}
          disabled={!valid}
          onClick={() => actions.commissionCounter.mutate({ commission_pct: value / 100, commission_payer: payer, note: note.trim() || null })}
        >
          Send counter
        </Button>
        <Button variant="ghost" size="lg" onClick={onCancel}>Cancel</Button>
      </div>
    </div>
  );
}

/** The signed terms behind "He agreed" (ADR 0006), revealed by that button. */
function RecordConsentForm({ deal, actions, onCancel }: { deal: Deal; actions: DealActions; onCancel: () => void }) {
  const confirm = useConfirm();
  const [file, setFile] = useState<File | null>(null);
  return (
    <div className="mt-4 border-t border-rule pt-4">
      <label htmlFor="pt-signed" className="block text-small font-medium text-text-secondary">
        Signed terms <span className="text-text-muted">(PDF or image, kept in your club&rsquo;s private deal-room channel)</span>
      </label>
      <input
        id="pt-signed"
        type="file"
        accept=".pdf,image/*"
        onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        className="mt-1.5 block w-full min-h-11 text-input lg:text-body text-text-secondary file:mr-3 file:rounded-md file:border-0 file:bg-surface-inset file:px-3 file:py-2 file:text-small file:font-semibold file:text-text"
      />
      <div className="mt-3 flex flex-wrap gap-2">
        <Button
          variant="primary"
          size="lg"
          disabled={!file}
          loading={actions.recordAgreement.isPending}
          onClick={async () => {
            if (!file) return;
            const ok = await confirm({
              title: "Record that the player agreed?",
              message: `Confirm that ${deal.player?.name ?? "the player"} has signed these terms (${file.name}). This is recorded as ${deal.buyer_club?.name ?? "your club"}'s confirmation, with the signed copy, and ${deal.seller_club?.name ?? "the selling club"} is notified.`,
              confirmLabel: "Record agreement",
            });
            if (ok) actions.recordAgreement.mutate(file);
          }}
        >
          Record agreement
        </Button>
        <Button variant="ghost" size="lg" onClick={onCancel}>Cancel</Button>
      </div>
    </div>
  );
}

/**
 * The one place the deal room says what happens next and who does it
 * (deal-room-focus §5.3). It replaces the "Blocked on" header, the lanes,
 * the stage banners, the paperwork block and the Actions card.
 */
type Inline = "propose-terms" | "record-consent" | "commission-counter" | "counter-terms";
type Ending = Extract<StatusAction, { kind: "commission-respond" | "terms-respond" | "player-consent" }>;

export default function DealStatusCard({ view, deal, viewerSide, actions, onOpenMessages, onShowSchedule, onRecordMedical, reminder }: Props) {
  const confirm = useConfirm();
  const [showSteps, setShowSteps] = useState(false);
  const [inline, setInline] = useState<Inline | null>(null);
  const [ending, setEnding] = useState<Ending | null>(null);
  const P = deal.player?.name ?? "the player";
  const B = deal.buyer_club?.name ?? "the buying club";
  const S = deal.seller_club_id ? deal.seller_club?.name ?? "the selling club" : null;
  const A = deal.agent?.display_name ?? "the agent";
  const toggle = (k: Inline) => setInline((v) => (v === k ? null : k));

  async function run(a: StatusAction) {
    switch (a.kind) {
      case "advance":
        actions.advance.mutate();
        break;
      case "complete":
        if (await confirm({
          title: "Complete the transfer?",
          message: `This registers ${P} at ${B} for ${formatCurrency(Number(deal.agreed_fee ?? 0))}. It can't be undone.`,
          confirmLabel: "Complete transfer",
        })) actions.advance.mutate();
        break;
      case "paperwork":
        if (a.step === "sign-agreement") {
          if (await confirm({
            title: "Sign the transfer agreement",
            message: "Confirm that your club has signed the transfer agreement for this deal. The other club is told.",
            confirmLabel: "Confirm signed",
          })) actions.paperwork.mutate("sign-agreement");
        } else if (await confirm({
          title: "Registration submitted",
          message: "Confirm that the registration has been submitted to the league (and international clearance requested, if needed).",
          confirmLabel: "Confirm submitted",
        })) actions.paperwork.mutate("submit-registration");
        break;
      case "record-medical":
        onRecordMedical();
        break;
      // Any answer that ends the transfer is confirmed first (EndTransferDialog).
      case "commission-respond":
      case "terms-respond":
      case "player-consent":
        if (a.agreement === "DECLINED") setEnding(a);
        else if (a.kind === "commission-respond") actions.commissionRespond.mutate({ agreement: "AGREED" });
        else if (a.kind === "terms-respond") actions.termsRespond.mutate({ agreement: "AGREED" });
        else actions.playerConsent.mutate({ agreement: "AGREED" });
        break;
      case "commission-counter": case "counter-terms": case "propose-terms": case "record-consent":
        toggle(a.kind);
        break;
      case "agent-accept":
        actions.agentAccept.mutate();
        break;
      case "open-messages":
        onOpenMessages();
        break;
      case "show-schedule":
        onShowSchedule();
        break;
      case "open-profile":
        break;
    }
  }

  const pending = (a: StatusAction): boolean => {
    switch (a.kind) {
      case "advance": case "complete": return actions.advance.isPending;
      case "paperwork": return actions.paperwork.isPending;
      case "commission-respond": return actions.commissionRespond.isPending;
      case "terms-respond": return actions.termsRespond.isPending;
      case "agent-accept": return actions.agentAccept.isPending;
      case "player-consent": return actions.playerConsent.isPending;
      default: return false;
    }
  };

  function actionButton(a: StatusAction, primary: boolean) {
    const danger = "danger" in a && a.danger;
    const cls = `w-full ${danger ? "text-danger-text-alt" : ""}`;
    if (a.kind === "open-profile") {
      return (
        <Link to="/player/profile" className="inline-flex min-h-12 w-full items-center justify-center rounded-xl bg-accent px-5 py-2.5 text-body font-semibold text-on-accent no-underline shadow-sm hover:bg-accent-hover">
          {a.label}
        </Link>
      );
    }
    const expanded = (a.kind === "propose-terms" || a.kind === "record-consent" || a.kind === "commission-counter" || a.kind === "counter-terms")
      ? inline === a.kind : undefined;
    return (
      <Button
        variant={primary ? "primary" : "secondary"}
        size="lg"
        className={cls}
        loading={pending(a)}
        aria-expanded={expanded}
        onClick={() => run(a)}
      >
        {a.label}
      </Button>
    );
  }

  /** The confirmation for whichever transfer-ending answer was chosen. */
  function endDialog() {
    const e = ending!;
    const close = () => setEnding(null);
    const and = (...xs: (string | null)[]) => xs.filter(Boolean).join(" and ");
    const recording = e.kind === "player-consent" && viewerSide === "buyer";
    const text = e.kind === "commission-respond"
      ? { title: "Decline the agent's commission?", who: and(A, S), counter: "commission-counter" as const }
      : e.kind === "terms-respond"
        ? { title: `Decline ${P}'s terms?`, who: and(deal.personal_terms?.agent_id ? A : P, S), counter: "counter-terms" as const }
        : recording
          ? { title: `Record that ${P} declined?`, who: S ?? "Nobody else", counter: undefined }
          : { title: `Decline the terms for ${P}?`, who: and(B, S), counter: "counter-terms" as const };
    const mutation = e.kind === "commission-respond" ? actions.commissionRespond
      : e.kind === "terms-respond" ? actions.termsRespond : actions.playerConsent;
    return (
      <EndTransferDialog
        open
        title={text.title}
        who={text.who}
        confirmLabel={recording ? "Record and end the transfer" : "Decline and end the transfer"}
        loading={mutation.isPending}
        onConfirm={(reason) => mutation.mutate({ agreement: "DECLINED", reason }, { onSettled: close })}
        onCounter={text.counter ? () => setInline(text.counter) : undefined}
        onClose={close}
      />
    );
  }

  const steps = deal.paperwork ?? [];
  const nextMine = steps.find((s) => !s.done && s.owner === viewerSide);
  const checklist = view.showChecklist && steps.length > 0 && (
    <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-1">
      {steps.map((s) => {
        const mine = s.owner === viewerSide;
        const isNext = nextMine?.key === s.key;
        return (
          <li key={s.key} className="flex items-center gap-2.5">
            <span
              aria-hidden
              className={`flex h-[22px] w-[22px] shrink-0 items-center justify-center rounded-full text-caption font-bold ${
                s.done ? "bg-success text-white" : isNext ? "ring-2 ring-accent" : "ring-1 ring-input-border"
              }`}
            >
              {s.done ? "✓" : ""}
            </span>
            <span className={`min-w-0 flex-1 text-body ${isNext ? "font-semibold text-text" : "text-text-secondary"}`}>{s.label}</span>
            <span className="shrink-0 text-small text-text-muted">{s.done ? "Done" : mine ? "Your move" : "Their move"}</span>
          </li>
        );
      })}
    </ul>
  );
  const advanceError = actions.advance.isError ? getApiError(actions.advance.error, "Failed.") : null;

  return (
    <StatusCardShell
      tone={view.tone}
      overline={view.overline}
      meta={view.meta}
      headline={view.headline}
      headlineId="deal-status-headline"
      body={view.body && <p className="mt-1.5 text-body leading-normal text-text-secondary">{view.body}</p>}
      actions={(view.primary || view.secondary || view.tertiary) && (
        <>
          {view.primary && actionButton(view.primary, true)}
          {view.secondary && (
            // R-d: on a phone the tabs sit right below, so "Message …" beside a
            // main action is left to them.
            <div className={view.primary && view.secondary.kind === "open-messages" ? "hidden sm:block" : undefined}>
              {actionButton(view.secondary, false)}
            </div>
          )}
          {view.tertiary && (
            <button
              type="button"
              onClick={() => run(view.tertiary!)}
              className="min-h-11 w-full text-body font-semibold text-danger-text-alt hover:underline lg:min-h-0"
            >
              {view.tertiary.label}
            </button>
          )}
          {advanceError && <p role="alert" className="text-body text-danger-text">{advanceError}</p>}
        </>
      )}
      footer={
        <>
          {checklist && (
            <>
              <div className="hidden border-t border-rule pt-3 mt-4 sm:block lg:hidden">{checklist}</div>
              <div className="sm:hidden">
                <button
                  type="button"
                  aria-expanded={showSteps}
                  aria-controls="deal-status-steps"
                  onClick={() => setShowSteps((v) => !v)}
                  className="mt-2 min-h-11 w-full text-body font-semibold text-accent"
                >
                  {showSteps ? "Hide the steps" : `Show the ${steps.length} paperwork steps`}
                </button>
                {showSteps && <div id="deal-status-steps" className="mt-2">{checklist}</div>}
              </div>
            </>
          )}

          {inline === "propose-terms" && (
            <ProposeTermsForm actions={actions} onCancel={() => setInline(null)}
              submitLabel={viewerSide === "buyer" ? "Send to player" : `Send to ${B}`} />
          )}
          {inline === "counter-terms" && deal.personal_terms && (
            <ProposeTermsForm actions={actions} onCancel={() => setInline(null)} submitLabel="Send counter"
              initial={{ wage: deal.personal_terms.wage_weekly, bonus: deal.personal_terms.signing_bonus, years: deal.personal_terms.length_years }} />
          )}
          {inline === "commission-counter" && (
            <CommissionCounterForm actions={actions} onCancel={() => setInline(null)} initialPayer="BUYER" />
          )}
          <TermRounds deal={deal} />
          {inline === "record-consent" && <RecordConsentForm deal={deal} actions={actions} onCancel={() => setInline(null)} />}

          {view.strips.map((s) => (
            <div key={s.title} role="note" className="mt-3 rounded-lg bg-warning-bg px-3 py-2.5 text-small text-warning-text">
              <p className="font-semibold">{s.title}</p>
              <p>{s.body}</p>
            </div>
          ))}
          {reminder && <div className="mt-4 border-t border-rule pt-3">{reminder}</div>}
        </>
      }
    >
      {checklist && <div className="hidden lg:block lg:w-[300px] lg:shrink-0">{checklist}</div>}
      {ending && endDialog()}
    </StatusCardShell>
  );
}
