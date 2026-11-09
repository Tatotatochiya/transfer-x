import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import api from "../lib/api";
import { getApiError } from "../lib/utils";
import { useToast } from "../context/ToastContext";
import type { DealStub, Offer } from "../types/api";

export interface ImproveBody {
  fee_amount?: number;
  wage_weekly?: number;
  loan_fee?: number;
}

/**
 * Every action on an offer (offer-room-focus §5.12), moved out of the page
 * with the same endpoints, invalidations, toasts and navigation. Each one
 * also refreshes the Lite offer card the page reads its deadline and
 * valuation from. `improve` is new: the buyer raising a pending offer (D6).
 */
export function useOfferActions(offer: Offer | undefined) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const { addToast } = useToast();
  const id = offer?.id;

  const invalidateLite = () => queryClient.invalidateQueries({ queryKey: ["lite", "offer-card", id] });
  const invalidateBook = () => {
    queryClient.invalidateQueries({ queryKey: ["offers", "competition", offer?.player_id] });
    if (offer?.sale_id) queryClient.invalidateQueries({ queryKey: ["sales", offer.sale_id, "order-book"] });
  };

  const accept = useMutation({
    mutationFn: () => api.post<DealStub>(`/offers/${id}/accept`).then((r) => r.data),
    onSuccess: (deal) => {
      queryClient.invalidateQueries({ queryKey: ["offers"] });
      queryClient.invalidateQueries({ queryKey: ["deals"] });
      invalidateBook();
      invalidateLite();
      // Phase 5 (D7): 202 means the acceptance was captured for approval.
      if ("approval_id" in (deal as object)) {
        addToast("Acceptance sent for approval — an approver at your club must sign it off.", "info");
        queryClient.invalidateQueries({ queryKey: ["offers", id] });
        queryClient.invalidateQueries({ queryKey: ["clubs", "me", "approvals"] });
        return;
      }
      addToast("Offer accepted — deal created!", "success");
      navigate(`/deals/${deal.id}`);
    },
    onError: (err) => addToast(getApiError(err, "Failed to accept offer."), "error"),
  });

  const reject = useMutation({
    mutationFn: () => api.post<Offer>(`/offers/${id}/reject`).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["offers", id] });
      queryClient.invalidateQueries({ queryKey: ["offers", "received"] });
      invalidateBook();
      invalidateLite();
      addToast("Offer rejected.", "info");
    },
    onError: (err) => addToast(getApiError(err, "Failed to reject offer."), "error"),
  });

  const withdraw = useMutation({
    mutationFn: () => api.post<Offer>(`/offers/${id}/withdraw`).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["offers", id] });
      queryClient.invalidateQueries({ queryKey: ["offers", "sent"] });
      invalidateBook();
      invalidateLite();
      addToast("Offer withdrawn.", "info");
    },
    onError: (err) => addToast(getApiError(err, "Failed to withdraw offer."), "error"),
  });

  // Counter and raise: the form shows the error itself, so no toast.
  const afterTermsChange = () => {
    queryClient.invalidateQueries({ queryKey: ["offers", id] });
    queryClient.invalidateQueries({ queryKey: ["offers", "received"] });
    queryClient.invalidateQueries({ queryKey: ["offers", "sent"] });
    queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    invalidateBook();
    invalidateLite();
  };

  const counter = useMutation({
    mutationFn: (body: object) => api.post<Offer>(`/offers/${id}/counter`, body).then((r) => r.data),
    onSuccess: afterTermsChange,
  });

  const improve = useMutation({
    mutationFn: (body: ImproveBody) => api.post<Offer>(`/offers/${id}/improve`, body).then((r) => r.data),
    onSuccess: afterTermsChange,
  });

  return { accept, reject, withdraw, counter, improve };
}

export type OfferActions = ReturnType<typeof useOfferActions>;
