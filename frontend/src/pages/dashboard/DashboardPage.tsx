import { useNavigate } from "react-router-dom";
import OnboardingChecklist from "../../components/OnboardingChecklist";
import { useQuery } from "@tanstack/react-query";
import api from "../../lib/api";
import type {
  Club,
  Deal,
  ExpiringContractItem,
  Offer,
  Paginated,
  PendingApproval,
  Player,
  Sale,
  ShortlistHit,
  TransferWindowStatus,
} from "../../types/api";
import Card from "../../components/ui/Card";
import ClubLink from "../../components/ui/ClubLink";
import PageHeader from "../../components/ui/PageHeader";
import ResponsiveTable, { type ResponsiveColumn } from "../../components/ui/ResponsiveTable";
import Spinner from "../../components/ui/Spinner";
import TransferWindowBanner from "../../components/transfers/TransferWindowBanner";
import { formatCurrency, formatDate } from "../../lib/utils";
import { useAuth } from "../../hooks/useAuth";
import { useClubCapabilities } from "../../hooks/useClubCapabilities";
import { ScoutReportPanel } from "../../components/ai/ScoutReportPanel";
import { dealWhoseMove, offerWhoseMove, saleWhoseMove } from "../../lib/whoseMove";
import WaitingOnYouBand, { type WaitingItem } from "../../components/dashboard/WaitingOnYouBand";
import { useClubDashboard } from "../../hooks/useClubDashboard";
import type { DashboardItem } from "../../types/api";

// B2 returns the situation in `reason`; the button verb comes from the kind.
const WAITING_ACTION_LABEL: Record<DashboardItem["kind"], string> = {
  approval: "Review",
  offer:    "Respond",
  deal:     "Open",
  sale:     "Review bids",
};

const WAITING_FALLBACK_TITLE: Record<DashboardItem["kind"], string> = {
  approval: "Approval request",
  offer:    "Offer",
  deal:     "Deal",
  sale:     "Listing",
};
import FigureCard from "../../components/dashboard/FigureCard";
import WorkingPanel from "../../components/dashboard/WorkingPanel";
import ReferencePanel from "../../components/dashboard/ReferencePanel";

// ── Tier 2 — Standing figures ────────────────────────────────────────────────

function StandingFiguresTier({ myClub, squadCount, squadNote, windowStatus }: {
  myClub: Club; squadCount: number; squadNote: string; windowStatus?: TransferWindowStatus;
}) {
  const finance = myClub.finance;
  const transferFree = finance ? Number(finance.transfer_remaining) : 0;
  const transferTotal = finance ? Number(finance.transfer_budget_total) : 0;
  const wageFree = finance ? Number(finance.wage_remaining_weekly) : 0;
  const wageTotal = finance ? Number(finance.wage_budget_total_weekly) : 0;

  const windowLabel = !windowStatus?.enforced
    ? "No window enforced"
    : windowStatus.is_open && windowStatus.current_window
    ? windowStatus.current_window.name
    : "Closed";

  return (
    <div className="mb-[18px] grid gap-3.5" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))" }}>
      <FigureCard
        label="Transfer budget free"
        value={formatCurrency(transferFree)}
        note={`of ${formatCurrency(transferTotal)}`}
        bar={{ pct: transferTotal > 0 ? (transferFree / transferTotal) * 100 : 0, colour: "bg-success" }}
      />
      <FigureCard
        label="Wage room / wk"
        value={formatCurrency(wageFree)}
        note={`of ${formatCurrency(wageTotal)}`}
        bar={{ pct: wageTotal > 0 ? (wageFree / wageTotal) * 100 : 0, colour: "bg-accent" }}
      />
      <FigureCard label="Window closes in" value={windowLabel} note={myClub.league_name ?? undefined} />
      <FigureCard label="Squad" value={String(squadCount)} note={squadNote} />
    </div>
  );
}

const POSITION_TARGETS = [
  { pos: "GK", min: 2, label: "Goalkeepers" },
  { pos: "DEF", min: 4, label: "Defenders" },
  { pos: "MID", min: 4, label: "Midfielders" },
  { pos: "FWD", min: 3, label: "Forwards" },
];

// ── Completed transfers ──────────────────────────────────────────────────────

interface CompletedRow { id: string; player: string; position: string | null; from: Deal["seller_club"]; to: Deal["buyer_club"]; fee: number; completedAt: string | null; }

