import { useState } from "react";
import { useMutation } from "@tanstack/react-query";

import api from "../../lib/api";
import { getApiError } from "../../lib/utils";
import { useTeamContact } from "../../hooks/useLite";
import { useToast } from "../../context/ToastContext";
import Modal from "../ui/Modal";

type Subject = { type: "player" | "offer" | "deal"; id: string } | { type: "general" };

/**
 * "Ask Sam about him" (Lite L7): a question to the club's team contact, about
 * a player, an offer or a deal. With `sendNow`, the text is sent as it is
 * ("Send to Sam" under an unanswered question); otherwise a sheet opens with
 * `draft` filled in to edit first.
 */
export default function AskTeamButton({
  subject, verb = "Ask", suffix = "", draft = "", sendNow = false, className,
}: {
  subject: Subject;
  verb?: "Ask" | "Send to" | "Message";
  suffix?: string;
  draft?: string;
  sendNow?: boolean;
  className: string;
}) {
  const { data: contact } = useTeamContact();
  const { addToast } = useToast();
  const [open, setOpen] = useState(false);
  const [text, setText] = useState(draft);
  const label = contact?.label ?? "your team";

  const ask = useMutation({
    mutationFn: (body: string) => api.post<{ sent_to: string }>("/lite/ask-team", {
      subject_type: subject.type, ...(subject.type !== "general" && { subject_id: subject.id }), text: body,
    }).then((r) => r.data),
    onSuccess: (r) => {
      setOpen(false);
      addToast(`Sent to ${r.sent_to === "your team" ? "your team" : r.sent_to}`, "success");
    },
    onError: (e) => addToast(getApiError(e), "error"),
  });

  return (
    <>
      <button
        type="button"
        className={className}
        disabled={ask.isPending}
        onClick={() => (sendNow ? ask.mutate(draft) : (setText(draft), setOpen(true)))}
      >
        {verb} {label}{suffix}
      </button>
      {open && (
        <Modal open onClose={() => setOpen(false)} title={`${verb} ${label}`}>
          <form
            className="space-y-4 px-6 py-5"
            onSubmit={(e) => { e.preventDefault(); if (text.trim()) ask.mutate(text.trim()); }}
          >
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              rows={3}
              maxLength={1000}
              aria-label="Your question"
              className="w-full rounded-xl bg-surface px-4 py-3 text-[1.125rem] text-text ring-1 ring-input-border focus:outline-none focus:ring-accent"
            />
            <p className="text-[0.9375rem] text-text-muted">
              {contact?.name ? `${contact.name} gets a notification with a link to this.` : "Everyone at your club who can make offers gets it."}
            </p>
            <button
              type="submit"
              disabled={!text.trim() || ask.isPending}
              className="min-h-[3.25rem] w-full rounded-[13px] bg-accent text-[1.0625rem] font-bold text-white disabled:opacity-50"
            >
              {ask.isPending ? "Sending…" : "Send"}
            </button>
          </form>
        </Modal>
      )}
    </>
  );
}
