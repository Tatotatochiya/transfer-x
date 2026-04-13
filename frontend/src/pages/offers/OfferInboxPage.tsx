import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import api from "../../lib/api";
import type { Offer, Paginated } from "../../types/api";
import type { OfferStatus } from "../../types/enums";
import Badge from "../../components/ui/Badge";
import ClubLink from "../../components/ui/ClubLink";
import EmptyState from "../../components/ui/EmptyState";
import PageHeader from "../../components/ui/PageHeader";
import Pagination from "../../components/ui/Pagination";
import { ListSkeleton } from "../../components/ui/Skeleton";
import { offerStatusVariant, positionVariant } from "../../lib/badges";
import { formatCurrency, formatDate } from "../../lib/utils";

// ── Types ──────────────────────────────────────────────────────────────────────

type PlayerGroup = {
  playerId: string;
  playerName: string;
  position: string | null;
  offers: Offer[];
  activeCount: number;
  bestFee: number | null;
  latestActivity: string;
};

// ── Helpers ────────────────────────────────────────────────────────────────────

const ACTIVE = new Set<OfferStatus>(["SENT", "COUNTERED"]);

function groupOffersByPlayer(offers: Offer[]): PlayerGroup[] {
  const map = new Map<string, Offer[]>();
  for (const offer of offers) {
    const pid = offer.player_id;
    if (!map.has(pid)) map.set(pid, []);
    map.get(pid)!.push(offer);
  }
  return [...map.entries()]
    .map(([playerId, playerOffers]) => {
      const first = playerOffers[0];
      const active = playerOffers.filter((o) => ACTIVE.has(o.status as OfferStatus));
      const fees = active.filter((o) => o.fee_amount != null).map((o) => o.fee_amount!);
      const latestActivity = playerOffers.reduce(
        (max, o) => (o.last_action_at > max ? o.last_action_at : max),
        ""
      );
      return {
        playerId,
        playerName: first.player?.name ?? "Unknown player",
        position: first.player?.position ?? null,
        offers: [...playerOffers].sort(
          (a, b) => new Date(b.last_action_at).getTime() - new Date(a.last_action_at).getTime()
        ),
        activeCount: active.length,
        bestFee: fees.length > 0 ? Math.max(...fees) : null,
        latestActivity,
      };
    })
    .sort((a, b) => b.latestActivity.localeCompare(a.latestActivity));
}

// ── Status filter tabs ─────────────────────────────────────────────────────────

const TABS: { label: string; value: OfferStatus | "" }[] = [
  { label: "All",       value: "" },
  { label: "Pending",   value: "SENT" },
  { label: "Countered", value: "COUNTERED" },
  { label: "Accepted",  value: "ACCEPTED" },
  { label: "Rejected",  value: "REJECTED" },
];

// ── Player group card ──────────────────────────────────────────────────────────

