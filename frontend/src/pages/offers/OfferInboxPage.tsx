import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import api from "../../lib/api";
import type { Club, FairValueSignal, Offer, Paginated } from "../../types/api";
import type { OfferStatus } from "../../types/enums";
import ClubLink from "../../components/ui/ClubLink";
import DateRangeFilter, { EMPTY_DATE_RANGE, type DateRange } from "../../components/ui/DateRangeFilter";
import PageHeader from "../../components/ui/PageHeader";
import Pagination from "../../components/ui/Pagination";
import ResponsiveTable, { type ResponsiveColumn } from "../../components/ui/ResponsiveTable";
import { ListSkeleton } from "../../components/ui/Skeleton";
import { offerOutcome } from "../../lib/badges";
import { offerWhoseMove } from "../../lib/whoseMove";
import { useDeadlineCountdown } from "../../hooks/useDeadlineCountdown";
import { formatCurrency, formatDate } from "../../lib/utils";

// ── Filter chips ──────────────────────────────────────────────────────────────

type Chip = "ALL" | "YOUR_MOVE" | "THEIR_MOVE" | "ACCEPTED" | "REJECTED";

const CHIPS: { label: string; value: Chip }[] = [
  { label: "All", value: "ALL" },
  { label: "Your move", value: "YOUR_MOVE" },
  { label: "Their move", value: "THEIR_MOVE" },
  { label: "Accepted", value: "ACCEPTED" },
  { label: "Rejected", value: "REJECTED" },
];

// Chips backed by a real server status filter get real pagination. "Your
// move"/"Their move" are derived client-side (whose_move isn't a server
// filter yet — B1), so they filter within the currently-fetched page rather
// than across the whole inbox; pagination hides while one of them is active.
const CHIP_STATUS: Partial<Record<Chip, OfferStatus>> = {
  ACCEPTED: "ACCEPTED",
  REJECTED: "REJECTED",
};

// ── Tier 1 — "Your move" ──────────────────────────────────────────────────────

const NEGOTIATION_TERMINAL = new Set<OfferStatus>(["ACCEPTED", "REJECTED", "WITHDRAWN", "EXPIRED"]);

function YourMoveDeadline({ deadline }: { deadline: string | null }) {
  const result = useDeadlineCountdown(deadline);
  if (!deadline) return <span className="text-success-text">—</span>;
  const urgent = result.state === "danger";
  return (
    <span className={`font-bold ${urgent ? "text-danger-text" : "text-text-secondary"}`}>
      {result.state === "expired" ? "Expired" : result.label}
    </span>
  );
}

function NegotiationHistory({ offer }: { offer: Offer }) {
  const entries = [...offer.events]
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
    .slice(0, 3);
  if (entries.length === 0) return null;

  return (
    <div className="mt-3 flex flex-wrap gap-x-[22px] gap-y-2 border-t border-rule-faint pt-3">
      {entries.map((e) => {
        const amount = e.payload && typeof e.payload.fee_amount === "number" ? e.payload.fee_amount : null;
        return (
          <div key={e.id}>
            <p className="text-[11px] text-text-muted">{formatDate(e.created_at)}</p>
            <p className="text-[13px] text-text-secondary">
              {e.event_type.charAt(0) + e.event_type.slice(1).toLowerCase()}
              {amount != null && <strong className="text-text"> {formatCurrency(amount)}</strong>}
            </p>
          </div>
        );
      })}
    </div>
  );
}

