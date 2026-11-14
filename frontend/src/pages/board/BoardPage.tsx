import { useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import api from "../../lib/api";
import { useMediaQuery } from "../../hooks/useMediaQuery";
import EmptyState from "../../components/ui/EmptyState";
import Spinner from "../../components/ui/Spinner";
import Button from "../../components/ui/Button";
import { Card, CardDetail, Columns, SIDE_STYLE } from "../../components/board/BoardColumns";
import BoardMoreMenu from "../../components/board/BoardMoreMenu";
import StageChips from "../../components/board/StageChips";
import TransferList, { ClosedList } from "../../components/board/TransferList";
import WaitingStrip from "../../components/board/WaitingStrip";
import { boardRows, stageCounts, stageLabels, yourMoveRows } from "../../components/board/boardList";
import type { Board, BoardCard, Side } from "../../components/board/types";

export type { Board, BoardCard } from "../../components/board/types";

/**
 * The Transfers board (Phase 3, product ADR 0008): every player the club is
 * buying or selling, once, at its furthest point. Backend: app/board.
 * Below 1280px it's a list grouped by whose move it is, with stage chips;
 * from 1280px the stage columns (README_TRANSFERS).
 */

const SIDE_KEY = "transferx-board-side";

function readSide(): Side {
  try {
    const v = localStorage.getItem(SIDE_KEY);
    return v === "BUYING" || v === "SELLING" ? v : "BOTH";
  } catch {
    return "BOTH";
  }
}

function SideSwitch({ side, onChange, full }: { side: Side; onChange: (s: Side) => void; full?: boolean }) {
  return (
    <div role="radiogroup" aria-label="Show" className={`flex rounded-lg bg-surface-inset p-0.5 ring-1 ring-border ${full ? "w-full" : ""}`}>
      {(["BOTH", "BUYING", "SELLING"] as Side[]).map((s) => (
        <button
          key={s}
          role="radio"
          aria-checked={side === s}
          onClick={() => onChange(s)}
          className={`rounded-md px-3 text-body font-medium ${full ? "min-h-11 flex-1" : "py-1.5"} ${
            side === s ? "bg-surface text-text shadow-sm" : "text-text-secondary"}`}
        >
          {s === "BOTH" ? "Both" : s === "BUYING" ? "Buying" : "Selling"}
        </button>
      ))}
    </div>
  );
}

const ICON_BUTTON = "inline-flex h-11 w-11 items-center justify-center rounded-lg bg-surface text-text-secondary ring-1 ring-inset ring-input-border hover:text-text";

export default function BoardPage() {
  const navigate = useNavigate();
  // ?side= wins (links from the old list pages, the assistant), else the
  // choice remembered in this browser.
  const [params, setParams] = useSearchParams();
  const urlSide = params.get("side");
  const [side, setSideState] = useState<Side>(() =>
    urlSide === "BUYING" || urlSide === "SELLING" || urlSide === "BOTH" ? urlSide : readSide());
  const [search, setSearch] = useState("");
  const [searchOpen, setSearchOpen] = useState(false);
  const searchRef = useRef<HTMLInputElement>(null);
  const [showClosed, setShowClosed] = useState(false);
  const [opened, setOpened] = useState<BoardCard | null>(null);
  const wide = useMediaQuery("(min-width: 1280px)");
  const sm = useMediaQuery("(min-width: 640px)");
  const setSide = (s: Side) => {
    setSideState(s);
    try { localStorage.setItem(SIDE_KEY, s); } catch { /* the choice still applies here */ }
  };
  const { data, isLoading, isError } = useQuery<Board>({
    queryKey: ["board", side],
    queryFn: () => api.get<Board>("/board", { params: { side } }).then((r) => r.data),
    refetchInterval: 60_000,
  });
  const total = data ? data.columns.reduce((n, c) => n + c.cards.length, 0) : 0;
  const needle = search.trim().toLowerCase();
  const matches = (c: BoardCard) =>
    !needle || c.player_name.toLowerCase().includes(needle) || (c.counterparty ?? "").toLowerCase().includes(needle);

  // The list (below 1280px): rows after the side and search filters, then the stage chip.
  const labels = data ? stageLabels(data) : {};
  const rows = data ? boardRows(data).filter(matches) : [];
  const stages = stageCounts(rows, labels);
  const urlStage = params.get("stage");
  const stage = urlStage && stages.some((s) => s.key === urlStage) ? urlStage : null;
  const setStage = (key: string | null) => setParams((p) => {
    const next = new URLSearchParams(p);
    if (key) next.set("stage", key); else next.delete("stage");
    return next;
  }, { replace: true });
  // A picked stage that's dropped to zero (a search, a side change) falls back to All.
  useEffect(() => {
    if (data && urlStage && !stage) setStage(null);
  }, [data, urlStage, stage]); // eslint-disable-line react-hooks/exhaustive-deps
  const shown = stage ? rows.filter((r) => r.column === stage) : rows;
  useEffect(() => { if (searchOpen) searchRef.current?.focus(); }, [searchOpen]);

  const counts = data && (
    <p className="mt-[3px] text-small text-text-secondary">
      <span className={data.counts.your_move > 0 ? "font-semibold text-danger-text" : undefined}>
        {data.counts.your_move} waiting on you
      </span>
      {` · ${data.counts.buying} buying · ${data.counts.selling} selling`}
    </p>
  );
  const title = <h1 className="text-title-sm font-bold tracking-[-0.01em] text-text sm:text-title">Transfers</h1>;
  const searchToggle = (
    <button type="button" aria-label="Find a player or club" aria-expanded={searchOpen || !!search}
      onClick={() => setSearchOpen((o) => !o)} className={ICON_BUTTON}>
      <svg aria-hidden viewBox="0 0 20 20" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.8">
        <circle cx="9" cy="9" r="5.5" /><path d="m13.5 13.5 3.5 3.5" strokeLinecap="round" />
      </svg>
    </button>
  );
  const searchField = !wide && total > 0 && (searchOpen || search) && (
    <div className="relative">
      <input
        ref={searchRef}
        type="search"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        onBlur={() => { if (!search) setSearchOpen(false); }}
        placeholder="Find a player or club"
        aria-label="Find a player or club on the board"
        className="w-full min-h-11 rounded-lg bg-surface pl-3 pr-11 text-input text-text ring-1 ring-input-border focus:outline-none focus:ring-accent"
      />
      {search && (
        <button type="button" aria-label="Clear" onClick={() => { setSearch(""); setSearchOpen(false); }}
          className="absolute right-0 top-0 h-11 w-11 text-text-muted hover:text-text">×</button>
      )}
    </div>
  );

  const header = wide ? (
    <div className="mb-5 flex flex-wrap items-center justify-between gap-4">
      <div>{title}{counts}</div>
      <div className="flex flex-wrap items-center gap-2">
        {total > 0 && (
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Find a player or club"
            aria-label="Find a player or club on the board"
            className="w-64 rounded-lg bg-surface px-3 py-1.5 text-body text-text ring-1 ring-input-border focus:outline-none focus:ring-accent"
          />
        )}
        <SideSwitch side={side} onChange={setSide} />
        <Button size="sm" variant="secondary" onClick={() => navigate("/board/history")}>History</Button>
        <Button size="sm" onClick={() => navigate("/sales/new")}>+ New listing</Button>
      </div>
    </div>
  ) : sm ? (
    <div className="mb-4 space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>{title}{counts}</div>
        <div className="flex items-center gap-2">
          <SideSwitch side={side} onChange={setSide} />
          {total > 0 && searchToggle}
          <BoardMoreMenu />
        </div>
      </div>
      {searchField}
    </div>
  ) : (
    <div className="mb-3 space-y-2.5">
      <div>
        <div className="flex items-center justify-between gap-2">
          {title}
          <div className="flex items-center gap-2">{total > 0 && searchToggle}<BoardMoreMenu /></div>
        </div>
        {counts}
      </div>
      <SideSwitch side={side} onChange={setSide} full />
      {searchField}
    </div>
  );

  const closed = data && data.closed.length > 0 && (
    <div className="mt-6">
      <button
        type="button"
        onClick={() => setShowClosed((v) => !v)}
        aria-expanded={showClosed}
        className="text-body font-semibold text-text-secondary hover:text-text"
      >
        Closed ({data.closed.length}) {showClosed ? "▾" : "▸"}
      </button>
      <button type="button" onClick={() => navigate("/board/history")} className="ml-4 text-body font-semibold text-accent hover:underline">
        Full history →
      </button>
      {showClosed && (wide ? (
        <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          {data.closed.map((c) => <Card key={`${c.key}:${c.entity_id}`} card={c} showSide={side === "BOTH"} onOpen={setOpened} />)}
        </div>
      ) : (
        <div className="mt-3"><ClosedList rows={data.closed} side={side} labels={labels} layout={sm ? "tablet" : "phone"} /></div>
      ))}
    </div>
  );

  function list() {
    if (rows.length === 0) {
      return (
        <div className="rounded-xl border border-dashed border-border px-4 py-6 text-center text-small text-text-secondary">
          No transfers match “{search.trim()}”.{" "}
          <button type="button" onClick={() => { setSearch(""); setSearchOpen(false); }} className="font-semibold text-accent hover:underline">
            Clear search
          </button>
        </div>
      );
    }
    return (
      <>
        <div className="mb-3"><StageChips total={rows.length} stages={stages} selected={stage} onSelect={setStage} /></div>
        <TransferList rows={shown} side={side} labels={labels} layout={sm ? "tablet" : "phone"} />
        {stage && (
          <p className="mt-4 text-small text-text-secondary">
            Showing {labels[stage] ?? stage} ·{" "}
            <button type="button" onClick={() => setStage(null)} className="font-semibold text-accent hover:underline">
              Show all {rows.length}
            </button>
          </p>
        )}
      </>
    );
  }

  function columns(board: Board) {
    // A column empty in every lane shown collapses, the same in both lanes so they line up.
    const collapsed = new Set(board.columns.filter((c) => !c.cards.some(matches)).map((c) => c.key));
    return (
      <>
        {board.counts.your_move > 0 && <WaitingStrip rows={yourMoveRows(rows)} onOpen={setOpened} />}
        {/* Both sides: a lane each, so it's never a guess which way a card goes. */}
        {side === "BOTH"
          ? (["BUYING", "SELLING"] as const).map((lane) => (
            <section key={lane} aria-label={SIDE_STYLE[lane].label} className="mb-5">
              <h2 className="mb-2 flex items-center gap-2 text-body font-bold text-text">
                <span className={`h-4 w-1 rounded-full ${SIDE_STYLE[lane].bar}`} aria-hidden />
                {SIDE_STYLE[lane].label}
                <span className="text-caption font-semibold tabular-nums text-text-muted">
                  {lane === "BUYING" ? board.counts.buying : board.counts.selling}
                </span>
                <span className="text-small font-normal text-text-muted">
                  {lane === "BUYING" ? "· players you're signing" : "· your players, to other clubs"}
                </span>
              </h2>
              {(lane === "BUYING" ? board.counts.buying : board.counts.selling) === 0 ? (
                <p className="rounded-xl border border-dashed border-border px-3 py-3 text-small text-text-muted">
                  {lane === "BUYING" ? "Nothing you're buying at the moment." : "Nothing you're selling at the moment."}
                </p>
              ) : <Columns columns={board.columns} pick={(c) => c.side === lane && matches(c)} collapsed={collapsed} showSide={false} onOpen={setOpened} />}
            </section>
          ))
          : <Columns columns={board.columns} pick={matches} collapsed={collapsed} showSide={false} onOpen={setOpened} />}
      </>
    );
  }

  return (
    <div>
      {header}
      {isLoading ? (
        <div className="flex justify-center py-16"><Spinner size="lg" /></div>
      ) : isError || !data ? (
        <EmptyState title="Couldn't load the board" body="Try again in a moment." />
      ) : total === 0 ? (
        <>
          <EmptyState
            title="Nothing in progress"
            body="Players you list, enquire about or make offers for appear here, one card each."
            action={{ label: "Browse players", to: "/players/market" }}
          />
          {closed}
        </>
      ) : (
        <>
          {wide ? columns(data) : list()}
          {closed}
        </>
      )}
      {opened && <CardDetail card={opened} onClose={() => setOpened(null)} />}
    </div>
  );
}
