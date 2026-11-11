import { useRef, useState } from "react";
import type { Offer } from "../../types/api";
import type { ImproveBody, OfferActions } from "../../hooks/useOfferActions";
import Button from "../ui/Button";
import CurrencyInput from "../ui/CurrencyInput";
import Sheet from "../ui/Sheet";
import { useConfirm } from "../../context/ConfirmContext";
import { useToast } from "../../context/ToastContext";
import { isLoan, offerHeadline } from "../../lib/offerTerms";
import { formatCurrency, getApiError } from "../../lib/utils";
import { cap } from "./offerStatus";

const LABEL = "mb-1 block text-body font-semibold text-text";
const INPUT = "w-full min-h-12 lg:min-h-10 rounded-lg bg-surface px-3 py-2 text-body text-text placeholder-text-muted ring-1 ring-input-border focus:outline-none focus:ring-accent";
const BIG = "w-full min-h-14 lg:min-h-12 rounded-lg bg-surface px-3 py-2 text-headline sm:text-title font-bold text-text ring-2 ring-accent focus:outline-none";

/**
 * The buyer raising their own pending offer while they wait (offer-room-focus
 * §5.7, D6): POST /offers/:id/improve, which already existed with no screen.
 * It reserves more of the transfer budget, so it is confirmed first. It does
 * not hand the turn back: the seller still answers.
 */
export default function RaiseOfferForm({ offer, other, layout, improve, onDone, formId }: {
  offer: Offer;
  other: string;
  layout: "sheet" | "inline";
  improve: OfferActions["improve"];
  onDone: (sent: boolean) => void;
  formId: string;
}) {
  const confirm = useConfirm();
  const { addToast } = useToast();
  const loan = isLoan(offer);
  const current = Number((loan ? offer.loan_fee : offer.fee_amount) ?? 0);
  const currentWage = offer.wage_weekly != null ? Number(offer.wage_weekly) : null;
  const [amount, setAmount] = useState(String(current || ""));
  const [wage, setWage] = useState(currentWage != null ? String(currentWage) : "");
  const [error, setError] = useState<string | null>(null);
  const opening = useRef(JSON.stringify([amount, wage]));
  const dirty = JSON.stringify([amount, wage]) !== opening.current;

  async function close() {
    if (dirty && !(await confirm({ title: "Discard this raise?", message: "Your offer stays as it is.", confirmLabel: "Discard", variant: "danger" }))) return;
    onDone(false);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const next = parseFloat(amount);
    const nextWage = parseFloat(wage);
    const body: ImproveBody = {};
    if (!isNaN(next) && next !== current) {
      if (loan) body.loan_fee = next; else body.fee_amount = next;
    }
    if (!loan && wage && !isNaN(nextWage) && nextWage !== currentWage) body.wage_weekly = nextWage;
    // Only upward: the server refuses anything that lowers the offer, too.
    if (isNaN(next) || next < current || (body.fee_amount == null && body.loan_fee == null && body.wage_weekly == null)) {
      setError(`Your new offer must be higher than ${offerHeadline(offer)}.`);
      return;
    }
    const delta = isNaN(next) ? 0 : next - current;
    const ok = await confirm({
      title: "Raise your offer?",
      message: `${cap(other)} is told straight away.` +
        (delta > 0 ? ` The extra ${formatCurrency(delta)} is reserved from your transfer budget.` : ""),
      confirmLabel: "Raise offer",
    });
    if (!ok) return;
    improve.mutate(body, {
      onSuccess: () => {
        addToast(`Offer raised. ${cap(other)} has been told.`, "success");
        onDone(true);
      },
      onError: (err: unknown) => setError(getApiError(err, "Failed to raise your offer.")),
    });
  }

  const form = (
    <form id={formId} onSubmit={handleSubmit} noValidate className="space-y-4">
      <div>
        <label htmlFor={`${formId}-amount`} className={LABEL}>{loan ? "New loan fee" : "New fee"}</label>
        <CurrencyInput id={`${formId}-amount`} data-autofocus value={amount} onChange={setAmount} className={BIG} />
        <p className="mt-1 text-small text-text-muted">Now {offerHeadline(offer)}.</p>
      </div>
      {!loan && (
        <div className="max-w-xs">
          <label htmlFor={`${formId}-wage`} className={LABEL}>Wage a week <span className="font-normal text-text-muted">(optional)</span></label>
          <CurrencyInput id={`${formId}-wage`} value={wage} onChange={setWage} className={INPUT} />
        </div>
      )}
      {error && <p role="alert" className="text-body text-danger-text">{error}</p>}
    </form>
  );

  const send = (
    <Button type="submit" form={formId} variant="primary" size="lg" loading={improve.isPending} className={layout === "sheet" ? "w-full" : ""}>
      Raise offer
    </Button>
  );
  const title = `Raise your offer to ${other}`;

  if (layout === "sheet") {
    return <Sheet open onClose={close} title={title} footer={send}>{form}</Sheet>;
  }
  return (
    <>
      <h2 id="offer-status-headline" tabIndex={-1} className="text-headline font-bold text-text focus:outline-none">{title}</h2>
      <div className="mt-4 max-w-xl">{form}</div>
      <div className="mt-4 flex items-center gap-3 border-t border-rule pt-3.5">
        {send}
        <Button type="button" variant="secondary" size="lg" onClick={close}>Cancel</Button>
      </div>
    </>
  );
}