function YourMoveRow({
  offer,
  valuation,
  rivalCount,
}: {
  offer: Offer;
  valuation: FairValueSignal | undefined;
  rivalCount: number;
}) {
  const navigate = useNavigate();
  const belowValuation = valuation != null && offer.fee_amount != null && offer.fee_amount < valuation.fair_value;

  return (
    <div className="border-b border-rule px-5 py-4 last:border-b-0">
      <div className="flex flex-wrap items-center gap-4">
        <div className="flex-1 basis-[260px]">
          <p className="text-base font-bold text-text">
            {offer.player?.name ?? "Unknown player"}
            {offer.player?.position && (
              <span className="ml-2 text-[11px] font-bold text-text-muted">{offer.player.position}</span>
            )}
          </p>
          <p className="text-[13px] text-text-muted">
            {offer.from_club?.name ?? "?"} · {offer.status === "COUNTERED" ? "countered your terms" : "sent an offer"}
          </p>
          {/* Deciding on an offer without knowing another club is also bidding
              is the seller losing their strongest card. */}
          {rivalCount > 0 && (
            <p className="mt-1 text-[12px] font-semibold text-warning-text">
              {rivalCount === 1 ? "1 other club is bidding" : `${rivalCount} other clubs are bidding`}
            </p>
          )}
        </div>
        <div className="basis-[120px] shrink">
          <p className="text-[11px] text-text-muted">Their offer</p>
          <p className="text-[17px] font-bold text-text">{offer.fee_amount != null ? formatCurrency(offer.fee_amount) : "TBD"}</p>
        </div>
        <div className="basis-[120px] shrink">
          <p className="text-[11px] text-text-muted">Your valuation</p>
          <p className={`text-[17px] font-bold ${belowValuation ? "text-danger-text" : "text-text"}`}>
            {valuation ? formatCurrency(valuation.fair_value) : "—"}
          </p>
        </div>
        <div className="basis-[110px] shrink">
          <p className="text-[11px] text-text-muted">Deadline</p>
          <YourMoveDeadline deadline={offer.expires_at} />
        </div>
        <div className="flex shrink-0 gap-2">
          <button
            onClick={() => navigate(`/offers/${offer.id}`)}
            className="rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-white hover:bg-accent-hover transition-colors"
          >
            Counter
          </button>
          <button
            onClick={() => navigate(`/offers/${offer.id}`)}
            className="rounded-lg bg-surface-inset px-4 py-2 text-sm font-semibold text-text ring-1 ring-border hover:ring-input-border transition-colors"
          >
            Accept
          </button>
        </div>
      </div>
      <NegotiationHistory offer={offer} />
    </div>
  );
}

function YourMoveBand({
  offers,
  valuations,
  liveOffersByPlayer,
}: {
  offers: Offer[];
  valuations: Record<string, FairValueSignal>;
  liveOffersByPlayer: Record<string, number>;
}) {
  if (offers.length === 0) {
    return <p className="mb-[18px] text-sm text-text-secondary">Nothing is waiting on you.</p>;
  }
  return (
    <div className="mb-[18px] rounded-xl bg-surface ring-1 ring-danger-ring shadow-[0_1px_2px_rgba(16,24,40,0.06)] overflow-hidden">
      <div className="flex items-center justify-between border-b border-danger-border bg-danger-bg px-5 py-3">
        <div className="flex items-center gap-2">
          <span className="h-2 w-2 rounded-full bg-danger" />
          <span className="text-[13px] font-bold text-danger-heading">Your move — {offers.length}</span>
        </div>
      </div>
      <div>
        {offers.map((o) => (
          <YourMoveRow
            key={o.id}
            offer={o}
            valuation={valuations[o.player_id]}
            rivalCount={Math.max((liveOffersByPlayer[o.player_id] ?? 1) - 1, 0)}
          />
        ))}
      </div>
    </div>
  );
}

// ── "Everything else" table ───────────────────────────────────────────────────

const TERMINAL_STATE_COLOUR: Record<string, string> = {
  ACCEPTED: "text-success-text",
  REJECTED: "text-danger-text",
};

// This page renders state as plain coloured text rather than badges, so it maps
// offerOutcome's badge variants onto the same text colours.
const OUTCOME_COLOUR: Record<string, string> = {
  success: "text-success-text",
  danger:  "text-danger-text",
  info:    "text-text-secondary",
  warning: "text-warning-text",
  neutral: "text-text-muted",
};

interface EverythingRow {
  offer: Offer;
  move: ReturnType<typeof offerWhoseMove>;
}