function PlayerGroupCard({ group }: { group: PlayerGroup }) {
  const navigate = useNavigate();
  const [expanded, setExpanded] = useState(true);

  const needsAction = group.offers.some((o) => o.status === "SENT");
  const hasCounter  = group.offers.some((o) => o.status === "COUNTERED");

  return (
    <div className={`rounded-xl ring-1 overflow-hidden ${
      needsAction
        ? "ring-emerald-500/20 bg-emerald-500/[0.03]"
        : hasCounter
        ? "ring-amber-500/20 bg-amber-500/[0.03]"
        : "ring-white/[0.06] bg-slate-900"
    }`}>
      {/* Group header — click to expand/collapse */}
      <button
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-white/[0.02] transition-colors text-left"
      >
        <div className="flex items-center gap-3 min-w-0">
          {/* Expand chevron */}
          <svg
            className={`h-4 w-4 text-slate-600 shrink-0 transition-transform ${expanded ? "rotate-90" : ""}`}
            fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
          </svg>

          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-sm font-semibold text-white">{group.playerName}</span>
              {group.position && (
                <Badge variant={positionVariant(group.position)}>{group.position}</Badge>
              )}
              {group.activeCount > 0 && (
                <span className="rounded-full bg-emerald-500/15 px-2 py-0.5 text-xs font-semibold text-emerald-400 ring-1 ring-emerald-500/20">
                  {group.activeCount} active
                </span>
              )}
              {needsAction && (
                <span className="flex items-center gap-1 text-xs text-emerald-400">
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
                  Action needed
                </span>
              )}
              {!needsAction && hasCounter && (
                <span className="text-xs text-amber-400/80">Countered</span>
              )}
            </div>
          </div>
        </div>

        <div className="shrink-0 ml-3 text-right">
          {group.bestFee != null && (
            <p className="text-sm font-semibold text-white tabular-nums">
              Best: {formatCurrency(group.bestFee)}
            </p>
          )}
          <p className="text-xs text-slate-500">{group.offers.length} offer{group.offers.length !== 1 ? "s" : ""}</p>
        </div>
      </button>

      {/* Offer rows */}
      {expanded && (
        <div className="border-t border-white/[0.06] divide-y divide-white/[0.04]">
          {group.offers.map((offer) => (
            <div
              key={offer.id}
              onClick={() => navigate(`/offers/${offer.id}`)}
              className={`flex items-center gap-4 px-4 py-3 cursor-pointer transition-colors hover:bg-white/[0.04] ${
                !ACTIVE.has(offer.status as OfferStatus) ? "opacity-50" : ""
              }`}
            >
              {/* Indent */}
              <div className="w-4 shrink-0" />

              {/* From club */}
              <div className="flex-1 min-w-0">
                <ClubLink id={offer.from_club?.id} name={offer.from_club?.name} />
              </div>

              {/* Fee */}
              <div className="shrink-0 tabular-nums text-sm font-semibold text-white">
                {offer.fee_amount != null ? formatCurrency(offer.fee_amount) : <span className="text-slate-500 font-normal">TBD</span>}
              </div>

              {/* Status */}
              <div className="shrink-0 w-28 text-right">
                <Badge variant={offerStatusVariant(offer.status)}>{offer.status}</Badge>
              </div>

              {/* Last activity */}
              <div className="shrink-0 text-xs text-slate-500 w-24 text-right hidden sm:block">
                {formatDate(offer.last_action_at)}
              </div>

              {/* Chevron */}
              <svg className="h-4 w-4 text-slate-700 shrink-0" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
              </svg>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Main page ──────────────────────────────────────────────────────────────────

export default function OfferInboxPage() {
  const [statusFilter, setStatusFilter] = useState<OfferStatus | "">("");
  const [page, setPage] = useState(1);

  const { data, isLoading } = useQuery<Paginated<Offer>>({
    queryKey: ["offers", "received", { status: statusFilter, page }],
    queryFn: () =>
      api
        .get<Paginated<Offer>>("/offers/received", {
          params: {
            page,
            page_size: 50,
            ...(statusFilter && { offer_status: statusFilter }),
          },
        })
        .then((r) => r.data),
  });

  function handleTabChange(val: OfferStatus | "") {
    setStatusFilter(val);
    setPage(1);
  }

  const groups = data ? groupOffersByPlayer(data.items) : [];
  const totalActive = data?.items.filter((o) => ACTIVE.has(o.status as OfferStatus)).length ?? 0;

  return (
    <div>
      <PageHeader
        title="Offer Inbox"
        subtitle={
          totalActive > 0
            ? `${totalActive} offer${totalActive !== 1 ? "s" : ""} requiring attention`
            : "Offers received from other clubs"
        }
      />

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

      {isLoading && <ListSkeleton count={4} />}

      {!isLoading && groups.length === 0 && (
        <EmptyState title="No offers received" body="When clubs make you an offer, it will appear here." />
      )}

      {groups.length > 0 && (
        <>
          <div className="space-y-3">
            {groups.map((group) => (
              <PlayerGroupCard key={group.playerId} group={group} />
            ))}
          </div>

          {data && data.total > data.page_size && (
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
