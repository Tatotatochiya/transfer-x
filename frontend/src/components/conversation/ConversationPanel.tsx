import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import api from "../../lib/api";
import { formatDateTime, getApiError } from "../../lib/utils";
import { useClubCapabilities } from "../../hooks/useClubCapabilities";
import Button from "../ui/Button";
import Spinner from "../ui/Spinner";

/**
 * One conversation per transfer (product ADR 0008): the enquiry, offers,
 * deal and agent thread between the two clubs about one player, in order.
 * Backend: app/conversation. Each message says who can read it.
 */

type Audience = "both_clubs" | "deal_everyone" | "our_club" | "with_agent";

interface Message {
  id: string;
  source: "enquiry" | "offer" | "deal" | "agent";
  audience: Audience;
  audience_label: string;
  author: string;
  mine: boolean;
  body: string;
  created_at: string;
  context: string;
}

interface Conversation {
  messages: Message[];
  can_post_to: { key: Audience; label: string }[];
}

export type ConversationContext = { offerId?: string; dealId?: string; enquiryId?: string };

function params(ctx: ConversationContext) {
  return {
    ...(ctx.offerId && { offer_id: ctx.offerId }),
    ...(ctx.dealId && { deal_id: ctx.dealId }),
    ...(ctx.enquiryId && { enquiry_id: ctx.enquiryId }),
  };
}

export default function ConversationPanel({ context, compact = false }: { context: ConversationContext; compact?: boolean }) {
  const qc = useQueryClient();
  const { can } = useClubCapabilities();
  const key = ["conversation", params(context)];
  const { data, isLoading, isError } = useQuery<Conversation>({
    queryKey: key,
    queryFn: () => api.get<Conversation>("/conversation", { params: params(context) }).then((r) => r.data),
    refetchInterval: 30_000,
  });
  const [body, setBody] = useState("");
  const [audience, setAudience] = useState<Audience | null>(null);
  useEffect(() => {
    if (data && (!audience || !data.can_post_to.some((o) => o.key === audience))) {
      setAudience(data.can_post_to[0]?.key ?? null);
    }
  }, [data, audience]);

  const send = useMutation({
    mutationFn: () => api.post<Conversation>("/conversation", { ...params(context), audience, body }).then((r) => r.data),
    onSuccess: (fresh) => {
      setBody("");
      qc.setQueryData(key, fresh);
      void qc.invalidateQueries({ queryKey: ["board"] });
    },
  });

  if (isLoading) return <div className="flex justify-center py-6"><Spinner /></div>;
  if (isError || !data) return <p className="text-sm text-text-muted">Couldn't load the conversation.</p>;

  // Writing needs the market permission before a deal, and the deal permission after.
  const writeCap = audience === "both_clubs" ? "MARKET_WRITE" : "DEAL_WRITE";
  const canWrite = data.can_post_to.length > 0 && can(writeCap);
  const selected = data.can_post_to.find((o) => o.key === audience);

  return (
    <div className="space-y-3">
      <div className={`space-y-2.5 overflow-y-auto ${compact ? "max-h-[50vh]" : "max-h-[60vh]"}`}>
        {data.messages.length === 0 && <p className="text-sm text-text-muted">Nothing said yet.</p>}
        {data.messages.map((m) => (
          <div key={`${m.source}:${m.id}`} className={`flex ${m.mine ? "justify-end" : "justify-start"}`}>
            <div
              className={`max-w-[85%] rounded-xl px-3.5 py-2 text-sm ${
                m.audience === "our_club" ? "bg-warning-fill/15 ring-1 ring-warning-fill/30"
                  : m.mine ? "bg-accent-bg" : "bg-surface-inset"
              } text-text`}
            >
              <p className="whitespace-pre-wrap">{m.body}</p>
              <p className="mt-1 text-[11px] text-text-muted">
                {m.author} · {formatDateTime(m.created_at)} · {m.context}
                {m.audience !== "both_clubs" && <> · <span className="font-semibold">{m.audience_label}</span></>}
              </p>
            </div>
          </div>
        ))}
      </div>

      {canWrite ? (
        <form
          className="space-y-2 border-t border-rule-faint pt-3"
          onSubmit={(e) => { e.preventDefault(); if (body.trim() && audience) send.mutate(); }}
        >
          <textarea
            value={body}
            onChange={(e) => setBody(e.target.value)}
            rows={2}
            maxLength={4000}
            placeholder="Write a message…"
            aria-label="Message"
            className="w-full resize-y rounded-lg bg-surface px-3 py-2 text-sm text-text ring-1 ring-input-border focus:outline-none focus:ring-accent"
          />
          {send.isError && <p className="text-sm text-danger-text">{getApiError(send.error)}</p>}
          <div className="flex flex-wrap items-center justify-between gap-2">
            {data.can_post_to.length > 1 ? (
              <label className="flex items-center gap-2 text-xs text-text-secondary">
                Who can read it
                <select
                  value={audience ?? ""}
                  onChange={(e) => setAudience(e.target.value as Audience)}
                  className="rounded-lg bg-surface px-2 py-1.5 text-xs text-text ring-1 ring-input-border"
                >
                  {data.can_post_to.map((o) => <option key={o.key} value={o.key}>{o.label}</option>)}
                </select>
              </label>
            ) : (
              <span className="text-xs text-text-muted">{selected?.label} can read this</span>
            )}
            <Button type="submit" size="sm" disabled={!body.trim() || send.isPending}>
              {send.isPending ? "Sending…" : "Send"}
            </Button>
          </div>
        </form>
      ) : (
        data.can_post_to.length === 0 && (
          <p className="border-t border-rule-faint pt-3 text-xs text-text-muted">Nothing is open on this transfer, so it can't take new messages.</p>
        )
      )}
    </div>
  );
}
