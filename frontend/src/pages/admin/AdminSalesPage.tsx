import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "../../lib/api";
import type { Paginated, Sale } from "../../types/api";
import Badge from "../../components/ui/Badge";
import DateRangeFilter, { EMPTY_DATE_RANGE, type DateRange } from "../../components/ui/DateRangeFilter";
import Pagination from "../../components/ui/Pagination";
import Spinner from "../../components/ui/Spinner";
import { formatCurrency, formatDate, getApiError } from "../../lib/utils";

const STATUSES = ["OPEN", "CLOSED", "CANCELLED", "SOLD"];

const STATUS_VARIANT: Record<string, "success" | "info" | "warning" | "neutral" | "danger"> = {
  OPEN:      "success",
  CLOSED:    "neutral",
  CANCELLED: "danger",
  SOLD:      "info",
};

export default function AdminSalesPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [status, setStatus] = useState("");
  const [dateRange, setDateRange] = useState<DateRange>(EMPTY_DATE_RANGE);
  const [page, setPage]     = useState(1);

  const { data, isLoading } = useQuery<Paginated<Sale>>({
    queryKey: ["admin", "sales", { status, ...dateRange, page }],
    queryFn: () =>
      api
        .get<Paginated<Sale>>("/admin/sales", {
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

  const cancelMutation = useMutation({
    mutationFn: (saleId: string) =>
      api.post(`/admin/sales/${saleId}/cancel`).then((r) => r.data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin", "sales"] }),
  });

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-text">Sales</h1>
          <p className="mt-1 text-sm text-text-muted">{data ? `${data.total} total` : ""}</p>
        </div>
        <select
          value={status}
          onChange={(e) => { setStatus(e.target.value); setPage(1); }}
          className="rounded-lg bg-surface px-3 py-2 text-sm text-text ring-1 ring-input-border focus:outline-none focus:ring-warning-fill"
        >
          <option value="">All statuses</option>
          {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>

      <div className="mb-4">
        <DateRangeFilter value={dateRange} onChange={handleDateRangeChange} accent="amber" />
      </div>

      {cancelMutation.isError && (
        <div className="mb-4 rounded-lg bg-danger-bg px-4 py-2 text-xs text-danger-text ring-1 ring-danger-border">
          {getApiError(cancelMutation.error, "Cancel failed.")}
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
                  <th className="px-4 py-3">Seller</th>
                  <th className="px-4 py-3">Type</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Price / Reserve</th>
                  <th className="px-4 py-3">Created</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-rule-faint">
                {data.items.map((s) => (
                  <tr
                    key={s.id}
                    onClick={() => navigate(`/sales/${s.id}`)}
                    className="cursor-pointer bg-surface hover:bg-surface-inset transition-colors"
                  >
                    <td className="px-4 py-3 font-medium text-text">{s.player?.name ?? "—"}</td>
                    <td className="px-4 py-3 text-text-muted text-xs">{s.seller_club?.name ?? "—"}</td>
                    <td className="px-4 py-3">
                      <Badge variant={s.sale_type === "AUCTION" ? "warning" : "info"}>
                        {s.sale_type}
                      </Badge>
                    </td>
                    <td className="px-4 py-3">
                      <Badge variant={STATUS_VARIANT[s.status] ?? "neutral"}>{s.status}</Badge>
                    </td>
                    <td className="px-4 py-3 text-text-muted text-xs">
                      {s.sale_type === "AUCTION"
                        ? `Reserve: ${s.reserve_price != null ? formatCurrency(s.reserve_price) : "—"}`
                        : s.asking_price != null ? formatCurrency(s.asking_price) : "—"}
                    </td>
                    <td className="px-4 py-3 text-xs text-text-muted">{formatDate(s.created_at)}</td>
                    <td className="px-4 py-3 text-right" onClick={(e) => e.stopPropagation()}>
                      {s.status === "OPEN" && (
                        <button
                          disabled={cancelMutation.isPending}
                          onClick={() => cancelMutation.mutate(s.id)}
                          className="rounded bg-danger/10 px-2 py-1 text-xs text-danger-text hover:bg-danger/20 transition-colors disabled:opacity-40"
                        >
                          Cancel
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
