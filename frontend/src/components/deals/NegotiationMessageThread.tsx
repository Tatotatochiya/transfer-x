import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "../../lib/api";
import type { NegotiationMessage, NegotiationThread } from "../../types/api";
import { useAuthStore } from "../../store/auth";
import { formatDateTime, getApiError } from "../../lib/utils";
import { useToast } from "../../context/ToastContext";

interface NegotiationMessageThreadProps {
  negotiationId: string;
  thread: NegotiationThread;
  /** Tailwind colour stem matching the surrounding panel, e.g. "purple" or "amber". */
  accent?: "purple" | "amber";
}

const ACCENT_RING: Record<string, string> = {
  purple: "focus:ring-purple-500",
  amber: "focus:ring-amber-500",
};

const ACCENT_BUTTON: Record<string, string> = {
  purple: "bg-purple-500 hover:bg-purple-400",
  amber: "bg-amber-500 hover:bg-amber-400",
};

export default function NegotiationMessageThread({
  negotiationId,
  thread,
  accent = "purple",
}: NegotiationMessageThreadProps) {
  const { user } = useAuthStore();
  const queryClient = useQueryClient();
  const { addToast } = useToast();
  const [body, setBody] = useState("");

  const queryKey = ["negotiations", negotiationId, "messages", thread];

  const { data: messages = [], isLoading } = useQuery<NegotiationMessage[]>({
    queryKey,
    queryFn: () =>
      api.get<NegotiationMessage[]>(`/negotiations/${negotiationId}/messages`, { params: { thread } })
        .then((r) => r.data),
    refetchInterval: 15_000,
  });

  const mutation = useMutation({
    mutationFn: (text: string) =>
      api.post<NegotiationMessage>(`/negotiations/${negotiationId}/messages`, { thread, body: text })
        .then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey });
      setBody("");
    },
    onError: (err: unknown) => addToast(getApiError(err, "Failed to send message."), "error"),
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = body.trim();
    if (!trimmed) return;
    mutation.mutate(trimmed);
  }

  return (
    <div className="mt-3 border-t border-white/[0.08] pt-3">
      <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-slate-500">Messages</p>

      <div className="max-h-56 space-y-2 overflow-y-auto pr-1">
        {isLoading ? (
          <p className="text-xs text-slate-600">Loading…</p>
        ) : messages.length === 0 ? (
          <p className="text-xs text-slate-600 italic">No messages yet.</p>
        ) : (
          messages.map((m) => {
            const isMine = m.sender_user_id === user?.id;
            return (
              <div key={m.id} className={`rounded-lg px-3 py-2 text-xs ${isMine ? "bg-white/[0.06]" : "bg-slate-800/60"}`}>
                <div className="mb-0.5 flex items-center justify-between gap-2">
                  <span className="font-semibold text-slate-300">{m.sender_label ?? "Unknown"}</span>
                  <span className="text-slate-600">{formatDateTime(m.created_at)}</span>
                </div>
                <p className="text-slate-200 whitespace-pre-wrap break-words">{m.body}</p>
              </div>
            );
          })
        )}
      </div>

      <form onSubmit={handleSubmit} className="mt-2 flex gap-2">
        <input
          type="text"
          value={body}
          onChange={(e) => setBody(e.target.value)}
          placeholder="Write a message…"
          className={`flex-1 rounded-lg bg-slate-800 px-3 py-1.5 text-xs text-white placeholder-slate-500 ring-1 ring-white/10 focus:outline-none ${ACCENT_RING[accent]}`}
        />
        <button
          type="submit"
          disabled={mutation.isPending || !body.trim()}
          className={`rounded-lg px-3 py-1.5 text-xs font-semibold text-white transition-colors disabled:opacity-50 ${ACCENT_BUTTON[accent]}`}
        >
          Send
        </button>
      </form>
    </div>
  );
}
