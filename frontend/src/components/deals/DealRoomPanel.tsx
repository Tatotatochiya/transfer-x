import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "../../lib/api";
import type { CommentAudience, DealAttachment, DealComment, DealParticipant } from "../../types/api";
import Button from "../ui/Button";
import Spinner from "../ui/Spinner";
import NegotiationMessageThread from "./NegotiationMessageThread";
import { formatDateTime, getApiError } from "../../lib/utils";
import { useAuthStore } from "../../store/auth";
import { useToast } from "../../context/ToastContext";

type ViewerSide = "buyer" | "seller" | null;
type Channel = "SHARED" | "CLUB_ONLY" | "AGENT";

/** Item 8: only club members have a private channel — the audience they'd
 * post into is whichever side of the deal their own club is on. */
function privateAudienceFor(viewerSide: ViewerSide): CommentAudience | null {
  if (viewerSide === "buyer") return "BUYER_ONLY";
  if (viewerSide === "seller") return "SELLER_ONLY";
  return null;
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

// ── Messages: shared/club-only comment thread ─────────────────────────────────

function CommentRow({
  comment,
  replies,
  onReply,
}: {
  comment: DealComment;
  replies: DealComment[];
  onReply: (c: DealComment) => void;
}) {
  const { user } = useAuthStore();
  const isMine = comment.author_user_id === user?.id;
  return (
    <div className="mt-3">
      <div className={`rounded-[10px] px-3 py-2 text-sm ${isMine ? "bg-accent-bg" : "bg-page"}`}>
        <div className="mb-0.5 flex items-center justify-between gap-2">
          <span className="text-xs font-bold text-text-secondary">{comment.author_label ?? "Unknown"}</span>
          <span className="text-[11px] text-text-muted">{formatDateTime(comment.created_at)}</span>
        </div>
        <p className="whitespace-pre-wrap break-words text-[13px] leading-normal text-text">{comment.body}</p>
        <button
          onClick={() => onReply(comment)}
          className="mt-1 text-[11px] text-text-muted transition-colors hover:text-text-secondary"
        >
          Reply
        </button>
      </div>
      {replies.map((r) => (
        <div key={r.id} className="ml-6 mt-2 rounded-[10px] bg-surface-inset px-3 py-2 text-sm">
          <div className="mb-0.5 flex items-center justify-between gap-2">
            <span className="text-xs font-bold text-text-secondary">{r.author_label ?? "Unknown"}</span>
            <span className="text-[11px] text-text-muted">{formatDateTime(r.created_at)}</span>
          </div>
          <p className="whitespace-pre-wrap break-words text-[13px] leading-normal text-text">{r.body}</p>
        </div>
      ))}
    </div>
  );
}

function CommentThread({
  dealId, canWrite, audience, channelLabel,
}: {
  dealId: string;
  canWrite: boolean;
  audience: CommentAudience;
  channelLabel: string;
}) {
  const queryClient = useQueryClient();
  const { addToast } = useToast();
  const [body, setBody] = useState("");
  const [replyTo, setReplyTo] = useState<DealComment | null>(null);
  const [mentions, setMentions] = useState<DealParticipant[]>([]);

  const { data: allComments = [], isLoading } = useQuery<DealComment[]>({
    queryKey: ["deals", dealId, "comments"],
    queryFn: () => api.get<DealComment[]>(`/deals/${dealId}/comments`).then((r) => r.data),
    refetchInterval: 20_000,
  });

  const { data: participants = [] } = useQuery<DealParticipant[]>({
    queryKey: ["deals", dealId, "participants"],
    queryFn: () => api.get<DealParticipant[]>(`/deals/${dealId}/participants`).then((r) => r.data),
  });

  const mutation = useMutation({
    mutationFn: () =>
      api.post<DealComment>(`/deals/${dealId}/comments`, {
        body,
        parent_id: replyTo?.id ?? null,
        mentioned_user_ids: mentions.map((m) => m.user_id),
        audience,
      }).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["deals", dealId, "comments"] });
      setBody("");
      setReplyTo(null);
      setMentions([]);
    },
    onError: (err: unknown) => addToast(getApiError(err, "Failed to post comment."), "error"),
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!body.trim()) return;
    mutation.mutate();
  }

  function toggleMention(p: DealParticipant) {
    const already = mentions.some((m) => m.user_id === p.user_id);
    if (already) {
      setMentions((prev) => prev.filter((m) => m.user_id !== p.user_id));
    } else {
      setMentions((prev) => [...prev, p]);
      setBody((b) => (b ? `${b} @${p.label}` : `@${p.label}`));
    }
  }

  const comments = allComments.filter((c) => c.audience === audience);
  const topLevel = comments.filter((c) => !c.parent_id);
  const repliesOf = (id: string) => comments.filter((c) => c.parent_id === id);

  return (
    <div>
      {isLoading ? (
        <div className="flex justify-center py-8"><Spinner size="md" /></div>
      ) : topLevel.length === 0 ? (
        <p className="py-6 text-center text-sm italic text-text-muted">No messages yet.</p>
      ) : (
        <div className="max-h-80 overflow-y-auto pr-1">
          {topLevel.map((c) => (
            <CommentRow key={c.id} comment={c} replies={repliesOf(c.id)} onReply={setReplyTo} />
          ))}
        </div>
      )}

      {canWrite && (
        <form onSubmit={handleSubmit} className="mt-4 border-t border-rule pt-3">
          {replyTo && (
            <div className="mb-2 flex items-center justify-between rounded-lg bg-surface-inset px-3 py-1.5 text-xs text-text-muted">
              <span>Replying to <span className="text-text-secondary">{replyTo.author_label}</span></span>
              <button type="button" onClick={() => setReplyTo(null)} className="text-text-muted hover:text-text">✕</button>
            </div>
          )}
          <textarea
            value={body}
            onChange={(e) => setBody(e.target.value)}
            rows={2}
            placeholder={`Write to ${channelLabel}…`}
            className="w-full resize-none rounded-lg bg-surface px-3 py-2 text-sm text-text placeholder-text-muted ring-1 ring-input-border focus:outline-none focus:ring-accent"
          />
          {participants.length > 0 && (
            <div className="mt-2 flex flex-wrap items-center gap-1.5">
              <span className="self-center text-[10px] text-text-muted">Mention:</span>
              {participants.map((p) => (
                <button
                  key={p.user_id}
                  type="button"
                  onClick={() => toggleMention(p)}
                  className={`rounded-full px-2 py-0.5 text-[10px] font-medium ring-1 transition-colors ${
                    mentions.some((m) => m.user_id === p.user_id)
                      ? "bg-accent-bg text-accent-active ring-accent"
                      : "bg-surface-inset text-text-muted ring-input-border hover:text-text"
                  }`}
                >
                  @{p.label}
                </button>
              ))}
            </div>
          )}
          <div className="mt-2 flex justify-end">
            <Button type="submit" variant="primary" size="sm" loading={mutation.isPending} disabled={!body.trim()}>
              Post
            </Button>
          </div>
        </form>
      )}
    </div>
  );
}

