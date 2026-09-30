import { Link, useNavigate } from "react-router-dom";

import Icon, { type IconName } from "../../components/layout/Icon";
import Spinner from "../../components/ui/Spinner";
import { useLiteHome, type LiteHome, type LiteTile } from "../../hooks/useLite";
import { liteMoney } from "../../lib/liteMoney";

function greeting(): string {
  const h = new Date().getHours();
  return h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
}

/** The line under the greeting (README "Screen 1" and "Screen 2"). */
function situation(home: LiteHome): string {
  const money = home.money ? `You have ${liteMoney(home.money.transfer_remaining)} left to spend` : null;
  const w = home.window;
  if (w.state === "open") {
    const days = w.days === 0 ? "the window closes today" : `${w.days} day${w.days === 1 ? "" : "s"} until the window closes`;
    return `What would you like to do? ${money ? `${money} and ${days}.` : `${days[0].toUpperCase()}${days.slice(1)}.`}`;
  }
  if (w.state === "closed") {
    if (!w.next_opens_at) return "The window is closed.";
    const when = new Date(w.next_opens_at).toLocaleDateString("en-GB", { day: "numeric", month: "long" });
    return `The window is closed. The next one opens on ${when}, in ${w.days} day${w.days === 1 ? "" : "s"}.`;
  }
  return `What would you like to do?${money ? ` ${money}.` : ""}`;
}

const TILE_ICON: Record<string, IconName> = {
  buy: "user-plus", sell: "tag", offers: "inbox", renew: "briefcase", plan: "list", squad: "users",
};

function Tile({ tile }: { tile: LiteTile }) {
  const navigate = useNavigate();
  const disabled = !!tile.disabled_reason;
  const quiet = tile.key === "offers" && !tile.badge;
  const look =
    tile.style === "accent" ? "bg-accent text-white ring-0"
    : tile.style === "ai" ? "bg-role-agent-text/10 text-text ring-2 ring-role-agent-text/30"
    : tile.style === "offers" && !quiet ? "bg-surface text-text ring-2 ring-danger-border"
    : "bg-surface text-text ring-1 ring-border";
  const sub = tile.style === "accent" ? "text-white/85" : "text-text-secondary";
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={() => navigate(tile.href)}
      className={`relative flex min-h-[7.5rem] flex-col justify-between rounded-3xl px-8 py-7 text-left transition-transform active:scale-[0.98] motion-reduce:transition-none disabled:cursor-not-allowed disabled:opacity-60 sm:min-h-[12rem] ${look}`}
    >
      <span className="flex items-start justify-between gap-3">
        {tile.style === "ai" ? (
          <span className="text-[2.25rem] leading-none text-role-agent-text">✦</span>
        ) : (
          <Icon name={TILE_ICON[tile.key] ?? "bolt"} className={`h-10 w-10 ${tile.style === "accent" ? "text-white" : quiet ? "text-text-muted" : "text-accent"}`} />
        )}
        {tile.badge && (
          <span className="rounded-full bg-danger px-3 py-1 text-[1.125rem] font-extrabold text-white">{tile.badge}</span>
        )}
      </span>
      <span className="mt-4 block">
        <span className={`block text-[1.5rem] font-extrabold leading-tight sm:text-[1.875rem] ${quiet ? "text-text-muted" : ""}`}>
          {tile.title}
        </span>
        <span className={`mt-1 block text-[1.125rem] ${sub}`}>{disabled ? tile.disabled_reason : tile.subtitle}</span>
      </span>
    </button>
  );
}

/** Lite home (README "Screen 1", "Screen 2", resume card from "3d"). */
export default function LiteHomePage() {
  const { data: home, isLoading, isError } = useLiteHome();

  if (isLoading) return <div className="flex justify-center py-20"><Spinner size="lg" /></div>;
  if (isError || !home) {
    return (
      <div className="space-y-4">
        <p className="text-[1.375rem] text-text">We couldn&rsquo;t load your home just now.</p>
        <Link to="/dashboard" className="text-[1.125rem] font-bold text-accent">Open the full app →</Link>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-8">
      <div>
        <h1 className="text-[2rem] font-extrabold leading-tight tracking-[-0.025em] text-text sm:text-[2.5rem]">
          {greeting()}, {home.club_name}.
        </h1>
        <p className="mt-2 text-[1.25rem] text-text-secondary sm:text-[1.375rem]">{situation(home)}</p>
        {home.briefing_headline && (
          <p className="mt-2 text-[1.125rem] text-text-muted">
            <span className="text-role-agent-text">✦</span> {home.briefing_headline}
          </p>
        )}
      </div>

      {home.resume && (
        <div className="flex flex-wrap items-center gap-4 rounded-[18px] bg-surface px-5 py-4 ring-2 ring-accent/25">
          <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-accent-bg text-accent">
            <Icon name="chevrons-right" className="h-6 w-6" />
          </span>
          <span className="min-w-0 flex-1">
            <span className="block text-[0.9375rem] font-semibold text-accent">Carry on where you left off</span>
            <span className="block truncate text-[1.25rem] font-bold text-text">{home.resume.title}</span>
          </span>
          <Link
            to={home.resume.href}
            className="flex min-h-[3.375rem] items-center rounded-xl bg-accent px-6 text-[1.0625rem] font-bold text-white no-underline"
          >
            Continue
          </Link>
        </div>
      )}

      <div className="grid gap-5 sm:grid-cols-2">
        {home.tiles.map((t) => <Tile key={t.key} tile={t} />)}
      </div>

      <p className="text-[1rem] text-text-muted">
        Need something else? <Link to="/dashboard" className="font-semibold text-accent">Open the full app</Link>
      </p>
    </div>
  );
}
