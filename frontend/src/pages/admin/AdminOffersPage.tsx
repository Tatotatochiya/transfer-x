import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "../../lib/api";
import type { Offer, Paginated } from "../../types/api";
import Badge from "../../components/ui/Badge";
import DateRangeFilter, { EMPTY_DATE_RANGE, type DateRange } from "../../components/ui/DateRangeFilter";
import Pagination from "../../components/ui/Pagination";
import Spinner from "../../components/ui/Spinner";
import { formatCurrency, formatDate, getApiError } from "../../lib/utils";
import type { OfferStatus } from "../../types/enums";

const OFFER_STATUSES = ["SENT", "COUNTERED", "ACCEPTED", "REJECTED", "WITHDRAWN", "EXPIRED"];

const STATUS_VARIANT: Record<string, "success" | "info" | "warning" | "neutral" | "danger"> = {
  SENT:      "info",
  COUNTERED: "warning",
  ACCEPTED:  "success",
  REJECTED:  "danger",
  WITHDRAWN: "neutral",
  EXPIRED:   "neutral",
};

const TERMINAL = new Set(["ACCEPTED", "REJECTED", "WITHDRAWN", "EXPIRED"]);

export default function AdminOffersPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [status, setStatus] = useState("");
  const [dateRange, setDateRange] = useState<DateRange>(EMPTY_DATE_RANGE);
  const [page,   setPage]   = useState(1);

  const { data, isLoading } = useQuery<Paginated<Offer>>({
    queryKey: ["admin", "offers", { status, ...dateRange, page }],
    queryFn: () =>
      api
        .get<Paginated<Offer>>("/admin/offers", {
          params: {
            page, page_size: 30,
            ...(status && { status }),
            ...(dateRange.dateFrom && { date_from: dateRange.dateFrom }),
            ...(dateRange.dateTo && { date_to: dateRange.dateTo }),
          },
        })
        .then((r) => r.data),
  });

  function handleDateRangeChange(range: DateRange) {
    setDateRange(range);
    setPage(1);
  }

  const withdrawMutation = useMutation({
    mutationFn: (offerId: string) =>
      api.post(`/admin/offers/${offerId}/force-withdraw`).then((r) => r.data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin", "offers"] }),
  });

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-text">Offers</h1>
          <p className="mt-1 text-sm text-text-muted">{data ? `${data.total} total` : ""}</p>
        </div>
        <select
          value={status}
          onChange={(e) => { setStatus(e.target.value); setPage(1); }}
          className="rounded-lg bg-surface px-3 py-2 text-sm text-text ring-1 ring-input-border focus:outline-none focus:ring-warning-fill"
        >
          <option value="">All statuses</option>
          {OFFER_STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>

      <div className="mb-4">
        <DateRangeFilter value={dateRange} onChange={handleDateRangeChange} accent="amber" />
      </div>

      {withdrawMutation.isError && (
        <div className="mb-4 rounded-lg bg-danger-bg px-4 py-2 text-xs text-danger-text ring-1 ring-danger-border">
          {getApiError(withdrawMutation.error, "Withdraw failed.")}
        </div>
      )}

      {isLoading && <div className="flex justify-center py-12"><Spinner size="lg" /></div>}

      {data && (
        <>
          <div className="overflow-x-auto rounded-xl ring-1 ring-border">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="border-b border-rule bg-surface-header text-left text-xs font-semibold uppercase tracking-wider text-text-muted">
                  <th className="px-4 py-3">Player</th>
                  <th className="px-4 py-3">From</th>
                  <th className="px-4 py-3">To</th>
                  <th className="px-4 py-3">Fee</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Last action</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-rule-faint">
                {data.items.map((o) => (
                  <tr
                    key={o.id}
                    onClick={() => navigate(`/offers/${o.id}`)}
                    className="cursor-pointer bg-surface hover:bg-surface-inset transition-colors"
                  >
                    <td className="px-4 py-3 font-medium text-text">{o.player?.name ?? "—"}</td>
                    <td className="px-4 py-3 text-xs text-text-muted">{o.from_club?.name ?? "—"}</td>
                    <td className="px-4 py-3 text-xs text-text-muted">{o.to_club?.name ?? "—"}</td>
                    <td className="px-4 py-3 text-text-secondary text-xs">
                      {o.fee_amount != null ? formatCurrency(o.fee_amount) : "—"}
                    </td>
                    <td className="px-4 py-3">
                      <Badge variant={STATUS_VARIANT[o.status as OfferStatus] ?? "neutral"}>
                        {o.status}
                      </Badge>
                    </td>
                    <td className="px-4 py-3 text-xs text-text-muted">{formatDate(o.last_action_at)}</td>
                    <td className="px-4 py-3 text-right" onClick={(e) => e.stopPropagation()}>
                      {!TERMINAL.has(o.status) && (
                        <button
                          disabled={withdrawMutation.isPending}
                          onClick={() => withdrawMutation.mutate(o.id)}
                          className="rounded bg-danger/10 px-2 py-1 text-xs text-danger-text hover:bg-danger/20 transition-colors disabled:opacity-40"
                        >
                          Force withdraw
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination page={data.page} total={data.total} pageSize={data.page_size} onChange={setPage} />
        </>
      )}
    </div>
  );
}