function CompletedTransfersTable({ deals, total }: { deals: Deal[]; total: number }) {
  const navigate = useNavigate();
  const rows: CompletedRow[] = deals.map((d) => ({
    id: d.id, player: d.player?.name ?? "—", position: d.player?.position ?? null,
    from: d.seller_club, to: d.buyer_club, fee: d.agreed_fee, completedAt: d.completed_at,
  }));

  const columns: ResponsiveColumn<CompletedRow>[] = [
    { key: "player", header: "Player", priority: 1, render: (r) => (
      <span className="font-medium text-text">{r.player}{r.position && <span className="ml-2 text-xs text-text-muted">{r.position}</span>}</span>
    ) },
    { key: "from", header: "From", priority: 4, render: (r) => r.from ? <ClubLink id={r.from.id} name={r.from.name} /> : <span className="text-text-muted">Free agent</span> },
    { key: "to", header: "To", priority: 3, render: (r) => r.to ? <ClubLink id={r.to.id} name={r.to.name} /> : "—" },
    { key: "fee", header: "Fee", priority: 2, className: "text-right", render: (r) => <span className="font-bold text-text">{formatCurrency(r.fee)}</span> },
    { key: "completed", header: "Completed", priority: 5, className: "text-right", render: (r) => <span className="text-text-muted text-xs">{r.completedAt ? formatDate(r.completedAt) : "—"}</span> },
  ];

  if (rows.length === 0) return null;

  return (
    <div>
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-lg font-bold text-text">Completed transfers</h2>
        {total > rows.length && (
          <button onClick={() => navigate("/deals")} className="text-xs font-semibold text-accent hover:text-accent-hover">
            View all {total} →
          </button>
        )}
      </div>
      <ResponsiveTable
        columns={columns}
        rows={rows}
        rowKey={(r) => r.id}
        onRowClick={(r) => navigate(`/deals/${r.id}`)}
        renderCard={(r) => (
          <div className="px-4 py-3">
            <div className="flex items-center justify-between">
              <span className="text-sm font-semibold text-text">{r.player}{r.position && <span className="ml-1.5 text-xs text-text-muted">{r.position}</span>}</span>
              <span className="text-sm font-bold text-text">{formatCurrency(r.fee)}</span>
            </div>
            <p className="mt-0.5 text-xs text-text-muted">
              {r.from ? r.from.name : "Free agent"} → {r.to ? r.to.name : "—"}
            </p>
            {r.completedAt && <p className="mt-0.5 text-xs text-text-muted">{formatDate(r.completedAt)}</p>}
          </div>
        )}
      />
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function DashboardPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const { can } = useClubCapabilities();

  const { data: myClub, isLoading: clubLoading } = useQuery<Club>({
    queryKey: ["clubs", "me"],
    queryFn: () => api.get<Club>("/clubs/me").then((r) => r.data),
    staleTime: 60_000,
  });

  const { data: windowStatus } = useQuery<TransferWindowStatus>({
    queryKey: ["transfer-window", "status"],
    queryFn: () => api.get<TransferWindowStatus>("/transfers/window/status").then((r) => r.data),
    staleTime: 60_000,
  });

  const { data: openSales } = useQuery<Paginated<Sale>>({
    queryKey: ["dashboard", "my-sales"],
    queryFn: () => api.get<Paginated<Sale>>("/sales", { params: { seller_club_id: myClub?.id, status: "OPEN", page_size: 20 } }).then((r) => r.data),
    enabled: !!myClub,
  });

  const { data: receivedOffers } = useQuery<Paginated<Offer>>({
    queryKey: ["dashboard", "offers-received"],
    queryFn: () => api.get<Paginated<Offer>>("/offers/received", { params: { page_size: 20 } }).then((r) => r.data),
    enabled: !!myClub,
  });

  const { data: sentOffers } = useQuery<Paginated<Offer>>({
    queryKey: ["dashboard", "offers-sent"],
    queryFn: () => api.get<Paginated<Offer>>("/offers/sent", { params: { page_size: 20 } }).then((r) => r.data),
    enabled: !!myClub,
  });

  const { data: activeDeals } = useQuery<Paginated<Deal>>({
    queryKey: ["dashboard", "active-deals"],
    queryFn: () => api.get<Paginated<Deal>>("/deals", { params: { deal_status: "IN_PROGRESS", page_size: 20 } }).then((r) => r.data),
    enabled: !!myClub,
  });

  const { data: completedDeals } = useQuery<Paginated<Deal>>({
    queryKey: ["dashboard", "completed-deals"],
    queryFn: () => api.get<Paginated<Deal>>("/deals", { params: { deal_status: "COMPLETED", page_size: 3 } }).then((r) => r.data),
    staleTime: 120_000,
  });

  const { data: squadData } = useQuery<Paginated<Player>>({
    queryKey: ["clubs", myClub?.id, "squad"],
    queryFn: () => api.get<Paginated<Player>>(`/clubs/${myClub!.id}/players`, { params: { page_size: 100 } }).then((r) => r.data),
    enabled: !!myClub,
  });

  const { data: shortlistHits } = useQuery<ShortlistHit[]>({
    queryKey: ["scouting", "market-hits"],
    queryFn: () => api.get<ShortlistHit[]>("/scouting/market-hits").then((r) => r.data),
    staleTime: 60_000,
  });

  const { data: expiringContracts } = useQuery<ExpiringContractItem[]>({
    queryKey: ["clubs", "me", "expiring-contracts"],
    queryFn: () => api.get<ExpiringContractItem[]>("/clubs/me/expiring-contracts", { params: { within_days: 180 } }).then((r) => r.data),
    staleTime: 300_000,
  });

  // Phase 4c: Sporting Director/Owner (APPROVE_ACTIONS) get pending team
  // requests in Tier 1 — genuinely their move. Managers/other staff get a
  // quiet pointer to their own pending requests instead, since nothing here
  // is waiting on them to decide (README.md's Tier 1 definition).
  const { data: pendingApprovals } = useQuery<PendingApproval[]>({
    queryKey: ["clubs", "me", "approvals", "PENDING"],
    queryFn: () => api.get<PendingApproval[]>("/clubs/me/approvals", { params: { approval_status: "PENDING" } }).then((r) => r.data),
    enabled: !!myClub,
  });

  // Shares its cache entry with the sidebar's badges — same key, one request.
  const { data: dashboard } = useClubDashboard(!!myClub);

  if (clubLoading) {
    return <div className="flex items-center justify-center py-20"><Spinner size="lg" /></div>;
  }

  if (!myClub) {
    return (
      <Card tier={4}>
        <p className="text-sm text-text-muted">No club profile found. Contact TransferX staff.</p>
      </Card>
    );
  }

  const myClubId = myClub.id;
  const sales = openSales?.items ?? [];
  // /offers/received and /offers/sent return every status when unfiltered;
  // offerWhoseMove only ever resolves "neither" for a terminal status, so
  // this doubles as the active-offers filter without a second status list.
  const offers = [...(receivedOffers?.items ?? []), ...(sentOffers?.items ?? [])]
    .filter((o) => offerWhoseMove(o, myClubId) !== "neither");
  const deals = activeDeals?.items ?? [];
  const players = squadData?.items ?? [];
  const isApprover = can("APPROVE_ACTIONS");
  const approvals = pendingApprovals ?? [];
  const myPendingApprovals = approvals.filter((a) => a.requested_by_user_id === user?.id);

  // ── Tier 1 ──
  // Server-derived (B2). This was four separate client-side whose-move passes
  // over the queries below; those queries stay because tiers 2-4 need their
  // rows, but the *verdict* now comes from one place — otherwise the sidebar
  // badge and this band can disagree while both are "right".
  const waitingItems: WaitingItem[] = (dashboard?.waiting_on_you ?? []).map((item) => ({
    key: `${item.kind}-${item.id}`,
    title: item.player_name ?? WAITING_FALLBACK_TITLE[item.kind],
    description: item.club_name ? `${item.reason} · ${item.club_name}` : item.reason,
    amount: item.amount,
    deadline: item.deadline,
    actionLabel: WAITING_ACTION_LABEL[item.kind],
    onClick: () => navigate(item.link),
  }));

  // ── Tier 2 ──
  const posCounts = Object.fromEntries(POSITION_TARGETS.map((t) => [t.pos, players.filter((p) => p.position === t.pos).length]));
  const gaps = POSITION_TARGETS.filter((t) => (posCounts[t.pos] ?? 0) < t.min);
  const squadNote = gaps.length > 0 ? `${gaps.length} position gap${gaps.length === 1 ? "" : "s"}` : "Fully covered";

  // ── Tier 3 ──
  const listingRows = sales.slice(0, 3).map((s) => ({
    key: s.id, onClick: () => navigate(`/sales/${s.id}`),
    name: s.player?.name ?? "—", sub: s.bid_count ? `${s.bid_count} bid${s.bid_count === 1 ? "" : "s"}` : "No bids yet",
    value: s.best_bid != null ? formatCurrency(s.best_bid) : s.asking_price != null ? formatCurrency(s.asking_price) : "—",
    move: saleWhoseMove(s),
  }));
  const offerRows = offers.slice(0, 3).map((o) => ({
    key: o.id, onClick: () => navigate(`/offers/${o.id}`),
    name: o.player?.name ?? "—",
    sub: o.from_club_id === myClubId ? `to ${o.to_club?.name ?? "—"}` : `from ${o.from_club?.name ?? "—"}`,
    value: o.fee_amount != null ? formatCurrency(o.fee_amount) : "TBD",
    move: offerWhoseMove(o, myClubId),
  }));
  const dealRows = deals.slice(0, 3).map((d) => ({
    key: d.id, onClick: () => navigate(`/deals/${d.id}`),
    name: d.player?.name ?? "—", sub: d.stage.replace(/_/g, " ").toLowerCase(),
    value: formatCurrency(d.agreed_fee), move: dealWhoseMove(d, myClubId),
  }));

  // ── Tier 4 ──
  const squadNeedRows = gaps.map((g) => ({
    key: g.pos, onClick: () => navigate(`/players/market?position=${g.pos}`),
    label: g.label, sub: `${posCounts[g.pos] ?? 0} of ${g.min} minimum`,
    value: `Need ${g.min - (posCounts[g.pos] ?? 0)}`, valueColour: "text-danger-text",
  }));
  const shortlistRows = (shortlistHits ?? []).slice(0, 5).map((h) => ({
    key: `${h.player_id}-${h.sale_id}`, onClick: () => navigate(`/sales/${h.sale_id}`),
    label: h.player_name, sub: h.shortlist_name,
    value: h.asking_price != null ? formatCurrency(h.asking_price) : "TBD", valueColour: "text-warning-text",
  }));
  const expiringRows = (expiringContracts ?? []).slice(0, 5).map((c) => ({
    key: c.player_id, onClick: () => navigate(`/players/market/${c.player_id}`),
    label: c.player_name, sub: formatDate(c.end_date),
    value: `${c.days_remaining}d`, valueColour: c.days_remaining <= 60 ? "text-danger-text" : c.days_remaining <= 120 ? "text-warning-text" : "text-text-secondary",
  }));

  return (
    <div>
      <PageHeader
        title="War Room"
        subtitle={`${myClub.name}${myClub.league_name ? ` · ${myClub.league_name}` : ""}`}
      />

      <TransferWindowBanner />
      <OnboardingChecklist />

      <WaitingOnYouBand items={waitingItems} />

      {!isApprover && myPendingApprovals.length > 0 && (
        <button
          onClick={() => navigate("/club/approvals")}
          className="mb-[18px] block text-sm text-text-muted hover:text-text-secondary transition-colors"
        >
          {myPendingApprovals.length} of your request{myPendingApprovals.length === 1 ? "" : "s"} {myPendingApprovals.length === 1 ? "is" : "are"} awaiting approval →
        </button>
      )}

      <StandingFiguresTier
        myClub={myClub}
        squadCount={players.length}
        squadNote={squadNote}
        windowStatus={windowStatus}
      />

      <div className="mb-[18px] grid gap-4" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))" }}>
        <WorkingPanel title="My open listings" linkTo="/sales/mine" rows={listingRows} />
        <WorkingPanel title="Active offers" linkTo="/offers/received" rows={offerRows} />
        <WorkingPanel title="Active deals" linkTo="/deals" rows={dealRows} />
      </div>

      <div className="mb-[18px] grid gap-4" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))" }}>
        <ReferencePanel title="Squad needs" linkTo="/players/market" linkLabel="Browse" rows={squadNeedRows} />
        <ReferencePanel title="Shortlist on market" linkTo="/scouting/shortlists" linkLabel="View" rows={shortlistRows} />
        <ReferencePanel title="Expiring contracts" linkTo="/club" linkLabel="View squad" rows={expiringRows} />
      </div>

      <div className="mb-[18px]">
        <ScoutReportPanel />
      </div>

      <CompletedTransfersTable deals={completedDeals?.items ?? []} total={completedDeals?.total ?? 0} />
    </div>
  );
}
