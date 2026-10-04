import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import api from "../../lib/api";
import type { Offer, OfferMessage, OfferEvent } from "../../types/api";
import type { OfferEventType } from "../../types/enums";
import { formatDateTime, getApiError } from "../../lib/utils";
import Button from "../ui/Button";
import ClubLink from "../ui/ClubLink";
import { DraftButton, useDraftTracking } from "../ai/DraftButton";

// ── Event label helpers ───────────────────────────────────────────────────────

const EVENT_LABELS: Record<OfferEventType, string> = {
  CREATED:   "Offer created",
  SENT:      "Offer sent",
  COUNTERED: "Counter offer submitted",
  IMPROVED:  "Offer improved",
  ACCEPTED:  "Offer accepted",
  REJECTED:  "Offer rejected",
  WITHDRAWN: "Offer withdrawn",
  EXPIRED:   "Offer expired",
  MESSAGE:   "Message",
};

const EVENT_COLOURS: Record<OfferEventType, string> = {
  CREATED:   "text-text-muted",
  SENT:      "text-accent",
  COUNTERED: "text-warning-text",
  IMPROVED:  "text-accent",
  ACCEPTED:  "text-success-text",
  REJECTED:  "text-danger-text",
  WITHDRAWN: "text-text-muted",
  EXPIRED:   "text-text-muted",
  MESSAGE:   "text-text-muted",
};

/** The offer's events (sent, countered, raised…) as conversation timeline rows. */
export function offerTimeline(offer: Offer): { id: string; created_at: string; text: string }[] {
  return offer.events
    .filter((e) => e.event_type !== "MESSAGE")
    .map((e) => ({ id: e.id, created_at: e.created_at, text: EVENT_LABELS[e.event_type] ?? e.event_type }));
}

// ── Thread item types ─────────────────────────────────────────────────────────

type ThreadItem =
  | { kind: "message"; data: OfferMessage; ts: string }
  | { kind: "event";   data: OfferEvent;   ts: string };

function buildThread(offer: Offer): ThreadItem[] {
  const msgs: ThreadItem[] = offer.messages.map((m) => ({
    kind: "message",
    data: m,
    ts: m.created_at,
  }));
  const evts: ThreadItem[] = offer.events
    .filter((e) => e.event_type !== "MESSAGE")
    .map((e) => ({ kind: "event", data: e, ts: e.created_at }));
  return [...msgs, ...evts].sort(
    (a, b) => new Date(a.ts).getTime() - new Date(b.ts).getTime()
  );
}

// ── Sub-components ────────────────────────────────────────────────────────────

function MessageBubble({
  msg,
  myClubId,
}: {
  msg: OfferMessage;
  myClubId: string | undefined;
}) {
  const isMine = !!myClubId && msg.sender_club_id === myClubId;
  return (
    <div className={`flex ${isMine ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-xs rounded-2xl px-4 py-2.5 text-sm ${
          isMine
            ? "bg-success text-white"
            : "bg-surface-inset text-text"
        }`}
      >
        {!isMine && msg.sender_club && (
          <p className="mb-1 text-xs font-semibold text-text-muted">
            {/* An anonymous buyer's messages arrive with no sender club (offers router _mask_buyer). */}
            <ClubLink id={msg.sender_club.id} name={msg.sender_club.name} crestUrl={msg.sender_club.crest_url ?? null} />
          </p>
        )}
        <p>{msg.body}</p>
        <p className={`mt-1 text-right text-[13px] ${isMine ? "text-white/70" : "text-text-muted"}`}>
          {formatDateTime(msg.created_at)}
        </p>
      </div>
    </div>
  );
}

function EventRow({ evt }: { evt: OfferEvent }) {
  const colour = EVENT_COLOURS[evt.event_type] ?? "text-text-muted";
  return (
    <div className="flex items-center gap-3 py-1">
      <div className="h-px flex-1 bg-rule" />
      <span className={`text-xs font-medium ${colour}`}>
        {EVENT_LABELS[evt.event_type] ?? evt.event_type}
        <span className="ml-2 text-text-muted font-normal">
          {formatDateTime(evt.created_at)}
        </span>
      </span>
      <div className="h-px flex-1 bg-rule" />
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

interface OfferThreadProps {
  offer: Offer;
  myClubId: string | undefined;
  canMessage: boolean;
}

export default function OfferThread({
  offer,
  myClubId,
  canMessage,
}: OfferThreadProps) {
  const queryClient = useQueryClient();
  const [body, setBody] = useState("");
  const [error, setError] = useState<string | null>(null);
  const draftTracking = useDraftTracking("counter_note", offer.id);

  const items = buildThread(offer);

  const mutation = useMutation({
    mutationFn: (text: string) =>
      api
        .post(`/offers/${offer.id}/messages`, { body: text })
        .then((r) => r.data),
    onSuccess: (_data, text) => {
      queryClient.invalidateQueries({ queryKey: ["offers", offer.id] });
      draftTracking.sent(text);
      setBody("");
      setError(null);
    },
    onError: (err: unknown) => {
      setError(getApiError(err, "Failed to send message."));
    },
  });

  function handleSend(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = body.trim();
    if (!trimmed) return;
    mutation.mutate(trimmed);
  }

  return (
    <div className="space-y-3">
      {/* Thread items */}
      {items.length === 0 ? (
        <p className="text-center text-xs text-text-muted py-4">
          No messages yet.
        </p>
      ) : (
        <div className="space-y-2">
          {items.map((item) =>
            item.kind === "message" ? (
              <MessageBubble
                key={item.data.id}
                msg={item.data}
                myClubId={myClubId}
              />
            ) : (
              <EventRow key={item.data.id} evt={item.data} />
            )
          )}
        </div>
      )}

      {/* Message form */}
      {canMessage && (
        <form onSubmit={handleSend} className="space-y-2 pt-2">
          <textarea
            value={body}
            onChange={(e) => setBody(e.target.value)}
            rows={2}
            placeholder="Write a message… (e.g. why your latest terms are fair)"
            className="w-full resize-y rounded-lg bg-surface px-3 py-2 text-sm text-text placeholder-text-muted ring-1 ring-input-border focus:outline-none focus:ring-accent transition-colors"
          />
          <div className="flex flex-wrap items-center justify-between gap-2">
            <DraftButton kind="counter_note" id={offer.id} current={body} onDraft={setBody} onDrafted={draftTracking.drafted} />
            <Button
              type="submit"
              variant="primary"
              size="sm"
              loading={mutation.isPending}
            >
              Send
            </Button>
          </div>
        </form>
      )}
      {error && <p className="text-xs text-danger-text">{error}</p>}
    </div>
  );
}
