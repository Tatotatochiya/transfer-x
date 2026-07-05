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
import EmptyState from "../../components/ui/EmptyState";
import PageHeader from "../../components/ui/PageHeader";
import Pagination from "../../components/ui/Pagination";
import { ListSkeleton } from "../../components/ui/Skeleton";
import { offerStatusVariant } from "../../lib/badges";
import { formatCurrency, formatDate } from "../../lib/utils";

const TABS: { label: string; value: OfferStatus | "" }[] = [
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

  function handleTabChange(val: OfferStatus | "") {
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
        title="Sent Offers"
        subtitle="Offers you've made to other clubs"
        actions={
          <Button variant="primary" onClick={() => navigate("/offers/new")}>
            + New offer
          </Button>
        }
      />

      {/* Tabs */}
      <div className="mb-4 flex flex-wrap gap-2">
        {TABS.map((tab) => (
          <button
            key={tab.value}
            onClick={() => handleTabChange(tab.value)}
            className={`rounded-lg px-3 py-1.5 text-sm transition-colors ${
              statusFilter === tab.value
                ? "bg-emerald-500/15 text-emerald-400 ring-1 ring-emerald-500/30"
                : "bg-slate-800 text-slate-400 hover:text-white"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="mb-6">
        <DateRangeFilter value={dateRange} onChange={handleDateRangeChange} />
      </div>

      {isLoading && <ListSkeleton count={6} />}

      {data && data.items.length === 0 && (
        <EmptyState
          title="No sent offers"
          body="Browse the player market to make offers."
          action={{ label: "Browse players", to: "/players/market" }}
        />
      )}

      {data && data.items.length > 0 && (
        <>
          <div className="overflow-x-auto rounded-xl ring-1 ring-white/[0.08]">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="border-b border-white/[0.08]">
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-400">Player</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-400">To</th>
                  <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wider text-slate-400">Fee</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-400">Status</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-400">Last activity</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.04]">
                {data.items.map((offer) => (
                  <tr
                    key={offer.id}
                    onClick={() => navigate(`/offers/${offer.id}`)}
                    className={`cursor-pointer transition-colors ${
                      offer.status === "COUNTERED"
                        ? "bg-amber-500/[0.04] hover:bg-amber-500/[0.08]"
                        : "bg-slate-900 hover:bg-slate-800/60"
                    }`}
                  >
                    <td className="px-4 py-3">
                      <p className="font-medium text-white">{offer.player?.name ?? "—"}</p>
                      {offer.player?.position && (
                        <p className="text-xs text-slate-500">{offer.player.position}</p>
                      )}
                    </td>
                    <td className="px-4 py-3 text-slate-300">
                      <ClubLink id={offer.to_club?.id} name={offer.to_club?.name} />
                    </td>
                    <td className="px-4 py-3 text-right font-semibold text-white tabular-nums">
                      {offer.fee_amount != null ? formatCurrency(offer.fee_amount) : "TBD"}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex flex-col gap-0.5">
                        <Badge variant={offerStatusVariant(offer.status)}>
                          {offer.status}
                        </Badge>
                        {offer.status === "COUNTERED" && (
                          <span className="text-[10px] text-amber-400/70">Response needed</span>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-slate-400 text-xs">
                      {formatDate(offer.last_action_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <Pagination
            page={data.page}
            total={data.total}
            pageSize={data.page_size}
            onChange={setPage}
          />
        </>
      )}
    </div>
  );
}
