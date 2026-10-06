import { useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";

import api from "../../lib/api";
import { formatCompactCurrency, formatDate, formatWage, getApiError } from "../../lib/utils";
import PlayerLink from "../../components/ui/PlayerLink";
import Spinner from "../../components/ui/Spinner";

/**
 * Ask TransferX as an analyst (AI analyst spec, Phase A). The model calls
 * read-only tools as the club; every table here is built by TransferX from
 * their results, with where it came from underneath. Follow-ups carry the
 * conversation. Backend: POST /ai/analyst.
 */

type Row = Record<string, unknown> & { path?: string; player_id?: string; photo_url?: string | null };

interface TableBlock {
  type: "table";
  title: string;
  kind: string;
  columns: string[];
  rows: Row[];
  total: number;
  source: { tool: string; label: string; filters: Record<string, unknown>; as_of: string; note: string | null };
}

interface AnalystAnswer {
  answer: string;
  blocks: TableBlock[];
  follow_ups: string[];
  proposal: { card_path: string; player: string | null; amount: number | null } | null;
  links: { label: string; path: string }[];
}

interface Turn {
  question: string;
  result?: AnalystAnswer;
  error?: string;
}

const STARTERS = [
  "Which of our players have had interest in the last 7 days?",
  "Show me 5 midfielders who are transfer listed",
  "What's waiting on us, and what expires this week?",
  "Our highest earners whose contract ends within 18 months",
  "How much transfer budget do we have left?",
  "Auctions ending this week",
];

const HEADERS: Record<string, string> = {
  player: "Player", position: "Pos", age: "Age", club: "Club", other_club: "Other club", nationality: "Nationality",
  contract_ends: "Contract ends", market_value: "Market value", asking_price: "Asking price", fair_value: "Fair value",
  wage_weekly: "Wage", your_valuation: "Your valuation", listed: "Listed", listed_for_sale: "Listed", amount: "Amount",
  stage: "Stage", side: "Side", status: "Status", deadline: "Deadline", outcome: "Outcome", when: "When", type: "Type",
  availability: "For", enquiries: "Enquiries", offers: "Offers", bids: "Bids",
  shortlisted_by_clubs: "Shortlisted by", viewed_by_clubs: "Viewed by", metric: "", value: "", your_move: "Your move",
};
const MONEY = new Set(["asking_price", "fair_value", "your_valuation", "amount"]);
const DATES = new Set(["contract_ends", "deadline", "when"]);
const COUNTS_OF_CLUBS = new Set(["shortlisted_by_clubs", "viewed_by_clubs"]);

function words(s: string): string {
  return s.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
}

function cell(col: string, row: Row): React.ReactNode {
  const v = row[col];
  if (col === "player") {
    return <PlayerLink id={row.player_id ?? null} name={String(v ?? "")} photoUrl={(row.photo_url as string) ?? null} />;
  }
  if (v == null || v === "") return <span className="text-text-muted">—</span>;
  if (col === "market_value") {
    const cur = row.market_value_currency === "EUR" ? "€" : row.market_value_currency === "USD" ? "$" : "£";
    return formatCompactCurrency(Number(v)).replace("£", cur);
  }
  if (MONEY.has(col)) return formatCompactCurrency(Number(v));
  if (col === "wage_weekly") return formatWage(Number(v));
  if (DATES.has(col)) return formatDate(String(v));
  if (COUNTS_OF_CLUBS.has(col)) return Number(v) ? `${v} club${Number(v) === 1 ? "" : "s"}` : "—";
  if (typeof v === "boolean") return v ? "Yes" : "No";
  if (col === "metric") return words(String(v));
  if (col === "value" && typeof v === "number") return Math.abs(v) >= 1000 ? formatCompactCurrency(v) : String(v);
  if (col === "side") return words(String(v));
  return String(v);
}

/** "contract ends within 18 months", "last 7 days", "sorted by wage". */
function filterText(k: string, v: unknown): string {
  if (typeof v === "boolean") return v ? words(k).toLowerCase() : `not ${words(k).toLowerCase()}`;
  const m = /^(.*)_within_(months|days)$/.exec(k);
  if (m) return `${words(m[1]).toLowerCase()} within ${v} ${m[2]}`;
  if (k === "days") return `last ${v} days`;
  if (k === "sort_by") return `sorted by ${words(String(v)).toLowerCase()}`;
  if (k.startsWith("min_") || k.startsWith("max_")) {
    const what = words(k.slice(4)).toLowerCase();
    const n = Number(v);
    const val = /value|price/.test(k) ? formatCompactCurrency(n) : String(v);
    return `${what} ${k.startsWith("min_") ? "at least" : "at most"} ${val}`;
  }
  return `${words(k).toLowerCase()} ${String(v)}`;
}

function sourceLine(s: TableBlock["source"]): string {
  const f = Object.entries(s.filters).filter(([k]) => k !== "sort_dir").map(([k, v]) => filterText(k, v));
  const at = new Date(s.as_of).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
  return `${s.label}${f.length ? ` · ${f.join(", ")}` : ""} · as of ${at}`;
}

function toCsv(b: TableBlock): string {
  const esc = (x: unknown) => {
    const s = x == null ? "" : String(x);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  return [b.columns.map((c) => HEADERS[c] || words(c)).map(esc).join(","),
    ...b.rows.map((r) => b.columns.map((c) => esc(r[c])).join(","))].join("\n");
}

function download(b: TableBlock) {
  const url = URL.createObjectURL(new Blob([toCsv(b)], { type: "text/csv" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = `${b.title.replace(/[^\w]+/g, "-").toLowerCase() || "transferx"}.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function AnswerTable({ block }: { block: TableBlock }) {
  const navigate = useNavigate();
  return (
    <div className="mt-3 overflow-hidden rounded-xl bg-surface ring-1 ring-border">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-rule px-4 py-2.5">
        <p className="text-sm font-semibold text-text">{block.title}</p>
        <div className="flex items-center gap-3 text-xs text-text-muted">
          <span>{block.rows.length < block.total ? `Showing ${block.rows.length} of ${block.total}` : `${block.total} ${block.total === 1 ? "row" : "rows"}`}</span>
          <button type="button" onClick={() => download(block)} className="font-semibold text-accent hover:underline">Export CSV</button>
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-rule-faint text-left text-xs text-text-muted">
              {block.columns.map((c) => <th key={c} className="whitespace-nowrap px-4 py-2 font-semibold">{HEADERS[c] ?? words(c)}</th>)}
            </tr>
          </thead>
          <tbody>
            {block.rows.map((r, i) => (
              <tr
                key={String(r.path ?? i)}
                onClick={() => r.path && navigate(String(r.path))}
                className={`border-b border-rule-faint last:border-b-0 ${r.path ? "cursor-pointer hover:bg-surface-inset" : ""}`}
              >
                {block.columns.map((c) => <td key={c} className="whitespace-nowrap px-4 py-2 text-text">{cell(c, r)}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="border-t border-rule-faint px-4 py-2 text-[11px] text-text-muted">
        {sourceLine(block.source)}
        {block.source.note && <> · {block.source.note}</>}
      </p>
    </div>
  );
}

const STORE = "transferx-ask-thread";

export default function AskPage() {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const [thread, setThread] = useState<Turn[]>(() => {
    try { return JSON.parse(sessionStorage.getItem(STORE) || "[]"); } catch { return []; }
  });
  const [text, setText] = useState("");
  const bottom = useRef<HTMLDivElement>(null);

  useEffect(() => {
    try { sessionStorage.setItem(STORE, JSON.stringify(thread.slice(-12))); } catch { /* the thread still works */ }
    bottom.current?.scrollIntoView?.({ behavior: "smooth", block: "end" });
  }, [thread]);

  const ask = useMutation({
    mutationFn: (question: string) => {
      const history = thread.filter((t) => t.result).slice(-4).map((t) => ({ question: t.question, answer: t.result!.answer }));
      return api.post<AnalystAnswer>("/ai/analyst", { question, history }).then((r) => r.data);
    },
    onMutate: (question) => setThread((t) => [...t, { question }]),
    onSuccess: (result) => setThread((t) => t.map((x, i) => (i === t.length - 1 ? { ...x, result } : x))),
    onError: (err) => setThread((t) => t.map((x, i) => (i === t.length - 1 ? { ...x, error: getApiError(err, "Couldn't answer just now.") } : x))),
  });
  const send = (q: string) => {
    const question = q.trim();
    if (question.length < 3 || ask.isPending) return;
    setText("");
    ask.mutate(question);
  };

  // ⌘K hands a question over as /ask?q=…
  useEffect(() => {
    const q = params.get("q");
    if (q) {
      setParams({}, { replace: true });
      send(q);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="mx-auto flex max-w-5xl flex-col">
      <div className="mb-4 flex items-baseline justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-text">Ask TransferX</h1>
          <p className="text-sm text-text-muted">Ask what you'd ask an analyst. Answers come from your club's data and the market on TransferX.</p>
        </div>
        {thread.length > 0 && (
          <button type="button" onClick={() => setThread([])} className="text-sm font-semibold text-text-secondary hover:text-text">New conversation</button>
        )}
      </div>

      {thread.length === 0 && (
        <div className="mb-6 grid gap-2 sm:grid-cols-2">
          {STARTERS.map((s) => (
            <button key={s} type="button" onClick={() => send(s)}
              className="rounded-xl bg-surface px-4 py-3 text-left text-sm text-text ring-1 ring-border hover:ring-accent">
              {s}
            </button>
          ))}
        </div>
      )}

      <div className="flex flex-col gap-6">
        {thread.map((t, i) => (
          <div key={i}>
            <div className="flex justify-end">
              <p className="max-w-[80%] rounded-2xl bg-accent-bg px-4 py-2.5 text-sm text-text">{t.question}</p>
            </div>
            <div className="mt-3">
              {!t.result && !t.error && (
                <p className="flex items-center gap-2 text-sm text-text-muted"><Spinner size="sm" /> Looking it up…</p>
              )}
              {t.error && <p className="text-sm text-danger-text">{t.error}</p>}
              {t.result && (
                <>
                  <p className="text-[15px] leading-relaxed text-text">{t.result.answer}</p>
                  {t.result.proposal && (
                    <button type="button" onClick={() => navigate(t.result!.proposal!.card_path)}
                      className="mt-2 rounded-lg bg-accent px-3 py-1.5 text-sm font-semibold text-white hover:bg-accent-hover">
                      Check and send →
                    </button>
                  )}
                  {t.result.links.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-2">
                      {t.result.links.map((l) => (
                        <button key={l.path} type="button" onClick={() => navigate(l.path)}
                          className="rounded-lg bg-accent-bg px-2.5 py-1 text-xs font-semibold text-accent ring-1 ring-accent/20">
                          {l.label} →
                        </button>
                      ))}
                    </div>
                  )}
                  {t.result.blocks.map((b, j) => <AnswerTable key={j} block={b} />)}
                  {i === thread.length - 1 && t.result.follow_ups.length > 0 && (
                    <div className="mt-3 flex flex-wrap gap-2">
                      {t.result.follow_ups.map((f) => (
                        <button key={f} type="button" onClick={() => send(f)}
                          className="rounded-full px-3 py-1 text-xs font-medium text-text-secondary ring-1 ring-border hover:text-text hover:ring-accent">
                          {f}
                        </button>
                      ))}
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
        ))}
        <div ref={bottom} />
      </div>

      <form
        onSubmit={(e) => { e.preventDefault(); send(text); }}
        className="sticky bottom-0 mt-6 flex gap-2 bg-page py-3"
      >
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder={thread.length ? "Ask a follow-up…" : "Ask anything about players, your squad, your transfers…"}
          aria-label="Your question"
          className="min-w-0 flex-1 rounded-xl bg-surface px-4 py-3 text-sm text-text ring-1 ring-input-border focus:outline-none focus:ring-accent"
        />
        <button type="submit" disabled={text.trim().length < 3 || ask.isPending}
          className="rounded-xl bg-accent px-5 text-sm font-semibold text-white disabled:opacity-50">
          {ask.isPending ? "…" : "Ask"}
        </button>
      </form>
    </div>
  );
}