/**
 * One row per *player*, not per offer.
 *
 * Two clubs bidding for the same player is the most valuable thing a seller can
 * know — it is the leverage — but as one row per offer it rendered as two
 * unrelated lines that happened to sit next to each other. Grouping puts the
 * competition in the headline, and the row leads to the best offer, whose
 * detail page already carries the ranked order book.
 */
interface PlayerGroup {
  playerId: string;
  offers: EverythingRow[];   // best fee first
  best: EverythingRow;
  /** Most recent activity across the whole group — not the best offer's own
   *  date, which can be older than a rival's and would misreport the row. */
  lastActivity: string;
}

function feeOf(o: Offer): number {
  return o.fee_amount ?? -1;   // a fee-less offer ranks below any priced one
}

function groupByPlayer(rows: EverythingRow[]): PlayerGroup[] {
  const byPlayer = new Map<string, EverythingRow[]>();
  for (const row of rows) {
    const existing = byPlayer.get(row.offer.player_id);
    if (existing) existing.push(row);
    else byPlayer.set(row.offer.player_id, [row]);
  }
  // Map preserves insertion order, so the server's ordering (last activity)
  // still decides where each player sits.
  return [...byPlayer.entries()].map(([playerId, group]) => {
    const offers = [...group].sort((a, b) => feeOf(b.offer) - feeOf(a.offer));
    const lastActivity = group
      .map((r) => r.offer.last_action_at)
      .reduce((latest, d) => (new Date(d) > new Date(latest) ? d : latest));
    return { playerId, offers, best: offers[0], lastActivity };
  });
}

/**
 * Is this offer still in play, or is it history?
 *
 * The previous single "Everything else" bucket mixed live negotiations, deals
 * already running, and dead offers — its own subheading admitted as much
 * ("Waiting on the other club, or closed"). They need different actions.
 */
function isLive(offer: Offer): boolean {
  if (offer.status === "SENT" || offer.status === "COUNTERED") return true;
  if (offer.deal) return offer.deal.status === "IN_PROGRESS" || offer.deal.status === "PENDING_COMPLETION";
  return false;
}

function StateCell({ row }: { row: EverythingRow }) {
  const { offer, move } = row;
  // A seller who accepted an offer has the same problem a buyer does: the deal
  // can collapse afterwards and "Accepted" would still read green.
  if (offer.deal) {
    const outcome = offerOutcome(offer.status, offer.deal);
    return <span className={`font-semibold ${OUTCOME_COLOUR[outcome.variant] ?? "text-text-secondary"}`}>{outcome.label}</span>;
  }
  if (offer.status === "ACCEPTED" || offer.status === "REJECTED") {
    return <span className={`font-semibold ${TERMINAL_STATE_COLOUR[offer.status]}`}>{offer.status === "ACCEPTED" ? "Accepted" : "Rejected"}</span>;
  }
  if (move === "neither") return <span className="text-text-muted">{offer.status}</span>;
  return <span className={move === "your" ? "text-danger-text font-semibold" : "text-text-secondary font-semibold"}>
    {move === "your" ? "Your move" : "Their move"}
  </span>;
}

