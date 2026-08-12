import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import api from "../../lib/api";
import type { Club, Deal, Paginated } from "../../types/api";
import type { DealStatus } from "../../types/enums";
import Badge from "../../components/ui/Badge";
import ClubLink from "../../components/ui/ClubLink";
import DateRangeFilter, { EMPTY_DATE_RANGE, type DateRange } from "../../components/ui/DateRangeFilter";
import EmptyState from "../../components/ui/EmptyState";
import PageHeader from "../../components/ui/PageHeader";
import Pagination from "../../components/ui/Pagination";
import ResponsiveTable, { type ResponsiveColumn } from "../../components/ui/ResponsiveTable";
import { ListSkeleton } from "../../components/ui/Skeleton";
import StageTracker from "../../components/deals/StageTracker";
import { dealStatusVariant } from "../../lib/badges";
import { formatCurrency, formatDate } from "../../lib/utils";
import { dealWhoseMove, dealWhoseMoveReason } from "../../lib/whoseMove";

const CHIPS: { label: string; value: DealStatus | "" }[] = [
  { label: "All",                value: "" },
  { label: "In progress",        value: "IN_PROGRESS" },
  { label: "Pending completion", value: "PENDING_COMPLETION" },
  { label: "Completed",          value: "COMPLETED" },
  { label: "Collapsed",          value: "COLLAPSED" },
];

const CLOSED_STATUSES = new Set<DealStatus>(["COMPLETED", "COLLAPSED"]);

// ── Active deal card ─────────────────────────────────────────────────────────

function DealCard({ deal, myClubId }: { deal: Deal; myClubId: string | undefined }) {
  const navigate = useNavigate();
  const move = myClubId ? dealWhoseMove(deal, myClubId) : "neither";
  const reason = dealWhoseMoveReason(deal);
  const isYourMove = move === "your";

  return (
    <div
      onClick={() => navigate(`/deals/${deal.id}`)}
      className={`cursor-pointer rounded-xl bg-surface px-5 py-4 ring-1 transition-all hover:ring-input-border ${
        isYourMove ? "ring-danger-ring shadow-[0_1px_2px_rgba(16,24,40,0.06)]" : "ring-border"
      }`}
    >
      <div className="flex flex-wrap items-center gap-4">
        <div className="flex-1 basis-[240px]">
          <p className="text-base font-bold text-text">{deal.player?.name ?? "Unknown"}</p>
          <p className="text-[13px] text-text-secondary">
            {deal.seller_club?.name ?? "?"} → {deal.buyer_club?.name ?? "?"}
          </p>
        </div>
        <div className="basis-[120px] shrink">
          <p className="text-[11px] text-text-muted">Agreed fee</p>
          <p className="text-[17px] font-bold text-text">{formatCurrency(deal.agreed_fee)}</p>
        </div>
        <div className="basis-[150px] shrink">
          <p className="text-[11px] text-text-muted">Whose move</p>
          {move === "neither" ? (
            <p className="text-sm text-text-muted">{reason}</p>
          ) : (
            <p className={`text-sm font-bold ${isYourMove ? "text-danger-text" : "text-text-secondary"}`}>
              {reason}
            </p>
          )}
        </div>
        <button
          onClick={(e) => { e.stopPropagation(); navigate(`/deals/${deal.id}`); }}
          className={`shrink-0 rounded-lg px-4 py-2 text-sm font-semibold transition-colors ${
            isYourMove
              ? "bg-accent text-white hover:bg-accent-hover"
              : "bg-surface-inset text-text ring-1 ring-border hover:ring-input-border"
          }`}
        >
          {isYourMove ? "Open" : "View"}
        </button>
      </div>
      <div className="mt-3.5 pt-3.5 border-t border-rule-faint">
        <StageTracker stage={deal.stage} status={deal.status} />
      </div>
    </div>
  );
}

// ── Closed deals table ────────────────────────────────────────────────────────

interface ClosedRow { deal: Deal }

