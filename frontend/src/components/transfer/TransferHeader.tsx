import type { ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import PlayerLink from "../ui/PlayerLink";

const POS_CLASS: Record<string, string> = {
  GK: "bg-pos-gk-bg text-pos-gk-text",
  DEF: "bg-pos-def-bg text-pos-def-text",
  MID: "bg-pos-mid-bg text-pos-mid-text",
  FWD: "bg-pos-fwd-bg text-pos-fwd-text",
};

function initials(name: string): string {
  const parts = name.trim().split(/\s+/);
  return ((parts[0]?.[0] ?? "") + (parts.length > 1 ? parts[parts.length - 1][0] : "")).toUpperCase();
}

/**
 * Who a transfer is for, shared by the deal room and the offer page
 * (deal-room-focus §5.1, offer-room-focus §5.1): the player as the page's
 * only h1, the route between the clubs, and the amount. No status: the
 * status card says it. `routeFrom` / `routeTo` are nodes so a masked buyer
 * can be plain text.
 */
export default function TransferHeader({ player, routeFrom, routeTo, amount, facts, lgSubExtra, moreMenu }: {
  player: { id: string; name: string | null; position: string | null; photoUrl: string | null };
  routeFrom: ReactNode;
  routeTo: ReactNode;
  amount: ReactNode;
  facts: ReactNode;
  lgSubExtra?: ReactNode;
  moreMenu: ReactNode;
}) {
  const navigate = useNavigate();
  const { name, position: pos } = player;

  return (
    <header>
      <div className="flex items-center justify-between">
        <button
          type="button"
          onClick={() => navigate(-1)}
          className="-ml-2.5 inline-flex min-h-11 items-center px-2.5 text-[15px] font-medium text-text-secondary hover:text-text"
        >
          ← Back
        </button>
        <div className="lg:hidden">{moreMenu}</div>
      </div>

      <div className="mt-1 flex items-center gap-3.5 lg:gap-4">
        {player.photoUrl ? (
          <img src={player.photoUrl} alt="" aria-hidden className="h-[52px] w-[52px] shrink-0 rounded-full bg-surface-inset object-cover object-top" />
        ) : (
          <span
            aria-hidden
            className={`flex h-[52px] w-[52px] shrink-0 items-center justify-center rounded-full text-lg font-bold ${
              (pos && POS_CLASS[pos]) || "bg-accent-avatar text-accent-active"
            }`}
          >
            {name ? initials(name) : "?"}
          </span>
        )}
        <div className="min-w-0 flex-1">
          <h1 className="text-[22px] font-bold leading-tight tracking-[-0.01em] text-text lg:text-2xl">
            <PlayerLink id={player.id} name={name} fallback="Unknown player" />
          </h1>
          <p className="mt-0.5 text-[15px] text-text-secondary">
            {pos && <>{pos} · </>}
            {routeFrom}
            {" → "}
            {routeTo}
            {lgSubExtra && <span className="hidden lg:inline"> · {lgSubExtra}</span>}
          </p>
        </div>
        <div className="hidden shrink-0 text-right sm:block">
          <p className="text-[22px] font-bold text-text lg:text-2xl">{amount}</p>
          <p className="text-sm text-text-muted">{facts}</p>
        </div>
        <div className="hidden lg:block">{moreMenu}</div>
      </div>

      <p className="mt-2.5 text-[15px] text-text-secondary sm:hidden">
        <span className="text-[17px] font-bold text-text">{amount}</span>
        {" · "}{facts}
      </p>
    </header>
  );
}
