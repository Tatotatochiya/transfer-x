import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import api from "../../lib/api";
import type { Enquiry } from "../../types/api";
import Button from "../ui/Button";
import Modal from "../ui/Modal";
import { getApiError } from "../../lib/utils";

/**
 * "Is he available, and what would it take?" — the informal first step
 * before an offer. Nothing is reserved or committed; the owning club answers
 * in a thread, and either side can move to a formal offer when ready.
 */
export default function AskAboutPlayerModal({
  open,
  onClose,
  player,
  ownerName,
}: {
  open: boolean;
  onClose: () => void;
  player: { id: string; name: string };
  ownerName: string;
}) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [body, setBody] = useState(`Is ${player.name} available? What would it take?`);
  const [anonymous, setAnonymous] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () =>
      api.post<Enquiry>("/enquiries", { player_id: player.id, body, is_anonymous: anonymous }).then((r) => r.data),
    onSuccess: (enquiry) => {
      queryClient.invalidateQueries({ queryKey: ["enquiries"] });
      onClose();
      navigate(`/enquiries/${enquiry.id}`);
    },
    onError: (err: unknown) => {
      // Already asked: take them to the open thread rather than showing an error.
      const detail = (err as { response?: { status?: number; data?: { detail?: { enquiry_id?: string } } } })
        ?.response;
      if (detail?.status === 409 && detail.data?.detail?.enquiry_id) {
        onClose();
        navigate(`/enquiries/${detail.data.detail.enquiry_id}`);
        return;
      }
      setError(getApiError(err, "Could not send the enquiry."));
    },
  });

  return (
    <Modal open={open} onClose={onClose} title={`Ask ${ownerName} about ${player.name}`}>
      <form
        className="space-y-4 px-6 py-5"
        onSubmit={(e) => { e.preventDefault(); setError(null); mutation.mutate(); }}
      >
        <p className="text-[13px] text-text-muted">
          An enquiry commits you to nothing — no budget is reserved and no offer is made. When you're both ready,
          make an offer from the thread.
        </p>
        <textarea
          value={body}
          onChange={(e) => setBody(e.target.value)}
          rows={4}
          maxLength={2000}
          required
          className="w-full resize-none rounded-lg bg-surface px-3 py-2.5 text-sm text-text ring-1 ring-input-border focus:outline-none focus:ring-accent"
        />
        <label className="flex cursor-pointer items-start gap-2.5">
          <input
            type="checkbox"
            checked={anonymous}
            onChange={(e) => setAnonymous(e.target.checked)}
            className="mt-0.5 h-4 w-4 shrink-0 accent-accent"
          />
          <span className="text-[13px] text-text-secondary">
            <span className="font-semibold">Ask anonymously</span> — {ownerName} sees only your league.
          </span>
        </label>
        {error && <p className="text-sm text-danger-text">{error}</p>}
        <div className="flex gap-3">
          <Button type="submit" variant="primary" size="md" loading={mutation.isPending}>Send enquiry</Button>
          <Button type="button" variant="ghost" size="md" onClick={onClose}>Cancel</Button>
        </div>
      </form>
    </Modal>
  );
}
