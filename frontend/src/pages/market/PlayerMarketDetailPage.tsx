import { useState, useRef, useEffect } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "../../lib/api";
import type { ActiveDealStub, Club, FairValueSignal, MandateResponse, OrderBook, Player, PlayerDetail, PlayerForm, PlayerStats } from "../../types/api";
import { useAuthStore } from "../../store/auth";
import { useClubCapabilities } from "../../hooks/useClubCapabilities";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import ClubLink from "../../components/ui/ClubLink";
import Spinner from "../../components/ui/Spinner";
import StatsPanel from "../../components/players/StatsPanel";
import VerifiedBadge from "../../components/verification/VerifiedBadge";
import {
  positionVariant,
  playerStatusLabel,
  playerStatusVariant,
} from "../../lib/badges";
import { formatCurrency, formatDate, formatWage } from "../../lib/utils";
import AddToShortlistButton from "../../components/scouting/AddToShortlistButton";
import { useCompare } from "../../context/CompareContext";
import CareerHistoryPanel from "../../components/players/CareerHistoryPanel";
import InjuryHistoryPanel from "../../components/players/InjuryHistoryPanel";
import { PlayerFitCard } from "../../components/ai/PlayerFitCard";
import FairValueBadge from "../../components/players/FairValueBadge";
import { Skeleton } from "../../components/ui/Skeleton";
import { useConfirm } from "../../context/ConfirmContext";

// ── Valuation card (TRA-73) ───────────────────────────────────────────────────

const SOURCE_LABEL: Record<string, string> = {
  ETV: "ETV",
  TRANSFERMARKT: "Transfermarkt",
  MANUAL: "Manual",
};

function ValuationCard({ player, isAuthenticated }: { player: Player; isAuthenticated: boolean }) {
  if (!isAuthenticated) return null;
  if (player.market_value == null) return null;

  const currency = player.market_value_currency ?? "EUR";
  const formatter = (v: number) =>
    new Intl.NumberFormat("en-GB", {
      style: "currency",
      currency,
      maximumFractionDigits: 0,
      notation: "compact",
    }).format(v);

  return (
    <div className="rounded-xl bg-surface-inset px-4 py-3 ring-1 ring-border">
      <div className="flex items-center justify-between mb-2">
        <p className="text-[11px] font-bold uppercase tracking-wider text-text-muted">Market Value</p>
        {player.valuation_source && (
          <span className="text-[13px] font-semibold text-text-muted bg-surface px-1.5 py-0.5 rounded">
            {SOURCE_LABEL[player.valuation_source] ?? player.valuation_source}
          </span>
        )}
      </div>

      <p className="text-xl font-bold text-text tabular-nums">
        {formatter(player.market_value)}
      </p>

      {(player.valuation_low != null || player.valuation_high != null) && (
        <p className="text-xs text-text-muted mt-0.5">
          Range:{" "}
          {player.valuation_low != null ? formatter(player.valuation_low) : "—"}
          {" – "}
          {player.valuation_high != null ? formatter(player.valuation_high) : "—"}
        </p>
      )}

      {player.valuation_as_of && (
        <p className="text-[13px] text-text-muted mt-1">
          As of {formatDate(player.valuation_as_of)}
        </p>
      )}
    </div>
  );
}


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

// ── Bio chip ───────────────────────────────────────────────────────────────────

function BioChip({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center gap-1.5 rounded-lg bg-surface-inset px-3 py-1.5 ring-1 ring-border">
      <span className="text-[11px] font-medium text-text-muted uppercase tracking-wide">{label}</span>
      <span className="text-sm font-semibold text-text">{value}</span>
    </div>
  );
}

// ── Contract sidebar ───────────────────────────────────────────────────────────

interface ContractSidebarProps {
  player: PlayerDetail;
  isMyPlayer: boolean;
  isAuthenticated: boolean;
  editingValuation: boolean;
  valuationDraft: string;
  valuationPending: boolean;
  onStartEditValuation: () => void;
  onValuationChange: (v: string) => void;
  onCommitValuation: () => void;
  onCancelValuation: () => void;
  onNavigateLogin: () => void;
}

