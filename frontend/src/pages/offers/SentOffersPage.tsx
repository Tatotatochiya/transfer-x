import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import api from "../../lib/api";
import type { Offer, Paginated } from "../../types/api";
import type { OfferStatus } from "../../types/enums";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import ClubLink from "../../components/ui/ClubLink";
import DateRangeFilter, { EMPTY_DATE_RANGE, type DateRange } from "../../components/ui/DateRangeFilter";
import PageHeader from "../../components/ui/PageHeader";
import Pagination from "../../components/ui/Pagination";
import ResponsiveTable, { type ResponsiveColumn } from "../../components/ui/ResponsiveTable";
import { ListSkeleton } from "../../components/ui/Skeleton";
import { offerOutcome } from "../../lib/badges";
import { formatCurrency, formatDate } from "../../lib/utils";

const CHIPS: { label: string; value: OfferStatus | "" }[] = [
  { label: "All",       value: "" },
  { label: "Sent",      value: "SENT" },
  { label: "Countered", value: "COUNTERED" },
  { label: "Accepted",  value: "ACCEPTED" },
  { label: "Rejected",  value: "REJECTED" },
];

export default function SentOffersPage() {
  const navigate = useNavigate();
  const [statusFilter, setStatusFilter] = useState<OfferStatus | "">("");
  const [dateRange, setDateRange] = useState<DateRange>(EMPTY_DATE_RANGE);
  const [page, setPage] = useState(1);

  const { data, isLoading } = useQuery<Paginated<Offer>>({
    queryKey: ["offers", "sent", { status: statusFilter, ...dateRange, page }],
    queryFn: () =>
      api
        .get<Paginated<Offer>>("/offers/sent", {
          params: {
            page,
            page_size: 30,
            ...(statusFilter && { offer_status: statusFilter }),
            ...(dateRange.dateFrom && { date_from: dateRange.dateFrom }),
            ...(dateRange.dateTo && { date_to: dateRange.dateTo }),
          },
        })
        .then((r) => r.data),
  });

  function handleChipChange(val: OfferStatus | "") {
    setStatusFilter(val);
    setPage(1);
  }

  function handleDateRangeChange(range: DateRange) {
    setDateRange(range);
    setPage(1);
  }

  const columns: ResponsiveColumn<Offer>[] = [
    { key: "player", header: "Player", priority: 1, render: (o) => (
      <span className="font-medium text-text">
        {o.player?.name ?? "—"}
        {o.player?.position && <span className="ml-2 text-xs text-text-muted">{o.player.position}</span>}
      </span>
    ) },
    { key: "to", header: "To", priority: 3, render: (o) => <ClubLink id={o.to_club?.id} name={o.to_club?.name} /> },
    { key: "fee", header: "Fee", priority: 2, className: "text-right", render: (o) => (
      <span className="font-bold text-text">{o.fee_amount != null ? formatCurrency(o.fee_amount) : "TBD"}</span>
    ) },
    { key: "status", header: "Status", priority: 4, render: (o) => {
      const outcome = offerOutcome(o.status, o.deal);
      return (
        <div className="flex flex-col gap-0.5">
          <Badge variant={outcome.variant}>{outcome.label}</Badge>
          {o.status === "COUNTERED" && <span className="text-[10px] text-warning-text">Response needed</span>}
          {outcome.note && <span className="text-[10px] text-text-muted">{outcome.note}</span>}
        </div>
      );
    } },
    { key: "activity", header: "Last activity", priority: 5, className: "text-right", render: (o) => (
      <span className="text-xs text-text-muted">{formatDate(o.last_action_at)}</span>
    ) },
  ];

  return (
    <div>
      <PageHeader
        title="Sent Offers"
        subtitle="Offers you've made to other clubs"
        actions={
          <Button variant="primary" onClick={() => navigate("/offers/new")}>
            + New offer
          </Button>
        }
      />

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

      {isLoading ? (
        <ListSkeleton count={6} />
      ) : (
        <>
          <ResponsiveTable
            columns={columns}
            rows={data?.items ?? []}
            rowKey={(o) => o.id}
            onRowClick={(o) => navigate(`/offers/${o.id}`)}
            emptyTitle="No sent offers"
            emptyBody="Browse the player market to make offers."
            renderCard={(o) => {
              const outcome = offerOutcome(o.status, o.deal);
              return (
                <div className="px-4 py-3">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-semibold text-text">
                      {o.player?.name ?? "—"}
                      {o.player?.position && <span className="ml-1.5 text-xs text-text-muted">{o.player.position}</span>}
                    </span>
                    <span className="text-sm font-bold text-text">{o.fee_amount != null ? formatCurrency(o.fee_amount) : "TBD"}</span>
                  </div>
                  <p className="mt-0.5 text-xs text-text-muted">{o.to_club?.name ?? "?"}</p>
                  <div className="mt-1 flex items-center justify-between">
                    <div className="flex items-center gap-1.5">
                      <Badge variant={outcome.variant}>{outcome.label}</Badge>
                      {outcome.note && <span className="text-[10px] text-text-muted">{outcome.note}</span>}
                    </div>
                    <span className="text-xs text-text-muted">{formatDate(o.last_action_at)}</span>
                  </div>
                </div>
              );
            }}
          />

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
