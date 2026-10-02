import { useState, useRef, useEffect, useCallback, type ReactNode } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "../../lib/api";
import type { ActiveDealStub, Club, FairValueSignal, OrderBook, PlayerDetail, PlayerLedger, PlayerRepresentation } from "../../types/api";
import { useAuthStore } from "../../store/auth";
import { useClubCapabilities } from "../../hooks/useClubCapabilities";
import { useListingClosedReason, useOpenListings } from "../../hooks/useListing";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import ClubLink from "../../components/ui/ClubLink";
import Spinner from "../../components/ui/Spinner";
import VerifiedBadge from "../../components/verification/VerifiedBadge";
import {
  positionVariant,
  playerStatusLabel,
  playerStatusVariant,
} from "../../lib/badges";
import { formatCurrency, getApiError } from "../../lib/utils";
import AddToShortlistButton from "../../components/scouting/AddToShortlistButton";
import AskAboutPlayerModal from "../../components/enquiries/AskAboutPlayerModal";
import { PotentialBuyersPanel } from "../../components/ai/Assistant";
import PlayerAccountCard from "../../components/players/PlayerAccountCard";
import ListPlayerModal from "../../components/sales/ListPlayerModal";
import { useCompare } from "../../context/CompareContext";
import FactsStrip from "../../components/players/ledger/FactsStrip";
import { CareerLedger, InjuriesLedger, OverviewLedger, type StatSet } from "../../components/players/ledger/LedgerTabs";
import { PlayerFitCard } from "../../components/ai/PlayerFitCard";
import { useConfirm } from "../../context/ConfirmContext";
import { useToast } from "../../context/ToastContext";

// ── Deal banner ───────────────────────────────────────────────────────────────

