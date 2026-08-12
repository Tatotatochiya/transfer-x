import Card from "../ui/Card";
import type { Sale } from "../../types/api";
import { formatCurrency, formatDateTime } from "../../lib/utils";

/**
 * SCREENS.md also specs a "Bidder history with you" rail section — there's no
 * endpoint for historical bid relationships between two specific clubs, so
 * it isn't included here rather than faked.
 */
export default function SaleRail({ sale, isSeller }: { sale: Sale; isSeller: boolean }) {
  const closingSoon = sale.deadline && sale.status === "OPEN"
    ? (new Date(sale.deadline).getTime() - Date.now()) / 3_600_000 <= 48
    : false;

  return (
    <div className="space-y-4">
      {isSeller && sale.status === "OPEN" && sale.bid_count != null && sale.bid_count > 0 && (
        <Card tier={4} noPadding>
          <div className="px-[18px] py-[13px]">
            <p className="text-[13px] font-semibold text-text-secondary">Accept now or wait</p>
          </div>
          <div className="space-y-3 px-[18px] pb-3.5 text-[13px] text-text">
            <div>
              <p className="font-semibold">Accept now</p>
              <p className="text-text-muted">
                {sale.reserve_met
                  ? "Reserve is met — the current best bid is a safe outcome today."
                  : "Reserve isn't met yet — accepting now settles below your minimum."}
              </p>
            </div>
            <div>
              <p className="font-semibold">Wait until the deadline</p>
              <p className="text-text-muted">
                {closingSoon
                  ? "Closing within 48 hours — limited time left for a better offer to arrive."
                  : "More time remains for competing bids to raise the price."}
              </p>
            </div>
          </div>
        </Card>
      )}

      <Card tier={4} noPadding>
        <div className="px-[18px] py-[13px]">
          <p className="text-[13px] font-semibold text-text-secondary">Listing terms</p>
        </div>
        <div className="space-y-2 px-[18px] pb-3.5">
          {sale.asking_price != null && (
            <div className="flex items-center justify-between text-[13px]">
              <span className="text-text-muted">Asking price</span>
              <span className="font-semibold text-text">{formatCurrency(sale.asking_price)}</span>
            </div>
          )}
          {isSeller && sale.reserve_price != null && (
            <div className="flex items-center justify-between text-[13px]">
              <span className="text-text-muted">Reserve</span>
              <span className="font-semibold text-text">{formatCurrency(sale.reserve_price)}</span>
            </div>
          )}
          <div className="flex items-center justify-between text-[13px]">
            <span className="text-text-muted">Minimum increment</span>
            <span className="font-semibold text-text">{formatCurrency(sale.min_increment)}</span>
          </div>
          {sale.deadline && (
            <div className="flex items-center justify-between text-[13px]">
              <span className="text-text-muted">Deadline</span>
              <span className="font-semibold text-text">{formatDateTime(sale.deadline)}</span>
            </div>
          )}
          {sale.notes && (
            <p className="border-t border-rule pt-2 text-[13px] text-text-secondary">{sale.notes}</p>
          )}
        </div>
      </Card>
    </div>
  );
}
