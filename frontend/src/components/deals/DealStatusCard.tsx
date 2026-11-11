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

const INPUT = "w-full min-h-12 lg:min-h-0 rounded-lg bg-surface px-3 py-2 text-[15px] text-text ring-1 ring-input-border focus:outline-none focus:ring-accent";

interface Props {
  view: DealStatusView;
  deal: Deal;
  viewerSide: "buyer" | "seller" | null;
  actions: DealActions;
  onOpenMessages: () => void;
  onShowSchedule: () => void;
  onRecordMedical: () => void;
}

/** Proposing the player's personal terms, inside the card (ADR 0001). */
function ProposeTermsForm({ actions, onCancel }: { actions: DealActions; onCancel: () => void }) {
  const [wage, setWage] = useState("");
  const [bonus, setBonus] = useState("");
  const [years, setYears] = useState("");
  return (
    <div className="mt-4 grid gap-3 border-t border-rule pt-4 sm:grid-cols-3">
      <div>
        <label htmlFor="pt-wage" className="mb-1 block text-sm font-medium text-text-secondary">Weekly wage (€)</label>
        <CurrencyInput id="pt-wage" value={wage} onChange={setWage} className={INPUT} />
      </div>
      <div>
        <label htmlFor="pt-bonus" className="mb-1 block text-sm font-medium text-text-secondary">Signing bonus (€)</label>
        <CurrencyInput id="pt-bonus" value={bonus} onChange={setBonus} className={INPUT} />
      </div>
      <div>
        <label htmlFor="pt-years" className="mb-1 block text-sm font-medium text-text-secondary">Contract length (years)</label>
        <input id="pt-years" type="number" min={1} max={10} value={years} onChange={(e) => setYears(e.target.value)} className={INPUT} />
      </div>
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
          })}
        >
          Send to player
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
      <label htmlFor="pt-signed" className="block text-sm font-medium text-text-secondary">
        Signed terms <span className="text-text-muted">(PDF or image, kept in your club&rsquo;s private deal-room channel)</span>
      </label>
      <input
        id="pt-signed"
        type="file"
        accept=".pdf,image/*"
        onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        className="mt-1.5 block w-full min-h-11 text-sm text-text-secondary file:mr-3 file:rounded-md file:border-0 file:bg-surface-inset file:px-3 file:py-2 file:text-sm file:font-semibold file:text-text"
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
export default function DealStatusCard({ view, deal, viewerSide, actions, onOpenMessages, onShowSchedule, onRecordMedical }: Props) {
  const confirm = useConfirm();
  const [showSteps, setShowSteps] = useState(false);
  const [inline, setInline] = useState<"propose-terms" | "record-consent" | null>(null);
  const P = deal.player?.name ?? "the player";
  const B = deal.buyer_club?.name ?? "the buying club";

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
      case "commission-respond":
        actions.commissionRespond.mutate(a.agreement);
        break;
      case "propose-terms":
        setInline((v) => (v === "propose-terms" ? null : "propose-terms"));
        break;
      case "record-consent":
        setInline((v) => (v === "record-consent" ? null : "record-consent"));
        break;
      case "player-consent":
        // From the buying club, declining collapses the deal: confirm first.
        // The agent answers straight away, as before.
        if (a.agreement === "DECLINED" && viewerSide === "buyer") {
          if (await confirm({
            title: "Record that the player declined?",
            message: "A declined proposal ends this transfer: the deal collapses and the committed budget is released.",
            confirmLabel: "Record and collapse",
            variant: "danger",
          })) actions.playerConsent.mutate("DECLINED");
        } else {
          actions.playerConsent.mutate(a.agreement);
        }
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
      case "player-consent": return actions.playerConsent.isPending;
      default: return false;
    }
  };

  function actionButton(a: StatusAction, primary: boolean) {
    const danger = "danger" in a && a.danger;
    const cls = `w-full ${danger ? "text-danger-text-alt" : ""}`;
    if (a.kind === "open-profile") {
      return (
        <Link to="/player/profile" className="inline-flex min-h-12 w-full items-center justify-center rounded-xl bg-accent px-5 py-2.5 text-sm font-semibold text-on-accent no-underline shadow-sm hover:bg-accent-hover">
          {a.label}
        </Link>
      );
    }
    const expanded = (a.kind === "propose-terms" || a.kind === "record-consent") ? inline === a.kind : undefined;
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
              className={`flex h-[22px] w-[22px] shrink-0 items-center justify-center rounded-full text-[13px] font-bold ${
                s.done ? "bg-success text-white" : isNext ? "ring-2 ring-accent" : "ring-1 ring-input-border"
              }`}
            >
              {s.done ? "✓" : ""}
            </span>
            <span className={`min-w-0 flex-1 text-[15px] ${isNext ? "font-semibold text-text" : "text-text-secondary"}`}>{s.label}</span>
            <span className="shrink-0 text-[13px] text-text-muted">{s.done ? "Done" : mine ? "Your move" : "Their move"}</span>
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
      body={view.body && <p className="mt-1.5 text-base leading-normal text-text-secondary">{view.body}</p>}
      actions={(view.primary || view.secondary) && (
        <>
          {view.primary && actionButton(view.primary, true)}
          {view.secondary && (
            // R-d: on a phone the tabs sit right below, so "Message …" beside a
            // main action is left to them.
            <div className={view.primary && view.secondary.kind === "open-messages" ? "hidden sm:block" : undefined}>
              {actionButton(view.secondary, false)}
            </div>
          )}
          {advanceError && <p role="alert" className="text-sm text-danger-text">{advanceError}</p>}
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
                  className="mt-2 min-h-11 w-full text-[15px] font-semibold text-accent"
                >
                  {showSteps ? "Hide the steps" : `Show the ${steps.length} paperwork steps`}
                </button>
                {showSteps && <div id="deal-status-steps" className="mt-2">{checklist}</div>}
              </div>
            </>
          )}

          {inline === "propose-terms" && <ProposeTermsForm actions={actions} onCancel={() => setInline(null)} />}
          {inline === "record-consent" && <RecordConsentForm deal={deal} actions={actions} onCancel={() => setInline(null)} />}

          {view.strips.map((s) => (
            <div key={s.title} role="note" className="mt-3 rounded-lg bg-warning-bg px-3 py-2.5 text-sm text-warning-text">
              <p className="font-semibold">{s.title}</p>
              <p>{s.body}</p>
            </div>
          ))}
        </>
      }
    >
      {checklist && <div className="hidden lg:block lg:w-[300px] lg:shrink-0">{checklist}</div>}
    </StatusCardShell>
  );
}
