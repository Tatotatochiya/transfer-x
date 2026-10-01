import { useRef } from "react";

import { reportDraftUsed, useAIStatus, useDraft } from "../../hooks/useAssistant";
import { getApiError } from "../../lib/utils";
import type { DraftKind } from "../../types/api";

/**
 * "Draft with AI" for a message box (ADR 0006: the assistant writes, the user
 * edits and sends). Whatever is already typed is passed as what the message
 * should say; the draft replaces it. Hidden when the assistant is off.
 */
export function DraftButton({
  kind, id, channel, current, onDraft, onDrafted,
}: {
  kind: DraftKind;
  id: string;
  channel?: string;
  /** The box's current text, used as the user's intent. */
  current: string;
  onDraft: (text: string) => void;
  /** Called with the draft, so the page can tell later whether it was sent. */
  onDrafted?: (text: string) => void;
}) {
  const { data: status } = useAIStatus();
  const draft = useDraft();
  if (!status?.available) return null;
  return (
    <span className="inline-flex flex-wrap items-center gap-2">
      <button
        type="button"
        onClick={() =>
          draft.mutate(
            { kind, id, channel, intent: current.trim() || undefined },
            { onSuccess: (r) => { onDraft(r.text); onDrafted?.(r.text); } },
          )
        }
        disabled={draft.isPending}
        title={current.trim() ? "Turn what you've typed into a message" : "Write a first draft from this deal's facts"}
        className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-semibold text-role-agent-text ring-1 ring-role-agent-text/30 hover:bg-role-agent-text/10 disabled:opacity-50"
      >
        ✦ {draft.isPending ? "Drafting…" : current.trim() ? "Polish with AI" : "Draft with AI"}
      </button>
      {draft.isError && <span className="text-xs text-danger-text">{getApiError(draft.error, "No draft this time.")}</span>}
      {draft.isSuccess && !draft.isPending && (
        <span className="text-xs text-text-muted">Draft ready: check it, edit it, then send.</span>
      )}
    </span>
  );
}

/** Content words, for comparing a sent message with the draft. */
function words(text: string): Set<string> {
  return new Set(text.toLowerCase().match(/[a-z£0-9]{3,}/g) ?? []);
}

/**
 * Remembers the latest draft and, when a message is sent, reports the draft
 * as used if the message is still mostly the draft (half its words or more).
 */
export function useDraftTracking(kind: DraftKind, ref: string) {
  const last = useRef<string | null>(null);
  return {
    drafted: (text: string) => { last.current = text; },
    sent: (text: string) => {
      const draft = last.current;
      last.current = null;
      if (!draft) return;
      const d = words(draft);
      const shared = [...words(text)].filter((w) => d.has(w)).length;
      if (d.size && shared / d.size >= 0.5) reportDraftUsed(kind, ref);
    },
  };
}
