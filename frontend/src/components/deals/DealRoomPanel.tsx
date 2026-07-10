import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "../../lib/api";
import type { CommentAudience, DealAttachment, DealComment, DealParticipant, DealTermsVersion, TermsDiff } from "../../types/api";
import Button from "../ui/Button";
import Spinner from "../ui/Spinner";
import { formatCurrency, formatDateTime, getApiError } from "../../lib/utils";
import { useAuthStore } from "../../store/auth";
import { useToast } from "../../context/ToastContext";

type ViewerSide = "buyer" | "seller" | null;

/** Item 8: only club members have a private channel — the audience they'd
 * post into is whichever side of the deal their own club is on. */
function privateAudienceFor(viewerSide: ViewerSide): CommentAudience | null {
  if (viewerSide === "buyer") return "BUYER_ONLY";
  if (viewerSide === "seller") return "SELLER_ONLY";
  return null;
}

function PrivateBadge({ audience }: { audience: CommentAudience }) {
  if (audience === "SHARED") return null;
  return (
    <span className="rounded-full bg-amber-500/15 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide text-amber-400">
      Private
    </span>
  );
}

const TERMS_FIELD_LABELS: Record<string, string> = {
  agreed_fee: "Agreed fee",
  agreed_wage_weekly: "Weekly wage",
  deal_type: "Deal type",
  loan_start: "Loan start",
  loan_end: "Loan end",
  loan_fee: "Loan fee",
  option_to_buy: "Option to buy",
  obligation_to_buy: "Obligation to buy",
  obligation_conditions: "Obligation conditions",
  sell_on_pct: "Sell-on %",
};

const CURRENCY_FIELDS = new Set(["agreed_fee", "agreed_wage_weekly", "loan_fee", "option_to_buy"]);

function formatTermValue(field: string, value: unknown): string {
  if (value == null || value === "") return "—";
  if (field === "sell_on_pct") return `${(Number(value) * 100).toFixed(1)}%`;
  if (CURRENCY_FIELDS.has(field)) return formatCurrency(Number(value));
  if (typeof value === "boolean") return value ? "Yes" : "No";
  return String(value);
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

// ── Comments tab ────────────────────────────────────────────────────────────────

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
      <div className={`rounded-lg px-3 py-2 text-sm ${isMine ? "bg-emerald-500/[0.06]" : "bg-slate-800/60"}`}>
        <div className="mb-0.5 flex items-center justify-between gap-2">
          <span className="flex items-center gap-1.5 text-xs font-semibold text-slate-300">
            {comment.author_label ?? "Unknown"}
            <PrivateBadge audience={comment.audience} />
          </span>
          <span className="text-[11px] text-slate-600">{formatDateTime(comment.created_at)}</span>
        </div>
        <p className="whitespace-pre-wrap break-words text-slate-200">{comment.body}</p>
        <button
          onClick={() => onReply(comment)}
          className="mt-1 text-[11px] text-slate-500 transition-colors hover:text-white"
        >
          Reply
        </button>
      </div>
      {replies.map((r) => (
        <div key={r.id} className="ml-6 mt-2 rounded-lg bg-slate-800/40 px-3 py-2 text-sm">
          <div className="mb-0.5 flex items-center justify-between gap-2">
            <span className="text-xs font-semibold text-slate-300">{r.author_label ?? "Unknown"}</span>
            <span className="text-[11px] text-slate-600">{formatDateTime(r.created_at)}</span>
          </div>
          <p className="whitespace-pre-wrap break-words text-slate-200">{r.body}</p>
        </div>
      ))}
    </div>
  );
}

