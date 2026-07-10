import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "../../lib/api";
import type { Bid, Club, PendingApprovalCaptured, Sale } from "../../types/api";
import Button from "../ui/Button";
import CurrencyInput from "../ui/CurrencyInput";
import Metric from "../ui/Metric";
import { formatCurrency, getApiError } from "../../lib/utils";
import { useToast } from "../../context/ToastContext";

interface BidFormProps {
  sale: Sale;
  /** The buyer's own existing active bid, if any (used to show "Replace" UI). */
  existingBid?: Bid;
}

export default function BidForm({ sale, existingBid }: BidFormProps) {
  const queryClient = useQueryClient();
  const { addToast } = useToast();

  const [amount, setAmount] = useState(
    existingBid ? String(Math.round(existingBid.amount)) : ""
  );
  const [notes, setNotes] = useState(existingBid?.notes ?? "");
  const [fieldError, setFieldError] = useState<string | null>(null);

  // Fetch own club finance for budget display
  const { data: club } = useQuery<Club>({
    queryKey: ["clubs", "me"],
    queryFn: () => api.get<Club>("/clubs/me").then((r) => r.data),
    staleTime: 60_000,
  });

  const minBid = sale.minimum_next_bid ?? sale.min_increment;

  const [pendingApproval, setPendingApproval] = useState(false);

  const mutation = useMutation({
    mutationFn: (body: { amount: number; notes?: string }) =>
      api
        .post<Bid | PendingApprovalCaptured>(`/sales/${sale.id}/bids`, {
          amount: body.amount,
          ...(body.notes && { notes: body.notes }),
        })
        .then((r) => r.data),
    onSuccess: (data) => {
      // Phase 5 (D7): a 202 means the bid was captured for approval, not placed.
      if ("approval_id" in data) {
        setPendingApproval(true);
        addToast("Bid sent for approval — an approver at your club must sign it off.", "info");
        queryClient.invalidateQueries({ queryKey: ["clubs", "me", "approvals"] });
        return;
      }
      queryClient.invalidateQueries({ queryKey: ["sales", sale.id] });
      queryClient.invalidateQueries({ queryKey: ["sales", sale.id, "bids"] });
      addToast(existingBid ? "Bid updated." : "Bid placed successfully.", "success");
      if (!existingBid) {
        setAmount("");
        setNotes("");
      }
    },
    onError: (err) => addToast(getApiError(err, "Failed to place bid."), "error"),
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setFieldError(null);

    const parsed = parseFloat(amount.replace(/,/g, ""));
    if (isNaN(parsed) || parsed <= 0) {
      setFieldError("Enter a valid bid amount.");
      return;
    }
    if (parsed < minBid) {
      setFieldError(`Minimum bid is ${formatCurrency(minBid)}.`);
      return;
    }

    const budget = club?.finance?.transfer_remaining;
    if (budget !== undefined && budget !== null && parsed > budget) {
      setFieldError(`Insufficient budget. You have ${formatCurrency(budget)} remaining.`);
      return;
    }

    mutation.mutate({ amount: parsed, notes: notes || undefined });
  }

  const serverError = mutation.isError ? getApiError(mutation.error, "Failed to place bid.") : null;

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <p className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-3">
        {existingBid ? "Replace Your Bid" : "Place a Bid"}
      </p>

      {/* Budget context */}
      {club?.finance && (
        <div className="rounded-lg bg-slate-800/60 px-4 py-3 space-y-1.5">
          <Metric
            label="Transfer budget remaining"
            value={formatCurrency(club.finance.transfer_remaining)}
          />
          <Metric
            label="Minimum bid"
            value={formatCurrency(minBid)}
          />
          {existingBid && (
            <Metric
              label="Your current bid"
              value={formatCurrency(existingBid.amount)}
            />
          )}
        </div>
      )}

      {/* Amount input */}
      <div>
        <label htmlFor="bid-amount" className="mb-1.5 block text-sm font-medium text-slate-300">
          Bid amount (£)
        </label>
        <CurrencyInput
          id="bid-amount"
          required
          value={amount}
          onChange={(raw) => { setAmount(raw); setFieldError(null); }}
          placeholder={minBid.toLocaleString("en-GB")}
          className="w-full rounded-lg bg-slate-800 px-3 py-2.5 text-sm text-white placeholder-slate-500 ring-1 ring-white/10 focus:outline-none focus:ring-emerald-500 transition-colors"
        />
      </div>

      {/* Notes */}
      <div>
        <label htmlFor="bid-notes" className="mb-1.5 block text-sm font-medium text-slate-300">
          Notes <span className="text-slate-500">(optional)</span>
        </label>
        <input
          id="bid-notes"
          type="text"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="Any message for the seller…"
          className="w-full rounded-lg bg-slate-800 px-3 py-2.5 text-sm text-white placeholder-slate-500 ring-1 ring-white/10 focus:outline-none focus:ring-emerald-500 transition-colors"
        />
      </div>

      {/* Errors */}
      {(fieldError || serverError) && (
        <p className="text-sm text-red-400">{fieldError ?? serverError}</p>
      )}

      {/* Success / pending approval */}
      {pendingApproval ? (
        <p className="text-sm text-amber-400">
          Pending approval — this bid is waiting for sign-off from your club's owner
          or sporting director. Track it on the Approvals page.
        </p>
      ) : (
        mutation.isSuccess && (
          <p className="text-sm text-emerald-400">
            {existingBid ? "Bid updated successfully." : "Bid placed successfully."}
          </p>
        )
      )}

      <Button
        type="submit"
        variant="primary"
        size="md"
        loading={mutation.isPending}
        className="w-full"
      >
        {existingBid ? "Replace bid" : "Place bid"}
      </Button>
    </form>
  );
}
