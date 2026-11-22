import type { CSSProperties } from "react";
import { Link } from "react-router-dom";

import FallbackImage from "../ui/FallbackImage";
import { INK, bandColours, stripeColour } from "../../lib/brandColour";
import { seasonLabel } from "../../lib/season";
import { useThemeName } from "../../context/ThemeContext";

export interface BandClub {
  name: string;
  crest_url: string | null;
  league_name: string | null;
  city: string | null;
  brand_primary?: string | null;
  brand_secondary?: string | null;
}

/** "Good afternoon" by the viewer's clock. */
export function greeting(now: Date = new Date()): string {
  const h = now.getHours();
  return h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
}

/**
 * The Dashboard's first block: the club's crest, name, league and season, in
 * its own colours (feature_spec/club-dashboard §4.1). Club colour lives here
 * and on the sidebar's crest ring only; everything interactive keeps
 * TransferX's colours. With no colours set it's a plain card.
 *
 * `preview` renders the phone layout at any width (My Club's colour preview).
 */
export default function ClubBand({ club, firstName, waitingCount = 0, windowText, canAddColours = false, preview = false }: {
  club: BandClub;
  /** The greeting's name, from 640px; no name, no greeting. */
  firstName?: string | null;
  waitingCount?: number;
  /** "Window: no deadline set", "Summer window · 12 days left", "Window closed". */
  windowText?: string | null;
  /** A club admin, with no colours set: offer to add them. */
  canAddColours?: boolean;
  preview?: boolean;
}) {
  const theme = useThemeName();
  const primary = club.brand_primary ?? null;
  const band = primary ? bandColours(primary, theme) : null;
  const wide = (cls: string) => (preview ? "" : cls);

  const style = band
    ? ({ "--band-bg": band.bg, "--band-text": band.text, backgroundColor: band.bg, color: band.text } as CSSProperties)
    : undefined;
  // The text colour at a share, for the disc ring, the pills and the greeting.
  const tint = (share: number) =>
    band ? `color-mix(in srgb, ${band.text} ${share}%, transparent)` : undefined;
  const Heading = preview ? "p" : "h1";
  const second = [club.league_name, seasonLabel()].filter(Boolean);
  const third = [...second, club.city].filter(Boolean);

  return (
    <header
      data-testid="club-band"
      style={style}
      className={`relative overflow-hidden rounded-2xl ${band ? "" : "bg-surface text-text ring-1 ring-border"} ${
        preview ? "px-4 pt-4 pb-5" : "px-4 pt-4 pb-5 sm:px-5 sm:pt-5 sm:pb-6 xl:px-7 xl:pt-6 xl:pb-8"}`}
    >
      {band && club.crest_url && !preview && (
        <img src={club.crest_url} alt="" aria-hidden="true"
          className="pointer-events-none absolute -right-6 -top-8 hidden h-48 w-48 object-contain opacity-10 grayscale brightness-[3] xl:block" />
      )}
      <div className="relative flex items-center gap-3.5 sm:gap-4">
        <span
          className={`grid shrink-0 place-items-center rounded-full ${band ? "bg-white" : "bg-surface-inset"} ${
            preview ? "h-[52px] w-[52px]" : "h-[52px] w-[52px] sm:h-[60px] sm:w-[60px] xl:h-[76px] xl:w-[76px]"}`}
          // The disc is always white, so its initials are always ink (the
          // --ink token turns light in dark mode).
          style={band ? { boxShadow: `0 0 0 3px ${tint(35)}`, color: INK } : undefined}
        >
          <FallbackImage src={club.crest_url} name={club.name} kind="club"
            sizeClass={preview ? "h-9 w-9 text-small" : "h-9 w-9 text-small sm:h-11 sm:w-11 xl:h-14 xl:w-14 xl:text-body"}
            colorClass={band ? "bg-transparent" : "text-text-muted"} loading="eager" />
        </span>
        <div className="min-w-0 flex-1">
          {firstName && (
            <p className={`hidden font-semibold ${wide("sm:block")} text-small xl:text-body`}
              style={band ? { color: tint(90) } : undefined}>
              {greeting()}, {firstName}
            </p>
          )}
          {/* The page's h1; the preview sits inside My Club, which has its own. */}
          <Heading className={`truncate font-bold tracking-[-0.01em] text-title-sm ${wide("sm:text-title")}`}>{club.name}</Heading>
          <p className={`truncate text-small ${band ? "" : "text-text-secondary"}`}
            style={band ? { color: tint(90) } : undefined}>
            <span className={wide("xl:hidden")}>{second.join(" · ")}</span>
            {!preview && <span className="hidden xl:inline">{third.join(" · ")}</span>}
          </p>
        </div>
        {!preview && (
          <div className="hidden shrink-0 flex-col items-end gap-2 sm:flex">
            {waitingCount > 0 && (
              <a href="#needs-you"
                className={`inline-flex h-[30px] items-center gap-1.5 rounded-full px-3 text-small font-semibold ${band ? "" : "bg-danger-bg text-danger-text"}`}
                style={band ? { backgroundColor: tint(16) } : undefined}>
                <span aria-hidden="true" className={`h-1.5 w-1.5 rounded-full ${band ? "" : "bg-danger"}`}
                  style={band ? { backgroundColor: band.text } : undefined} />
                {waitingCount} waiting on you
              </a>
            )}
            {windowText && (
              <span className="hidden h-[30px] items-center rounded-full px-3 text-small font-semibold xl:inline-flex"
                style={band ? { boxShadow: `inset 0 0 0 1px ${tint(45)}` } : { boxShadow: "inset 0 0 0 1px var(--color-border)" }}>
                {windowText}
              </span>
            )}
          </div>
        )}
        {!preview && !band && canAddColours && (
          <Link to="/club#club-colours" className="shrink-0 self-start text-small font-semibold text-accent hover:underline sm:self-center">
            Add club colours
          </Link>
        )}
      </div>
      {band && (
        <span aria-hidden="true" className="absolute inset-x-0 bottom-0 h-1.5"
          style={{ backgroundColor: stripeColour(club.brand_secondary, band) }} />
      )}
    </header>
  );
}
