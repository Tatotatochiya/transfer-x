import type { Offer } from "../../types/api";
import type { LiteOfferCard } from "../../hooks/useLite";
import { lastChange, offerRounds, type OfferRound } from "../../lib/offerChanges";
import { isLoan } from "../../lib/offerTerms";
import { formatCurrency, formatDate } from "../../lib/utils";
import { cap } from "./offerStatus";

interface Marker {
  key: string;
  label: string;
  value: number;
  dot: string;
  text: string;
}

/**
 * The markers on the price track (§5.8): their first and latest fee, the
 * seller's own valuation (seller only: it is confidential), and my latest.
 * In ink only, theirs hollow and mine filled: the labels say who's who.
 * A marker that repeats another's amount is dropped, keeping the later one.
 */
export function standingMarkers(rounds: OfferRound[], side: "buyer" | "seller", valuation: number | null): Marker[] {
  const theirs = rounds.filter((r) => r.side === "them" && r.fee != null);
  const mine = rounds.filter((r) => r.side === "me" && r.fee != null);
  const list: Marker[] = [];
  if (theirs.length) {
    list.push({ key: "first", label: "Their first", value: theirs[0].fee!, dot: "bg-surface ring-2 ring-text-muted", text: "text-text-secondary" });
    list.push({ key: "theirs", label: "Their offer", value: theirs[theirs.length - 1].fee!, dot: "bg-surface ring-2 ring-text-secondary", text: "text-text-secondary" });
  }
  if (side === "seller" && valuation != null) {
    list.push({ key: "valuation", label: "Your valuation", value: valuation, dot: "bg-text-secondary", text: "text-text" });
  }
  if (mine.length) {
    list.push({ key: "mine", label: side === "seller" ? "Your ask" : "Your offer", value: mine[mine.length - 1].fee!, dot: "bg-text", text: "text-text" });
  }
  return list.filter((m, i) => !list.slice(i + 1).some((later) => later.value === m.value));
}

