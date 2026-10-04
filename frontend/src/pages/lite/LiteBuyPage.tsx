import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router-dom";

import Icon from "../../components/layout/Icon";
import Spinner from "../../components/ui/Spinner";
import api from "../../lib/api";
import { liteMoney, liteWage } from "../../lib/liteMoney";
import {
  useLiteCandidates,
  useLiteHome,
  useLiteSquadCounts,
  type LiteBand,
  type LiteCandidate,
  type LitePosition,
} from "../../hooks/useLite";
import AskTeamButton from "../../components/lite/AskTeamButton";

/**
 * Buy a player, guided (docs/feature_spec/lite-mode README "Screen 3").
 * One question per screen: position, then budget, then three players picked
 * by TransferX (decision 3). The answers live in the URL, so Back and
 * "Carry on where you left off" both work.
 */

const POSITIONS: { key: LitePosition; label: string; plural: string }[] = [
  { key: "GK", label: "Goalkeeper", plural: "goalkeepers" },
  { key: "DEF", label: "Defender", plural: "defenders" },
  { key: "MID", label: "Midfielder", plural: "midfielders" },
  { key: "FWD", label: "Forward", plural: "forwards" },
  { key: "ANY", label: "Not sure", plural: "players" },
];

const BANDS: { key: LiteBand; label: string; floor: number }[] = [
  { key: "0-5", label: "Up to £5m", floor: 0 },
  { key: "5-10", label: "£5m to £10m", floor: 5_000_000 },
  { key: "10-20", label: "£10m to £20m", floor: 10_000_000 },
  { key: "free", label: "Free or loan", floor: 0 },
];

const isPosition = (v: string | null): v is LitePosition => POSITIONS.some((p) => p.key === v);
const isBand = (v: string | null): v is LiteBand => BANDS.some((b) => b.key === v);

function StepHeader({ step, back }: { step: string; back: () => void }) {
  return (
    <div className="flex items-center justify-between">
      <button
        type="button"
        onClick={back}
        className="flex min-h-[3.25rem] items-center gap-2 rounded-xl px-4 text-[1.0625rem] font-semibold text-text ring-1 ring-border hover:ring-accent"
      >
        <Icon name="chevron-right" className="h-5 w-5 rotate-180" /> Back
      </button>
      <span className="text-base font-semibold text-text-muted">{step}</span>
    </div>
  );
}

function Question({ title, hint }: { title: string; hint: string }) {
  return (
    <div>
      <h1 className="text-[1.75rem] font-extrabold tracking-[-0.02em] text-text sm:text-[2.375rem]">{title}</h1>
      <p className="mt-1 text-[1.25rem] text-text-secondary">{hint}</p>
    </div>
  );
}

function Choice({ label, sub, onClick }: { label: string; sub?: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex min-h-[7.5rem] flex-col items-start justify-center rounded-[20px] bg-surface px-6 text-left ring-2 ring-border transition-transform hover:ring-[3px] hover:ring-accent focus:outline-none focus-visible:ring-[3px] focus-visible:ring-accent active:scale-[0.98]"
    >
      <span className="text-[1.375rem] font-bold text-text">{label}</span>
      {sub && <span className="mt-0.5 text-[0.9375rem] text-text-muted">{sub}</span>}
    </button>
  );
}

// ── Step 1: position ─────────────────────────────────────────────────────────

export function LiteBuyPositionPage() {
  const navigate = useNavigate();
  const { data } = useLiteSquadCounts();
  const counts = data?.counts;
  return (
    <div className="flex flex-col gap-8">
      <StepHeader step="Step 1 of 2" back={() => navigate("/lite")} />
      <Question title="What position do you need?" hint="Tap one. You can change it later." />
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-3">
        {POSITIONS.map((p) => {
          const n = p.key !== "ANY" && counts ? counts[p.key] ?? 0 : null;
          const sub = p.key === "ANY" ? "We'll look where your squad is thinnest" : n == null ? undefined : n === 0 ? "You have none" : `You have ${n}`;
          return <Choice key={p.key} label={p.label} sub={sub} onClick={() => navigate(`/lite/buy/budget?position=${p.key}`)} />;
        })}
      </div>
    </div>
  );
}

// ── Step 2: budget ───────────────────────────────────────────────────────────

export function LiteBuyBudgetPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const position = params.get("position");
  const { data: home } = useLiteHome();
  if (!isPosition(position)) return <MissingStep />;
  const left = home?.money?.transfer_remaining;
  // Hide a band that is entirely above what's left to spend.
  const bands = BANDS.filter((b) => left == null || b.floor <= left);
  return (
    <div className="flex flex-col gap-8">
      <StepHeader step="Step 2 of 2" back={() => navigate("/lite/buy")} />
      <Question
        title="How much can you spend on the fee?"
        hint={left != null ? `You have ${liteMoney(left)} left this window.` : "Pick a range."}
      />
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {bands.map((b) => (
          <Choice key={b.key} label={b.label} onClick={() => navigate(`/lite/buy/results?position=${position}&budget=${b.key}`)} />
        ))}
      </div>
    </div>
  );
}

// ── Results ──────────────────────────────────────────────────────────────────

function initials(name: string) {
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]?.toUpperCase()).join("");
}

function Row({ label, value, strong }: { label: string; value: string; strong?: boolean }) {
  return (
    <div className="flex items-baseline justify-between gap-3 border-t border-rule py-2 text-[1.0625rem]">
      <span className="text-text-muted">{label}</span>
      <span className={strong ? "font-extrabold text-accent" : "font-semibold text-text"}>{value}</span>
    </div>
  );
}