function DealBanner({ deal }: { deal: ActiveDealStub }) {
  if (deal.status === "IN_PROGRESS") {
    return (
      <div className="mb-4 flex items-start gap-3 rounded-xl bg-warning-bg px-5 py-4 ring-1 ring-warning-fill/25">
        <div className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-warning-fill/20 text-warning-text font-bold text-xs">!</div>
        <div>
          <p className="text-sm font-semibold text-warning-text">Transfer in progress</p>
          <p className="mt-0.5 text-xs text-text-muted">
            {deal.buyer_club && deal.seller_club
              ? `${deal.seller_club.name} → ${deal.buyer_club.name} · Stage: ${deal.stage ?? "—"}`
              : "A deal for this player is currently being processed."}
          </p>
          <p className="mt-1 text-xs text-text-muted">
            New offers and sale listings are not permitted while a deal is active.
          </p>
        </div>
      </div>
    );
  }

  // COMPLETED
  return (
    <div className="mb-4 flex items-start gap-3 rounded-xl bg-success/10 px-5 py-4 ring-1 ring-success/20">
      <div className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-success/20 text-success-text font-bold text-xs">✓</div>
      <div>
        <p className="text-sm font-semibold text-success-text">Recently transferred</p>
        <p className="mt-0.5 text-xs text-text-muted">
          {deal.buyer_club && deal.seller_club
            ? `${deal.buyer_club.name} signed this player from ${deal.seller_club.name}`
            : "This player was recently transferred."}
          {deal.agreed_fee != null && ` for ${new Intl.NumberFormat("en-GB", { style: "currency", currency: "GBP", maximumFractionDigits: 0 }).format(deal.agreed_fee)}`}
          {deal.completed_at && ` on ${new Date(deal.completed_at).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" })}`}
          .
        </p>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────

const positionAvatarBg: Record<string, string> = {
  GK:  "bg-pos-gk-bg text-pos-gk-text ring-border",
  DEF: "bg-pos-def-bg text-pos-def-text ring-border",
  MID: "bg-pos-mid-bg text-pos-mid-text ring-border",
  FWD: "bg-pos-fwd-bg text-pos-fwd-text ring-border",
};

// ── Tab bar ────────────────────────────────────────────────────────────────────

type ProfileTab = "overview" | "career" | "injuries";
const PROFILE_TABS: ProfileTab[] = ["overview", "career", "injuries"];

interface TabDef { id: ProfileTab; label: string; count?: string }

function TabBar({
  tabs,
  active,
  onChange,
}: {
  tabs: TabDef[];
  active: ProfileTab;
  onChange: (t: ProfileTab) => void;
}) {
  const barRef = useRef<HTMLDivElement>(null);
  const activeRef = useRef<HTMLButtonElement>(null);
  const [inkStyle, setInkStyle] = useState<React.CSSProperties>({});

  useEffect(() => {
    const bar = barRef.current;
    const btn = activeRef.current;
    if (bar && btn) {
      const barRect = bar.getBoundingClientRect();
      const btnRect = btn.getBoundingClientRect();
      setInkStyle({ left: btnRect.left - barRect.left, width: btnRect.width });
    }
  }, [active]);

  return (
    <div
      ref={barRef}
      className="relative flex gap-1 border-b border-rule pb-px"
    >
      {/* sliding underline */}
      <span
        className="absolute bottom-0 h-0.5 rounded-full bg-success transition-all duration-200"
        style={inkStyle}
      />
      {tabs.map((t) => (
        <button
          key={t.id}
          ref={t.id === active ? activeRef : undefined}
          onClick={() => onChange(t.id)}
          className={`px-3 py-2 text-sm font-medium transition-colors ${
            t.id === active
              ? "text-text"
              : "text-text-muted hover:text-text-secondary"
          }`}
        >
          {t.label}
          {t.count && <span className="ml-1.5 text-[11px] font-semibold text-text-muted">{t.count}</span>}
        </button>
      ))}
    </div>
  );
}

// ── Agent representation card ─────────────────────────────────────────────────

function AgentRepresentationCard({ playerId }: { playerId: string }) {
  const queryClient = useQueryClient();

  const { data: mandates = [], refetch } = useQuery<PlayerRepresentation[]>({
    queryKey: ["players", playerId, "representation"],
    queryFn: () =>
      api.get<PlayerRepresentation[]>(`/players/${playerId}/representation`).then((r) => r.data),
  });

  const [exclusive, setExclusive]   = useState(false);
  const [startDate, setStartDate]   = useState("");
  const [endDate, setEndDate]       = useState("");
  const [territory, setTerritory]   = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError]           = useState<string | null>(null);
  const [success, setSuccess]       = useState(false);

  async function handleCreate() {
    setError(null);
    setSubmitting(true);
    try {
      await api.post("/mandates/", {
        player_id: playerId,
        exclusive,
        start_date:  startDate  || null,
        end_date:    endDate    || null,
        territory:   territory.trim() || null,
      });
      setSuccess(true);
      queryClient.invalidateQueries({ queryKey: ["players", playerId, "representation"] });
      queryClient.invalidateQueries({ queryKey: ["agents", "me", "players"] });
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(typeof msg === "string" ? msg : "Failed to create mandate.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleRevoke(mandateId: string) {
    try {
      await api.post(`/mandates/${mandateId}/revoke`);
      queryClient.invalidateQueries({ queryKey: ["players", playerId, "representation"] });
      queryClient.invalidateQueries({ queryKey: ["agents", "me", "players"] });
      refetch();
      setSuccess(false);
    } catch {
      // silent — player still sees mandate until page refresh
    }
  }

  const INPUT = "w-full rounded bg-surface px-2 py-1.5 text-xs text-text ring-1 ring-input-border focus:outline-none focus:ring-success";

  return (
    <div className="rounded-xl bg-surface ring-1 ring-border px-4 py-4">
      <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-text-muted">
        Representation
      </p>

      {/* Whose representation this is: yours (revocable), or another agent's. */}
      {mandates.length > 0 && (
        <div className="mb-3 divide-y divide-rule-faint">
          {mandates.map((m) => (
            <div key={m.id} className="flex items-start justify-between gap-2 py-2 text-[13px]">
              <p className="min-w-0 text-text-secondary">
                {m.is_mine ? (
                  <span className="font-semibold text-success-text">You represent him</span>
                ) : (
                  <>Represented by <span className="font-semibold text-text">{m.agent_name}</span> ({m.agency_name})</>
                )}
                <span className="block text-xs text-text-muted">
                  {m.exclusive ? "Exclusive mandate" : "Non-exclusive"}
                  {m.end_date && ` · until ${new Date(m.end_date).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" })}`}
                  {m.territory && ` · ${m.territory}`}
                </span>
              </p>
              {m.is_mine && (
                <button
                  onClick={() => handleRevoke(m.id)}
                  className="shrink-0 text-xs text-danger-text hover:text-danger-text-alt transition-colors"
                >
                  Revoke
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      {mandates.some((m) => m.is_mine) ? null : mandates.some((m) => m.exclusive && !m.is_mine) ? (
        <p className="text-[13px] text-text-muted">
          Another agent holds an exclusive mandate, so you can&rsquo;t represent him while it runs.
        </p>
      ) : success ? (
        <p className="text-sm text-success-text">
          Mandate created. Player added to your clients.
        </p>
      ) : (
        <div className="space-y-2.5">
          {error && (
            <p className="rounded bg-danger-bg px-3 py-2 text-xs text-danger-text ring-1 ring-danger-border">
              {error}
            </p>
          )}
          <label className="flex items-center gap-2 text-sm text-text-secondary cursor-pointer select-none">
            <input
              type="checkbox"
              checked={exclusive}
              onChange={(e) => setExclusive(e.target.checked)}
              className="accent-success"
            />
            Exclusive mandate
          </label>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <p className="text-[13px] text-text-muted mb-1">Start date</p>
              <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} className={INPUT} />
            </div>
            <div>
              <p className="text-[13px] text-text-muted mb-1">End date</p>
              <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} className={INPUT} />
            </div>
          </div>
          <div>
            <p className="text-[13px] text-text-muted mb-1">Territory (optional)</p>
            <input
              type="text"
              value={territory}
              onChange={(e) => setTerritory(e.target.value)}
              placeholder="e.g. Europe"
              className={INPUT + " placeholder-text-muted"}
            />
          </div>
          <Button
            variant="primary"
            size="sm"
            className="w-full"
            loading={submitting}
            onClick={handleCreate}
          >
            Represent this player
          </Button>
        </div>
      )}
    </div>
  );
}

// ── Offers on our player (own club) ──────────────────────────────────────────

function OffersPanel({ book, onOpen }: { book: OrderBook; onOpen: () => void }) {
  const active = book.entries.filter((e) => e.is_active).slice(0, 5);
  return (
    <div className="rounded-xl bg-surface px-3.5 py-3 ring-1 ring-border">
      <div className="mb-1 flex items-center justify-between">
        <p className="text-sm font-semibold text-text">Offers</p>
        <button onClick={onOpen} className="text-xs font-semibold text-accent hover:underline">Open inbox →</button>
      </div>
      {active.length === 0 ? (
        <p className="text-[13px] text-text-muted">No active offers.</p>
      ) : (
        <ul>
          {active.map((e) => {
            const loan = e.deal_type === "LOAN";
            const fee = loan ? e.loan_fee : e.fee_amount;
            return (
              <li key={e.id} className="flex items-center justify-between gap-2 border-t border-rule-faint py-1.5 text-[13px] first:border-t-0">
                {/* An anonymous buyer arrives already masked from the server. */}
                <span className="min-w-0 truncate text-text-secondary">{e.club?.name ?? "An undisclosed club"}</span>
                <span className="shrink-0 font-bold tabular-nums text-text">
                  {fee != null ? formatCurrency(fee) : "—"}{loan && <span className="ml-1 text-xs font-normal text-text-muted">loan</span>}
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

// ── Page ───────────────────────────────────────────────────────────────────────

export default function PlayerMarketDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const confirm = useConfirm();
  const { addToast } = useToast();
  const { accessToken, user } = useAuthStore();
  const { can } = useClubCapabilities();
  const isAuthenticated = !!accessToken;
  const isAgent = user?.user_type === "AGENT";
  const isPlayerAccount = user?.user_type === "PLAYER";
  const { toggle, has } = useCompare();
  // The tab lives in the URL (?tab=), so a link or Back returns to it.
  const [searchParams, setSearchParams] = useSearchParams();
  const tabParam = searchParams.get("tab");
  const activeTab: ProfileTab = PROFILE_TABS.includes(tabParam as ProfileTab) ? (tabParam as ProfileTab) : "overview";
  const setActiveTab = (t: ProfileTab) =>
    setSearchParams((prev) => { const next = new URLSearchParams(prev); if (t === "overview") next.delete("tab"); else next.set("tab", t); return next; }, { replace: true });
  // The Overview's column set is remembered on this device.
  const [statSet, setStatSetState] = useState<StatSet>(() => {
    try { const v = localStorage.getItem("profileStatSet"); return v === "passing" || v === "defending" ? v : "output"; } catch { return "output"; }
  });
  const setStatSet = (v: StatSet) => { setStatSetState(v); try { localStorage.setItem("profileStatSet", v); } catch { /* private mode */ } };

  // Keyed on sign-in: a public page can load before the session is back,
  // and the signed-out answer has no contract; this refetches once it is.
  const { data: player, isLoading, isError } = useQuery<PlayerDetail>({
    queryKey: ["players", "market", id, isAuthenticated],
    queryFn: () => api.get<PlayerDetail>(`/players/market/${id}`).then((r) => r.data),
    enabled: !!id,
  });

  // The season ledger: Overview, Career and Injuries all read it.
  const { data: ledger, isLoading: ledgerLoading } = useQuery<PlayerLedger>({
    queryKey: ["players", id, "ledger", isAuthenticated],
    queryFn: () => api.get<PlayerLedger>(`/players/market/${id}/ledger`).then((r) => r.data),
    enabled: !!id,
    staleTime: 300_000,
  });

  const { data: myClub } = useQuery<Club>({
    queryKey: ["clubs", "me"],
    queryFn: () => api.get<Club>("/clubs/me").then((r) => r.data),
    enabled: isAuthenticated,
    staleTime: 60_000,
  });

  // TRA-92: fair-value model signal — never requested for a player identity (D6)
  const { data: fairValue = null } = useQuery<FairValueSignal | null>({
    queryKey: ["valuation", id],
    queryFn: () =>
      api.get<FairValueSignal>(`/valuation/players/${id}`).then((r) => r.data).catch(() => null),
    enabled: !!id && isAuthenticated && !isPlayerAccount,
    staleTime: 300_000,
  });

  const isMyPlayer = !!(player && myClub && player.current_club?.id === myClub.id);

  const { data: competition } = useQuery<OrderBook>({
    queryKey: ["offers", "competition", id],
    queryFn: () =>
      api.get<OrderBook>(`/offers/competition/${id}`).then((r) => r.data),
    enabled: !!id && isMyPlayer,
    refetchInterval: 300_000,
  });

  // Listing from here. A player on loan *to* us is in our squad but not ours
  // to sell; one we loaned out is not `isMyPlayer` at all (current_club is
  // the loanee).
  const canList = isMyPlayer && can("MARKET_WRITE") && !player?.active_loan;
  const { byPlayer: openListings, isSuccess: listingsKnown } = useOpenListings(myClub?.id, canList);
  const listingId = id ? openListings.get(id) : undefined;
  const listClosedReason = useListingClosedReason(canList);
  const [listOpen, setListOpen] = useState(false);
  const closeListing = useCallback(() => setListOpen(false), []);
  const [askOpen, setAskOpen] = useState(false);
  const closeAsk = useCallback(() => setAskOpen(false), []);

  // Item 14: buyer meets the release clause, bypassing seller consent entirely.
  const releaseClauseMutation = useMutation({
    mutationFn: () =>
      api.post<{ id: string }>(`/players/${id}/trigger-release-clause`).then((r) => r.data),
    onSuccess: (deal) => {
      queryClient.invalidateQueries({ queryKey: ["players", "market", id] });
      navigate(`/deals/${deal.id}`);
    },
  });

  async function handleTriggerReleaseClause() {
    const clause = player?.active_contract?.release_clause;
    if (clause == null) return;
    const ok = await confirm({
      title: "Trigger release clause?",
      message: `This commits ${formatCurrency(clause)} from your transfer budget immediately and creates a binding deal for this player — the selling club cannot block it.`,
      confirmLabel: "Trigger clause",
      variant: "danger",
    });
    if (ok) releaseClauseMutation.mutate();
  }

  // Item 13: direct free-agent signing and Bosman pre-contract deals.
  const isFreeAgentPlayer =
    !!player && player.status === "FREE_AGENT" && !player.current_club && !player.team_name;
  // Contracted to a real-world club that is not on TransferX (ADR 0003).
  const isOffPlatform = !!player && player.status === "EXTERNAL";
  const contractEndDate = player?.active_contract?.end_date ?? player?.contract_expiry ?? null;
  const daysUntilContractEnd = contractEndDate
    ? Math.ceil((new Date(contractEndDate).getTime() - Date.now()) / (1000 * 60 * 60 * 24))
    : null;
  const inPreContractWindow =
    !isFreeAgentPlayer && daysUntilContractEnd != null && daysUntilContractEnd >= 0 && daysUntilContractEnd <= 180;

  const signFreeAgentMutation = useMutation({
    mutationFn: () => api.post<{ id: string }>(`/players/${id}/sign-free-agent`).then((r) => r.data),
    onSuccess: (deal) => {
      queryClient.invalidateQueries({ queryKey: ["players", "market", id] });
      navigate(`/deals/${deal.id}`);
    },
  });

  const preContractMutation = useMutation({
    mutationFn: () => api.post<{ id: string }>(`/players/${id}/pre-contract`).then((r) => r.data),
    onSuccess: (deal) => {
      queryClient.invalidateQueries({ queryKey: ["players", "market", id] });
      navigate(`/deals/${deal.id}`);
    },
  });

  async function handleSignFreeAgent() {
    const ok = await confirm({
      title: "Sign free agent?",
      message: `This creates a binding transfer deal for ${player?.name ?? "this player"} with no transfer fee.`,
      confirmLabel: "Sign player",
    });
    if (ok) signFreeAgentMutation.mutate();
  }

  async function handlePreContract() {
    const ok = await confirm({
      title: "Offer a pre-contract?",
      message: `${player?.name ?? "This player"} would join for free once their current contract expires. This creates a binding deal now.`,
      confirmLabel: "Offer pre-contract",
    });
    if (ok) preContractMutation.mutate();
  }

  // The club's own valuation of its player, edited in the facts strip.
  const valuationMutation = useMutation({
    mutationFn: (value: number | null) =>
      api.patch(`/clubs/me/players/${id}`, { club_valuation: value }).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["players", "market", id] });
      addToast("Club valuation saved.", "success");
    },
    // Say why, rather than leaving the old value as if nothing happened.
    onError: (err: unknown) => addToast(getApiError(err, "Couldn't save the club valuation."), "error"),
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Spinner size="lg" />
      </div>
    );
  }

  if (isError || !player) {
    return (
      <div className="rounded-xl bg-danger-bg px-5 py-4 text-sm text-danger-text ring-1 ring-danger-border">
        Player not found.{" "}
        <button onClick={() => navigate(-1)} className="underline">Go back</button>
      </div>
    );
  }

  const avatarBg = player.position
    ? (positionAvatarBg[player.position] ?? "bg-surface-inset text-text-muted ring-border")
    : "bg-surface-inset text-text-muted ring-border";

  const clubCrest = player.current_club?.crest_url ?? player.world_team?.crest_url ?? null;
  const clubName  = player.current_club?.name ?? player.world_team?.name ?? player.team_name ?? null;
  const isContracted = !!(player.current_club || player.world_team || player.team_name);

  // Bio fields — shown to anyone if data is available
  const bioChips: { label: string; value: string }[] = [];
  if (player.age)         bioChips.push({ label: "Age", value: String(player.age) });
  if (player.nationality) bioChips.push({ label: "Nat.", value: player.nationality });
  if (player.height)      bioChips.push({ label: "Height", value: player.height });
  if (player.weight)      bioChips.push({ label: "Weight", value: player.weight });
  if (player.birth_date) {
    const dob = new Date(player.birth_date).toLocaleDateString("en-GB", {
      day: "numeric", month: "short", year: "numeric",
    });
    bioChips.push({ label: "Born", value: dob });
  }
  if (player.birth_country && !player.birth_place) {
    bioChips.push({ label: "From", value: player.birth_country });
  }
  if (player.birth_place) {
    const place = [player.birth_place, player.birth_country].filter(Boolean).join(", ");
    bioChips.push({ label: "From", value: place });
  }

  const metaItems: ReactNode[] = [];
  if (clubName) metaItems.push(
    <span key="club" className="flex items-center gap-1.5 font-medium text-text">
      {clubCrest && <img src={clubCrest} alt="" loading="lazy" className="h-4 w-4 object-contain" />}
      <ClubLink id={player.current_club?.id} worldTeamId={player.world_team?.id} name={clubName} />
    </span>,
  );
  if (player.age) metaItems.push(<span key="age">{player.age} yrs</span>);
  if (player.nationality) metaItems.push(<span key="nat">{player.nationality}</span>);
  // Heights and weights arrive as bare numbers from the vendor ("195"); give them units.
  const unit = (v: string | null | undefined, u: string) => (v ? (/^\d+(\.\d+)?$/.test(v.trim()) ? `${v.trim()} ${u}` : v) : null);
  if (player.height || player.weight) metaItems.push(<span key="hw">{[unit(player.height, "cm"), unit(player.weight, "kg")].filter(Boolean).join(" · ")}</span>);
  if (player.birth_date) metaItems.push(
    <span key="born">
      Born {new Date(player.birth_date).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" })}
      {player.birth_place ? `, ${player.birth_place}` : ""}
    </span>,
  );

  const moves = ledger?.transfers.length ?? 0;
  const injuryCount = ledger?.injuries
    ? ledger.injuries.periods.filter((p) => ledger.seasons.some((s) => s.season === p.season)).length
    : null;

  return (
    <div className="mx-auto flex max-w-[1280px] flex-col gap-3">
      {/* Breadcrumb */}
      <nav className="flex items-center gap-2 text-[13px] text-text-muted" aria-label="Breadcrumb">
        <button onClick={() => navigate(-1)} className="hover:text-text">← Back</button>
        <span aria-hidden="true">·</span>
        <button onClick={() => navigate("/players/market")} className="hover:text-text">Market</button>
        <span aria-hidden="true">/</span>
        <span className="truncate text-text-secondary">{player.name}</span>
      </nav>

      {/* Header */}
      <div className="flex flex-wrap items-start gap-3.5">
        {player.photo_url ? (
          <img src={player.photo_url} alt={player.name} loading="lazy"
            className="h-[52px] w-[52px] shrink-0 rounded-full object-cover object-top ring-2 ring-border" />
        ) : (
          <div className={`flex h-[52px] w-[52px] shrink-0 items-center justify-center rounded-full text-[22px] font-extrabold ring-2 ${avatarBg}`}>
            {player.name[0]?.toUpperCase()}
          </div>
        )}
        <div className="flex min-w-[280px] flex-1 flex-col gap-1">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-[22px] font-bold text-text">{player.name}</h1>
            {player.is_verified_player && <VerifiedBadge />}
            {player.position && <Badge variant={positionVariant(player.position)}>{player.position}</Badge>}
            {isContracted ? (
              <Badge variant="info">Contracted</Badge>
            ) : (
              <Badge variant={playerStatusVariant(player.status)}>{playerStatusLabel(player.status)}</Badge>
            )}
            {/* open_to_offers now means "listed" (sales/service.sync_listed_flag). */}
            {player.open_to_offers && (
              <span className="flex items-center gap-1 rounded-full bg-success/15 px-2 py-0.5 text-[11px] font-semibold text-success-text">
                <span className="h-1.5 w-1.5 rounded-full bg-success" aria-hidden="true" /> Listed
              </span>
            )}
            {isMyPlayer && competition && competition.active_count > 0 && (
              <button
                onClick={() => navigate("/offers/received")}
                className="flex items-center gap-1 rounded-full bg-accent/15 px-2 py-0.5 text-[11px] font-semibold text-accent hover:bg-accent/25"
              >
                <span className="h-1.5 w-1.5 rounded-full bg-accent" aria-hidden="true" />
                {competition.active_count} active offer{competition.active_count !== 1 ? "s" : ""}
              </button>
            )}
          </div>
          {metaItems.length > 0 && (
            <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[13px] text-text-secondary">
              {metaItems.map((m, i) => (
                <span key={i} className="flex items-center gap-2">{i > 0 && <span aria-hidden="true" className="text-text-muted">·</span>}{m}</span>
              ))}
            </p>
          )}
          {/* A loan is public knowledge, and it changes who an approach
              goes to: the club shown above holds his registration, but
              the parent club owns him and is the one who can sell. */}
          {player.active_loan && (
            <p className="text-[13px] text-accent">
              On loan at {player.active_loan.loanee_club?.name ?? "another club"} until{" "}
              {new Date(player.active_loan.end_date).toLocaleDateString("en-GB", { month: "long", year: "numeric" })}
              {player.active_loan.parent_club?.name && (
                <span className="text-text-muted"> · owned by {player.active_loan.parent_club.name}</span>
              )}
            </p>
          )}
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2 flex-wrap">
          <button
            onClick={() => toggle(player.id)}
            title={has(player.id) ? "Remove from comparison" : "Add to comparison"}
            className={`flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium ring-1 transition-colors ${
              has(player.id)
                ? "bg-success/15 text-success-text ring-success/30"
                : "bg-surface-inset text-text-muted ring-input-border hover:text-text"
            }`}
          >
            <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
            Compare
          </button>

          {/* Not until his listing state is known, or a listed player
              offers "List for sale" for a moment. */}
          {canList && listingsKnown && (
            listingId ? (
              <Button variant="secondary" onClick={() => navigate(`/sales/${listingId}`)}>
                View listing
              </Button>
            ) : (
              <>
                <Button
                  variant="primary"
                  disabled={player.active_deal?.status === "IN_PROGRESS" || !!listClosedReason}
                  title={
                    player.active_deal?.status === "IN_PROGRESS"
                      ? "A transfer deal is already in progress for this player"
                      : listClosedReason ?? undefined
                  }
                  onClick={() => setListOpen(true)}
                >
                  List for sale
                </Button>
                {/* The deal case needs no line here: the deal banner
                    below already says so. */}
                {listClosedReason && (
                  <span className="text-[13px] text-text-muted">{listClosedReason}</span>
                )}
              </>
            )
          )}

          {!isMyPlayer && (
            <>
              <AddToShortlistButton playerId={player.id} />
              {/* A club outside TransferX cannot answer an offer, and the
                  server refuses one — so say so here, instead of a Make
                  Offer that leads to an offer no one will ever see. */}
              {isOffPlatform && (
                <p className="basis-full text-[13px] text-text-muted">
                  {player.world_team?.name ?? player.team_name ?? "His club"} is not on TransferX, so an offer
                  could not be answered. Shortlist him to follow his form and contract.
                </p>
              )}
              {/* Ask first: the informal step before an offer, committing
                  nobody to anything. */}
              {isAuthenticated && !isAgent && can("MARKET_WRITE") && !isFreeAgentPlayer && !isOffPlatform && (
                <>
                  <Button variant="secondary" onClick={() => setAskOpen(true)}>
                    Ask about him
                  </Button>
                  <AskAboutPlayerModal
                    open={askOpen}
                    onClose={closeAsk}
                    player={{ id: player.id, name: player.name }}
                    ownerName={player.active_loan?.parent_club?.name ?? player.current_club?.name ?? "His club"}
                  />
                </>
              )}
              {isAuthenticated && !isAgent && can("MARKET_WRITE") && !isFreeAgentPlayer && !isOffPlatform && (
                <Button
                  variant="primary"
                  disabled={player.active_deal?.status === "IN_PROGRESS"}
                  title={player.active_deal?.status === "IN_PROGRESS" ? "A transfer deal is already in progress for this player" : undefined}
                  onClick={() => navigate(`/offers/new?player_id=${player.id}`)}
                >
                  Make Offer
                </Button>
              )}
              {isAuthenticated && !isAgent && can("MARKET_WRITE") && isFreeAgentPlayer && (
                <Button
                  variant="primary"
                  loading={signFreeAgentMutation.isPending}
                  disabled={player.active_deal?.status === "IN_PROGRESS"}
                  onClick={handleSignFreeAgent}
                >
                  Sign Free Agent
                </Button>
              )}
              {isAuthenticated && !isAgent && can("MARKET_WRITE") && inPreContractWindow && (
                <Button
                  variant="secondary"
                  loading={preContractMutation.isPending}
                  disabled={player.active_deal?.status === "IN_PROGRESS"}
                  title="Contract expires within 6 months — a pre-contract (Bosman) signing is legal"
                  onClick={handlePreContract}
                >
                  Offer Pre-Contract
                </Button>
              )}
              {isAuthenticated && !isAgent && can("MARKET_WRITE") && player.active_contract?.release_clause != null && (
                <Button
                  variant="danger"
                  loading={releaseClauseMutation.isPending}
                  disabled={player.active_deal?.status === "IN_PROGRESS"}
                  title={player.active_deal?.status === "IN_PROGRESS" ? "A transfer deal is already in progress for this player" : undefined}
                  onClick={handleTriggerReleaseClause}
                >
                  Trigger release clause ({formatCurrency(player.active_contract.release_clause)})
                </Button>
              )}
            </>
          )}

          {/* A club member whose role can't send offers sees why, not nothing. */}
        {isAuthenticated && !isAgent && !isPlayerAccount && !isMyPlayer && !can("MARKET_WRITE") && !isOffPlatform && (
          <Button variant="primary" disabled title="Your role can't send offers. Ask your club's owner or sporting director.">
            Make Offer
          </Button>
        )}
        {!isAuthenticated && !isOffPlatform && (
            <button
              onClick={() => navigate("/login")}
              className="rounded-lg bg-success/10 px-4 py-2 text-sm font-semibold text-success-text ring-1 ring-success/30 hover:bg-success/20 transition-colors"
            >
              Sign in to make offer
            </button>
          )}
        </div>
      </div>

      {/* Deal banner: new offers, the clause and listing pause while a deal is live */}
      {player.active_deal && <DealBanner deal={player.active_deal} />}

      {/* Facts strip */}
      <FactsStrip
        player={player}
        fairValue={isAuthenticated && !isPlayerAccount ? fairValue : null}
        form={{ score: ledger?.form.score ?? null, trend: ledger?.form.trend ?? null }}
        isMyPlayer={isMyPlayer}
        valuationPending={valuationMutation.isPending}
        onSaveValuation={(v) => valuationMutation.mutate(v)}
      />

      {/* Body: the ledger, and the panels for this viewer */}
      <div className="mt-1 grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_300px]">
        <div className="flex min-w-0 flex-col gap-3">
          <TabBar
            active={activeTab}
            onChange={setActiveTab}
            tabs={[
              { id: "overview", label: "Overview" },
              { id: "career", label: "Career", count: moves ? `${moves} move${moves === 1 ? "" : "s"}` : undefined },
              { id: "injuries", label: "Injuries", count: injuryCount ? String(injuryCount) : undefined },
            ]}
          />
          <div className="rounded-[14px] bg-surface p-4 ring-1 ring-border">
            {ledgerLoading || !ledger ? (
              <div className="flex justify-center py-10"><Spinner size="md" /></div>
            ) : activeTab === "career" ? (
              <CareerLedger ledger={ledger} />
            ) : activeTab === "injuries" ? (
              <InjuriesLedger ledger={ledger} />
            ) : (
              <OverviewLedger ledger={ledger} statSet={statSet} onStatSet={setStatSet} />
            )}
          </div>
        </div>

        <div className="flex flex-col gap-3">
          {isAuthenticated && !isMyPlayer && (
            <PlayerFitCard playerId={player.id} />
          )}
          {isMyPlayer && competition && <OffersPanel book={competition} onOpen={() => navigate("/offers/received")} />}
          {isPlayerAccount && (
            <div className="rounded-xl bg-surface px-3.5 py-3 text-[13px] text-text-secondary ring-1 ring-border">
              <p className="mb-1 text-sm font-semibold text-text">Your profile</p>
              Clubs see your season record, transfers and public injury history. Your contract terms stay private to you,
              your club and your agent.
            </div>
          )}
          {/* His own account: invite him so he answers personal terms himself */}
          {isMyPlayer && <PlayerAccountCard playerId={player.id} playerName={player.name} canInvite={can("TEAM_MANAGE")} />}
          {/* Selling: clubs whose squads look short in his position */}
          {isMyPlayer && can("MARKET_WRITE") && <PotentialBuyersPanel playerId={player.id} />}
          {isAgent && !isMyPlayer && id && (
            <AgentRepresentationCard playerId={id} />
          )}
        </div>
      </div>

      {canList && (
        <ListPlayerModal open={listOpen} onClose={closeListing} player={{ id: player.id, name: player.name }} />
      )}
    </div>
  );
}
