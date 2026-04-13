import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import api from "../../lib/api";
import type { Deal, Paginated } from "../../types/api";
import type { DealStatus } from "../../types/enums";
import Badge from "../../components/ui/Badge";
import ClubLink from "../../components/ui/ClubLink";
import EmptyState from "../../components/ui/EmptyState";
import PageHeader from "../../components/ui/PageHeader";
import Pagination from "../../components/ui/Pagination";
import { ListSkeleton } from "../../components/ui/Skeleton";
import { dealStatusVariant, dealStageLabel } from "../../lib/badges";
import { formatCurrency, formatDate } from "../../lib/utils";

const TABS: { label: string; value: DealStatus | "" }[] = [
  { label: "All",        value: "" },
  { label: "In Progress", value: "IN_PROGRESS" },
  { label: "Pending",    value: "PENDING_COMPLETION" },
  { label: "Completed",  value: "COMPLETED" },
  { label: "Collapsed",  value: "COLLAPSED" },
];

export default function DealListPage() {
  const navigate = useNavigate();
  const [statusFilter, setStatusFilter] = useState<DealStatus | "">("");
  const [page, setPage] = useState(1);

  const { data, isLoading } = useQuery<Paginated<Deal>>({
    queryKey: ["deals", { status: statusFilter, page }],
    queryFn: () =>
      api
        .get<Paginated<Deal>>("/deals", {
          params: {
            page,
            page_size: 20,
            ...(statusFilter && { deal_status: statusFilter }),
          },
        })
        .then((r) => r.data),
  });

  function handleTabChange(val: DealStatus | "") {
    setStatusFilter(val);
    setPage(1);
  }

  return (
    <div>
      <PageHeader title="My Deals" subtitle="Transfer deals you're involved in" />

      {/* Tabs */}
      <div className="mb-6 flex flex-wrap gap-2">
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

      {isLoading && <ListSkeleton count={6} />}

      {data && data.items.length === 0 && (
        <EmptyState
          title="No deals"
          body="Accepted offers and won auctions will appear here."
        />
      )}

      {data && data.items.length > 0 && (
        <>
          <div className="overflow-x-auto rounded-xl ring-1 ring-white/[0.08]">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="border-b border-white/[0.08]">
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-400">Player</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-400">Buyer</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-400">Seller</th>
                  <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wider text-slate-400">Fee</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-400">Stage</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-400">Status</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-400">Date</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.04]">
                {data.items.map((deal) => (
                  <tr
                    key={deal.id}
                    onClick={() => navigate(`/deals/${deal.id}`)}
                    className="bg-slate-900 hover:bg-slate-800/60 cursor-pointer transition-colors"
                  >
                    <td className="px-4 py-3">
                      <p className="font-medium text-white">{deal.player?.name ?? "—"}</p>
                      {deal.player?.position && (
                        <p className="text-xs text-slate-500">{deal.player.position}</p>
                      )}
                    </td>
                    <td className="px-4 py-3 text-slate-300">
                      <ClubLink id={deal.buyer_club?.id} name={deal.buyer_club?.name} />
                    </td>
                    <td className="px-4 py-3 text-slate-300">
                      <ClubLink id={deal.seller_club?.id} name={deal.seller_club?.name} />
                    </td>
                    <td className="px-4 py-3 text-right font-semibold text-white tabular-nums">
                      {formatCurrency(deal.agreed_fee)}
                    </td>
                    <td className="px-4 py-3 text-slate-300 text-xs">
                      {dealStageLabel(deal.stage)}
                    </td>
                    <td className="px-4 py-3">
                      <Badge variant={dealStatusVariant(deal.status)}>
                        {deal.status.replace("_", " ")}
                      </Badge>
                    </td>
                    <td className="px-4 py-3 text-slate-400 text-xs">
                      {formatDate(deal.created_at)}
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
