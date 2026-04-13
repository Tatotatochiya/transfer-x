import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "../../lib/api";
import type { Club, Deal } from "../../types/api";
import { useAuthStore } from "../../store/auth";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import ClubLink from "../../components/ui/ClubLink";
import Metric from "../../components/ui/Metric";
import Panel from "../../components/ui/Panel";
import Spinner from "../../components/ui/Spinner";
import StageTracker from "../../components/deals/StageTracker";
import { dealStatusVariant, dealStageLabel } from "../../lib/badges";
import { formatCurrency, formatDate, formatWage, getApiError } from "../../lib/utils";
import { useToast } from "../../context/ToastContext";

// ── Note form ─────────────────────────────────────────────────────────────────

function NoteForm({ dealId }: { dealId: string }) {
  const queryClient = useQueryClient();
  const [body, setBody] = useState("");
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: (text: string) =>
      api.post(`/deals/${dealId}/notes`, { body: text }).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["deals", dealId] });
      setBody("");
      setError(null);
    },
    onError: (err: unknown) => {
      setError(getApiError(err, "Failed to add note."));
    },
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = body.trim();
    if (!trimmed) return;
    mutation.mutate(trimmed);
  }

  return (
    <form onSubmit={handleSubmit} className="flex gap-2 pt-2">
      <input
        type="text"
        value={body}
        onChange={(e) => setBody(e.target.value)}
        placeholder="Add a note…"
        className="flex-1 rounded-lg bg-slate-800 px-3 py-2 text-sm text-white placeholder-slate-500 ring-1 ring-white/10 focus:outline-none focus:ring-emerald-500 transition-colors"
      />
      <Button type="submit" variant="secondary" size="sm" loading={mutation.isPending}>
        Add
      </Button>
      {error && <p className="text-xs text-red-400 self-center">{error}</p>}
    </form>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function DealDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { addToast } = useToast();
  const { accessToken } = useAuthStore();
  const isAuthenticated = !!accessToken;
  const [showCollapsePanel, setShowCollapsePanel] = useState(false);
  const [collapseReason, setCollapseReason] = useState("");

  const { data: deal, isLoading, isError } = useQuery<Deal>({
    queryKey: ["deals", id],
    queryFn: () => api.get<Deal>(`/deals/${id}`).then((r) => r.data),
    enabled: !!id,
  });

  const { data: myClub } = useQuery<Club>({
    queryKey: ["clubs", "me"],
    queryFn: () => api.get<Club>("/clubs/me").then((r) => r.data),
    enabled: isAuthenticated,
    staleTime: 60_000,
  });

  const advanceMutation = useMutation({
    mutationFn: () =>
      api.post<Deal>(`/deals/${id}/advance`).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["deals", id] });
      addToast("Deal advanced to next stage.", "success");
    },
    onError: (err) => addToast(getApiError(err, "Failed to advance deal."), "error"),
  });

  const collapseMutation = useMutation({
    mutationFn: () =>
      api.post<Deal>(`/deals/${id}/collapse`).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["deals", id] });
      queryClient.invalidateQueries({ queryKey: ["deals"] });
      setShowCollapsePanel(false);
      setCollapseReason("");
      addToast("Deal collapsed.", "warning");
    },
    onError: (err) => addToast(getApiError(err, "Failed to collapse deal."), "error"),
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Spinner size="lg" />
      </div>
    );
  }

  if (isError || !deal) {
    return (
      <div className="rounded-xl bg-red-500/10 px-5 py-4 text-sm text-red-400 ring-1 ring-red-500/30">
        Deal not found.{" "}
        <button onClick={() => navigate(-1)} className="underline">
          Go back
        </button>
      </div>
    );
  }

  const myClubId   = myClub?.id;
  const isBuyer    = myClubId === deal.buyer_club_id;
  const isSeller   = myClubId === deal.seller_club_id;
  const isParty    = isBuyer || isSeller;
  const isActive   = deal.status === "IN_PROGRESS" || deal.status === "PENDING_COMPLETION";

  // At PAPERWORK stage, clubs cannot advance — only staff can
  const atPaperwork      = deal.stage === "PAPERWORK";
  const atConfirmed      = deal.stage === "CONFIRMED";
  const clubCanAdvance   = isParty && isActive && !atPaperwork && !deal.is_auction_deal;
  const clubCanCollapse  = isParty && isActive;

  const advanceError =
    advanceMutation.isError ? getApiError(advanceMutation.error, "Failed.") : null;

  return (
    <div>
      <button
        onClick={() => navigate(-1)}
        className="mb-6 flex items-center gap-1.5 text-sm text-slate-400 hover:text-white transition-colors"
      >
        ← Back to deals
      </button>

      {/* Stage tracker */}
      <div className="mb-6 rounded-xl bg-slate-900 px-6 py-5 ring-1 ring-white/[0.08]">
        <div className="mb-4 flex items-center justify-between">
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">
            Deal Progress
          </p>
          <Badge variant={dealStatusVariant(deal.status)}>
            {deal.status.replace(/_/g, " ")}
          </Badge>
        </div>
        <StageTracker stage={deal.stage} status={deal.status} />
      </div>

      {/* PAPERWORK banner */}
      {atPaperwork && isParty && deal.status === "IN_PROGRESS" && (
        <div className="mb-6 rounded-xl bg-sky-500/10 px-5 py-4 text-sm text-sky-300 ring-1 ring-sky-500/20">
          <p className="font-semibold mb-1">TransferX is handling the paperwork</p>
          <p className="text-sky-400/80">
            Our team is processing the documentation. You'll be notified when it's ready for confirmation.
          </p>
        </div>
      )}

      {/* CONFIRMED / Ready to Execute banner */}
      {atConfirmed && isParty && deal.status === "IN_PROGRESS" && (
        <div className="mb-6 rounded-xl bg-emerald-500/10 px-5 py-4 text-sm text-emerald-300 ring-1 ring-emerald-500/20">
          <p className="font-semibold mb-1">Documents verified — ready to execute</p>
          <p className="text-emerald-400/80">
            TransferX has processed all documentation. Use the <strong>Execute Transfer</strong> button to complete the deal and register the player.
          </p>
        </div>
      )}

      {/* Auction deal banner */}
      {deal.is_auction_deal && isParty && deal.status === "IN_PROGRESS" && (
        <div className="mb-6 rounded-xl bg-amber-500/10 px-5 py-4 text-sm text-amber-300 ring-1 ring-amber-500/20">
          <p className="font-semibold mb-1">Auction deal</p>
          <p className="text-amber-400/80">
            This deal was created from an auction result. Stage advancement is handled by TransferX staff.
          </p>
        </div>
      )}

      {/* Completed banner */}
      {deal.status === "COMPLETED" && (
        <div className="mb-6 rounded-xl bg-emerald-500/10 px-5 py-4 text-sm text-emerald-300 ring-1 ring-emerald-500/20">
          <p className="font-semibold">Transfer completed</p>
          {deal.completed_at && (
            <p className="text-emerald-400/80 mt-1">
              Completed on {formatDate(deal.completed_at)}
            </p>
          )}
        </div>
      )}

      {/* Collapsed banner */}
      {deal.status === "COLLAPSED" && (
        <div className="mb-6 rounded-xl bg-red-500/10 px-5 py-4 text-sm text-red-300 ring-1 ring-red-500/20">
          <p className="font-semibold">Deal collapsed</p>
          <p className="text-red-400/80 mt-1">This transfer has fallen through.</p>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-3">
        {/* ── Left: info ── */}
        <div className="lg:col-span-1 space-y-4">
          {/* Player */}
          <Card>
            <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-400">
              Player
            </p>
            <button
              onClick={() =>
                deal.player_id && navigate(`/players/market/${deal.player_id}`)
              }
              className="text-lg font-semibold text-white hover:text-emerald-400 transition-colors text-left"
            >
              {deal.player?.name ?? "Unknown"}
            </button>
            {deal.player?.position && (
              <p className="text-xs text-slate-500 mt-0.5">{deal.player.position}</p>
            )}
          </Card>

          {/* Terms */}
          <Card>
            <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-400">
              Agreed Terms
            </p>
            <div className="space-y-2">
              <Metric label="Transfer fee" value={formatCurrency(deal.agreed_fee)} />
              {deal.agreed_wage_weekly != null && (
                <Metric label="Wage" value={formatWage(deal.agreed_wage_weekly)} />
              )}
              <Metric
                label="Buyer"
                valueNode={<ClubLink id={deal.buyer_club?.id} name={deal.buyer_club?.name} />}
              />
              <Metric
                label="Seller"
                valueNode={<ClubLink id={deal.seller_club?.id} name={deal.seller_club?.name} />}
              />
              <Metric label="Stage" value={dealStageLabel(deal.stage)} />
              <Metric label="Created" value={formatDate(deal.created_at)} />
              {deal.is_auction_deal && (
                <p className="mt-1 text-xs text-amber-400/70 border-t border-white/[0.06] pt-2">
                  Auction deal
                </p>
              )}
            </div>
          </Card>

          {/* Actions */}
          {isParty && isActive && (
            <Card>
              <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-400">
                Actions
              </p>
              <div className="space-y-2">
                {clubCanAdvance && (
                  <Button
                    variant="primary"
                    size="sm"
                    className="w-full"
                    loading={advanceMutation.isPending}
                    onClick={() => advanceMutation.mutate()}
                  >
                    {atConfirmed ? "Execute Transfer" : `Advance to ${dealStageLabel(nextStage(deal.stage))}`}
                  </Button>
                )}
                {advanceError && (
                  <p className="text-xs text-red-400">{advanceError}</p>
                )}
                {clubCanCollapse && !showCollapsePanel && (
                  <button
                    onClick={() => setShowCollapsePanel(true)}
                    className="w-full rounded-lg px-3 py-2 text-sm text-slate-500 hover:text-red-400 hover:bg-red-500/[0.06] ring-1 ring-white/[0.06] hover:ring-red-500/20 transition-colors"
                  >
                    Collapse deal…
                  </button>
                )}
              </div>

              {/* Inline collapse confirmation panel */}
              {clubCanCollapse && showCollapsePanel && (
                <div className="mt-3 rounded-lg bg-red-500/[0.06] ring-1 ring-red-500/20 px-4 py-4 space-y-3">
                  <div className="flex items-start gap-2">
                    <svg className="h-4 w-4 text-red-400 shrink-0 mt-0.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v4m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
                    </svg>
                    <div>
                      <p className="text-sm font-semibold text-red-400">Collapse this deal?</p>
                      <p className="text-xs text-slate-400 mt-0.5">This cannot be undone. The transfer will fall through and reserved budget will be released.</p>
                    </div>
                  </div>
                  <div>
                    <label className="mb-1.5 block text-xs text-slate-400">Reason (optional)</label>
                    <textarea
                      rows={2}
                      value={collapseReason}
                      onChange={(e) => setCollapseReason(e.target.value)}
                      placeholder="e.g. Clubs could not agree on fee"
                      className="w-full rounded-lg bg-slate-800 px-3 py-2 text-sm text-white placeholder-slate-600 ring-1 ring-white/10 focus:outline-none focus:ring-red-500/50 resize-none transition-colors"
                    />
                  </div>
                  <div className="flex gap-2">
                    <Button
                      variant="danger"
                      size="sm"
                      loading={collapseMutation.isPending}
                      onClick={() => collapseMutation.mutate()}
                    >
                      Confirm collapse
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => { setShowCollapsePanel(false); setCollapseReason(""); }}
                    >
                      Cancel
                    </Button>
                  </div>
                </div>
              )}
            </Card>
          )}
        </div>

        {/* ── Right: notes + timeline ── */}
        <div className="lg:col-span-2 space-y-4">
          <Panel title="Deal Notes">
            {deal.deal_notes.length === 0 ? (
              <p className="text-sm text-slate-500 pb-2">No notes yet.</p>
            ) : (
              <div className="space-y-3 mb-4">
                {deal.deal_notes.map((note) => (
                  <div
                    key={note.id}
                    className="rounded-lg bg-slate-800/60 px-4 py-3"
                  >
                    <div className="flex items-center justify-between mb-1">
                      <p className="text-xs font-semibold text-slate-400">
                        {note.author_club?.name ?? "System"}
                      </p>
                      <p className="text-[10px] text-slate-500">
                        {formatDate(note.created_at)}
                      </p>
                    </div>
                    <p className="text-sm text-slate-300">{note.body}</p>
                  </div>
                ))}
              </div>
            )}
            {isParty && isActive && <NoteForm dealId={deal.id} />}
          </Panel>

          <Panel title="Activity Timeline">
            <DealTimeline deal={deal} />
          </Panel>
        </div>
      </div>
    </div>
  );
}

