import { useCallback, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import api from "../../lib/api";
import type {
  Club, Deal, ExpiringContractItem, Paginated, PendingApproval, Player, ShortlistHit, TransferWindowStatus,
} from "../../types/api";
import type { Board } from "../../components/board/types";
import Card from "../../components/ui/Card";
import Spinner from "../../components/ui/Spinner";
import Sheet from "../../components/ui/Sheet";
import Button from "../../components/ui/Button";
import TransferWindowBanner from "../../components/transfers/TransferWindowBanner";
import DeadlineBanner from "../../components/deadline/DeadlineBanner";
import { ClubChecklist, useOnboardingSteps } from "../../components/OnboardingChecklist";
import { useNamePrompt } from "../../components/account/NamePrompt";
import ClubBand from "../../components/dashboard/ClubBand";
import NeedsYouCard from "../../components/dashboard/NeedsYouCard";
import MoneyCard from "../../components/dashboard/MoneyCard";
import TeamCards from "../../components/dashboard/TeamCards";
import TransfersInProgress from "../../components/dashboard/TransfersInProgress";
import MarketForYou from "../../components/dashboard/MarketForYou";
import RecentlyCompleted from "../../components/dashboard/RecentlyCompleted";
import { squadSummary } from "../../components/dashboard/squadSummary";
import { ScoutReportPanel } from "../../components/ai/ScoutReportPanel";
import { BriefingCard } from "../../components/ai/Assistant";
import ListPlayerModal from "../../components/sales/ListPlayerModal";
import { useAuth } from "../../hooks/useAuth";
import { useClubCapabilities } from "../../hooks/useClubCapabilities";
import { useClubDashboard } from "../../hooks/useClubDashboard";
import { useOpenListings } from "../../hooks/useListing";
import { useMediaQuery } from "../../hooks/useMediaQuery";
import { timeLeft } from "../../lib/timeLeft";

/** The band's window pill (feature_spec/club-dashboard §4.1). */
export function windowText(status: TransferWindowStatus | undefined): string | null {
  if (!status) return null;
  if (!status.enforced) return "Window: no deadline set";
  if (status.is_open && status.current_window) {
    const left = timeLeft(status.current_window.closes_at);
    return left ? `${status.current_window.name} · ${left.text}` : status.current_window.name;
  }
  return "Window closed";
}

/** Money held for these: the buying side's open offers and deals. */
const HOLDING = new Set(["offers", "fee_agreed", "terms", "paperwork"]);

/**
 * The club's front door (feature_spec/club-dashboard): its band, then what
 * needs you, money, the squad, transfers in progress, the market and recent
 * activity. Queries and layout only; each block is its own component.
 *
 * One grid, each block rendered once. Below 1280px it's one column (the
 * market and recent cards side by side from 768px), ordered by `order`:
 * phones end market, scout report, briefing, recent; from 640px market,
 * recent, briefing, scout report. From 1280px blocks are placed in two columns.
 */
export default function DashboardPage() {
  const { user } = useAuth();
  const { can } = useClubCapabilities();
  const sm = useMediaQuery("(min-width: 640px)");

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
  // The Transfers board's own query: same key, one cache entry.
  const { data: board } = useQuery<Board>({
    queryKey: ["board", "BOTH"],
    queryFn: () => api.get<Board>("/board", { params: { side: "BOTH" } }).then((r) => r.data),
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
  const isApprover = can("APPROVE_ACTIONS");
  // Someone who doesn't approve sees their own requests waiting on an approver.
  const { data: pendingApprovals } = useQuery<PendingApproval[]>({
    queryKey: ["clubs", "me", "approvals", "PENDING"],
    queryFn: () => api.get<PendingApproval[]>("/clubs/me/approvals", { params: { approval_status: "PENDING" } }).then((r) => r.data),
    enabled: !!myClub,
  });
  // Shares its cache entry with the sidebar's badges: same key, one request.
  const { data: dashboard } = useClubDashboard(!!myClub);
  const { byPlayer: listedIds } = useOpenListings(myClub?.id);
  const onboarding = useOnboardingSteps();
  const namePrompt = useNamePrompt();

  const [listTarget, setListTarget] = useState<{ id: string; name: string } | null>(null);
  const closeList = useCallback(() => setListTarget(null), []);
  const [setupOpen, setSetupOpen] = useState(false);

  if (clubLoading) {
    return <div className="flex items-center justify-center py-20"><Spinner size="lg" /></div>;
  }
  if (!myClub) {
    return (
      <Card tier={4}>
        <p className="text-small text-text-muted">No club profile found. Contact TransferX staff.</p>
      </Card>
    );
  }

  const waiting = dashboard?.waiting_on_you ?? [];
  const myPending = isApprover ? 0 : (pendingApprovals ?? []).filter((a) => a.requested_by_user_id === user?.id).length;
  const expiringSoon = (expiringContracts ?? [])
    .filter((c) => c.days_remaining <= 60 && !listedIds.has(c.player_id))
    .map((c) => ({ player_id: c.player_id, player_name: c.player_name, days_remaining: c.days_remaining }));
  const committedNames = (board?.columns ?? [])
    .filter((col) => HOLDING.has(col.key))
    .flatMap((col) => col.cards)
    .filter((c) => c.side === "BUYING")
    .map((c) => c.player_name);
  const teams = [{
    key: "first",
    name: "First team",
    summary: squadSummary(squadData?.items ?? [], expiringContracts ?? []),
  }];

  return (
    <div className="space-y-4 xl:space-y-5">
      <ClubBand
        club={myClub}
        firstName={user?.first_name ?? null}
        waitingCount={waiting.length}
        windowText={windowText(windowStatus)}
        canAddColours={can("CLUB_ADMIN")}
      />
      {/* Banners sit between the band and Needs you, unchanged; empty ones take no space. */}
      <div className="empty:hidden [&>*]:mb-0">
        <TransferWindowBanner />
        <DeadlineBanner />
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-[minmax(0,1.55fr)_minmax(0,1fr)] xl:gap-5">
        <div className="order-1 md:col-span-2 xl:order-none xl:col-span-1 xl:col-start-1 xl:row-start-1">
          <NeedsYouCard
            items={waiting}
            myPendingApprovals={myPending}
            expiring={expiringSoon}
            onList={can("MARKET_WRITE") ? (c) => setListTarget({ id: c.player_id, name: c.player_name }) : undefined}
            setup={onboarding ? { done: onboarding.done, total: onboarding.steps.length } : null}
            onOpenSetup={() => setSetupOpen(true)}
            namePrompt={namePrompt}
          />
        </div>
        <div className="order-2 md:col-span-2 xl:order-none xl:col-span-1 xl:col-start-2 xl:row-start-1">
          <MoneyCard finance={myClub.finance} committedNames={committedNames} />
        </div>
        <div className="order-3 md:col-span-2 xl:order-none xl:row-start-2">
          <TeamCards teams={teams} />
        </div>
        <div className="order-4 self-start md:col-span-2 xl:order-none xl:col-span-1 xl:col-start-1 xl:row-start-3">
          <TransfersInProgress board={board} />
        </div>
        {/* The right column from 1280px. Below that it isn't a box at all
            (display: contents), so its cards take their places in the one
            column by `order`. */}
        <div className="contents xl:col-start-2 xl:row-start-3 xl:flex xl:flex-col xl:gap-5 xl:self-start">
          <div className="order-7 empty:hidden md:col-span-2 xl:order-none">
            <BriefingCard />
          </div>
          <div className="order-5 empty:hidden xl:order-none">
            <MarketForYou hits={shortlistHits ?? []} />
          </div>
          <div className="order-6 empty:hidden sm:order-8 md:col-span-2 xl:order-none">
            <ScoutReportPanel />
          </div>
          <div className="order-8 empty:hidden sm:order-6 xl:order-none">
            <RecentlyCompleted deals={completedDeals?.items ?? []} myClubId={myClub.id} limit={sm ? 2 : 1} />
          </div>
        </div>
      </div>

      <ListPlayerModal open={!!listTarget} onClose={closeList} player={listTarget ?? undefined} />
      <Sheet open={setupOpen} onClose={() => setSetupOpen(false)} title="Finish setting up" closeLabel="Close"
        footer={<Button variant="secondary" onClick={() => setSetupOpen(false)}>Close</Button>}>
        <ClubChecklist onDismiss={() => setSetupOpen(false)} />
      </Sheet>
    </div>
  );
}
