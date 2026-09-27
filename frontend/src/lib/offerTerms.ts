import type { Offer, OrderBookEntry } from "../types/api";
import { formatCurrency, formatDate } from "./utils";

/**
 * How an offer's terms read to either club. A loan's money is `loan_fee`, never
 * `fee_amount`, so a surface reading `fee_amount` alone shows a loan as having
 * no terms at all — which is how the seller's pages presented every loan until
 * these helpers existed. Read an offer's money through here, not the raw field.
 */

type Money = number | string | null | undefined;
type OfferMoney = { deal_type?: string | null; fee_amount: Money; loan_fee?: Money };

const num = (v: Money): number | null => (v == null ? null : Number(v));

export function isLoan(o: { deal_type?: string | null }): boolean {
  return o.deal_type === "LOAN";
}

/**
 * The one figure a list row shows. Never "TBD": a missing fee is a deliberate
 * term (the offer form makes "no fee" an explicit choice), not an open question.
 */
export function offerHeadline(o: OfferMoney | OrderBookEntry): string {
  if (isLoan(o)) {
    const fee = num(o.loan_fee);
    return fee ? `${formatCurrency(fee)} loan fee` : "No loan fee";
  }
  const fee = num(o.fee_amount);
  return fee != null ? formatCurrency(fee) : "No fee";
}

/** Share of the player's wage the borrowing club pays, as a whole percentage. */
export function wageSharePct(o: Pick<Offer, "wage_split_pct">): number {
  const split = num(o.wage_split_pct);
  return Math.round((split ?? 1) * 100);
}

export function loanPeriod(o: Pick<Offer, "loan_start" | "loan_end">): string {
  return `${formatDate(o.loan_start)} – ${formatDate(o.loan_end)}`;
}

/** "Obligation to buy at £18,000,000", "Option to buy at …", or null. */
export function purchaseClause(
  o: Pick<Offer, "option_to_buy" | "obligation_to_buy">,
): string | null {
  const price = num(o.option_to_buy);
  if (price == null) return null;
  return `${o.obligation_to_buy ? "Obligation" : "Option"} to buy at ${formatCurrency(price)}`;
}