function InboxSection({
  title,
  hint,
  groups,
  columns,
  navigate,
  emptyTitle,
}: {
  title: string;
  hint: string;
  groups: PlayerGroup[];
  columns: ResponsiveColumn<PlayerGroup>[];
  navigate: ReturnType<typeof useNavigate>;
  emptyTitle: string;
}) {
  // A grouped row leads to the best offer, whose detail page carries the ranked
  // order book across every competing club — rather than duplicating that
  // comparison here.
  const open = (g: PlayerGroup) => navigate(`/offers/${g.best.offer.id}`);

  return (
    <div className="mb-6">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-bold text-text">
          {title}
          {groups.length > 0 && <span className="ml-2 font-semibold text-text-muted">{groups.length}</span>}
        </h2>
        <span className="text-xs text-text-muted">{hint}</span>
      </div>
      <ResponsiveTable
        columns={columns}
        rows={groups}
        rowKey={(g) => g.playerId}
        onRowClick={open}
        emptyTitle={emptyTitle}
        renderCard={(g) => (
          <div className="px-4 py-3">
            <div className="flex items-center justify-between">
              <span className="text-sm font-semibold text-text">
                {g.best.offer.player?.name ?? "—"}
                {g.best.offer.player?.position && (
                  <span className="ml-1.5 text-xs text-text-muted">{g.best.offer.player.position}</span>
                )}
              </span>
              <span className="text-sm font-bold text-text">
                {g.best.offer.fee_amount != null ? formatCurrency(g.best.offer.fee_amount) : "TBD"}
              </span>
            </div>
            <p className="mt-0.5 text-xs text-text-muted">
              {g.offers.map((r) => r.offer.from_club?.name ?? "?").join(" · ")}
              {g.offers.length > 1 && (
                <span className="ml-1.5 font-bold text-warning-text">{g.offers.length} clubs</span>
              )}
            </p>
            <div className="mt-1 flex items-center justify-between text-xs">
              <StateCell row={g.best} />
              <span className="text-text-muted">{formatDate(g.lastActivity)}</span>
            </div>
          </div>
        )}
      />
    </div>
  );
}

// ── Main page ──────────────────────────────────────────────────────────────────

