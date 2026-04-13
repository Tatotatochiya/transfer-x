import { useNavigate, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import api from "../../lib/api";
import type {
  Club,
  Deal,
  ExpiringContractItem,
  Offer,
  Paginated,
  Player,
  Sale,
  ShortlistHit,
  TransferWindowStatus,
} from "../../types/api";
import Badge from "../../components/ui/Badge";
import ClubLink from "../../components/ui/ClubLink";
import Spinner from "../../components/ui/Spinner";
import {
  saleStatusVariant,
  saleTypeLabel,
  offerStatusVariant,
  dealStatusVariant,
  dealStageLabel,
  positionVariant,
} from "../../lib/badges";
import { formatCurrency, formatDate } from "../../lib/utils";
import { useDeadlineCountdown } from "../../hooks/useDeadlineCountdown";
import type { PlayerPosition } from "../../types/enums";

// ── Helpers ───────────────────────────────────────────────────────────────────

function DeadlineCell({ deadline }: { deadline: string | null }) {
  const result = useDeadlineCountdown(deadline);
  if (!deadline) return <span className="text-slate-600">—</span>;
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

function PanelShell({
  title, count, linkTo, linkLabel, children, loading,
}: {
  title: string; count?: number; linkTo?: string; linkLabel?: string;
  children: React.ReactNode; loading?: boolean;
}) {
  const navigate = useNavigate();
  return (
    <div className="rounded-2xl bg-slate-900 ring-1 ring-white/[0.08] flex flex-col">
      <div className="flex items-center justify-between px-5 py-4 border-b border-white/[0.06]">
        <div className="flex items-center gap-2">
          <p className="text-sm font-semibold text-white">{title}</p>
          {count !== undefined && count > 0 && (
            <span className="rounded-full bg-emerald-500/20 px-2 py-0.5 text-xs font-semibold text-emerald-400">
              {count}
            </span>
          )}
        </div>
        {linkTo && linkLabel && (
          <button
            onClick={() => navigate(linkTo)}
            className="text-xs text-slate-500 hover:text-emerald-400 transition-colors"
          >
            {linkLabel} →
          </button>
        )}
      </div>
      <div className="flex-1 px-5 py-4">
        {loading ? (
          <div className="flex items-center justify-center py-8"><Spinner size="sm" /></div>
        ) : children}
      </div>
    </div>
  );
}

function EmptyPanel({ message }: { message: string }) {
  return <p className="text-sm text-slate-600 text-center py-6">{message}</p>;
}

// ── #1 Urgent Actions Banner ──────────────────────────────────────────────────

function UrgentActionsPanel() {
  const navigate = useNavigate();

  const { data: confirmedDeals } = useQuery<Paginated<Deal>>({
    queryKey: ["urgent", "confirmed-deals"],
    queryFn: () =>
      api.get<Paginated<Deal>>("/deals", { params: { deal_status: "IN_PROGRESS", page_size: 10 } })
        .then((r) => r.data),
    staleTime: 30_000,
  });

  const { data: receivedOffers } = useQuery<Paginated<Offer>>({
    queryKey: ["urgent", "received-offers"],
    queryFn: () =>
      api.get<Paginated<Offer>>("/offers/received", { params: { offer_status: "SENT", page_size: 10 } })
        .then((r) => r.data),
    staleTime: 30_000,
  });

  const { data: counteredOffers } = useQuery<Paginated<Offer>>({
    queryKey: ["urgent", "countered-offers"],
    queryFn: () =>
      api.get<Paginated<Offer>>("/offers/sent", { params: { offer_status: "COUNTERED", page_size: 10 } })
        .then((r) => r.data),
    staleTime: 30_000,
  });

  const readyDeals = confirmedDeals?.items.filter((d) => d.stage === "CONFIRMED") ?? [];
  const received  = receivedOffers?.items ?? [];
  const countered = counteredOffers?.items ?? [];

  const items: { key: string; label: string; sub: string; colour: string; onClick: () => void }[] = [
    ...readyDeals.map((d) => ({
      key: `deal-${d.id}`,
      label: `Execute transfer — ${d.player?.name ?? "Unknown"}`,
      sub: `${formatCurrency(d.agreed_fee)} · Ready to Execute`,
      colour: "emerald",
      onClick: () => navigate(`/deals/${d.id}`),
    })),
    ...countered.map((o) => ({
      key: `counter-${o.id}`,
      label: `Counter-offer received — ${o.player?.name ?? "Unknown"}`,
      sub: `from ${o.to_club?.name ?? "—"} · respond now`,
      colour: "amber",
      onClick: () => navigate(`/offers/${o.id}`),
    })),
    ...received.map((o) => ({
      key: `recv-${o.id}`,
      label: `Offer received — ${o.player?.name ?? "Unknown"}`,
      sub: `from ${o.from_club?.name ?? "—"} · ${o.fee_amount != null ? formatCurrency(o.fee_amount) : "TBD"}`,
      colour: "sky",
      onClick: () => navigate(`/offers/${o.id}`),
    })),
  ];

  if (items.length === 0) return null;

  const COLOUR = {
    emerald: "bg-emerald-500/10 ring-emerald-500/20 text-emerald-400 before:bg-emerald-400",
    amber:   "bg-amber-500/10   ring-amber-500/20   text-amber-400   before:bg-amber-400",
    sky:     "bg-sky-500/10     ring-sky-500/20     text-sky-400     before:bg-sky-400",
  } as const;

  return (
    <div className="mb-6 rounded-xl bg-slate-900 ring-1 ring-white/[0.08] overflow-hidden">
      <div className="flex items-center gap-2 border-b border-white/[0.06] px-5 py-3">
        <span className="h-2 w-2 rounded-full bg-red-400 animate-pulse" />
        <p className="text-xs font-bold uppercase tracking-wider text-red-400">
          Requires Action ({items.length})
        </p>
      </div>
      <div className="divide-y divide-white/[0.04]">
        {items.map((item) => (
          <button
            key={item.key}
            onClick={item.onClick}
            className={`w-full flex items-center gap-3 px-5 py-3 text-left hover:bg-white/[0.03] transition-colors ring-inset ${COLOUR[item.colour as keyof typeof COLOUR]}`}
          >
            <span className={`h-1.5 w-1.5 shrink-0 rounded-full before:content-[''] ${COLOUR[item.colour as keyof typeof COLOUR]}`} />
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-white">{item.label}</p>
              <p className="text-xs text-slate-400">{item.sub}</p>
            </div>
            <span className="text-xs text-slate-500 shrink-0">→</span>
          </button>
        ))}
      </div>
    </div>
  );
}

// ── #2 Transfer Window Banner ─────────────────────────────────────────────────

function WindowCountdown({ closesAt }: { closesAt: string }) {
  const result = useDeadlineCountdown(closesAt);
  if (result.state === "expired") return <span className="text-slate-400">Closing soon</span>;
  const colour = result.state === "danger" ? "text-red-400" : result.state === "warning" ? "text-amber-400" : "text-emerald-400";
  return <span className={`font-bold tabular-nums ${colour}`}>{result.label} remaining</span>;
}

function TransferWindowBanner({ myClub }: { myClub: Club | undefined }) {
  const { data: windowStatus } = useQuery<TransferWindowStatus>({
    queryKey: ["transfer-window", "status"],
    queryFn: () => api.get<TransferWindowStatus>("/transfers/window/status").then((r) => r.data),
    staleTime: 60_000,
    refetchInterval: 60_000,
  });

  if (!windowStatus?.enforced) return null;

  if (windowStatus.is_open && windowStatus.current_window) {
    const w = windowStatus.current_window;
    return (
      <div className="mb-6 flex items-center justify-between rounded-xl bg-emerald-500/10 px-5 py-3 ring-1 ring-emerald-500/20">
        <div className="flex items-center gap-3">
          <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse shrink-0" />
          <div>
            <span className="text-sm font-semibold text-emerald-300">{w.name}</span>
            <span className="ml-2 text-sm text-emerald-400/70">is open</span>
          </div>
        </div>
        <WindowCountdown closesAt={w.closes_at} />
      </div>
    );
  }

  // Window enforced but closed
  const next = windowStatus.next_window;
  return (
    <div className="mb-6 flex items-center justify-between rounded-xl bg-red-500/10 px-5 py-3 ring-1 ring-red-500/20">
      <div className="flex items-center gap-3">
        <span className="h-2 w-2 rounded-full bg-red-400 shrink-0" />
        <span className="text-sm font-semibold text-red-300">Transfer window is closed</span>
      </div>
      {next ? (
        <span className="text-xs text-slate-400">
          Next: <span className="text-white">{next.name}</span> opens {formatDate(next.opens_at)}
        </span>
      ) : (
        <span className="text-xs text-slate-500">No upcoming window scheduled</span>
      )}
    </div>
  );
}

// ── #3 Budget Panel ───────────────────────────────────────────────────────────

function BudgetBar({
  label, total, committed, remaining, colour,
}: {
  label: string; total: number; committed: number; remaining: number; colour: string;
}) {
  const spent   = Math.max(0, total - committed - remaining);
  const pctSpent     = total > 0 ? Math.round((spent / total) * 100)     : 0;
  const pctCommitted = total > 0 ? Math.round((committed / total) * 100) : 0;
  const pctFree      = Math.max(0, 100 - pctSpent - pctCommitted);

  return (
    <div>
      <div className="mb-1.5 flex items-center justify-between text-xs">
        <span className="font-semibold text-slate-300">{label}</span>
        <span className="tabular-nums text-slate-400">
          <span className={colour}>{formatCurrency(remaining)}</span> free of {formatCurrency(total)}
        </span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-slate-700">
        <div className="flex h-full">
          <div className="bg-slate-500 transition-all"   style={{ width: `${pctSpent}%` }} />
          <div className="bg-amber-500/70 transition-all" style={{ width: `${pctCommitted}%` }} />
          <div className={`${colour.replace("text-", "bg-")} opacity-70 transition-all`} style={{ width: `${pctFree}%` }} />
        </div>
      </div>
      <div className="mt-1 flex gap-3 text-[10px] text-slate-500">
        <span><span className="inline-block h-1.5 w-1.5 rounded-full bg-slate-500 mr-1" />Spent {formatCurrency(spent)}</span>
        <span><span className="inline-block h-1.5 w-1.5 rounded-full bg-amber-500/70 mr-1" />Committed {formatCurrency(committed)}</span>
        <span><span className={`inline-block h-1.5 w-1.5 rounded-full ${colour.replace("text-", "bg-")} opacity-70 mr-1`} />Free {formatCurrency(remaining)}</span>
      </div>
    </div>
  );
}

function BudgetPanel({ myClub }: { myClub: Club }) {
  const finance = myClub.finance;
  if (!finance) return null;

  return (
    <div className="rounded-2xl bg-slate-900 ring-1 ring-white/[0.08] px-5 py-4 space-y-4">
      <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">Budget</p>
      <BudgetBar
        label="Transfer"
        total={Number(finance.transfer_budget_total)}
        committed={Number(finance.transfer_committed)}
        remaining={Number(finance.transfer_remaining)}
        colour="text-emerald-400"
      />
      <BudgetBar
        label="Wages (weekly)"
        total={Number(finance.wage_budget_total_weekly)}
        committed={Number(finance.wage_committed_weekly)}
        remaining={Number(finance.wage_remaining_weekly)}
        colour="text-sky-400"
      />
    </div>
  );
}

// ── #4 Shortlist Pulse Panel ──────────────────────────────────────────────────

function ShortlistPulsePanel() {
  const navigate = useNavigate();
  const { data: hits, isLoading } = useQuery<ShortlistHit[]>({
    queryKey: ["scouting", "market-hits"],
    queryFn: () => api.get<ShortlistHit[]>("/scouting/market-hits").then((r) => r.data),
    staleTime: 60_000,
  });

  if (!isLoading && (!hits || hits.length === 0)) return null;

  return (
    <PanelShell
      title="Shortlist on Market"
      count={hits?.length}
      linkTo="/scouting/shortlists"
      linkLabel="View shortlists"
      loading={isLoading}
    >
      {hits && hits.length > 0 && (
        <div className="space-y-2">
          {hits.map((h) => (
            <div
              key={`${h.player_id}-${h.sale_id}`}
              onClick={() => navigate(`/sales/${h.sale_id}`)}
              className="flex items-center justify-between rounded-lg px-3 py-2.5 bg-amber-500/[0.06] hover:bg-amber-500/[0.1] cursor-pointer transition-colors ring-1 ring-amber-500/20"
            >
              <div className="min-w-0">
                <p className="text-sm font-medium text-white truncate">{h.player_name}</p>
                <div className="mt-0.5 flex items-center gap-2">
                  {h.position && (
                    <Badge variant={positionVariant(h.position as PlayerPosition)} className="text-[10px]">
                      {h.position}
                    </Badge>
                  )}
                  <span className="text-xs text-slate-500">from {h.shortlist_name}</span>
                </div>
              </div>
              <div className="text-right shrink-0 ml-3">
                <p className="text-sm font-semibold text-white tabular-nums">
                  {h.asking_price != null ? formatCurrency(h.asking_price) : "TBD"}
                </p>
                <p className="text-[10px] text-amber-400">{h.sale_type === "AUCTION" ? "Auction" : "Listed"}</p>
              </div>
            </div>
          ))}
        </div>
      )}
    </PanelShell>
  );
}

// ── #5 Expiring Contracts Panel ───────────────────────────────────────────────

function ExpiringContractsPanel() {
  const navigate = useNavigate();
  const { data: expiring, isLoading } = useQuery<ExpiringContractItem[]>({
    queryKey: ["clubs", "me", "expiring-contracts"],
    queryFn: () =>
      api.get<ExpiringContractItem[]>("/clubs/me/expiring-contracts", { params: { within_days: 180 } })
        .then((r) => r.data),
    staleTime: 300_000,
  });

  if (!isLoading && (!expiring || expiring.length === 0)) return null;

  return (
    <PanelShell
      title="Expiring Contracts"
      count={expiring?.length}
      linkTo="/club"
      linkLabel="View squad"
      loading={isLoading}
    >
      {expiring && expiring.length > 0 && (
        <div className="space-y-2">
          {expiring.map((item) => {
            const urgent = item.days_remaining <= 60;
            const warning = !urgent && item.days_remaining <= 120;
            return (
              <div
                key={item.player_id}
                onClick={() => navigate(`/players/market/${item.player_id}`)}
                className={`flex items-center justify-between rounded-lg px-3 py-2.5 cursor-pointer transition-colors ${
                  urgent  ? "bg-red-500/[0.06] ring-1 ring-red-500/20 hover:bg-red-500/10" :
                  warning ? "bg-amber-500/[0.06] ring-1 ring-amber-500/20 hover:bg-amber-500/10" :
                            "bg-slate-800/50 hover:bg-slate-800"
                }`}
              >
                <div className="min-w-0">
                  <p className="text-sm font-medium text-white truncate">{item.player_name}</p>
                  {item.position && (
                    <Badge variant={positionVariant(item.position as PlayerPosition)} className="mt-0.5 text-[10px]">
                      {item.position}
                    </Badge>
                  )}
                </div>
                <div className="text-right shrink-0 ml-3">
                  <p className={`text-sm font-semibold tabular-nums ${urgent ? "text-red-400" : warning ? "text-amber-400" : "text-slate-300"}`}>
                    {item.days_remaining}d
                  </p>
                  <p className="text-[10px] text-slate-500">{formatDate(item.end_date)}</p>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </PanelShell>
  );
}

// ── Existing panels (unchanged logic) ────────────────────────────────────────

function MyListingsPanel({ myClub }: { myClub: Club }) {
  const navigate = useNavigate();
  const { data, isLoading } = useQuery<Paginated<Sale>>({
    queryKey: ["dashboard", "my-sales"],
    queryFn: () =>
      api.get<Paginated<Sale>>("/sales", { params: { seller_club_id: myClub.id, status: "OPEN", page_size: 5 } })
        .then((r) => r.data),
  });
  return (
    <PanelShell title="My Open Listings" count={data?.total} linkTo="/sales/mine" linkLabel="View all" loading={isLoading}>
      {data?.items.length === 0 && <EmptyPanel message="No open listings." />}
      {data && data.items.length > 0 && (
        <div className="space-y-2">
          {data.items.map((sale) => (
            <div key={sale.id} onClick={() => navigate(`/sales/${sale.id}`)}
              className="flex items-center justify-between rounded-lg px-3 py-2.5 bg-slate-800/50 hover:bg-slate-800 cursor-pointer transition-colors">
              <div className="min-w-0">
                <p className="text-sm font-medium text-white truncate">{sale.player?.name ?? "—"}</p>
                <div className="mt-0.5 flex items-center gap-2">
                  <Badge variant={saleStatusVariant(sale.status)}>{saleTypeLabel(sale.sale_type)}</Badge>
                  {sale.bid_count > 0 && <span className="text-xs text-slate-500">{sale.bid_count} bid{sale.bid_count !== 1 ? "s" : ""}</span>}
                </div>
              </div>
              <div className="text-right shrink-0 ml-3">
                <p className="text-sm font-semibold text-white tabular-nums">
                  {sale.best_bid != null ? formatCurrency(sale.best_bid) : sale.asking_price != null ? formatCurrency(sale.asking_price) : "—"}
                </p>
                <DeadlineCell deadline={sale.deadline} />
              </div>
            </div>
          ))}
        </div>
      )}
    </PanelShell>
  );
}

function PendingOffersPanel() {
  const navigate = useNavigate();
  const { data: receivedSentData, isLoading: l1 } = useQuery<Paginated<Offer>>({
    queryKey: ["dashboard", "pending-offers-received-sent"],
    queryFn: () => api.get<Paginated<Offer>>("/offers/received", { params: { offer_status: "SENT", page_size: 5 } }).then((r) => r.data),
  });
  const { data: counteredData, isLoading: l2 } = useQuery<Paginated<Offer>>({
    queryKey: ["dashboard", "pending-offers-countered"],
    queryFn: () => api.get<Paginated<Offer>>("/offers/sent", { params: { offer_status: "COUNTERED", page_size: 5 } }).then((r) => r.data),
  });
  const { data: mySentData, isLoading: l3 } = useQuery<Paginated<Offer>>({
    queryKey: ["dashboard", "pending-offers-my-sent"],
    queryFn: () => api.get<Paginated<Offer>>("/offers/sent", { params: { offer_status: "SENT", page_size: 5 } }).then((r) => r.data),
  });
  const isLoading = l1 || l2 || l3;
  const pendingReceived = receivedSentData?.items ?? [];
  const awaitingResponse = counteredData?.items ?? [];
  const mySentPending = mySentData?.items ?? [];
  const totalActionable = (receivedSentData?.total ?? 0) + (counteredData?.total ?? 0) + (mySentData?.total ?? 0);

  return (
    <PanelShell title="Active Offers" count={totalActionable} linkTo="/offers/received" linkLabel="View all" loading={isLoading}>
      {totalActionable === 0 && <EmptyPanel message="No active offers." />}
      {pendingReceived.length > 0 && (
        <><p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-slate-500">Offers received</p>
        <div className="space-y-1.5 mb-4">
          {pendingReceived.map((offer) => (
            <div key={offer.id} onClick={() => navigate(`/offers/${offer.id}`)}
              className="flex items-center justify-between rounded-lg px-3 py-2.5 bg-slate-800/50 hover:bg-slate-800 cursor-pointer transition-colors">
              <div className="min-w-0">
                <p className="text-sm font-medium text-white truncate">{offer.player?.name ?? "—"}</p>
                <p className="text-xs text-slate-500 truncate">from <ClubLink id={offer.from_club?.id} name={offer.from_club?.name} /></p>
              </div>
              <div className="text-right shrink-0 ml-3">
                <p className="text-sm font-semibold text-white tabular-nums">{offer.fee_amount != null ? formatCurrency(offer.fee_amount) : "TBD"}</p>
                <Badge variant="info">Received</Badge>
              </div>
            </div>
          ))}
        </div></>
      )}
      {awaitingResponse.length > 0 && (
        <><p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-slate-500">Counter-offers — your response needed</p>
        <div className="space-y-1.5 mb-4">
          {awaitingResponse.map((offer) => (
            <div key={offer.id} onClick={() => navigate(`/offers/${offer.id}`)}
              className="flex items-center justify-between rounded-lg px-3 py-2.5 bg-amber-500/[0.06] hover:bg-amber-500/[0.1] cursor-pointer transition-colors ring-1 ring-amber-500/20">
              <div className="min-w-0">
                <p className="text-sm font-medium text-white truncate">{offer.player?.name ?? "—"}</p>
                <p className="text-xs text-amber-400/70 truncate">countered by <ClubLink id={offer.to_club?.id} name={offer.to_club?.name} /></p>
              </div>
              <div className="text-right shrink-0 ml-3">
                <p className="text-sm font-semibold text-white tabular-nums">{offer.fee_amount != null ? formatCurrency(offer.fee_amount) : "TBD"}</p>
                <span className="text-xs text-amber-400">Respond →</span>
              </div>
            </div>
          ))}
        </div></>
      )}
      {mySentPending.length > 0 && (
        <><p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-slate-500">Sent — awaiting response</p>
        <div className="space-y-1.5">
          {mySentPending.map((offer) => (
            <div key={offer.id} onClick={() => navigate(`/offers/${offer.id}`)}
              className="flex items-center justify-between rounded-lg px-3 py-2.5 bg-slate-800/50 hover:bg-slate-800 cursor-pointer transition-colors">
              <div className="min-w-0">
                <p className="text-sm font-medium text-white truncate">{offer.player?.name ?? "—"}</p>
                <p className="text-xs text-slate-500 truncate">to <ClubLink id={offer.to_club?.id} name={offer.to_club?.name} /></p>
              </div>
              <div className="text-right shrink-0 ml-3">
                <p className="text-sm font-semibold text-white tabular-nums">{offer.fee_amount != null ? formatCurrency(offer.fee_amount) : "TBD"}</p>
                <Badge variant="info">Sent</Badge>
              </div>
            </div>
          ))}
        </div></>
      )}
    </PanelShell>
  );
}

function ActiveDealsPanel() {
  const navigate = useNavigate();
  const { data, isLoading } = useQuery<Paginated<Deal>>({
    queryKey: ["dashboard", "active-deals"],
    queryFn: () =>
      api.get<Paginated<Deal>>("/deals", { params: { deal_status: "IN_PROGRESS", page_size: 5 } }).then((r) => r.data),
  });
  return (
    <PanelShell title="Active Deals" count={data?.total} linkTo="/deals" linkLabel="View all" loading={isLoading}>
      {data?.items.length === 0 && <EmptyPanel message="No active deals." />}
      {data && data.items.length > 0 && (
        <div className="space-y-2">
          {data.items.map((deal) => (
            <div key={deal.id} onClick={() => navigate(`/deals/${deal.id}`)}
              className="flex items-center justify-between rounded-lg px-3 py-2.5 bg-slate-800/50 hover:bg-slate-800 cursor-pointer transition-colors">
              <div className="min-w-0">
                <p className="text-sm font-medium text-white truncate">{deal.player?.name ?? "—"}</p>
                <p className="text-xs text-slate-500">{dealStageLabel(deal.stage)}</p>
              </div>
              <div className="text-right shrink-0 ml-3">
                <p className="text-sm font-semibold text-white tabular-nums">{formatCurrency(deal.agreed_fee)}</p>
                <Badge variant={dealStatusVariant(deal.status)}>{deal.status.replace(/_/g, " ")}</Badge>
              </div>
            </div>
          ))}
        </div>
      )}
    </PanelShell>
  );
}

const POSITION_TARGETS = [
  { pos: "GK",  min: 2, label: "Goalkeepers", colour: "text-amber-400",   filterColour: "bg-amber-500/20 text-amber-300 ring-amber-500/30" },
  { pos: "DEF", min: 4, label: "Defenders",   colour: "text-blue-400",    filterColour: "bg-blue-500/20 text-blue-300 ring-blue-500/30" },
  { pos: "MID", min: 4, label: "Midfielders", colour: "text-emerald-400", filterColour: "bg-emerald-500/20 text-emerald-300 ring-emerald-500/30" },
  { pos: "FWD", min: 3, label: "Forwards",    colour: "text-red-400",     filterColour: "bg-red-500/20 text-red-300 ring-red-500/30" },
];

function SquadGapPanel({ myClub }: { myClub: Club }) {
  const navigate = useNavigate();
  const { data: squadData } = useQuery<Paginated<Player>>({
    queryKey: ["clubs", myClub.id, "squad-gap"],
    queryFn: () =>
      api.get<Paginated<Player>>(`/clubs/${myClub.id}/players`, { params: { page_size: 100 } }).then((r) => r.data),
  });
  const players = squadData?.items ?? [];
  const counts = Object.fromEntries(POSITION_TARGETS.map((t) => [t.pos, players.filter((p) => p.position === t.pos).length]));
  const gaps = POSITION_TARGETS.filter((t) => (counts[t.pos] ?? 0) < t.min);
  if (!squadData || gaps.length === 0) return null;
  return (
    <PanelShell title="Squad Needs" linkTo="/players/market" linkLabel="Browse all">
      <div className="space-y-2">
        {gaps.map((g) => {
          const have = counts[g.pos] ?? 0;
          const need = g.min - have;
          return (
            <button key={g.pos} onClick={() => navigate(`/players/market?position=${g.pos}`)}
              className="flex w-full items-center justify-between rounded-lg px-3 py-2.5 bg-slate-800/50 hover:bg-slate-800 transition-colors group">
              <div className="flex items-center gap-3">
                <span className={`rounded px-1.5 py-0.5 text-xs font-bold ring-1 ${g.filterColour}`}>{g.pos}</span>
                <div className="text-left">
                  <p className="text-sm font-medium text-white">{g.label}</p>
                  <p className="text-xs text-slate-500">{have} / {g.min} minimum</p>
                </div>
              </div>
              <span className={`text-sm font-bold tabular-nums ${g.colour}`}>Need {need}</span>
            </button>
          );
        })}
      </div>
    </PanelShell>
  );
}

// ── Recent Completed Deals Panel ──────────────────────────────────────────────

function RecentCompletedDealsPanel() {
  const navigate = useNavigate();
  const { data, isLoading } = useQuery<Paginated<Deal>>({
    queryKey: ["dashboard", "completed-deals"],
    queryFn: () =>
      api.get<Paginated<Deal>>("/deals", { params: { deal_status: "COMPLETED", page_size: 10 } })
        .then((r) => r.data),
    staleTime: 120_000,
  });

  const deals = data?.items ?? [];

  return (
    <PanelShell
      title="Completed Transfers"
      count={data?.total}
      linkTo="/deals"
      linkLabel="View all"
      loading={isLoading}
    >
      {deals.length === 0 && !isLoading && <EmptyPanel message="No completed transfers yet." />}
      {deals.length > 0 && (
        <div className="overflow-x-auto -mx-1">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[10px] font-semibold uppercase tracking-wider text-slate-500 border-b border-white/[0.05]">
                <th className="pb-2 pr-4 text-left font-semibold">Player</th>
                <th className="pb-2 pr-4 text-left font-semibold">From</th>
                <th className="pb-2 pr-4 text-left font-semibold">To</th>
                <th className="pb-2 pr-4 text-right font-semibold">Fee</th>
                <th className="pb-2 text-right font-semibold">Completed</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/[0.04]">
              {deals.map((deal) => (
                <tr
                  key={deal.id}
                  onClick={() => navigate(`/deals/${deal.id}`)}
                  className="cursor-pointer hover:bg-white/[0.02] transition-colors group"
                >
                  <td className="py-2.5 pr-4">
                    <span className="font-medium text-white group-hover:text-emerald-400 transition-colors">
                      {deal.player?.name ?? "—"}
                    </span>
                    {deal.player?.position && (
                      <span className="ml-2 text-[10px] text-slate-500">{deal.player.position}</span>
                    )}
                  </td>
                  <td className="py-2.5 pr-4 text-slate-400 text-xs">
                    {deal.seller_club ? (
                      <ClubLink id={deal.seller_club.id} name={deal.seller_club.name} />
                    ) : (
                      <span className="text-slate-600">Free agent</span>
                    )}
                  </td>
                  <td className="py-2.5 pr-4 text-slate-400 text-xs">
                    {deal.buyer_club ? (
                      <ClubLink id={deal.buyer_club.id} name={deal.buyer_club.name} />
                    ) : "—"}
                  </td>
                  <td className="py-2.5 pr-4 text-right font-semibold tabular-nums text-white">
                    {formatCurrency(deal.agreed_fee)}
                  </td>
                  <td className="py-2.5 text-right text-xs text-slate-500 tabular-nums">
                    {deal.completed_at ? formatDate(deal.completed_at) : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {(data?.total ?? 0) > 10 && (
            <p className="mt-3 text-center text-xs text-slate-500">
              Showing 10 of {data!.total} completed deals.{" "}
              <button onClick={() => navigate("/deals")} className="text-emerald-400 hover:underline">
                View all →
              </button>
            </p>
          )}
        </div>
      )}
    </PanelShell>
  );
}

function StatCard({ label, value, sub, colour }: { label: string; value: string | number; sub?: string; colour: string }) {
  return (
    <div className="rounded-2xl bg-slate-900 px-5 py-4 ring-1 ring-white/[0.08]">
      <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">{label}</p>
      <p className={`mt-1 text-2xl font-bold tabular-nums ${colour}`}>{value}</p>
      {sub && <p className="mt-0.5 text-xs text-slate-500">{sub}</p>}
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function DashboardPage() {
  const { data: myClub, isLoading: clubLoading } = useQuery<Club>({
    queryKey: ["clubs", "me"],
    queryFn: () => api.get<Club>("/clubs/me").then((r) => r.data),
    staleTime: 60_000,
  });

  const { data: openSales } = useQuery<Paginated<Sale>>({
    queryKey: ["dashboard", "open-sales-count"],
    queryFn: () =>
      api.get<Paginated<Sale>>("/sales", { params: { seller_club_id: myClub?.id, status: "OPEN", page_size: 1 } }).then((r) => r.data),
    enabled: !!myClub,
  });

  const { data: pendingOffers } = useQuery<Paginated<Offer>>({
    queryKey: ["dashboard", "pending-offers-count"],
    queryFn: async () => {
      const [a, b, c] = await Promise.all([
        api.get<Paginated<Offer>>("/offers/received", { params: { offer_status: "SENT", page_size: 1 } }),
        api.get<Paginated<Offer>>("/offers/sent",     { params: { offer_status: "COUNTERED", page_size: 1 } }),
        api.get<Paginated<Offer>>("/offers/sent",     { params: { offer_status: "SENT", page_size: 1 } }),
      ]);
      return { ...a.data, total: a.data.total + b.data.total + c.data.total };
    },
  });

  const { data: activeDeals } = useQuery<Paginated<Deal>>({
    queryKey: ["dashboard", "active-deals-count"],
    queryFn: () =>
      api.get<Paginated<Deal>>("/deals", { params: { deal_status: "IN_PROGRESS", page_size: 1 } }).then((r) => r.data),
  });

  if (clubLoading) {
    return <div className="flex items-center justify-center py-20"><Spinner size="lg" /></div>;
  }

  const finance = myClub?.finance;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white">War Room</h1>
        {myClub && (
          <p className="mt-0.5 text-sm text-slate-400">
            {myClub.name}{myClub.league_name && ` · ${myClub.league_name}`}
          </p>
        )}
      </div>

      {/* Transfer window banner */}
      <TransferWindowBanner myClub={myClub} />

      {/* Urgent actions */}
      {myClub && <UrgentActionsPanel />}

      {/* Stat cards */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
        <StatCard label="Open listings"   value={openSales?.total ?? "—"} colour="text-emerald-400" />
        <StatCard label="Action required" value={pendingOffers?.total ?? "—"} sub="offers need response" colour="text-sky-400" />
        <StatCard label="Active deals"    value={activeDeals?.total ?? "—"} colour="text-amber-400" />
      </div>

      {myClub ? (
        <div className="space-y-6">
          {/* Budget */}
          <BudgetPanel myClub={myClub} />

          {/* Main panels */}
          <div className="grid gap-6 lg:grid-cols-3">
            <MyListingsPanel myClub={myClub} />
            <PendingOffersPanel />
            <ActiveDealsPanel />
          </div>

          {/* Secondary panels */}
          <div className="grid gap-6 lg:grid-cols-3">
            <SquadGapPanel myClub={myClub} />
            <ShortlistPulsePanel />
            <ExpiringContractsPanel />
          </div>

          {/* Completed transfers */}
          <RecentCompletedDealsPanel />
        </div>
      ) : (
        <div className="rounded-xl bg-slate-900 px-5 py-8 text-center ring-1 ring-white/[0.08]">
          <p className="text-sm text-slate-400">No club profile found. Contact TransferX staff.</p>
        </div>
      )}
    </div>
  );
}
