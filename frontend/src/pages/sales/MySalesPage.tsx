import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "../../lib/api";
import type { Club, Paginated, Sale } from "../../types/api";
import type { SaleStatus } from "../../types/enums";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import PageHeader from "../../components/ui/PageHeader";
import Pagination from "../../components/ui/Pagination";
import EmptyState from "../../components/ui/EmptyState";
import { saleStatusVariant, saleTypeLabel, saleTypeVariant } from "../../lib/badges";
import { formatCurrency, formatDeadline } from "../../lib/utils";
import { useConfirm } from "../../context/ConfirmContext";
import { ListSkeleton } from "../../components/ui/Skeleton";
import { useDeadlineCountdown } from "../../hooks/useDeadlineCountdown";

const STATUS_TABS: { label: string; value: SaleStatus | "" }[] = [
  { label: "All",      value: "" },
  { label: "Open",     value: "OPEN" },
  { label: "Closed",   value: "CLOSED" },
  { label: "Expired",  value: "EXPIRED" },
];

function DeadlineCell({ deadline }: { deadline: string | null }) {
  const result = useDeadlineCountdown(deadline);
  if (!deadline) return <span className="text-slate-500">—</span>;
  const colour =
    result.state === "danger"  ? "text-red-400" :
    result.state === "warning" ? "text-amber-400" :
    result.state === "expired" ? "text-slate-500" : "text-slate-300";
  return (
    <span className={`tabular-nums text-xs font-medium ${colour}`}>
      {result.state === "expired" ? "Expired" : result.label}
    </span>
  );
}

export default function MySalesPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const confirm = useConfirm();
  const [statusFilter, setStatusFilter] = useState<SaleStatus | "">("");
  const [page, setPage] = useState(1);

  // Need own club id to query sales
  const { data: myClub } = useQuery<Club>({
    queryKey: ["clubs", "me"],
    queryFn: () => api.get<Club>("/clubs/me").then((r) => r.data),
    staleTime: 60_000,
  });

  const { data, isLoading } = useQuery<Paginated<Sale>>({
    queryKey: ["sales", "mine", { status: statusFilter, page }],
    queryFn: () =>
      api
        .get<Paginated<Sale>>("/sales", {
          params: {
            seller_club_id: myClub!.id,
            page,
            page_size: 20,
            ...(statusFilter && { status: statusFilter }),
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

  return (
    <div>
      <PageHeader
        title="My Listings"
        subtitle="Sales and auctions you've created"
        actions={
          <Button variant="primary" onClick={() => navigate("/sales/new")}>
            + New listing
          </Button>
        }
      />

      {/* Status tabs */}
      <div className="mb-6 flex flex-wrap gap-2">
        {STATUS_TABS.map((tab) => (
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

      {isLoading && <ListSkeleton count={5} />}

      {data && data.items.length === 0 && (
        <EmptyState
          title="No listings"
          body="You haven't listed any players yet."
          action={{ label: "Create a listing", to: "/sales/new" }}
        />
      )}

      {data && data.items.length > 0 && (
        <>
          <div className="overflow-x-auto rounded-xl ring-1 ring-white/[0.08]">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="border-b border-white/[0.08]">
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-400">Player</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-400">Type</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-400">Status</th>
                  <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wider text-slate-400">Price / Best bid</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-400">Deadline</th>
                  <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wider text-slate-400">Bids</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.04]">
                {data.items.map((sale) => (
                  <tr
                    key={sale.id}
                    className="bg-slate-900 hover:bg-slate-800/60 cursor-pointer transition-colors"
                    onClick={() => navigate(`/sales/${sale.id}`)}
                  >
                    <td className="px-4 py-3">
                      <p className="font-medium text-white">{sale.player?.name ?? "—"}</p>
                      {sale.player?.position && (
                        <p className="text-xs text-slate-500">{sale.player.position}</p>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <Badge variant={saleTypeVariant(sale.sale_type)}>
                        {saleTypeLabel(sale.sale_type)}
                      </Badge>
                    </td>
                    <td className="px-4 py-3">
                      <Badge variant={saleStatusVariant(sale.status)}>{sale.status}</Badge>
                    </td>
                    <td className="px-4 py-3 text-right font-semibold text-white tabular-nums">
                      {sale.best_bid != null
                        ? formatCurrency(sale.best_bid)
                        : sale.asking_price != null
                        ? formatCurrency(sale.asking_price)
                        : "—"}
                    </td>
                    <td className="px-4 py-3">
                      <DeadlineCell deadline={sale.deadline} />
                    </td>
                    <td className="px-4 py-3 text-right text-slate-400">
                      {sale.sale_type === "AUCTION" ? sale.bid_count : "—"}
                    </td>
                    <td
                      className="px-4 py-3 text-right"
                      onClick={(e) => e.stopPropagation()}
                    >
                      {sale.status === "OPEN" && (
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
                      )}
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
