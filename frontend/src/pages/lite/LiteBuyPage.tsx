import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router-dom";

import Icon from "../../components/layout/Icon";
import Spinner from "../../components/ui/Spinner";
import { liteMoney } from "../../lib/liteMoney";
import { useDebounce } from "../../hooks/useDebounce";
import {
  useLiteBuySearch,
  useLiteBuyTargets,
  useLiteShortlist,
  type LiteSearchResult,
} from "../../hooks/useLite";
import AskTeamButton from "../../components/lite/AskTeamButton";

/**
 * Buy a player (docs/feature_spec/lite-mode README "Screen 3"): a search by
 * name, and below it the players the club is already after, from its
 * shortlists and the players it marked as of interest. Each row says whether
 * the club can make an offer now and at what price, or why not, and puts the
 * player on the shortlist or takes him off. The search lives in the URL, so
 * Back from a bid returns to it. This replaced the guided position → budget →
 * suggestions path on 2026-10-18.
 */

const POSITION_LABEL: Record<string, string> = { GK: "Goalkeeper", DEF: "Defender", MID: "Midfielder", FWD: "Forward" };

function initials(name: string) {
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]?.toUpperCase()).join("");
}

function Avatar({ name, photo }: { name: string; photo?: string | null }) {
  return photo ? (
    <img src={photo} alt="" className="h-12 w-12 shrink-0 rounded-full bg-surface-inset object-cover object-top" />
  ) : (
    <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-accent-bg text-[1.25rem] font-extrabold text-accent">
      {initials(name)}
    </span>
  );
}

const rowBtn = "flex min-h-[3.25rem] items-center justify-center rounded-xl px-5 text-[1.0625rem] font-bold no-underline";
const plainBtn = `${rowBtn} text-text ring-1 ring-border hover:ring-accent`;

function ShortlistButton({ p }: { p: LiteSearchResult }) {
  const shortlist = useLiteShortlist();
  const [error, setError] = useState<string | null>(null);
  const on = p.shortlisted;
  const toggle = () => {
    setError(null);
    shortlist.mutate({ playerId: p.player_id, on: !on }, {
      onError: (e: unknown) => {
        const code = (e as { response?: { status?: number } })?.response?.status;
        setError(code === 403 ? "Your role can't change the shortlist." : "That didn't work. Try again in a moment.");
      },
    });
  };
  return (
    <span className="flex flex-col">
      <button
        type="button"
        onClick={toggle}
        disabled={shortlist.isPending}
        aria-pressed={on}
        className={`${plainBtn} gap-2 disabled:opacity-60`}
      >
        {on ? <><Icon name="check" className="h-5 w-5 text-accent" /> On your shortlist</> : "Shortlist"}
      </button>
      {error && <span role="alert" className="mt-1 text-[0.9375rem] text-danger-text">{error}</span>}
    </span>
  );
}

/** One player: who he is, his price, what the club can do now (or why not), and the shortlist. */
function PlayerRow({ p }: { p: LiteSearchResult }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const facts = [p.club ?? (p.state === "free_agent" ? "Free agent" : null), p.position && POSITION_LABEL[p.position], p.age != null && `age ${p.age}`]
    .filter(Boolean).join(" · ");
  const price = p.state === "buyable" && p.price != null
    ? `${liteMoney(p.price)}${p.price_basis === "listed" ? "" : " (our estimate)"}`
    : p.state === "free_agent" ? "Free" : null;
  return (
    <li className="flex flex-wrap items-center gap-x-4 gap-y-3 rounded-[20px] bg-surface px-5 py-4 ring-1 ring-border">
      <Avatar name={p.name} photo={p.photo_url} />
      <div className="min-w-0 flex-1 basis-48">
        <Link to={`/players/market/${p.player_id}`} className="block truncate text-[1.25rem] font-extrabold text-text no-underline hover:text-accent">{p.name}</Link>
        {facts && <span className="block truncate text-base text-text-muted">{facts}</span>}
        {p.note && <span className="block text-base text-text-secondary">{p.note}</span>}
      </div>
      {price && <span className="text-[1.125rem] font-extrabold text-accent">{price}</span>}
      <div className="flex w-full flex-wrap gap-2 sm:w-auto [&>*]:flex-1">
        {p.state === "buyable" ? (
          <button
            type="button"
            onClick={() => {
              queryClient.invalidateQueries({ queryKey: ["lite", "home"] });
              navigate(`/lite/bid?player_id=${p.player_id}`);
            }}
            className={`${rowBtn} bg-accent text-white`}
          >
            Make an offer
          </button>
        ) : p.state === "offer_in" && p.offer_id ? (
          <Link to={`/lite/offers/${p.offer_id}`} className={plainBtn}>See your offer</Link>
        ) : p.state === "free_agent" ? (
          <Link to={`/players/market/${p.player_id}`} className={`${rowBtn} bg-accent text-white`}>See how to sign him</Link>
        ) : p.state === "outside" ? (
          <AskTeamButton
            subject={{ type: "player", id: p.player_id }}
            suffix=" about him"
            draft={`What do you think of ${p.name}?`}
            className={plainBtn}
          />
        ) : null}
        {p.state !== "yours" && <ShortlistButton p={p} />}
      </div>
    </li>
  );
}

