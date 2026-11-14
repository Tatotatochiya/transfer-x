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
import EndTransferDialog from "../../components/deals/EndTransferDialog";
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
          className={`flex-1 rounded-lg px-3 py-2 text-caption font-medium ring-1 transition-all ${
            value === opt.value
              ? "bg-accent-bg ring-accent text-accent"
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
          <span className="text-body font-medium text-text">Agent representation</span>
          {mandate.exclusive && <Badge variant="success">Exclusive</Badge>}
        </div>
        <div className="mt-0.5 flex flex-wrap gap-x-3 gap-y-0.5 text-small text-text-muted">
          {mandate.start_date && <span>From {mandate.start_date}</span>}
          {mandate.end_date   && <span>Until {mandate.end_date}</span>}
          {mandate.territory  && <span>Territory: {mandate.territory}</span>}
          <span>Since {new Date(mandate.created_at).toLocaleDateString()}</span>
        </div>
        {error && <p className="mt-1 text-small text-danger-text">{error}</p>}
      </div>
      <button
        onClick={handleRevoke}
        disabled={revoking}
        className="shrink-0 rounded-lg bg-danger-bg px-3 py-1.5 text-caption font-medium text-danger-text ring-1 ring-danger-ring hover:brightness-95 transition-colors disabled:opacity-50"
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
    mutationFn: ({ agreement, reason }: { agreement: AgreementStatus; reason?: string | null }) =>
      api.post(`/deals/${activeDealId}/personal-terms/player-consent`, { agreement, reason }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["players", "me"] });
      queryClient.invalidateQueries({ queryKey: ["deals", activeDealId, "personal-terms"] });
      setDeclining(false);
    },
  });
  // ADR 0012: the player can counter the club's terms himself.
  const [countering, setCountering] = useState(false);
  const [declining, setDeclining] = useState(false);
  const [counter, setCounter] = useState({ wage: "", bonus: "", years: "", note: "" });
  const counterMutation = useMutation({
    mutationFn: () => api.put(`/deals/${activeDealId}/personal-terms`, {
      wage_weekly: Number(counter.wage), signing_bonus: counter.bonus ? Number(counter.bonus) : null,
      length_years: Number(counter.years), note: counter.note.trim() || null,
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["deals", activeDealId, "personal-terms"] });
      setCountering(false);
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
      // A player at a club is made available by his club listing him; the
      // server refuses his own switch (product ADR 0005), so only a free agent
      // sends it.
      await api.patch("/players/me", player?.current_club ? { visibility } : { visibility, open_to_offers: openToOffers });
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
        <p className="mb-4 text-caption font-semibold text-text-secondary">
          Profile settings
        </p>

        <div className="space-y-4">
          <div>
            <p className="mb-2 text-body font-medium text-text-secondary">Visibility</p>
            <VisibilitySelector value={visibility} onChange={handleVisibilityChange} />
          </div>

          {player.current_club ? (
            <div>
              <p className="text-body font-medium text-text-secondary">Available for transfer</p>
              <p className="text-small text-text-muted">
                {player.open_to_offers
                  ? `Yes — ${player.current_club.name} has listed you.`
                  : `Not listed. ${player.current_club.name} makes you available by listing you.`}
              </p>
            </div>
          ) : (
          <div className="flex items-center justify-between">
            <div>
              <p className="text-body font-medium text-text-secondary">Open to offers</p>
              <p className="text-small text-text-muted">Clubs can express interest in signing you</p>
            </div>
            <button
              type="button"
              onClick={() => handleOTOChange(!openToOffers)}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                openToOffers ? "bg-accent" : "bg-border"
              }`}
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                  openToOffers ? "translate-x-6" : "translate-x-1"
                }`}
              />
            </button>
          </div>
          )}

          {dirty && (
            <Button
              variant="primary"
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
      {dealInPersonalTerms && personalTerms && personalTerms.player_consent === "PENDING" && personalTerms.proposed_by === "PLAYER" && (
        <div className="mt-6 rounded-xl bg-surface-inset px-5 py-4 text-small text-text-secondary">
          Your side asked for {personalTerms.wage_weekly != null ? formatWage(personalTerms.wage_weekly) : "new terms"}
          {personalTerms.length_years != null ? ` for ${personalTerms.length_years} years` : ""}. Waiting on{" "}
          <span className="font-semibold text-text">{personalTerms.buyer_club_name}</span> to answer.
        </div>
      )}
      {dealInPersonalTerms && personalTerms && personalTerms.player_consent === "PENDING" && personalTerms.proposed_by !== "PLAYER" && (
        <div className="mt-6 rounded-xl bg-warning-bg ring-1 ring-warning-ring px-5 py-5">
          <p className="text-body font-semibold text-warning-text mb-1">Personal terms require your consent</p>
          <p className="text-small text-warning-text-alt mb-4">
            <span className="font-semibold text-warning-text">{personalTerms.buyer_club_name}</span> offers you
            these contract terms. Accept them, counter, or decline.
          </p>
          <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-small mb-5">
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
          <div className="flex flex-wrap gap-3">
            <button
              onClick={() => consentMutation.mutate({ agreement: "AGREED" })}
              disabled={consentMutation.isPending}
              className="flex-1 rounded-lg bg-accent px-4 py-2 text-body font-semibold text-on-accent hover:bg-accent-hover transition-colors disabled:opacity-50"
            >
              {consentMutation.isPending ? "…" : "Accept terms"}
            </button>
            <button
              onClick={() => setCountering((v) => !v)}
              aria-expanded={countering}
              className="flex-1 rounded-lg bg-surface px-4 py-2 text-body font-semibold text-text ring-1 ring-input-border hover:bg-surface-inset transition-colors"
            >
              Counter
            </button>
            <button
              onClick={() => setDeclining(true)}
              disabled={consentMutation.isPending}
              className="flex-1 rounded-lg bg-danger-bg px-4 py-2 text-body font-semibold text-danger-text ring-1 ring-danger-ring hover:brightness-95 transition-colors disabled:opacity-50"
            >
              Decline
            </button>
          </div>
          {countering && (
            <div className="mt-4 grid gap-3 sm:grid-cols-3">
              {([["wage", "Weekly wage (£)"], ["bonus", "Signing bonus (£)"], ["years", "Contract length (years)"]] as const).map(([k, label]) => (
                <div key={k}>
                  <label htmlFor={`counter-${k}`} className="mb-1 block text-small font-medium text-text-secondary">{label}</label>
                  <input id={`counter-${k}`} type="number" min={k === "years" ? 1 : 0} value={counter[k]}
                    onChange={(e) => setCounter((c) => ({ ...c, [k]: e.target.value }))}
                    className="w-full rounded-lg bg-surface px-3 py-2 text-input lg:text-body text-text ring-1 ring-input-border" />
                </div>
              ))}
              <div className="sm:col-span-3">
                <label htmlFor="counter-note" className="mb-1 block text-small font-medium text-text-secondary">Note to the club (optional)</label>
                <input id="counter-note" maxLength={200} value={counter.note}
                  onChange={(e) => setCounter((c) => ({ ...c, note: e.target.value }))}
                  className="w-full rounded-lg bg-surface px-3 py-2 text-input lg:text-body text-text ring-1 ring-input-border" />
              </div>
              <div className="sm:col-span-3">
                <Button variant="primary" loading={counterMutation.isPending} disabled={!counter.wage || !counter.years}
                  onClick={() => counterMutation.mutate()}>
                  Send counter
                </Button>
              </div>
            </div>
          )}
          <EndTransferDialog
            open={declining}
            title="Decline these terms?"
            who={personalTerms.buyer_club_name}
            confirmLabel="Decline and end the transfer"
            loading={consentMutation.isPending}
            onConfirm={(reason) => consentMutation.mutate({ agreement: "DECLINED", reason })}
            onCounter={() => setCountering(true)}
            onClose={() => setDeclining(false)}
          />
          {consentMutation.isError && (
            <p className="mt-2 text-small text-danger-text">Failed to respond. Please try again.</p>
          )}
        </div>
      )}

      {/* Personal terms accepted/declined status (read-only) */}
      {dealInPersonalTerms && personalTerms && personalTerms.player_consent !== "PENDING" && (
        <div className={`mt-6 rounded-xl px-5 py-4 text-small ring-1 ${
          personalTerms.player_consent === "AGREED"
            ? "bg-success-bg text-success-text-alt ring-success-ring"
            : "bg-danger-bg text-danger-text-alt ring-danger-ring"
        }`}>
          <p className="font-semibold">
            Personal terms {personalTerms.player_consent === "AGREED" ? "accepted" : "declined"} — {personalTerms.buyer_club_name}
          </p>
        </div>
      )}

      {/* Representation */}
      <div className="mt-6">
        <Card>
          <p className="mb-2 text-caption font-semibold text-text-secondary">
            Representation
          </p>

          {mandates.length === 0 ? (
            <p className="text-small text-text-muted py-2">
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