function ContractSidebar({
  player,
  isMyPlayer,
  isAuthenticated,
  editingValuation,
  valuationDraft,
  valuationPending,
  onStartEditValuation,
  onValuationChange,
  onCommitValuation,
  onCancelValuation,
  onNavigateLogin,
}: ContractSidebarProps) {
  const contract = player.active_contract;
  const isFreeAgent =
    player.status === "FREE_AGENT" && !player.current_club && !player.team_name;

  // Row helper
  function Row({ label, value, accent }: { label: string; value: string; accent?: string }) {
    return (
      <div className="flex items-center justify-between py-2 border-b border-rule-faint last:border-0">
        <span className="text-xs text-text-muted">{label}</span>
        <span className={`text-sm font-semibold tabular-nums ${accent ?? "text-text"}`}>{value}</span>
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <div className="rounded-xl bg-surface-inset px-4 py-4 ring-1 ring-border text-sm text-text-muted">
        <button onClick={onNavigateLogin} className="text-success-text hover:underline font-medium">
          Sign in
        </button>{" "}
        to view contract details and make offers.
      </div>
    );
  }

  if (isFreeAgent) {
    return (
      <div className="rounded-xl bg-success/10 px-4 py-4 ring-1 ring-success/30">
        <p className="text-sm font-semibold text-success-text">Available — Free Agent</p>
        <p className="mt-0.5 text-xs text-text-muted">No contract with any club.</p>
      </div>
    );
  }

  return (
    <div className="rounded-xl bg-surface-inset px-4 py-3 ring-1 ring-border">
      <p className="mb-2 text-[11px] font-bold uppercase tracking-wider text-text-muted">Contract</p>
      {contract ? (
        <div>
          {contract.start_date && isMyPlayer && (
            <Row label="Start" value={formatDate(contract.start_date)} />
          )}
          {(contract.end_date ?? player.contract_expiry) && (
            <Row
              label="Expires"
              value={formatDate((contract.end_date ?? player.contract_expiry)!)}
            />
          )}
          {(contract.wage_weekly ?? player.wage_weekly) != null && (
            <Row
              label={`Weekly wage${player.wage_source && !contract.wage_weekly ? ` (${player.wage_source === "CAPOLOGY" ? "Capology" : "est."})` : ""}`}
              value={formatWage((contract.wage_weekly ?? player.wage_weekly)!)}
              accent="text-success-text"
            />
          )}
          {contract.release_clause != null && (
            <Row label="Release clause" value={formatCurrency(contract.release_clause)} />
          )}

          {/* Club valuation — owner editable */}
          {isMyPlayer && (
            <div className="flex items-center justify-between py-2 border-b border-rule-faint last:border-0">
              <span className="text-xs text-text-muted">Club valuation</span>
              {editingValuation ? (
                <div className="flex items-center gap-2">
                  <input
                    autoFocus
                    type="text"
                    value={valuationDraft}
                    onChange={(e) => onValuationChange(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") onCommitValuation();
                      if (e.key === "Escape") onCancelValuation();
                    }}
                    placeholder="e.g. 5000000"
                    className="w-28 rounded-md bg-surface px-2 py-1 text-xs text-text ring-1 ring-success/50 focus:outline-none"
                  />
                  <button
                    onClick={onCommitValuation}
                    disabled={valuationPending}
                    className="text-xs font-medium text-success-text hover:text-success-text-alt disabled:opacity-50"
                  >
                    Save
                  </button>
                  <button onClick={onCancelValuation} className="text-xs text-text-muted hover:text-text-secondary">
                    ✕
                  </button>
                </div>
              ) : (
                <button
                  onClick={onStartEditValuation}
                  className="group flex items-center gap-1.5 text-sm"
                  title="Click to edit"
                >
                  {contract.club_valuation != null ? (
                    <span className="font-semibold text-text group-hover:text-success-text transition-colors">
                      {formatCurrency(contract.club_valuation)}
                    </span>
                  ) : (
                    <span className="text-text-muted group-hover:text-text-secondary transition-colors text-xs">
                      Not set
                    </span>
                  )}
                  <svg className="h-3 w-3 text-text-muted group-hover:text-text-secondary" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                  </svg>
                </button>
              )}
            </div>
          )}

          {contract.notes && isMyPlayer && (
            <div className="mt-2 rounded-lg bg-surface px-3 py-2">
              <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted mb-0.5">Notes</p>
              <p className="text-xs text-text-secondary">{contract.notes}</p>
            </div>
          )}
        </div>
      ) : (
        <p className="text-xs text-text-muted py-1">
          {isMyPlayer
            ? "No formal contract on file. Add one via the admin panel."
            : "Contract details not available."}
        </p>
      )}
    </div>
  );
}