function ClosedDealsTable({ deals }: { deals: Deal[] }) {
  const navigate = useNavigate();
  if (deals.length === 0) return null;

  const columns: ResponsiveColumn<ClosedRow>[] = [
    { key: "player", header: "Player", priority: 1, render: ({ deal }) => (
      <span className="font-medium text-text">{deal.player?.name ?? "—"}</span>
    ) },
    { key: "route", header: "Route", priority: 3, render: ({ deal }) => (
      <span className="text-text-secondary">
        <ClubLink id={deal.seller_club?.id} name={deal.seller_club?.name} /> → <ClubLink id={deal.buyer_club?.id} name={deal.buyer_club?.name} />
      </span>
    ) },
    { key: "fee", header: "Fee", priority: 2, className: "text-right", render: ({ deal }) => (
      <span className="font-bold text-text">{formatCurrency(deal.agreed_fee)}</span>
    ) },
    { key: "outcome", header: "Outcome", priority: 4, render: ({ deal }) => (
      <Badge variant={dealStatusVariant(deal.status)}>{deal.status === "COMPLETED" ? "Completed" : "Collapsed"}</Badge>
    ) },
    { key: "date", header: "Date", priority: 5, className: "text-right", render: ({ deal }) => (
      <span className="text-xs text-text-muted">{formatDate(deal.completed_at ?? deal.updated_at)}</span>
    ) },
  ];

  return (
    <div className="mt-6">
      <h2 className="mb-3 text-sm font-bold text-text">Closed this window</h2>
      <ResponsiveTable
        columns={columns}
        rows={deals.map((deal) => ({ deal }))}
        rowKey={(r) => r.deal.id}
        onRowClick={(r) => navigate(`/deals/${r.deal.id}`)}
        renderCard={({ deal }) => (
          <div className="px-4 py-3">
            <div className="flex items-center justify-between">
              <span className="text-sm font-semibold text-text">{deal.player?.name ?? "—"}</span>
              <span className="text-sm font-bold text-text">{formatCurrency(deal.agreed_fee)}</span>
            </div>
            <p className="mt-0.5 text-xs text-text-muted">{deal.seller_club?.name ?? "?"} → {deal.buyer_club?.name ?? "?"}</p>
            <div className="mt-1 flex items-center justify-between">
              <Badge variant={dealStatusVariant(deal.status)}>{deal.status === "COMPLETED" ? "Completed" : "Collapsed"}</Badge>
              <span className="text-xs text-text-muted">{formatDate(deal.completed_at ?? deal.updated_at)}</span>
            </div>
          </div>
        )}
      />
    </div>
  );
}

// ── Main page ──────────────────────────────────────────────────────────────────

export default function DealListPage() {
  const [statusFilter, setStatusFilter] = useState<DealStatus | "">("");
  const [dateRange, setDateRange] = useState<DateRange>(EMPTY_DATE_RANGE);
  const [page, setPage] = useState(1);

  const { data: myClub } = useQuery<Club>({
    queryKey: ["clubs", "me"],
    queryFn: () => api.get<Club>("/clubs/me").then((r) => r.data),
    staleTime: 60_000,
  });

  const { data, isLoading } = useQuery<Paginated<Deal>>({
    queryKey: ["deals", { status: statusFilter, ...dateRange, page }],
    queryFn: () =>
      api
        .get<Paginated<Deal>>("/deals", {
          params: {
            page,
            page_size: 30,
            ...(statusFilter && { deal_status: statusFilter }),
            ...(dateRange.dateFrom && { date_from: dateRange.dateFrom }),
            ...(dateRange.dateTo && { date_to: dateRange.dateTo }),
          },
        })
        .then((r) => r.data),
  });

  function handleChipChange(val: DealStatus | "") {
    setStatusFilter(val);
    setPage(1);
  }

  function handleDateRangeChange(range: DateRange) {
    setDateRange(range);
    setPage(1);
  }

  const items = data?.items ?? [];
  const activeDeals = items.filter((d) => !CLOSED_STATUSES.has(d.status));
  const closedDeals = items.filter((d) => CLOSED_STATUSES.has(d.status));

  return (
    <div>
      <PageHeader title="My Deals" subtitle="Transfer deals you're involved in" />

      <div className="mb-4 flex flex-wrap gap-2">
        {CHIPS.map((c) => (
          <button
            key={c.value}
            onClick={() => handleChipChange(c.value)}
            className={`rounded-lg px-3.5 py-1.5 text-[13px] font-semibold transition-colors ${
              statusFilter === c.value
                ? "bg-ink text-white"
                : "bg-surface text-text-secondary ring-1 ring-input-border hover:ring-accent"
            }`}
          >
            {c.label}
          </button>
        ))}
      </div>

      <div className="mb-6">
        <DateRangeFilter value={dateRange} onChange={handleDateRangeChange} />
      </div>

      {isLoading && <ListSkeleton count={6} />}

      {!isLoading && items.length === 0 && (
        <EmptyState title="No deals" body="Accepted offers and won auctions will appear here." />
      )}

      {!isLoading && items.length > 0 && (
        <>
          {activeDeals.length > 0 && (
            <div className="space-y-3">
              {activeDeals.map((deal) => (
                <DealCard key={deal.id} deal={deal} myClubId={myClub?.id} />
              ))}
            </div>
          )}

          <ClosedDealsTable deals={closedDeals} />

          {data && data.total > data.page_size && (
            <div className="mt-6">
              <Pagination page={data.page} total={data.total} pageSize={data.page_size} onChange={setPage} />
            </div>
          )}
        </>
      )}
    </div>
  );
}
