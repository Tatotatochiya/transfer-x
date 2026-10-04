import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import api from "../../lib/api";
import { formatCompactCurrency, formatDate } from "../../lib/utils";
import EmptyState from "../../components/ui/EmptyState";
import PageHeader from "../../components/ui/PageHeader";
import Spinner from "../../components/ui/Spinner";
import type { BoardCard } from "./BoardPage";

/**
 * Transfer history (product ADR 0008): every completed transfer and
 * everything that went nowhere (collapsed deals, offers rejected, withdrawn
 * or expired, closed enquiries, ended listings), newest first. What the old
 * offer, listing, deal and enquiry list pages kept. Backend: GET /board/history.
 */

interface History {
  items: BoardCard[];
  total: number;
  page: number;
  page_size: number;
}

type Side = "BOTH" | "BUYING" | "SELLING";
type Outcome = "" | "completed" | "ended";

const PAGE_SIZE = 30;

export default function BoardHistoryPage() {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const side = (params.get("side") as Side) || "BOTH";
  const outcome = (params.get("outcome") as Outcome) || "";
  const page = Math.max(1, Number(params.get("page")) || 1);
  const [q, setQ] = useState(params.get("q") ?? "");

  const set = (changes: Record<string, string>) => {
    const next = new URLSearchParams(params);
    for (const [k, v] of Object.entries(changes)) {
      if (v) next.set(k, v); else next.delete(k);
    }
    if (!("page" in changes)) next.delete("page");
    setParams(next, { replace: true });
  };
  // Search as you type, a moment after typing stops.
  useEffect(() => {
    const t = window.setTimeout(() => { if ((params.get("q") ?? "") !== q.trim()) set({ q: q.trim() }); }, 300);
    return () => window.clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q]);

  const { data, isLoading, isError } = useQuery<History>({
    queryKey: ["board", "history", side, outcome, params.get("q") ?? "", page],
    queryFn: () => api.get<History>("/board/history", {
      params: { side, ...(outcome && { outcome }), ...(params.get("q") && { q: params.get("q") }), page, page_size: PAGE_SIZE },
    }).then((r) => r.data),
  });
  const pages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;
  const select = "rounded-lg bg-surface px-2.5 py-1.5 text-sm text-text ring-1 ring-input-border";

  return (
    <div className="mx-auto max-w-4xl">
      <PageHeader
        title="Transfer history"
        subtitle="Completed transfers, and everything that ended without one."
        actions={<Link to="/board" className="text-sm font-semibold text-accent">← Transfers board</Link>}
      />
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <input
          type="search"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search a player or club"
          aria-label="Search a player or club"
          className="min-w-0 flex-1 basis-56 rounded-lg bg-surface px-3 py-1.5 text-sm text-text ring-1 ring-input-border focus:outline-none focus:ring-accent"
        />
        <select aria-label="Buying or selling" value={side} onChange={(e) => set({ side: e.target.value === "BOTH" ? "" : e.target.value })} className={select}>
          <option value="BOTH">Buying and selling</option>
          <option value="BUYING">Buying</option>
          <option value="SELLING">Selling</option>
        </select>
        <select aria-label="Outcome" value={outcome} onChange={(e) => set({ outcome: e.target.value })} className={select}>
          <option value="">Every outcome</option>
          <option value="completed">Completed</option>
          <option value="ended">Ended without a transfer</option>
        </select>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-16"><Spinner size="lg" /></div>
      ) : isError || !data ? (
        <EmptyState title="Couldn't load the history" body="Try again in a moment." />
      ) : data.items.length === 0 ? (
        <EmptyState title="Nothing here" body={params.get("q") || outcome || side !== "BOTH" ? "Nothing matches these filters." : "Finished transfers and ones that ended will be listed here."} />
      ) : (
        <>
          <p className="mb-2 text-xs text-text-muted">{data.total} {data.total === 1 ? "item" : "items"}</p>
          <div className="divide-y divide-rule-faint rounded-xl bg-surface ring-1 ring-border">
            {data.items.map((c) => (
              <button
                key={`${c.kind}:${c.entity_id}`}
                type="button"
                onClick={() => navigate(c.link)}
                className="flex w-full flex-wrap items-center gap-x-4 gap-y-1 px-4 py-3 text-left hover:bg-surface-inset"
              >
                <span className="min-w-0 flex-1 basis-48">
                  <span className="block truncate text-sm font-semibold text-text">
                    {c.player_name}
                    {c.player_position && <span className="ml-1.5 text-xs font-normal text-text-muted">{c.player_position}</span>}
                  </span>
                  <span className="block truncate text-xs text-text-muted">
                    {c.side === "BUYING" ? "Buying" : "Selling"}
                    {c.counterparty && (c.side === "BUYING" ? ` from ${c.counterparty}` : ` to ${c.counterparty}`)}
                  </span>
                </span>
                <span className={`text-xs font-semibold ${c.column === "done" ? "text-success-text" : "text-text-secondary"}`}>{c.detail}</span>
                <span className="w-20 text-right text-sm font-bold tabular-nums text-text">
                  {c.amount != null ? formatCompactCurrency(Number(c.amount)) : "—"}
                </span>
                <span className="w-24 text-right text-xs text-text-muted">{c.updated_at ? formatDate(c.updated_at) : ""}</span>
              </button>
            ))}
          </div>
          {pages > 1 && (
            <div className="mt-4 flex items-center justify-between text-sm">
              <button type="button" disabled={page <= 1} onClick={() => set({ page: String(page - 1) })}
                className="font-semibold text-accent disabled:text-text-muted">← Newer</button>
              <span className="text-text-muted">Page {page} of {pages}</span>
              <button type="button" disabled={page >= pages} onClick={() => set({ page: String(page + 1) })}
                className="font-semibold text-accent disabled:text-text-muted">Older →</button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