// ── Tab bar ────────────────────────────────────────────────────────────────────

type ProfileTab = "overview" | "career" | "medical";

interface TabDef { id: ProfileTab; label: string; authRequired?: boolean }

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
      className="relative mb-4 flex gap-1 border-b border-rule pb-px"
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
        </button>
      ))}
    </div>
  );
}

// ── Agent representation card ─────────────────────────────────────────────────

function AgentRepresentationCard({ playerId }: { playerId: string }) {
  const queryClient = useQueryClient();

  const { data: mandates = [], refetch } = useQuery<MandateResponse[]>({
    queryKey: ["players", playerId, "representation"],
    queryFn: () =>
      api.get<MandateResponse[]>(`/players/${playerId}/representation`).then((r) => r.data),
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

      {mandates.length > 0 && (
        <div className="mb-3 divide-y divide-rule-faint">
          {mandates.map((m) => (
            <div key={m.id} className="flex items-center justify-between py-2">
              <div className="text-xs">
                {m.exclusive
                  ? <span className="font-semibold text-success-text">Exclusive</span>
                  : <span className="text-text-muted">Non-exclusive</span>}
                {m.end_date && (
                  <span className="ml-2 text-text-muted">until {m.end_date}</span>
                )}
                {m.territory && (
                  <span className="ml-2 text-text-muted">· {m.territory}</span>
                )}
              </div>
              <button
                onClick={() => handleRevoke(m.id)}
                className="ml-3 text-xs text-danger-text hover:text-danger-text-alt transition-colors"
              >
                Revoke
              </button>
            </div>
          ))}
        </div>
      )}

      {success ? (
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

// ── Page ───────────────────────────────────────────────────────────────────────

export default function PlayerMarketDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const confirm = useConfirm();
  const { accessToken, user } = useAuthStore();
  const { can } = useClubCapabilities();
  const isAuthenticated = !!accessToken;
  const isAgent = user?.user_type === "AGENT";
  const isPlayerAccount = user?.user_type === "PLAYER";
  const { toggle, has } = useCompare();
  const [activeTab, setActiveTab] = useState<ProfileTab>("overview");

  const { data: player, isLoading, isError } = useQuery<PlayerDetail>({
    queryKey: ["players", "market", id],
    queryFn: () => api.get<PlayerDetail>(`/players/market/${id}`).then((r) => r.data),
    enabled: !!id,
  });

  const { data: stats = [] } = useQuery<PlayerStats[]>({
    queryKey: ["players", id, "stats"],
    queryFn: () => api.get<PlayerStats[]>(`/players/${id}/stats`).then((r) => r.data),
    enabled: !!id,
    retry: false,
  });

  const { data: form = null } = useQuery<PlayerForm | null>({
    queryKey: ["players", id, "form"],
    queryFn: () =>
      api.get<PlayerForm>(`/players/${id}/form`).then((r) => r.data).catch(() => null),
    enabled: !!id,
  });

  const { data: myClub } = useQuery<Club>({
    queryKey: ["clubs", "me"],
    queryFn: () => api.get<Club>("/clubs/me").then((r) => r.data),
    enabled: isAuthenticated,
    staleTime: 60_000,
  });

  // TRA-92: fair-value model signal — never requested for a player identity (D6)
  const { data: fairValue = null, isLoading: fairValueLoading } = useQuery<FairValueSignal | null>({
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

  const toggleOTOMutation = useMutation({
    mutationFn: (next: boolean) =>
      api.patch(`/clubs/me/players/${id}`, { open_to_offers: next }).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["players", "market", id] });
    },
  });

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

  // ── Valuation inline edit ──────────────────────────────────────────────────
  const [editingValuation, setEditingValuation] = useState(false);
  const [valuationDraft, setValuationDraft] = useState("");

  const valuationMutation = useMutation({
    mutationFn: (value: number | null) =>
      api.patch(`/clubs/me/players/${id}`, { club_valuation: value }).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["players", "market", id] });
      setEditingValuation(false);
    },
  });

  function commitValuation() {
    const trimmed = valuationDraft.trim();
    const parsed = trimmed === "" ? null : Number(trimmed.replace(/[^0-9.]/g, ""));
    valuationMutation.mutate(parsed != null && !isNaN(parsed) ? parsed : null);
  }

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

  return (
    <div>
      {/* Back */}
      <button
        onClick={() => navigate(-1)}
        className="mb-4 flex items-center gap-1.5 text-sm text-text-muted hover:text-text transition-colors"
      >
        ← Back
      </button>

      {/* ── Hero ────────────────────────────────────────────────────────────── */}
      <div className="mb-4 rounded-xl bg-surface ring-1 ring-border p-5">
        <div className="flex items-start gap-5">
          <div className="shrink-0">
            {player.photo_url ? (
              <img
                src={player.photo_url}
                alt={player.name}
                loading="lazy"
                className="h-20 w-20 rounded-full object-cover object-top ring-2 ring-border"
              />
            ) : (
              <div className={`h-20 w-20 rounded-full flex items-center justify-center text-3xl font-black ring-2 ${avatarBg}`}>
                {player.name[0]?.toUpperCase()}
              </div>
            )}
          </div>

          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <h1 className="text-2xl font-bold text-text">{player.name}</h1>
                  {player.is_verified_player && <VerifiedBadge />}
                </div>
                <div className="mt-1.5 flex flex-wrap items-center gap-2">
                  {player.position && (
                    <Badge variant={positionVariant(player.position)}>{player.position}</Badge>
                  )}
                  {isContracted ? (
                    <Badge variant="info">Contracted</Badge>
                  ) : (
                    <Badge variant={playerStatusVariant(player.status)}>
                      {playerStatusLabel(player.status)}
                    </Badge>
                  )}
                  {player.open_to_offers && (
                    <span className="flex items-center gap-1 rounded-full bg-success/15 px-2 py-0.5 ring-1 ring-success/30">
                      <span className="h-1.5 w-1.5 rounded-full bg-success animate-pulse" />
                      <span className="text-xs font-semibold text-success-text">Open to offers</span>
                    </span>
                  )}
                  {isMyPlayer && competition && competition.active_count > 0 && (
                    <button
                      onClick={() => navigate("/offers/received")}
                      className="flex items-center gap-1.5 rounded-full bg-accent/15 px-2.5 py-0.5 ring-1 ring-accent/25 hover:bg-accent/25 transition-colors"
                    >
                      <span className="h-1.5 w-1.5 rounded-full bg-accent animate-pulse" />
                      <span className="text-xs font-semibold text-accent">
                        {competition.active_count} active offer{competition.active_count !== 1 ? "s" : ""}
                      </span>
                    </button>
                  )}
                </div>

                {/* Club line */}
                {clubName && (
                  <div className="mt-2 flex items-center gap-1.5 text-sm text-text-muted">
                    {clubCrest ? (
                      <img src={clubCrest} alt={clubName} loading="lazy" className="h-4 w-4 object-contain" />
                    ) : (
                      <span className="h-4 w-4 rounded-full bg-surface-inset flex items-center justify-center text-[11px] font-bold text-text-muted">
                        {clubName[0]?.toUpperCase()}
                      </span>
                    )}
                    <ClubLink
                      id={player.current_club?.id}
                      worldTeamId={player.world_team?.id}
                      name={clubName}
                    />
                  </div>
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

                {isMyPlayer && can("MARKET_WRITE") && (
                  <button
                    disabled={toggleOTOMutation.isPending || player.active_deal?.status === "IN_PROGRESS"}
                    title={player.active_deal?.status === "IN_PROGRESS" ? "Cannot change while a transfer deal is in progress" : undefined}
                    onClick={() => toggleOTOMutation.mutate(!player.open_to_offers)}
                    className={`flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium ring-1 transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${
                      player.open_to_offers
                        ? "bg-success/15 text-success-text ring-success/30 hover:bg-success/25"
                        : "bg-surface-inset text-text-muted ring-input-border hover:text-text"
                    }`}
                  >
                    <span className={`h-2 w-2 rounded-full ${player.open_to_offers ? "bg-success animate-pulse" : "bg-border"}`} />
                    {player.open_to_offers ? "Open to offers" : "Closed to offers"}
                  </button>
                )}

                {!isMyPlayer && (
                  <>
                    <AddToShortlistButton playerId={player.id} />
                    {isAuthenticated && !isAgent && can("MARKET_WRITE") && !isFreeAgentPlayer && (
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

                {!isAuthenticated && (
                  <button
                    onClick={() => navigate("/login")}
                    className="rounded-lg bg-success/10 px-4 py-2 text-sm font-semibold text-success-text ring-1 ring-success/30 hover:bg-success/20 transition-colors"
                  >
                    Sign in to make offer
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ── Deal banner ─────────────────────────────────────────────────────── */}
      {player.active_deal && (
        <DealBanner deal={player.active_deal} />
      )}

      {/* ── Bio strip ───────────────────────────────────────────────────────── */}
      {bioChips.length > 0 && (
        <div className="mb-4 flex flex-wrap gap-2">
          {bioChips.map((chip) => (
            <BioChip key={chip.label} label={chip.label} value={chip.value} />
          ))}
        </div>
      )}

      {/* ── Main two-column layout ───────────────────────────────────────────── */}
      <div className="grid gap-4 lg:grid-cols-3">

        {/* ── Left: tabbed content (spans 2 cols) ─────────────────────────── */}
        <div className="lg:col-span-2">
          <TabBar
            active={activeTab}
            onChange={setActiveTab}
            tabs={[
              { id: "overview", label: "Overview" },
              { id: "career",   label: "Career" },
              ...(isAuthenticated ? [{ id: "medical" as ProfileTab, label: "Medical" }] : []),
            ]}
          />

          {activeTab === "overview" && (
            <Card>
              <StatsPanel stats={stats} form={form} position={player.position} />
            </Card>
          )}

          {activeTab === "career" && (
            <Card>
              <CareerHistoryPanel playerId={player.id} />
            </Card>
          )}

          {activeTab === "medical" && isAuthenticated && (
            <Card>
              <InjuryHistoryPanel playerId={player.id} />
            </Card>
          )}
        </div>

        {/* ── Right: sidebar ──────────────────────────────────────────────── */}
        <div className="space-y-3">
          {/* Fair-value model signal (TRA-92) — value + range only; a profile
              has no reference price */}
          {isAuthenticated && !isPlayerAccount && (
            <Card>
              <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-text-muted">
                Model Valuation
              </p>
              {fairValueLoading ? (
                <Skeleton className="h-5 w-48" />
              ) : fairValue ? (
                <FairValueBadge signal={fairValue} />
              ) : (
                <p className="text-xs text-text-muted">
                  No model valuation — insufficient recent data.
                </p>
              )}
            </Card>
          )}
          {/* Market valuation (TRA-73) */}
          {player.market_value != null && (
            <ValuationCard player={player} isAuthenticated={isAuthenticated} />
          )}
          <ContractSidebar
            player={player}
            isMyPlayer={isMyPlayer}
            isAuthenticated={isAuthenticated}
            editingValuation={editingValuation}
            valuationDraft={valuationDraft}
            valuationPending={valuationMutation.isPending}
            onStartEditValuation={() => {
              setValuationDraft(
                player.active_contract?.club_valuation != null
                  ? String(player.active_contract.club_valuation)
                  : ""
              );
              setEditingValuation(true);
            }}
            onValuationChange={setValuationDraft}
            onCommitValuation={commitValuation}
            onCancelValuation={() => setEditingValuation(false)}
            onNavigateLogin={() => navigate("/login")}
          />
          {isAuthenticated && !isMyPlayer && (
            <PlayerFitCard playerId={player.id} />
          )}
          {isAgent && !isMyPlayer && id && (
            <AgentRepresentationCard playerId={id} />
          )}
        </div>
      </div>
    </div>
  );
}