// ── Helpers ───────────────────────────────────────────────────────────────────

import type { DealStage } from "../../types/enums";

function nextStage(stage: DealStage): DealStage {
  const seq: DealStage[] = ["AGREEMENT", "PAPERWORK", "CONFIRMED", "COMPLETED"];
  const idx = seq.indexOf(stage);
  return idx < seq.length - 1 ? seq[idx + 1] : stage;
}

// ── Deal timeline ─────────────────────────────────────────────────────────────

interface TimelineEvent {
  id: string;
  ts: string;
  label: string;
  sublabel?: string;
  dot: "emerald" | "sky" | "amber" | "red" | "slate";
}

function DealTimeline({ deal }: { deal: Deal }) {
  const events: TimelineEvent[] = [];

  // Deal created
  events.push({
    id: "created",
    ts: deal.created_at,
    label: "Deal created",
    sublabel: `Agreed fee: ${formatCurrency(deal.agreed_fee)}`,
    dot: "emerald",
  });

  // Notes in chronological order
  const sortedNotes = [...deal.deal_notes].sort(
    (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
  );
  for (const note of sortedNotes) {
    events.push({
      id: `note-${note.id}`,
      ts: note.created_at,
      label: note.author_club?.name ? `Note by ${note.author_club.name}` : "System note",
      sublabel: note.body,
      dot: "sky",
    });
  }

  // Terminal states
  if (deal.status === "COMPLETED" && deal.completed_at) {
    events.push({
      id: "completed",
      ts: deal.completed_at,
      label: "Transfer completed",
      dot: "emerald",
    });
  } else if (deal.status === "COLLAPSED") {
    events.push({
      id: "collapsed",
      ts: deal.updated_at,
      label: "Deal collapsed",
      dot: "red",
    });
  }

  events.sort((a, b) => new Date(a.ts).getTime() - new Date(b.ts).getTime());

  const dotClass: Record<TimelineEvent["dot"], string> = {
    emerald: "bg-emerald-500",
    sky:     "bg-sky-500",
    amber:   "bg-amber-500",
    red:     "bg-red-500",
    slate:   "bg-slate-600",
  };

  return (
    <div className="relative pl-4">
      {/* Vertical line */}
      <div className="absolute left-[7px] top-2 bottom-2 w-px bg-white/[0.06]" />

      <div className="space-y-5">
        {events.map((ev) => (
          <div key={ev.id} className="relative flex gap-3">
            <div className={`mt-1 h-3 w-3 shrink-0 rounded-full ring-2 ring-slate-900 ${dotClass[ev.dot]}`} />
            <div className="min-w-0">
              <div className="flex items-baseline gap-2">
                <span className="text-sm font-medium text-white">{ev.label}</span>
                <span className="text-[10px] text-slate-500 shrink-0">
                  {new Date(ev.ts).toLocaleString("en-GB", {
                    day: "numeric", month: "short", year: "numeric",
                    hour: "2-digit", minute: "2-digit",
                  })}
                </span>
              </div>
              {ev.sublabel && (
                <p className="mt-0.5 text-xs text-slate-400 break-words">{ev.sublabel}</p>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