function SearchResults({ q }: { q: string }) {
  const { data, isFetching, isError } = useLiteBuySearch(q);
  if (isError) return <p className="text-[1.25rem] text-danger-text">We couldn&rsquo;t search just now. Try again in a moment.</p>;
  if (!data) return <div className="flex justify-center py-6"><Spinner size="lg" /></div>;
  if (data.players.length === 0) {
    return (
      <p className="rounded-[20px] bg-surface px-6 py-5 text-[1.25rem] text-text ring-1 ring-border">
        No one called &ldquo;{data.q}&rdquo;. Check the spelling, or ask TransferX below.
      </p>
    );
  }
  return (
    <ul className={`flex flex-col gap-3 transition-opacity ${isFetching ? "opacity-60" : ""}`} aria-label="Players found">
      {data.players.map((p) => <PlayerRow key={p.player_id} p={p} />)}
    </ul>
  );
}

function Targets() {
  const { data, isLoading, isError } = useLiteBuyTargets();
  return (
    <section className="flex flex-col gap-4" aria-labelledby="targets-heading">
      <h2 id="targets-heading" className="text-[1.375rem] font-bold text-text">Your shortlist</h2>
      {isLoading ? (
        <div className="flex justify-center py-6"><Spinner size="lg" /></div>
      ) : isError ? (
        <p className="text-[1.25rem] text-danger-text">We couldn&rsquo;t load your shortlist. Try again in a moment.</p>
      ) : !data || data.players.length === 0 ? (
        <p className="rounded-[20px] bg-surface px-6 py-5 text-[1.25rem] text-text ring-1 ring-border">
          No one on it yet. Search for a player above and tap <strong>Shortlist</strong> to keep him here.
        </p>
      ) : (
        <>
          <ul className="flex flex-col gap-3" aria-label="Your shortlist">
            {data.players.map((p) => <PlayerRow key={p.player_id} p={p} />)}
          </ul>
          {data.total > data.players.length && (
            <Link to="/scouting/shortlists" className="text-[1.125rem] font-bold text-accent">
              See all {data.total} in Scouting →
            </Link>
          )}
        </>
      )}
    </section>
  );
}

export function LiteBuyPage() {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const typed = params.get("q") ?? "";
  const q = useDebounce(typed, 250);
  const searching = q.trim().length >= 2;
  return (
    <div className="flex flex-col gap-8">
      <div>
        <button
          type="button"
          onClick={() => navigate("/lite")}
          className="flex min-h-[3.25rem] items-center gap-2 rounded-xl px-4 text-[1.0625rem] font-semibold text-text ring-1 ring-border hover:ring-accent"
        >
          <Icon name="chevron-right" className="h-5 w-5 rotate-180" /> Back
        </button>
      </div>
      <div>
        <h1 className="text-[1.75rem] font-extrabold tracking-[-0.02em] text-text sm:text-[2.375rem]">Who are you looking for?</h1>
        <p className="mt-1 text-[1.25rem] text-text-secondary">Search by name, or pick from your shortlist.</p>
      </div>
      <div className="flex flex-col gap-4">
        <label className="flex min-h-[4.25rem] items-center gap-3 rounded-[18px] bg-surface px-5 ring-2 ring-border focus-within:ring-[3px] focus-within:ring-accent">
          <Icon name="search" className="h-6 w-6 shrink-0 text-text-muted" />
          <span className="sr-only">Search players by name</span>
          <input
            type="search"
            value={typed}
            // Kept in the URL (replacing, not stacking history), so Back from a bid returns to these results.
            onChange={(e) => setParams(e.target.value ? { q: e.target.value } : {}, { replace: true })}
            placeholder="Search by name"
            autoComplete="off"
            enterKeyHint="search"
            className="min-w-0 flex-1 bg-transparent text-[1.25rem] text-text outline-none placeholder:text-text-muted"
          />
        </label>
        {searching && <SearchResults q={q} />}
      </div>
      {!searching && <Targets />}
      <div className="flex flex-col gap-2 border-t border-rule pt-6 text-[1.125rem]">
        <span className="text-text-secondary">Not sure who you need?</span>
        <div className="flex flex-wrap gap-x-6 gap-y-2">
          <Link to="/lite/ask" className="font-bold text-accent">Ask TransferX →</Link>
          <Link to="/players/market" className="font-bold text-accent">Browse all players →</Link>
        </div>
      </div>
    </div>
  );
}

/** The old guided steps' addresses (a "Carry on where you left off" link may still point at one). */
export function LiteBuyRedirect() {
  return <Navigate to="/lite/buy" replace />;
}