// ── Documents ──────────────────────────────────────────────────────────────────

function DocumentsTab({
  dealId, canWrite, viewerSide,
}: {
  dealId: string;
  canWrite: boolean;
  viewerSide: ViewerSide;
}) {
  const queryClient = useQueryClient();
  const { addToast } = useToast();
  const [uploading, setUploading] = useState(false);
  const [audience, setAudience] = useState<CommentAudience>("SHARED");
  const privateAudience = privateAudienceFor(viewerSide);

  const { data: attachments = [], isLoading } = useQuery<DealAttachment[]>({
    queryKey: ["deals", dealId, "attachments"],
    queryFn: () => api.get<DealAttachment[]>(`/deals/${dealId}/attachments`).then((r) => r.data),
  });

  async function handleUpload(file: File) {
    setUploading(true);
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("audience", audience);
      await api.post(`/deals/${dealId}/attachments`, form);
      queryClient.invalidateQueries({ queryKey: ["deals", dealId, "attachments"] });
      addToast("File uploaded.", "success");
    } catch (err: unknown) {
      addToast(getApiError(err, "Failed to upload file."), "error");
    } finally {
      setUploading(false);
    }
  }

  async function handleDownload(attachment: DealAttachment) {
    const resp = await api.get(`/deals/${dealId}/attachments/${attachment.id}/download`, { responseType: "blob" });
    const url = URL.createObjectURL(resp.data as Blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = attachment.filename;
    link.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div>
      {isLoading ? (
        <div className="flex justify-center py-8"><Spinner size="md" /></div>
      ) : attachments.length === 0 ? (
        <p className="py-6 text-center text-sm italic text-text-muted">No documents yet.</p>
      ) : (
        <div className="space-y-1.5">
          {attachments.map((a) => (
            <button
              key={a.id}
              onClick={() => handleDownload(a)}
              className="flex w-full items-center justify-between rounded-lg px-3 py-2.5 text-left transition-colors hover:bg-surface-inset"
            >
              <div className="min-w-0 flex-1">
                <p className="flex items-center gap-1.5 truncate text-[13px] font-medium text-text">
                  {a.filename}
                  {a.audience !== "SHARED" && (
                    <span className="shrink-0 rounded-full bg-warning-bg px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide text-warning-text">
                      Private
                    </span>
                  )}
                </p>
                <p className="text-[11px] text-text-muted">
                  {formatFileSize(a.size_bytes)} · {a.uploaded_by_label ?? "Unknown"} · {formatDateTime(a.created_at)}
                </p>
              </div>
              <span className="shrink-0 text-text-muted">↓</span>
            </button>
          ))}
        </div>
      )}

      {canWrite && (
        <div className="mt-4">
          {privateAudience && (
            <div className="mb-2 flex w-fit gap-1 rounded-lg bg-surface-inset p-0.5 text-[11px]">
              <button
                type="button"
                onClick={() => setAudience("SHARED")}
                className={`rounded-md px-2 py-1 font-medium transition-colors ${
                  audience === "SHARED" ? "bg-surface text-text shadow-sm" : "text-text-muted hover:text-text"
                }`}
              >
                Shared
              </button>
              <button
                type="button"
                onClick={() => setAudience(privateAudience)}
                className={`rounded-md px-2 py-1 font-medium transition-colors ${
                  audience === privateAudience ? "bg-warning-bg text-warning-text" : "text-text-muted hover:text-text"
                }`}
              >
                My club only
              </button>
            </div>
          )}
          <label className="flex cursor-pointer items-center justify-center gap-2 rounded-lg border border-dashed border-input-border px-4 py-3 text-xs text-text-muted transition-colors hover:border-accent hover:text-text">
            {uploading ? "Uploading…" : "+ Upload file (PDF, DOC, JPG, PNG — max 10MB)"}
            <input
              type="file"
              accept=".pdf,.doc,.docx,.jpg,.jpeg,.png"
              className="hidden"
              disabled={uploading}
              onChange={(e) => { const f = e.target.files?.[0]; if (f) handleUpload(f); }}
            />
          </label>
        </div>
      )}
    </div>
  );
}

