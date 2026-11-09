import type { ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import type { Offer } from "../../types/api";
import type { OfferActions } from "../../hooks/useOfferActions";
import Button from "../ui/Button";
import StatusCardShell, { StatusCardFrame } from "../transfer/StatusCardShell";
import { useConfirm } from "../../context/ConfirmContext";
import { isLoan } from "../../lib/offerTerms";
import { getApiError } from "../../lib/utils";
import { acceptMessage, type OfferAction, type OfferStatusView } from "./offerStatus";

export const OFFER_HEADLINE_ID = "offer-status-headline";

/** Focus the status card's headline once the page has re-rendered after an action. */
export function focusOfferHeadline() {
  requestAnimationFrame(() => document.getElementById(OFFER_HEADLINE_ID)?.focus());
}

/**
 * The offer page's answer (offer-room-focus §5.5): whose move it is, what
 * they just changed and what you can do about it. Accept, Counter and Reject
 * keep their confirmations. From 1024px a counter or a raise replaces the
 * card's content (`editing`).
 */
export default function OfferStatusCard({
  view, offer, actions, desktop, editing, onCounter, onRaise, onOpenMessages, onShowAllChanges,
}: {
  view: OfferStatusView;
  /** From 1024px the changes are the card's middle column; below, under the body. */
  desktop: boolean;
  offer: Offer;
  actions: OfferActions;
  editing?: ReactNode;
  onCounter: () => void;
  onRaise: () => void;
  onOpenMessages: () => void;
  onShowAllChanges: () => void;
}) {
  const confirm = useConfirm();
  const navigate = useNavigate();

  if (editing) {
    return <StatusCardFrame labelledBy={OFFER_HEADLINE_ID} ring="ring-2 ring-accent">{editing}</StatusCardFrame>;
  }

  async function run(a: OfferAction) {
    switch (a.kind) {
      case "accept":
        if (await confirm({ title: isLoan(offer) ? "Accept loan" : "Accept offer", message: acceptMessage(offer), confirmLabel: "Accept" })) {
          actions.accept.mutate();
        }
        break;
      case "reject":
        if (await confirm({ message: "Reject this offer?", confirmLabel: "Reject", variant: "danger" })) {
          actions.reject.mutate(undefined, { onSuccess: () => focusOfferHeadline() });
        }
        break;
      case "counter": onCounter(); break;
      case "raise": onRaise(); break;
      case "open-messages": onOpenMessages(); break;
      case "view-deal": if (offer.deal) navigate(`/deals/${offer.deal.id}`); break;
      case "view-approvals": navigate("/club/approvals"); break;
    }
  }

  const shown = view.changes.slice(0, 4);
  const more = view.changes.length - shown.length;
  const changes = view.changes.length > 0 && (
    <ul aria-label="What they changed" className="lg:w-[320px] lg:shrink-0">
      {shown.map((c) => (
        <li key={c.label} className="flex justify-between gap-2.5 border-t border-rule py-2 text-sm lg:border-t-0 lg:py-1.5">
          <span className="text-text-secondary">{c.label}</span>
          <span className="text-right">
            <s className="text-text-muted">{c.was}</s> <span aria-hidden>→</span>
            <span className="sr-only">changed to</span> <strong className="text-text">{c.now}</strong>
          </span>
        </li>
      ))}
      {more > 0 && (
        <li className="border-t border-rule lg:border-t-0">
          <button type="button" onClick={onShowAllChanges} className="min-h-11 text-sm font-semibold text-accent lg:min-h-8">
            and {more} more change{more === 1 ? "" : "s"}
          </button>
        </li>
      )}
    </ul>
  );

  const mutError = actions.accept.isError ? getApiError(actions.accept.error, "Failed.")
    : actions.reject.isError ? getApiError(actions.reject.error, "Failed.")
    : actions.withdraw.isError ? getApiError(actions.withdraw.error, "Failed.")
    : null;

  const highlight = view.primary?.kind === "accept" && view.primary.highlight;
  const button = (a: OfferAction, variant: "primary" | "secondary") => (
    <Button
      variant={variant}
      size="lg"
      className={`w-full lg:min-h-11 ${a.kind === "accept" && highlight ? "ring-2 ring-accent ring-offset-2" : ""}`}
      loading={a.kind === "accept" ? actions.accept.isPending : false}
      onClick={() => run(a)}
    >
      {a.label}
    </Button>
  );

  const hasActions = view.primary || view.secondary || view.tertiary;
  const actionsNode = hasActions && (
    <>
      {highlight && <p className="text-sm font-semibold text-accent">From your notification: accept this offer?</p>}
      <div className={`grid gap-2 ${view.primary && view.secondary ? "grid-cols-2 sm:grid-cols-1" : "grid-cols-1"}`}>
        {view.primary && button(view.primary, "primary")}
        {view.secondary && button(view.secondary, "secondary")}
      </div>
      {view.tertiary && (
        <button
          type="button"
          disabled={actions.reject.isPending}
          onClick={() => run(view.tertiary!)}
          className="min-h-11 w-full text-[15px] font-semibold text-danger-text-alt hover:underline disabled:opacity-50 lg:min-h-8 lg:text-sm"
        >
          {view.tertiary.label}
        </button>
      )}
      {mutError && <p role="alert" className="text-sm text-danger-text">{mutError}</p>}
    </>
  );

  return (
    <StatusCardShell
      tone={view.tone}
      overline={view.overline}
      overlineClassName={view.urgent ? "text-danger-text" : undefined}
      meta={view.meta}
      headline={view.headline}
      headlineId={OFFER_HEADLINE_ID}
      body={
        <>
          {view.body && <p className="mt-1.5 text-base leading-normal text-text-secondary">{view.body}</p>}
          {changes && !desktop && <div className="mt-3">{changes}</div>}
        </>
      }
      actions={actionsNode || undefined}
    >
      {changes && desktop ? changes : null}
    </StatusCardShell>
  );
}
