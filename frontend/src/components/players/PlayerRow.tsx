import { forwardRef } from "react";
import { Link } from "react-router-dom";
import type { FairValueSignal, NLPlayerSearchResult, Player } from "../../types/api";
import type { PlayerPosition } from "../../types/enums";
import { playerPrice, type PlayerPrice } from "../../lib/playerPrice";
import { formatCompactCurrency } from "../../lib/utils";
import AddToShortlistButton from "../scouting/AddToShortlistButton";
import FallbackImage from "../ui/FallbackImage";

export interface PlayerRowData {
  id: string;
  name: string;
  position: PlayerPosition | null;
  photoUrl?: string | null;
  club: string | null;
  age: number | null;
  nationality: string | null;
  listed: boolean;
  price: PlayerPrice;
  form: number | null;
  /** Why an AI search matched him, one phrase per filter. */
  why?: string[];
}

const POS_AVATAR: Record<PlayerPosition, string> = {
  GK: "bg-pos-gk-bg text-pos-gk-text",
  DEF: "bg-pos-def-bg text-pos-def-text",
  MID: "bg-pos-mid-bg text-pos-mid-text",
  FWD: "bg-pos-fwd-bg text-pos-fwd-text",
};

/** The same bands as FormBadge. */
function formText(score: number): string {
  if (score >= 75) return "text-success-text";
  if (score >= 55) return "text-success-text-alt";
  if (score >= 35) return "text-warning-text";
  return "text-danger-text";
}

export function rowFromPlayer(player: Player, signal?: FairValueSignal | null, form?: number | null): PlayerRowData {
  return {
    id: player.id,
    name: player.name,
    position: player.position ?? null,
    photoUrl: player.photo_url,
    club: player.current_club?.name ?? player.world_team?.name ?? player.team_name ?? null,
    age: player.age ?? null,
    nationality: player.nationality ?? null,
    listed: !!player.open_to_offers,
    price: playerPrice(player, signal),
    form: form ?? null,
  };
}

export function rowFromSearchResult(r: NLPlayerSearchResult): PlayerRowData {
  const basis = r.price_basis === "free agent" ? "free agent" : r.price_basis === "listed" ? "asking" : r.price != null ? "model" : null;
  return {
    id: r.player_id,
    name: r.name,
    position: (r.position as PlayerPosition | null) ?? null,
    club: r.current_club,
    age: r.age,
    nationality: r.nationality,
    listed: r.open_to_offers,
    price: {
      amount: r.price ?? null,
      basis,
      text: basis === "free agent" ? "Free" : r.price != null ? formatCompactCurrency(r.price) : "—",
    },
    form: r.form_score,
    why: r.why,
  };
}

/**
 * One player in the phone list (browse-players-focus §5.6): a 72px row whose
 * whole body links to the player, with the shortlist button beside the link.
 * Make offer and Compare live on the player page.
 */
const PlayerRow = forwardRef<HTMLAnchorElement, { row: PlayerRowData }>(function PlayerRow({ row }, ref) {
  const meta = [row.club ?? "Free agent", row.age != null ? String(row.age) : null, row.nationality].filter(Boolean).join(" · ");
  return (
    <li className="flex items-center border-t border-rule first:border-t-0">
      <Link
        ref={ref}
        to={`/players/market/${row.id}`}
        className="flex min-h-[72px] min-w-0 flex-1 items-center gap-3 py-2.5 pl-3.5 pr-1 no-underline hover:bg-surface-inset focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-accent"
      >
        <FallbackImage
          src={row.photoUrl}
          name={row.name}
          sizeClass="h-10 w-10 text-small"
          colorClass={row.position ? POS_AVATAR[row.position] : "bg-surface-inset text-text-muted"}
        />
        <span className="min-w-0 flex-1">
          <span className="flex min-w-0 items-center gap-1.5">
            <span className="truncate text-body font-semibold text-text">{row.name}</span>
            {row.position && (
              <span className={`shrink-0 rounded px-1.5 py-px text-caption font-bold ${POS_AVATAR[row.position]}`}>{row.position}</span>
            )}
          </span>
          <span className="flex min-w-0 items-center gap-1.5 text-small text-text-muted">
            <span className="truncate">{meta}</span>
            {row.listed && (
              <span className="shrink-0 rounded-full bg-success-bg px-1.5 text-caption font-semibold text-success-text">Listed</span>
            )}
          </span>
          {row.why && row.why.length > 0 && (
            <span className="block truncate text-caption text-text-muted">{row.why.join(" · ")}</span>
          )}
        </span>
        <span className="shrink-0 text-right">
          <span className="block text-body font-bold tabular-nums text-text">
            {row.price.text}
            {row.price.basis === "model" && <span className="ml-1 text-caption font-medium text-text-muted">model</span>}
          </span>
          {row.form != null && (
            <span className={`block text-caption font-semibold tabular-nums ${formText(row.form)}`}>Form {Math.round(row.form)}</span>
          )}
        </span>
      </Link>
      <div className="flex h-11 w-11 shrink-0 items-center justify-center">
        <AddToShortlistButton playerId={row.id} size="compact" />
      </div>
    </li>
  );
});

export default PlayerRow;