function CandidateCard({ p }: { p: LiteCandidate }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const priceLabel = p.free_agent ? "Free agent" : `${liteMoney(p.price)}${p.price_basis === "listed" ? "" : " (our estimate)"}`;
  return (
    <div className="flex flex-col gap-4 rounded-3xl bg-surface p-6 ring-1 ring-border">
      <div className="flex items-center gap-3">
        {p.photo_url ? (
          <img src={p.photo_url} alt="" className="h-14 w-14 shrink-0 rounded-full bg-surface-inset object-cover object-top" />
        ) : (
          <span className="flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-accent-bg text-[1.25rem] font-extrabold text-accent">
            {initials(p.name)}
          </span>
        )}
        <span className="min-w-0">
          <Link to={`/players/market/${p.player_id}`} className="block truncate text-[1.375rem] font-extrabold text-text no-underline hover:text-accent">{p.name}</Link>
          <span className="block truncate text-base text-text-muted">{p.club ?? "No club"}</span>
        </span>
      </div>
      <div>
        {p.age != null && <Row label="Age" value={String(p.age)} />}
        <Row label="Price" value={priceLabel} strong />
        <Row label="Wages" value={p.wage_weekly != null ? liteWage(p.wage_weekly) : "—"} />
      </div>
      <p className="rounded-xl bg-surface-inset px-4 py-3 text-base text-text-secondary">{p.reason}</p>
      <div className="mt-auto flex flex-col gap-2">
        {p.free_agent ? (
          // No club to make an offer to: a free agent is signed from his page.
          <Link
            to={`/players/market/${p.player_id}`}
            className="flex min-h-[3.5rem] items-center justify-center rounded-xl bg-accent text-[1.0625rem] font-bold text-white no-underline"
          >
            See how to sign him
          </Link>
        ) : (
          <button
            type="button"
            onClick={() => {
              queryClient.invalidateQueries({ queryKey: ["lite", "home"] });
              navigate(`/lite/bid?player_id=${p.player_id}`);
            }}
            className="min-h-[3.5rem] rounded-xl bg-accent text-[1.0625rem] font-bold text-white"
          >
            Make an offer
          </button>
        )}
        <Link
          to={`/players/market/${p.player_id}`}
          className="flex min-h-[3rem] items-center justify-center rounded-xl text-[1.0625rem] font-semibold text-text no-underline ring-1 ring-border hover:ring-accent"
        >
          See his profile
        </Link>
        <AskTeamButton
          subject={{ type: "player", id: p.player_id }}
          suffix=" about him"
          draft={`What do you think of ${p.name}?`}
          className="min-h-[3rem] rounded-xl text-[1.0625rem] font-semibold text-text ring-1 ring-border hover:ring-accent"
        />
      </div>
    </div>
  );
}

export function LiteBuyResultsPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const queryClient = useQueryClient();
  const [params] = useSearchParams();
  const position = params.get("position");
  const band = params.get("budget");
  const valid = isPosition(position) && isBand(band);
  const { data, isLoading, isError } = useLiteCandidates(valid ? position : null, valid ? band : null);
  const players = data?.players ?? [];
  const pos = POSITIONS.find((p) => p.key === position);
  const bandLabel = BANDS.find((b) => b.key === band)?.label ?? "";

  // "Carry on where you left off" (README 3d): remember this search.
  useEffect(() => {
    if (!valid || !data) return;
    const title = `${pos?.label === "Not sure" ? "Player" : pos?.label} search, ${bandLabel.toLowerCase()} · ${players.length} player${players.length === 1 ? "" : "s"} found`;
    api
      .put("/lite/resume", { title, href: `${location.pathname}${location.search}` })
      .then(() => queryClient.invalidateQueries({ queryKey: ["lite", "home"] }))
      .catch(() => undefined);
  }, [valid, data, pos, bandLabel, players.length, location.pathname, location.search, queryClient]);

  if (!valid) return <MissingStep />;
  const plural = pos?.plural ?? "players";
  return (
    <div className="flex flex-col gap-8">
      <StepHeader step="Results" back={() => navigate(`/lite/buy/budget?position=${position}`)} />
      <Question
        title={players.length ? `${players.length} player${players.length === 1 ? "" : "s"} who fit` : "Looking…"}
        hint={`${plural[0].toUpperCase()}${plural.slice(1)} you could make an offer for now, ${bandLabel.toLowerCase()}.`}
      />
      {isLoading ? (
        <div className="flex justify-center py-12"><Spinner size="lg" /></div>
      ) : isError ? (
        <p className="text-[1.25rem] text-danger-text">We couldn&rsquo;t search just now. Try again in a moment.</p>
      ) : players.length === 0 ? (
        <div className="flex flex-col items-start gap-4 rounded-3xl bg-surface px-8 py-8 ring-1 ring-border">
          <p className="text-[1.375rem] text-text">No {plural} in that price range right now.</p>
          <button
            type="button"
            onClick={() => navigate(`/lite/buy/budget?position=${position}`)}
            className="min-h-[3.25rem] rounded-xl bg-accent px-6 text-[1.0625rem] font-bold text-white"
          >
            Try a different budget
          </button>
        </div>
      ) : (
        <div className="grid gap-5 lg:grid-cols-3">
          {players.map((p) => <CandidateCard key={p.player_id} p={p} />)}
        </div>
      )}
    </div>
  );
}

function MissingStep() {
  return (
    <div className="space-y-4">
      <p className="text-[1.375rem] text-text">Let&rsquo;s start from the first question.</p>
      <Link to="/lite/buy" className="text-[1.125rem] font-bold text-accent">What position do you need? →</Link>
    </div>
  );
}
