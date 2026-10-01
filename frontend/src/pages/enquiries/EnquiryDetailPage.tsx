import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "../../lib/api";
import type { Enquiry } from "../../types/api";
import Button from "../../components/ui/Button";
import Spinner from "../../components/ui/Spinner";
import { useConfirm } from "../../context/ConfirmContext";
import { useToast } from "../../context/ToastContext";
import { useClubCapabilities } from "../../hooks/useClubCapabilities";
import { formatDateTime, getApiError } from "../../lib/utils";
import { DraftButton, useDraftTracking } from "../../components/ai/DraftButton";

/**
 * One enquiry's thread. The asking club can move to a formal offer from here
 * when it is ready — the enquiry itself reserves and commits nothing.
 */
export default function EnquiryDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const confirm = useConfirm();
  const { addToast } = useToast();
  const { can } = useClubCapabilities();
  const [body, setBody] = useState("");
  const draftTracking = useDraftTracking("enquiry_reply", id ?? "");

  const { data: e, isLoading, isError } = useQuery<Enquiry>({
    queryKey: ["enquiries", id],
    queryFn: () => api.get<Enquiry>(`/enquiries/${id}`).then((r) => r.data),
    enabled: !!id,
  });

  const refresh = (updated: Enquiry) => {
    queryClient.setQueryData(["enquiries", id], updated);
    queryClient.invalidateQueries({ queryKey: ["enquiries"] });
    queryClient.invalidateQueries({ queryKey: ["dashboard"] });
  };
  const reply = useMutation({
    mutationFn: () => api.post<Enquiry>(`/enquiries/${id}/messages`, { body }).then((r) => r.data),
    onSuccess: (updated) => { draftTracking.sent(body); setBody(""); refresh(updated); },
    onError: (err: unknown) => addToast(getApiError(err, "Could not send."), "error"),
  });
  const close = useMutation({
    mutationFn: () => api.post<Enquiry>(`/enquiries/${id}/close`).then((r) => r.data),
    onSuccess: refresh,
    onError: (err: unknown) => addToast(getApiError(err, "Could not close."), "error"),
  });

  if (isLoading) return <div className="flex justify-center py-20"><Spinner size="lg" /></div>;
  if (isError || !e) return <p className="text-sm text-danger-text">Enquiry not found.</p>;

  const other = e.role === "owning" ? e.asking_club : e.owning_club;
  const open = e.status === "OPEN";
  const canWrite = can("MARKET_WRITE");

  return (
    <div className="max-w-2xl">
      <button onClick={() => navigate("/enquiries")} className="mb-6 text-sm text-text-muted hover:text-text">
        ← Enquiries
      </button>
      <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-text">{e.player_name ?? "Player"}</h1>
          <p className="mt-1 text-sm text-text-muted">
            {e.role === "owning" ? `${other.name} is asking about your player` : `You asked ${other.name}`}
            {e.is_anonymous && (e.role === "owning" ? " — anonymously" : " — anonymously; they see only your league")}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {e.role === "asking" && open && canWrite && (
            <Button variant="primary" size="sm" onClick={() => navigate(`/offers/new?player_id=${e.player_id}`)}>
              Make an offer
            </Button>
          )}
          {open && canWrite && (
            <Button
              variant="ghost"
              size="sm"
              loading={close.isPending}
              onClick={async () => {
                if (await confirm({ title: "Close this enquiry", message: "Neither club can write in it afterwards.", confirmLabel: "Close" })) {
                  close.mutate();
                }
              }}
            >
              Close
            </Button>
          )}
        </div>
      </div>

      <div className="space-y-3 rounded-xl bg-surface p-5 ring-1 ring-border">
        {e.messages.map((m) => (
          <div key={m.id} className={`flex ${m.side === "mine" ? "justify-end" : "justify-start"}`}>
            <div
              className={`max-w-[85%] rounded-xl px-4 py-2.5 text-sm ${
                m.side === "mine" ? "bg-accent-bg text-text" : "bg-surface-inset text-text"
              }`}
            >
              <p className="whitespace-pre-wrap">{m.body}</p>
              <p className="mt-1 text-[11px] text-text-muted">
                {m.side === "mine" ? "You" : other.name} · {formatDateTime(m.created_at)}
              </p>
            </div>
          </div>
        ))}

        {open && canWrite ? (
          <form
            className="space-y-2 border-t border-rule-faint pt-3"
            onSubmit={(ev) => { ev.preventDefault(); if (body.trim()) reply.mutate(); }}
          >
            <textarea
              value={body}
              onChange={(ev) => setBody(ev.target.value)}
              rows={2}
              maxLength={2000}
              placeholder="Write a reply…"
              className="w-full resize-y rounded-lg bg-surface px-3 py-2 text-sm text-text ring-1 ring-input-border focus:outline-none focus:ring-accent"
            />
            <div className="flex flex-wrap items-center justify-between gap-2">
              {id && <DraftButton kind="enquiry_reply" id={id} current={body} onDraft={setBody} onDrafted={draftTracking.drafted} />}
              <Button type="submit" variant="primary" size="sm" loading={reply.isPending}>Send</Button>
            </div>
          </form>
        ) : (
          !open && <p className="border-t border-rule-faint pt-3 text-[13px] text-text-muted">This enquiry is closed.</p>
        )}
      </div>
    </div>
  );
}