export default function OfferInboxPage() {
  const navigate = useNavigate();
  const [chip, setChip] = useState<Chip>("ALL");
  const [dateRange, setDateRange] = useState<DateRange>(EMPTY_DATE_RANGE);
  const [page, setPage] = useState(1);

  const { data: myClub } = useQuery<Club>({
    queryKey: ["clubs", "me"],
    queryFn: () => api.get<Club>("/clubs/me").then((r) => r.data),
    staleTime: 60_000,
  });

  const serverStatus = CHIP_STATUS[chip];
  const isClientFiltered = chip === "YOUR_MOVE" || chip === "THEIR_MOVE";

  const { data, isLoading } = useQuery<Paginated<Offer>>({
    queryKey: ["offers", "received", { status: serverStatus, ...dateRange, page }],
    queryFn: () =>
      api
        .get<Paginated<Offer>>("/offers/received", {
          params: {
            page,
            page_size: 30,
            ...(serverStatus && { offer_status: serverStatus }),
            ...(dateRange.dateFrom && { date_from: dateRange.dateFrom }),
            ...(dateRange.dateTo && { date_to: dateRange.dateTo }),
          },
        })
        .then((r) => r.data),
  });

  const myClubId = myClub?.id;
  const allOffers = data?.items ?? [];

  const yourMoveOffers = useMemo(
    () => (myClubId ? allOffers.filter((o) => offerWhoseMove(o, myClubId) === "your") : []),
    [allOffers, myClubId]
  );

  const playerIds = useMemo(
    () => [...new Set(yourMoveOffers.map((o) => o.player_id))],
    [yourMoveOffers]
  );

  const { data: valuationData } = useQuery<{ valuations: Record<string, FairValueSignal> }>({
    queryKey: ["valuation", "batch", "offer-inbox", playerIds],
    queryFn: () => api.get<{ valuations: Record<string, FairValueSignal> }>("/valuation/players", { params: { ids: playerIds.join(",") } }).then((r) => r.data),
    enabled: playerIds.length > 0,
  });

  const everythingRows: EverythingRow[] = allOffers
    .filter((o) => !myClubId || offerWhoseMove(o, myClubId) !== "your")
    .filter((o) => {
      if (!isClientFiltered || !myClubId) return true;
      const move = offerWhoseMove(o, myClubId);
      return chip === "YOUR_MOVE" ? move === "your" : move === "their";
    })
    .map((o) => ({ offer: o, move: myClubId ? offerWhoseMove(o, myClubId) : "neither" }));

  const inPlayGroups = groupByPlayer(everythingRows.filter((r) => isLive(r.offer)));
  const closedGroups = groupByPlayer(everythingRows.filter((r) => !isLive(r.offer)));

  // How many clubs are live on each player, across both bands — a rival sitting
  // in "In play" still counts against an offer that's waiting on you.
  const liveOffersByPlayer = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const o of allOffers) {
      if (!isLive(o)) continue;
      counts[o.player_id] = (counts[o.player_id] ?? 0) + 1;
    }
    return counts;
  }, [allOffers]);

  const columns: ResponsiveColumn<PlayerGroup>[] = [
    { key: "player", header: "Player", priority: 1, render: (g) => (
      <span className="font-medium text-text">
        {g.best.offer.player?.name ?? "—"}
        {g.best.offer.player?.position && (
          <span className="ml-2 text-xs text-text-muted">{g.best.offer.player.position}</span>
        )}
        {g.offers.length > 1 && (
          <span className="ml-2 rounded-full bg-warning-bg px-2 py-0.5 text-[11px] font-bold text-warning-text ring-1 ring-warning-fill/25">
            {g.offers.length} clubs
          </span>
        )}
      </span>
    ) },
    { key: "club", header: "Club", priority: 3, render: (g) =>
      g.offers.length === 1 ? (
        <ClubLink id={g.best.offer.from_club?.id} name={g.best.offer.from_club?.name} />
      ) : (
        <span className="text-text-secondary">
          {g.offers.map((r) => r.offer.from_club?.name ?? "?").join(" · ")}
        </span>
      )
    },
    { key: "fee", header: "Fee", priority: 2, className: "text-right", render: (g) => (
      <span className="font-bold text-text">
        {g.best.offer.fee_amount != null ? formatCurrency(g.best.offer.fee_amount) : "TBD"}
        {g.offers.length > 1 && (
          <span className="ml-1.5 text-[11px] font-normal text-text-muted">best</span>
        )}
      </span>
    ) },
    { key: "state", header: "State", priority: 4, render: (g) => <StateCell row={g.best} /> },
    { key: "activity", header: "Last activity", priority: 5, className: "text-right", render: (g) => (
      <span className="text-xs text-text-muted">{formatDate(g.lastActivity)}</span>
    ) },
  ];

  return (
    <div>
      <PageHeader title="Offer Inbox" subtitle="Offers received from other clubs" />

      <div className="mb-5 flex flex-wrap gap-2">
        {CHIPS.map((c) => (
          <button
            key={c.value}
            onClick={() => { setChip(c.value); setPage(1); }}
            className={`rounded-lg px-3.5 py-1.5 text-[13px] font-semibold transition-colors ${
              chip === c.value
                ? "bg-ink text-white"
                : "bg-surface text-text-secondary ring-1 ring-input-border hover:ring-accent"
            }`}
          >
            {c.label}
          </button>
        ))}
      </div>

      <div className="mb-6">
        <DateRangeFilter value={dateRange} onChange={(r) => { setDateRange(r); setPage(1); }} />
      </div>

      {isLoading ? (
        <ListSkeleton count={4} />
      ) : (
        <>
          <YourMoveBand
            offers={yourMoveOffers}
            valuations={valuationData?.valuations ?? {}}
            liveOffersByPlayer={liveOffersByPlayer}
          />

          <InboxSection
            title="In play"
            hint="Live negotiations and deals already running"
            groups={inPlayGroups}
            columns={columns}
            navigate={navigate}
            emptyTitle="Nothing in play"
          />

          {closedGroups.length > 0 && (
            <InboxSection
              title="Closed"
              hint="Completed, rejected, withdrawn or expired"
              groups={closedGroups}
              columns={columns}
              navigate={navigate}
              emptyTitle="Nothing closed yet"
            />
          )}

          {!isClientFiltered && data && data.total > data.page_size && (
            <Pagination page={data.page} total={data.total} pageSize={data.page_size} onChange={setPage} />
          )}
        </>
      )}
    </div>
  );
}