function Track({ markers }: { markers: Marker[] }) {
  const values = markers.map((m) => m.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const pos = (v: number) => ((v - min) / (max - min)) * 100;
  const sorted = [...markers].sort((a, b) => a.value - b.value);
  const theirs = markers.find((m) => m.key === "theirs");
  const near = markers.find((m) => m.key === "valuation") ?? markers.find((m) => m.key === "mine");
  const gap = theirs && near ? Math.abs(near.value - theirs.value) : null;
  const label = [...markers.map((m) => `${m.label} ${formatCurrency(m.value)}.`), gap != null ? `Gap ${formatCurrency(gap)}.` : ""].join(" ").trim();

  return (
    <div role="img" aria-label={label} className="relative mx-2 h-[84px]">
      <div className="absolute inset-x-0 top-[39px] h-1.5 rounded-full bg-border-quiet" />
      {theirs && near && (
        <div
          className="absolute top-[39px] h-1.5 bg-border"
          style={{ left: `${Math.min(pos(theirs.value), pos(near.value))}%`, width: `${Math.abs(pos(near.value) - pos(theirs.value))}%` }}
        />
      )}
      {sorted.map((m, i) => {
        const p = pos(m.value);
        const above = i > 0 && p - pos(sorted[i - 1].value) < 18;
        // The smallest sits at 0% and the largest at 100%: align those to the edges.
        const end = i === 0 ? "left" : i === sorted.length - 1 ? "right" : null;
        const align = end === "left" ? "text-left" : end === "right" ? "text-right" : "-translate-x-1/2 text-center";
        return (
          <div key={m.key} aria-hidden>
            <span className={`absolute top-[36px] h-3 w-3 -translate-x-1/2 rounded-full ${m.dot}`} style={{ left: `${p}%` }} />
            <span
              className={`absolute whitespace-nowrap ${align} ${above ? "top-0" : "top-[52px]"}`}
              style={end ? { [end]: 0 } : { left: `${p}%` }}
            >
              <span className={`block text-caption font-bold leading-tight ${m.text}`}>{formatCurrency(m.value)}</span>
              <span className="block text-small leading-tight text-text-muted">{m.label}</span>
            </span>
          </div>
        );
      })}
    </div>
  );
}

const VERB: Record<OfferRound["kind"], string> = { SENT: "offered", COUNTERED: "countered", IMPROVED: "raised" };

export function RoundsList({ offer, rounds, other }: { offer: Offer; rounds: OfferRound[]; other: string }) {
  const change = lastChange(offer);
  const summary = change?.changes.map((c) => `${c.label} ${c.was} → ${c.now}`).join(" · ");
  const who = (r: OfferRound) => r.side === "me" ? "You" : r.side === "them" ? cap(other)
    : r.side === "buyer" ? "The buying club" : "The selling club";
  return (
    <ol className="divide-y divide-rule">
      {[...rounds].reverse().map((r, i) => (
        <li key={`${r.at}-${i}`} className="flex items-start justify-between gap-3 py-2.5">
          <div className="min-w-0">
            <p className="text-body font-semibold text-text">{who(r)} {VERB[r.kind]}</p>
            <p className="text-small text-text-muted">{formatDate(r.at)}</p>
            {i === 0 && r.kind !== "SENT" && summary && <p className="mt-0.5 text-body text-text-secondary">{summary}</p>}
          </div>
          {r.fee != null && !isLoan(offer) && <p className="shrink-0 text-body font-bold text-text">{formatCurrency(r.fee)}</p>}
        </li>
      ))}
    </ol>
  );
}

/**
 * "Where it stands" (offer-room-focus §5.8): how far apart the clubs are,
 * and every round, once there is more than one. Below 1024px the rounds are a disclosure; from 1024px
 * "all rounds" opens the Offer history tab.
 */
export default function OfferStanding({ offer, myClubId, side, other, card, desktop, roundsOpen, onToggleRounds, onShowHistory }: {
  offer: Offer;
  myClubId: string | undefined;
  side: "buyer" | "seller" | null;
  other: string;
  card?: LiteOfferCard;
  desktop: boolean;
  roundsOpen: boolean;
  onToggleRounds: () => void;
  onShowHistory: () => void;
}) {
  const rounds = offerRounds(offer, myClubId);
  // One round is just the offer, which the status card already states.
  if (rounds.length < 2) return null;
  const markers = side && !isLoan(offer)
    ? standingMarkers(rounds, side, side === "seller" ? card?.your_valuation ?? null : null)
    : [];
  const track = markers.length >= 2 && new Set(markers.map((m) => m.value)).size >= 2 ? <Track markers={markers} /> : null;
  const n = rounds.length;

  if (desktop) {
    return (
      <section aria-label="Where it stands" className="flex items-center gap-6 rounded-xl bg-surface px-4 py-3.5 ring-1 ring-border">
        <div className="w-[150px] shrink-0">
          <p className="text-body font-semibold text-text">Where it stands</p>
          <p className="text-small text-text-muted">
            Round {n} ·{" "}
            <button type="button" onClick={onShowHistory} className="font-semibold text-accent hover:underline">all rounds</button>
          </p>
        </div>
        <div className="min-w-0 flex-1">{track}</div>
      </section>
    );
  }

  return (
    <section aria-label="Where it stands" className="rounded-xl bg-surface px-4 py-3.5 ring-1 ring-border">
      <div className="flex items-baseline justify-between">
        <p className="text-body font-semibold text-text">Where it stands</p>
        <p className="text-small text-text-muted">Round {n}</p>
      </div>
      {track && <div className="mt-1">{track}</div>}
      <button
        type="button"
        aria-expanded={roundsOpen}
        aria-controls="offer-rounds"
        onClick={onToggleRounds}
        className="min-h-11 text-body font-semibold text-accent"
      >
        {roundsOpen ? "Hide rounds" : `Show all ${n} round${n === 1 ? "" : "s"}`}
      </button>
      {roundsOpen && <div id="offer-rounds"><RoundsList offer={offer} rounds={rounds} other={other} /></div>}
    </section>
  );
}
