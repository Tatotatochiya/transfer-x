import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "../../lib/api";
import type { Club, Paginated, Sale } from "../../types/api";
import type { SaleStatus } from "../../types/enums";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import DateRangeFilter, { EMPTY_DATE_RANGE, type DateRange } from "../../components/ui/DateRangeFilter";
import PageHeader from "../../components/ui/PageHeader";
import { useClubCapabilities } from "../../hooks/useClubCapabilities";
import Pagination from "../../components/ui/Pagination";
import ResponsiveTable, { type ResponsiveColumn } from "../../components/ui/ResponsiveTable";
import EmptyState from "../../components/ui/EmptyState";
import { saleStatusLabel, saleStatusVariant, saleTypeLabel, saleTypeVariant } from "../../lib/badges";
import { formatCurrency, formatDeadline } from "../../lib/utils";
import { useConfirm } from "../../context/ConfirmContext";
import { useDeadlineCountdown } from "../../hooks/useDeadlineCountdown";

const STATUS_TABS: { label: string; value: SaleStatus | "" }[] = [
  { label: "All",      value: "" },
  { label: "Open",     value: "OPEN" },
  { label: "Closed",   value: "CLOSED" },
  { label: "Expired",  value: "EXPIRED" },
];

function DeadlineCell({ deadline }: { deadline: string | null }) {
  const result = useDeadlineCountdown(deadline);
  if (!deadline) return <span className="text-text-muted">—</span>;
  const colour =
    result.state === "danger"  ? "text-danger-text" :
    result.state === "warning" ? "text-warning-text" :
    result.state === "expired" ? "text-text-muted" : "text-text-secondary";
  return (
    <span className={`tabular-nums text-xs font-medium ${colour}`}>
      {result.state === "expired" ? "Expired" : result.label}
    </span>
  );
}

export default function MySalesPage() {
  const { can } = useClubCapabilities();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const confirm = useConfirm();
  const [statusFilter, setStatusFilter] = useState<SaleStatus | "">("");
  const [dateRange, setDateRange] = useState<DateRange>(EMPTY_DATE_RANGE);
  const [page, setPage] = useState(1);

  // Need own club id to query sales
  const { data: myClub } = useQuery<Club>({
    queryKey: ["clubs", "me"],
    queryFn: () => api.get<Club>("/clubs/me").then((r) => r.data),
    staleTime: 60_000,
  });

  const { data, isLoading } = useQuery<Paginated<Sale>>({
    queryKey: ["sales", "mine", { status: statusFilter, ...dateRange, page }],
    queryFn: () =>
      api
        .get<Paginated<Sale>>("/sales", {
          params: {
            seller_club_id: myClub!.id,
            page,
            page_size: 30,
            ...(statusFilter && { status: statusFilter }),
            ...(dateRange.dateFrom && { date_from: dateRange.dateFrom }),
            ...(dateRange.dateTo && { date_to: dateRange.dateTo }),
          },
        })
        .then((r) => r.data),
    enabled: !!myClub,
  });

  const withdrawMutation = useMutation({
    mutationFn: (saleId: string) =>
      api.post<Sale>(`/sales/${saleId}/withdraw`).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sales", "mine"] });
    },
  });

  function handleTabChange(val: SaleStatus | "") {
    setStatusFilter(val);
    setPage(1);
  }

  function handleDateRangeChange(range: DateRange) {
    setDateRange(range);
    setPage(1);
  }

  return (
    <div>
      <PageHeader
        title="My Listings"
        subtitle="Sales and auctions you've created"
        actions={
          can("MARKET_WRITE") && (
            <Button variant="primary" onClick={() => navigate("/sales/new")}>
              + New listing
            </Button>
          )
        }
      />

      {/* Status tabs */}
      <div className="mb-4 flex flex-wrap gap-2">
        {STATUS_TABS.map((tab) => (
          <button
            key={tab.value}
            onClick={() => handleTabChange(tab.value)}
            className={`rounded-lg px-3 py-1.5 text-sm transition-colors ${
              statusFilter === tab.value
                ? "bg-success/15 text-success-text ring-1 ring-success/30"
                : "bg-surface-inset text-text-muted hover:text-text"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="mb-6">
        <DateRangeFilter value={dateRange} onChange={handleDateRangeChange} />
      </div>

      {data && data.items.length === 0 && !isLoading && (
        <EmptyState
          title="No listings"
          body="You haven't listed any players yet."
          action={{ label: "Create a listing", to: "/sales/new" }}
        />
      )}

      {(isLoading || (data && data.items.length > 0)) && (
        <>
          <ResponsiveTable
            columns={[
              {
                key: "player", header: "Player", priority: 1, render: (sale) => (
                  <>
                    <p className="font-medium text-text">{sale.player?.name ?? "—"}</p>
                    {sale.player?.position && (
                      <p className="text-xs text-text-muted">{sale.player.position}</p>
                    )}
                  </>
                ),
              },
              {
                key: "type", header: "Type", priority: 4, render: (sale) => (
                  <Badge variant={sale.status === "OPEN" ? saleTypeVariant(sale.sale_type) : "neutral"}>
                    {saleTypeLabel(sale.sale_type)}
                  </Badge>
                ),
              },
              {
                key: "status", header: "Status", priority: 3, render: (sale) => (
                  <Badge variant={saleStatusVariant(sale.status)}>{saleStatusLabel(sale.status)}</Badge>
                ),
              },
              {
                key: "price", header: "Price / Best bid", priority: 2, className: "text-right", render: (sale) => (
                  <span className="font-semibold text-text tabular-nums">
                    {sale.best_bid != null
                      ? formatCurrency(sale.best_bid)
                      : sale.asking_price != null
                      ? formatCurrency(sale.asking_price)
                      : "—"}
                  </span>
                ),
              },
              {
                key: "deadline", header: "Deadline", priority: 5, render: (sale) => <DeadlineCell deadline={sale.deadline} />,
              },
              {
                key: "bids", header: "Bids", priority: 6, className: "text-right", render: (sale) => (
                  <span className="text-text-muted">{sale.sale_type === "AUCTION" ? sale.bid_count : "—"}</span>
                ),
              },
              {
                key: "actions", header: "", render: (sale) =>
                  sale.status === "OPEN" ? (
                    <div onClick={(e) => e.stopPropagation()}>
                      <Button
                        variant="danger"
                        size="sm"
                        loading={
                          withdrawMutation.isPending &&
                          withdrawMutation.variables === sale.id
                        }
                        onClick={async () => {
                          if (await confirm({ message: `Withdraw listing for ${sale.player?.name}?`, confirmLabel: "Withdraw", variant: "danger" })) {
                            withdrawMutation.mutate(sale.id);
                          }
                        }}
                      >
                        Withdraw
                      </Button>
                    </div>
                  ) : null,
              },
            ] satisfies ResponsiveColumn<Sale>[]}
            rows={data?.items ?? []}
            rowKey={(sale) => sale.id}
            loading={isLoading}
            onRowClick={(sale) => navigate(`/sales/${sale.id}`)}
          />

          {data && (
            <Pagination
              page={data.page}
              total={data.total}
              pageSize={data.page_size}
              onChange={setPage}
            />
          )}
        </>
      )}
    </div>
  );
}