function CommentThread({
  dealId, canWrite, viewerSide,
}: {
  dealId: string;
  canWrite: boolean;
  viewerSide: ViewerSide;
}) {
  const queryClient = useQueryClient();
  const { addToast } = useToast();
  const [body, setBody] = useState("");
  const [replyTo, setReplyTo] = useState<DealComment | null>(null);
  const [mentions, setMentions] = useState<DealParticipant[]>([]);
  const [audience, setAudience] = useState<CommentAudience>("SHARED");
  const privateAudience = privateAudienceFor(viewerSide);

  const { data: comments = [], isLoading } = useQuery<DealComment[]>({
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

  const topLevel = comments.filter((c) => !c.parent_id);
  const repliesOf = (id: string) => comments.filter((c) => c.parent_id === id);

  return (
    <div>
      {isLoading ? (
        <div className="flex justify-center py-8"><Spinner size="md" /></div>
      ) : topLevel.length === 0 ? (
        <p className="py-6 text-center text-sm italic text-slate-600">No comments yet.</p>
      ) : (
        <div className="max-h-80 overflow-y-auto pr-1">
          {topLevel.map((c) => (
            <CommentRow key={c.id} comment={c} replies={repliesOf(c.id)} onReply={setReplyTo} />
          ))}
        </div>
      )}

      {!canWrite ? null : (
      <form onSubmit={handleSubmit} className="mt-4 border-t border-white/[0.08] pt-3">
        {replyTo && (
          <div className="mb-2 flex items-center justify-between rounded-lg bg-slate-800/60 px-3 py-1.5 text-xs text-slate-400">
            <span>Replying to <span className="text-slate-300">{replyTo.author_label}</span></span>
            <button type="button" onClick={() => setReplyTo(null)} className="text-slate-500 hover:text-white">✕</button>
          </div>
        )}
        <textarea
          value={body}
          onChange={(e) => setBody(e.target.value)}
          rows={2}
          placeholder="Write a comment…"
          className="w-full resize-none rounded-lg bg-slate-800 px-3 py-2 text-sm text-white placeholder-slate-500 ring-1 ring-white/10 focus:outline-none focus:ring-emerald-500"
        />
        {participants.length > 0 && (
          <div className="mt-2 flex flex-wrap items-center gap-1.5">
            <span className="self-center text-[10px] text-slate-600">Mention:</span>
            {participants.map((p) => (
              <button
                key={p.user_id}
                type="button"
                onClick={() => toggleMention(p)}
                className={`rounded-full px-2 py-0.5 text-[10px] font-medium ring-1 transition-colors ${
                  mentions.some((m) => m.user_id === p.user_id)
                    ? "bg-emerald-500/20 text-emerald-400 ring-emerald-500/40"
                    : "bg-slate-800 text-slate-400 ring-white/10 hover:text-white"
                }`}
              >
                @{p.label}
              </button>
            ))}
          </div>
        )}
        <div className="mt-2 flex items-center justify-between gap-2">
          {privateAudience ? (
            <div className="flex gap-1 rounded-lg bg-slate-800/60 p-0.5 text-[11px]">
              <button
                type="button"
                onClick={() => setAudience("SHARED")}
                className={`rounded-md px-2 py-1 font-medium transition-colors ${
                  audience === "SHARED" ? "bg-slate-700 text-white" : "text-slate-500 hover:text-white"
                }`}
              >
                Shared
              </button>
              <button
                type="button"
                onClick={() => setAudience(privateAudience)}
                className={`rounded-md px-2 py-1 font-medium transition-colors ${
                  audience === privateAudience ? "bg-amber-500/20 text-amber-400" : "text-slate-500 hover:text-white"
                }`}
              >
                My club only
              </button>
            </div>
          ) : <span />}
          <Button type="submit" variant="primary" size="sm" loading={mutation.isPending} disabled={!body.trim()}>
            Post
          </Button>
        </div>
      </form>
      )}
    </div>
  );
}

// ── Version history tab ──────────────────────────────────────────────────────────

function VersionHistory({ dealId }: { dealId: string }) {
  const { data: versions = [], isLoading } = useQuery<DealTermsVersion[]>({
    queryKey: ["deals", dealId, "versions"],
    queryFn: () => api.get<DealTermsVersion[]>(`/deals/${dealId}/versions`).then((r) => r.data),
  });

  const { data: diff } = useQuery<TermsDiff>({
    queryKey: ["deals", dealId, "versions", "diff"],
    queryFn: () => api.get<TermsDiff>(`/deals/${dealId}/versions/diff`).then((r) => r.data),
    enabled: versions.length >= 2,
  });

  if (isLoading) return <div className="flex justify-center py-8"><Spinner size="md" /></div>;

  if (versions.length === 0) {
    return <p className="py-6 text-center text-sm italic text-slate-600">No term changes recorded yet.</p>;
  }

  return (
    <div>
      {diff && diff.changes.length > 0 && (
        <div className="mb-4 rounded-xl bg-amber-500/[0.06] px-4 py-3 ring-1 ring-amber-500/20">
          <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-amber-400">
            What changed (v{diff.from_version ?? "—"} → v{diff.to_version})
          </p>
          <div className="space-y-1">
            {diff.changes.map((c) => (
              <div key={c.field} className="flex items-center justify-between text-xs">
                <span className="text-slate-400">{TERMS_FIELD_LABELS[c.field] ?? c.field}</span>
                <span className="text-white">
                  <span className="mr-1.5 text-slate-500 line-through">{formatTermValue(c.field, c.old_value)}</span>
                  {formatTermValue(c.field, c.new_value)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="space-y-2">
        {[...versions].reverse().map((v) => (
          <div key={v.id} className="rounded-lg bg-slate-800/60 px-3 py-2 text-xs">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-slate-300">Version {v.version_number}</span>
              <span className="text-slate-600">{formatDateTime(v.created_at)}</span>
            </div>
            <p className="mt-0.5 text-slate-500">
              {v.changed_by_label ? `Changed by ${v.changed_by_label}` : "Original terms"}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Attachments tab ──────────────────────────────────────────────────────────────

function AttachmentsTab({
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
        <p className="py-6 text-center text-sm italic text-slate-600">No attachments yet.</p>
      ) : (
        <div className="space-y-2">
          {attachments.map((a) => (
            <button
              key={a.id}
              onClick={() => handleDownload(a)}
              className="flex w-full items-center justify-between rounded-lg bg-slate-800/60 px-3 py-2 text-left text-xs transition-colors hover:bg-slate-800"
            >
              <div className="min-w-0 flex-1">
                <p className="flex items-center gap-1.5 truncate font-medium text-slate-200">
                  {a.filename}
                  <PrivateBadge audience={a.audience} />
                </p>
                <p className="text-slate-600">
                  {formatFileSize(a.size_bytes)} · {a.uploaded_by_label ?? "Unknown"} · {formatDateTime(a.created_at)}
                </p>
              </div>
              <span className="shrink-0 text-slate-500">↓</span>
            </button>
          ))}
        </div>
      )}

      {canWrite && (
        <div className="mt-4">
          {privateAudience && (
            <div className="mb-2 flex gap-1 rounded-lg bg-slate-800/60 p-0.5 text-[11px] w-fit">
              <button
                type="button"
                onClick={() => setAudience("SHARED")}
                className={`rounded-md px-2 py-1 font-medium transition-colors ${
                  audience === "SHARED" ? "bg-slate-700 text-white" : "text-slate-500 hover:text-white"
                }`}
              >
                Shared
              </button>
              <button
                type="button"
                onClick={() => setAudience(privateAudience)}
                className={`rounded-md px-2 py-1 font-medium transition-colors ${
                  audience === privateAudience ? "bg-amber-500/20 text-amber-400" : "text-slate-500 hover:text-white"
                }`}
              >
                My club only
              </button>
            </div>
          )}
          <label className="flex cursor-pointer items-center justify-center gap-2 rounded-lg border border-dashed border-white/15 px-4 py-3 text-xs text-slate-400 transition-colors hover:border-white/25 hover:text-white">
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
}: {
  dealId: string;
  /** TRA-151: club members without DEAL_WRITE (scout/read-only) view the room
   * but the composer and upload controls are hidden. Agents/players pass true. */
  canWrite?: boolean;
  /** Item 8: which side of the deal the viewer's own club is on, if any —
   * agents/players and non-participants pass null and never see a private-channel option. */
  viewerSide?: ViewerSide;
}) {
  const [tab, setTab] = useState<"comments" | "history" | "attachments">("comments");

  return (
    <div className="mb-6 rounded-xl bg-slate-900 ring-1 ring-white/[0.08]">
      <div className="flex items-center justify-between border-b border-white/[0.07] px-5 py-3">
        <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">Deal Room</p>
        <div className="flex gap-1">
          {(["comments", "history", "attachments"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`rounded-lg px-3 py-1 text-xs font-medium capitalize transition-colors ${
                tab === t ? "bg-slate-700 text-white" : "text-slate-500 hover:text-white"
              }`}
            >
              {t === "history" ? "Version history" : t}
            </button>
          ))}
        </div>
      </div>
      <div className="px-5 py-4">
        {tab === "comments" && <CommentThread dealId={dealId} canWrite={canWrite} viewerSide={viewerSide} />}
        {tab === "history" && <VersionHistory dealId={dealId} />}
        {tab === "attachments" && <AttachmentsTab dealId={dealId} canWrite={canWrite} viewerSide={viewerSide} />}
      </div>
    </div>
  );
}
