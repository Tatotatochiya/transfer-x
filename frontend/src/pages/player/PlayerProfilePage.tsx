import { useEffect, useState } from "react";
import OnboardingChecklist from "../../components/OnboardingChecklist";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "../../lib/api";
import type { MandateResponse, PersonalTerms, PlayerDetail } from "../../types/api";
import type { AgreementStatus, PlayerVisibility } from "../../types/enums";
import Card from "../../components/ui/Card";
import PageHeader from "../../components/ui/PageHeader";
import Spinner from "../../components/ui/Spinner";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import VerifiedBadge from "../../components/verification/VerifiedBadge";
import RequestVerificationPanel from "../../components/verification/RequestVerificationPanel";
import { formatCurrency, formatWage } from "../../lib/utils";

// ── Visibility selector ───────────────────────────────────────────────────────

const VISIBILITY_OPTIONS: { value: PlayerVisibility; label: string; description: string }[] = [
  { value: "PUBLIC",     label: "Public",      description: "Anyone can view your profile" },
  { value: "CLUBS_ONLY", label: "Clubs only",  description: "Signed-in clubs and agents only" },
  { value: "PRIVATE",    label: "Private",     description: "Only you can view your profile" },
];

function VisibilitySelector({
  value,
  onChange,
}: {
  value: PlayerVisibility;
  onChange: (v: PlayerVisibility) => void;
}) {
  return (
    <div className="flex gap-2">
      {VISIBILITY_OPTIONS.map((opt) => (
        <button
          key={opt.value}
          type="button"
          onClick={() => onChange(opt.value)}
          title={opt.description}
          className={`flex-1 rounded-lg px-3 py-2 text-xs font-medium ring-1 transition-all ${
            value === opt.value
              ? "bg-accent/15 ring-accent text-accent"
              : "bg-surface-inset ring-input-border text-text-muted hover:text-text hover:ring-accent"
          }`}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}

// ── Mandate row ───────────────────────────────────────────────────────────────

function MandateRow({
  mandate,
  playerId,
  onRevoked,
}: {
  mandate: MandateResponse;
  playerId: string;
  onRevoked: () => void;
}) {
  const [revoking, setRevoking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleRevoke() {
    setRevoking(true);
    setError(null);
    try {
      await api.post(`/players/${playerId}/representation/${mandate.id}/revoke`);
      onRevoked();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(typeof msg === "string" ? msg : "Failed to revoke mandate.");
    } finally {
      setRevoking(false);
    }
  }

  return (
    <div className="flex items-start justify-between gap-4 py-3 border-b border-rule-faint last:border-0">
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm font-medium text-text">Agent representation</span>
          {mandate.exclusive && <Badge variant="success">Exclusive</Badge>}
        </div>
        <div className="mt-0.5 flex flex-wrap gap-x-3 gap-y-0.5 text-xs text-text-muted">
          {mandate.start_date && <span>From {mandate.start_date}</span>}
          {mandate.end_date   && <span>Until {mandate.end_date}</span>}
          {mandate.territory  && <span>Territory: {mandate.territory}</span>}
          <span>Since {new Date(mandate.created_at).toLocaleDateString()}</span>
        </div>
        {error && <p className="mt-1 text-xs text-danger-text">{error}</p>}
      </div>
      <button
        onClick={handleRevoke}
        disabled={revoking}
        className="shrink-0 rounded-lg bg-danger/10 px-3 py-1.5 text-xs font-medium text-danger-text ring-1 ring-danger/30 hover:bg-danger/20 transition-colors disabled:opacity-50"
      >
        {revoking ? "Revoking…" : "Revoke"}
      </button>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function PlayerProfilePage() {
  const queryClient = useQueryClient();

  const { data: player, isLoading } = useQuery<PlayerDetail>({
    queryKey: ["players", "me"],
    queryFn: () => api.get<PlayerDetail>("/players/me").then((r) => r.data),
  });

  const { data: mandates = [], refetch: refetchMandates } = useQuery<MandateResponse[]>({
    queryKey: ["players", player?.id, "representation"],
    queryFn: () =>
      api.get<MandateResponse[]>(`/players/${player!.id}/representation`).then((r) => r.data),
    enabled: !!player?.id,
  });

  const activeDealId = player?.active_deal?.id ?? null;
  const dealInPersonalTerms = player?.active_deal?.stage === "PERSONAL_TERMS";

  const { data: personalTerms } = useQuery<PersonalTerms>({
    queryKey: ["deals", activeDealId, "personal-terms"],
    queryFn: () =>
      api.get<PersonalTerms>(`/deals/${activeDealId}/personal-terms`).then((r) => r.data),
    enabled: !!activeDealId && dealInPersonalTerms,
  });

  const consentMutation = useMutation({
    mutationFn: (agreement: AgreementStatus) =>
      api.post(`/deals/${activeDealId}/personal-terms/player-consent`, { agreement }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["players", "me"] });
      queryClient.invalidateQueries({ queryKey: ["deals", activeDealId, "personal-terms"] });
    },
  });

  const [visibility, setVisibility] = useState<PlayerVisibility>("PUBLIC");
  const [openToOffers, setOpenToOffers] = useState(false);
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);

  useEffect(() => {
    if (player) {
      setVisibility(player.visibility as PlayerVisibility);
      setOpenToOffers(player.open_to_offers);
      setDirty(false);
    }
  }, [player]);

  function handleVisibilityChange(v: PlayerVisibility) {
    setVisibility(v);
    setDirty(true);
  }

  function handleOTOChange(v: boolean) {
    setOpenToOffers(v);
    setDirty(true);
  }

  async function handleSave() {
    setSaving(true);
    try {
      await api.patch("/players/me", { visibility, open_to_offers: openToOffers });
      await queryClient.invalidateQueries({ queryKey: ["players", "me"] });
      setDirty(false);
    } finally {
      setSaving(false);
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Spinner size="lg" />
      </div>
    );
  }

  if (!player) return null;

  return (
    <div className="max-w-xl">
      <PageHeader
        title={player.name}
        subtitle={player.position ?? "Player"}
        actions={player.is_verified_player ? <VerifiedBadge /> : undefined}
      />

      {/* First-run checklist (Phase 6) */}
      <OnboardingChecklist />

      {/* Visibility & open-to-offers controls */}
      <Card>
        <p className="mb-4 text-xs font-semibold uppercase tracking-wider text-text-muted">
          Profile settings
        </p>

        <div className="space-y-4">
          <div>
            <p className="mb-2 text-sm font-medium text-text-secondary">Visibility</p>
            <VisibilitySelector value={visibility} onChange={handleVisibilityChange} />
          </div>

          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-text-secondary">Open to offers</p>
              <p className="text-xs text-text-muted">Clubs can express interest in signing you</p>
            </div>
            <button
              type="button"
              onClick={() => handleOTOChange(!openToOffers)}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                openToOffers ? "bg-success" : "bg-border"
              }`}
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                  openToOffers ? "translate-x-6" : "translate-x-1"
                }`}
              />
            </button>
          </div>

          {dirty && (
            <Button
              variant="primary-success"
              className="w-full"
              loading={saving}
              onClick={handleSave}
            >
              Save changes
            </Button>
          )}

          <RequestVerificationPanel verified={player.is_verified_player} />
        </div>
      </Card>

      {/* Personal terms consent (TRA-74) */}
      {dealInPersonalTerms && personalTerms && personalTerms.player_consent === "PENDING" && (
        <div className="mt-6 rounded-xl bg-warning-bg ring-1 ring-warning-fill/25 px-5 py-5">
          <p className="text-sm font-semibold text-warning-text mb-1">Personal terms require your consent</p>
          <p className="text-xs text-warning-text-alt mb-4">
            Your agent has proposed the following contract terms to join{" "}
            <span className="font-semibold text-warning-text">{personalTerms.buyer_club_name}</span>. Review and respond.
          </p>
          <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm mb-5">
            {personalTerms.wage_weekly != null && (
              <><dt className="text-text-muted">Weekly wage</dt><dd className="text-text font-semibold">{formatWage(personalTerms.wage_weekly)}</dd></>
            )}
            {personalTerms.signing_bonus != null && (
              <><dt className="text-text-muted">Signing bonus</dt><dd className="text-text font-semibold">{formatCurrency(personalTerms.signing_bonus)}</dd></>
            )}
            {personalTerms.length_years != null && (
              <><dt className="text-text-muted">Contract length</dt><dd className="text-text font-semibold">{personalTerms.length_years} yr{personalTerms.length_years !== 1 ? "s" : ""}</dd></>
            )}
          </dl>
          <div className="flex gap-3">
            <button
              onClick={() => consentMutation.mutate("AGREED")}
              disabled={consentMutation.isPending}
              className="flex-1 rounded-lg bg-success px-4 py-2 text-sm font-semibold text-white hover:bg-success-text-alt transition-colors disabled:opacity-50"
            >
              {consentMutation.isPending ? "…" : "Accept terms"}
            </button>
            <button
              onClick={() => consentMutation.mutate("DECLINED")}
              disabled={consentMutation.isPending}
              className="flex-1 rounded-lg bg-danger/15 px-4 py-2 text-sm font-semibold text-danger-text ring-1 ring-danger/30 hover:bg-danger/25 transition-colors disabled:opacity-50"
            >
              Decline
            </button>
          </div>
          {consentMutation.isError && (
            <p className="mt-2 text-xs text-danger-text">Failed to respond. Please try again.</p>
          )}
        </div>
      )}

      {/* Personal terms accepted/declined status (read-only) */}
      {dealInPersonalTerms && personalTerms && personalTerms.player_consent !== "PENDING" && (
        <div className={`mt-6 rounded-xl px-5 py-4 text-sm ring-1 ${
          personalTerms.player_consent === "AGREED"
            ? "bg-success/10 text-success-text-alt ring-success/20"
            : "bg-danger/10 text-danger-text-alt ring-danger/20"
        }`}>
          <p className="font-semibold">
            Personal terms {personalTerms.player_consent === "AGREED" ? "accepted" : "declined"} — {personalTerms.buyer_club_name}
          </p>
        </div>
      )}

      {/* Representation */}
      <div className="mt-6">
        <Card>
          <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-text-muted">
            Representation
          </p>

          {mandates.length === 0 ? (
            <p className="text-sm text-text-muted py-2">
              No active agent representation.
            </p>
          ) : (
            <div>
              {mandates.map((m) => (
                <MandateRow
                  key={m.id}
                  mandate={m}
                  playerId={player.id}
                  onRevoked={() => refetchMandates()}
                />
              ))}
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
