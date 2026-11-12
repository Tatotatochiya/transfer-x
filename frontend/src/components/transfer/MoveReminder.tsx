import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import api from "../../lib/api";
import { formatDate, getApiError } from "../../lib/utils";
import { useToast } from "../../context/ToastContext";
import Button from "../ui/Button";
import Modal from "../ui/Modal";
import { ChasedBadge, SentBadge, StalledBadge, stalledDays } from "./ReminderBadges";

export type ReminderSubject = "offer" | "deal" | "enquiry";

export interface ReminderState {
  holder: { kind: "club" | "agent" | "player"; name: string } | null;
  waiting_since: string | null;
  can_send: boolean;
  reason: string | null;
  next_allowed_at: string | null;
  would_escalate: boolean;
  preview: string | null;
  last: { at: string; by: string; escalated: boolean; note: string | null; by_you?: boolean } | null;
  /** A reminder sent to the viewer: they hold the move. */
  to_you?: { at: string; by: string; escalated: boolean; note: string | null } | null;
}

const NOTE_MAX = 200;

/** "today", "yesterday" or "on 9 Nov". */
function when(iso: string, now = new Date()): string {
  const d = new Date(iso);
  const days = Math.floor((new Date(now.toDateString()).getTime() - new Date(d.toDateString()).getTime()) / 86_400_000);
  return days <= 0 ? "today" : days === 1 ? "yesterday" : `on ${formatDate(iso)}`;
}

/**
 * Chase whoever holds the move on an offer, deal or enquiry
 * (docs/feature_spec/move-reminders): who was last reminded and when, and a
 * quiet "Send a reminder" (or "Escalate") that opens the exact message they'll
 * get. The server decides who holds the move and whether this viewer may send;
 * this shows nothing to a non-party, or while it's the viewer's own move.
 */
export default function MoveReminder({ subjectType, subjectId, lite = false, className = "" }: {
  subjectType: ReminderSubject;
  subjectId: string;
  /** Lite's larger sizes. */
  lite?: boolean;
  className?: string;
}) {
  const queryClient = useQueryClient();
  const { addToast } = useToast();
  const [open, setOpen] = useState(false);
  const [note, setNote] = useState("");
  const key = ["reminders", subjectType, subjectId];

  const { data: st } = useQuery<ReminderState>({
    queryKey: key,
    queryFn: () => api.get<ReminderState>(`/reminders/${subjectType}/${subjectId}`).then((r) => r.data),
    retry: false,
  });

  const send = useMutation({
    mutationFn: () => api.post<ReminderState>(`/reminders/${subjectType}/${subjectId}`, { note: note.trim() || null }).then((r) => r.data),
    onSuccess: (next) => {
      queryClient.setQueryData(key, next);
      if (subjectType === "deal") queryClient.invalidateQueries({ queryKey: ["deals", subjectId, "audit-log"] });
      addToast(`${st?.would_escalate ? "Escalated to" : "Reminder sent to"} ${st?.holder?.name ?? "them"}.`, "success");
      setOpen(false);
      setNote("");
    },
    onError: (err: unknown) => addToast(getApiError(err, "Could not send the reminder."), "error"),
  });

  // Being chased: red, with who and when. No button: it's their move.
  if (st?.to_you && st.reason === "It's your move.") {
    const r = st.to_you;
    return (
      <div className={`flex flex-wrap items-center gap-x-3 gap-y-1 ${className}`}>
        <ChasedBadge escalated={r.escalated} />
        <p className={`min-w-0 ${lite ? "text-lite-caption" : "text-small"} text-text-secondary`}>
          {r.by} {r.escalated ? "escalated this to you" : "reminded you"} {when(r.at)}.
          {r.note && <span className="text-text-muted"> “{r.note}”</span>}
        </p>
      </div>
    );
  }
  if (!st?.holder || (!st.can_send && !st.last) || st.reason === "It's your move.") return null;

  const last = st.last;
  const lastLine = last
    ? `${last.by_you ? "You" : last.by} ${last.escalated ? "escalated it to" : "reminded"} ${st.holder.name} ${when(last.at)}.`
    : null;
  const label = st.would_escalate ? "Escalate" : lite ? "Remind them" : "Send a reminder";
  const text = lite ? "text-lite-caption" : "text-small";

  return (
    <div className={`flex flex-wrap items-center justify-between gap-x-4 gap-y-2 ${className}`}>
      <div className={`flex min-w-0 flex-wrap items-baseline gap-x-2 gap-y-1 ${text} text-text-secondary`}>
        {last
          ? <SentBadge escalated={last.escalated} stalled={stalledDays(st.waiting_since) != null} />
          : <StalledBadge since={st.waiting_since} />}
        {lastLine && <p>{lastLine}{last?.note && <span className="text-text-muted"> “{last.note}”</span>}</p>}
        {!st.can_send && st.next_allowed_at && st.reason && <p className="text-text-muted">{st.reason.replace(/^You reminded them [^.]*\. /, "")}</p>}
        {st.can_send && !lastLine && st.waiting_since && (
          <p>Waiting on {st.holder.name} since {formatDate(st.waiting_since)}.</p>
        )}
      </div>
      {st.can_send && (
        <Button variant="secondary" size={lite ? "lg" : "sm"} onClick={() => setOpen(true)} className={lite ? "text-lite-body" : undefined}>
          {label}
        </Button>
      )}

      <Modal open={open} onClose={() => setOpen(false)} title={st.would_escalate ? `Escalate to ${st.holder.name}` : `Remind ${st.holder.name}`}>
        <div className="space-y-4 px-6 py-5">
          <div>
            <p className="text-caption font-semibold text-text-secondary">They'll get, by notification, email and push</p>
            <p className="mt-1 rounded-lg bg-surface-inset px-3 py-2.5 text-body text-text">{st.preview}</p>
            {st.would_escalate && (
              <p className="mt-2 text-small text-text-secondary">
                {st.holder.kind === "club"
                  ? "It goes to the club's owner and sporting directors too."
                  : st.holder.kind === "agent"
                    ? "The player and the other club are told too."
                    : "His agent, or the selling club, is told too."}
              </p>
            )}
          </div>
          <div>
            <label htmlFor="reminder-note" className="block text-small font-semibold text-text-secondary">Add a note (optional)</label>
            <textarea
              id="reminder-note"
              value={note}
              maxLength={NOTE_MAX}
              rows={2}
              onChange={(e) => setNote(e.target.value)}
              className="mt-1.5 w-full resize-none rounded-lg bg-surface px-3 py-2 text-input text-text ring-1 ring-input-border focus:outline-none focus:ring-2 focus:ring-accent lg:text-body"
            />
            <p className="mt-1 text-right text-caption text-text-muted">{note.length}/{NOTE_MAX}</p>
          </div>
          <p className="text-small text-text-muted">Both sides see that you sent it, and the note.</p>
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setOpen(false)}>Cancel</Button>
            <Button variant="primary" loading={send.isPending} onClick={() => send.mutate()}>
              {st.would_escalate ? "Escalate" : "Send reminder"}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
