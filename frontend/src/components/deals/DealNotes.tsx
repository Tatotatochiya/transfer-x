import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import api from "../../lib/api";
import type { Deal } from "../../types/api";
import Button from "../ui/Button";
import { formatDate, getApiError } from "../../lib/utils";

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
        className="flex-1 rounded-lg bg-surface px-3 py-2 text-input lg:text-body text-text placeholder-text-muted ring-1 ring-input-border focus:outline-none focus:ring-accent transition-colors"
      />
      <Button type="submit" variant="secondary" size="sm" loading={mutation.isPending}>
        Add
      </Button>
      {error && <p className="text-caption text-danger-text self-center">{error}</p>}
    </form>
  );
}

/**
 * Deal notes (D10): shared with everyone who can open the deal, with the
 * author's club shown.
 */
export default function DealNotes({ deal, canAdd }: { deal: Deal; canAdd: boolean }) {
  return (
    <div>
      <p className="mb-3 text-small text-text-muted">Everyone who can open this deal sees these notes.</p>
      {deal.deal_notes.length === 0 ? (
        <p className="pb-2 text-body text-text-muted">No notes yet.</p>
      ) : (
        <div className="mb-4 space-y-3">
          {deal.deal_notes.map((note) => (
            <div key={note.id} className="rounded-lg bg-surface-inset px-4 py-3">
              <div className="mb-1 flex items-center justify-between">
                <p className="text-caption font-semibold text-text-secondary">{note.author_club?.name ?? "System"}</p>
                <p className="text-caption text-text-muted">{formatDate(note.created_at)}</p>
              </div>
              <p className="text-body text-text-secondary">{note.body}</p>
            </div>
          ))}
        </div>
      )}
      {canAdd && <NoteForm dealId={deal.id} />}
    </div>
  );
}