// ── Main panel ────────────────────────────────────────────────────────────────

export default function DealRoomPanel({
  dealId,
  canWrite = true,
  viewerSide = null,
  negotiationId = null,
  myClubName,
  theirClubName,
}: {
  dealId: string;
  /** TRA-151: club members without DEAL_WRITE (scout/read-only) view the room
   * but the composer and upload controls are hidden. Agents/players pass true. */
  canWrite?: boolean;
  /** Item 8: which side of the deal the viewer's own club is on, if any —
   * agents/players and non-participants pass null and never see a private-channel option. */
  viewerSide?: ViewerSide;
  /** Only non-null while the deal is at AGENT_NEGOTIATION and a negotiation
   * exists — the same window the existing agent workspace is shown in. */
  negotiationId?: string | null;
  myClubName?: string;
  theirClubName?: string;
}) {
  const [tab, setTab] = useState<"messages" | "documents">("messages");
  const privateAudience = privateAudienceFor(viewerSide);
  const [channel, setChannel] = useState<Channel>("SHARED");

  const availableChannels: { key: Channel; label: string }[] = [
    { key: "SHARED", label: "Shared" },
    ...(privateAudience ? [{ key: "CLUB_ONLY" as Channel, label: `${myClubName ?? "My club"} only` }] : []),
    ...(negotiationId ? [{ key: "AGENT" as Channel, label: "Agent thread" }] : []),
  ];
  const activeChannel = availableChannels.some((c) => c.key === channel) ? channel : "SHARED";

  return (
    <div className="mb-6 rounded-xl bg-surface ring-1 ring-border">
      <div className="flex items-center justify-between border-b border-rule px-5 py-3">
        <p className="text-xs font-semibold uppercase tracking-wider text-text-muted">Deal Room</p>
        <div className="flex gap-1">
          {(["messages", "documents"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`rounded-lg px-3 py-1 text-xs font-medium capitalize transition-colors ${
                tab === t ? "bg-surface-inset text-text" : "text-text-muted hover:text-text"
              }`}
            >
              {t}
            </button>
          ))}
        </div>
      </div>

      {tab === "messages" && (
        <>
          {availableChannels.length > 1 && (
            <div className="flex border-b border-rule">
              {availableChannels.map((c) => (
                <button
                  key={c.key}
                  onClick={() => setChannel(c.key)}
                  className={`flex-1 py-2.5 text-sm font-semibold transition-colors ${
                    activeChannel === c.key
                      ? "text-accent border-b-2 border-accent"
                      : "text-text-muted border-b-2 border-transparent hover:text-text"
                  }`}
                >
                  {c.label}
                </button>
              ))}
            </div>
          )}

          {activeChannel === "CLUB_ONLY" && (
            <div className="bg-warning-bg px-5 py-2.5 text-[13px] text-warning-text">
              Private to {myClubName ?? "your club"} — {theirClubName ?? "the counterparty"} and the agent cannot see this channel.
            </div>
          )}

          <div className="px-5 py-4">
            {activeChannel === "AGENT" && negotiationId ? (
              <NegotiationMessageThread negotiationId={negotiationId} thread="CLUB_SIDE" />
            ) : (
              <CommentThread
                dealId={dealId}
                canWrite={canWrite}
                audience={activeChannel === "CLUB_ONLY" && privateAudience ? privateAudience : "SHARED"}
                channelLabel={availableChannels.find((c) => c.key === activeChannel)?.label ?? "Shared"}
              />
            )}
          </div>
        </>
      )}

      {tab === "documents" && (
        <div className="px-5 py-4">
          <DocumentsTab dealId={dealId} canWrite={canWrite} viewerSide={viewerSide} />
        </div>
      )}
    </div>
  );
}
