import type { ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import PlayerLink from "../ui/PlayerLink";
import FallbackImage from "../ui/FallbackImage";

const POS_CLASS: Record<string, string> = {
  GK: "bg-pos-gk-bg text-pos-gk-text",
  DEF: "bg-pos-def-bg text-pos-def-text",
  MID: "bg-pos-mid-bg text-pos-mid-text",
  FWD: "bg-pos-fwd-bg text-pos-fwd-text",
};

/**
 * Who a transfer is for, shared by the deal room and the offer page
 * (deal-room-focus §5.1, offer-room-focus §5.1): the player as the page's
 * only h1, the route between the clubs, and the amount. No status: the
 * status card says it. `routeFrom` / `routeTo` are nodes so a masked buyer
 * can be plain text.
 *
 * The player page (player-actions D4) passes `sub` in place of the route,
 * no amount, and `actions` for its buttons from 1024px; `moreMenu` is then
 * the back row's controls below 1024px only.
 */
export default function TransferHeader({ player, routeFrom, routeTo, sub, amount, facts, lgSubExtra, moreMenu, actions, linkName = true }: {
  player: { id: string; name: string | null; position: string | null; photoUrl: string | null };
  routeFrom?: ReactNode;
  routeTo?: ReactNode;
  /** Used instead of the route line when given. */
  sub?: ReactNode;
  amount?: ReactNode;
  facts?: ReactNode;
  lgSubExtra?: ReactNode;
  moreMenu: ReactNode;
  /** From 1024px, beside the name, in place of `moreMenu`. */
  actions?: ReactNode;
  /** The name links to his profile; not on the profile itself. */
  linkName?: boolean;
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
        <FallbackImage
          src={player.photoUrl}
          name={name ?? "?"}
          sizeClass="h-[52px] w-[52px] text-lg"
          colorClass={(pos && POS_CLASS[pos]) || "bg-accent-avatar text-accent-active"}
        />
        <div className="min-w-0 flex-1">
          <h1 className={`text-[22px] font-bold leading-tight tracking-[-0.01em] text-text lg:text-2xl ${actions ? "lg:truncate" : ""}`}>
            {linkName ? <PlayerLink id={player.id} name={name} fallback="Unknown player" /> : (name ?? "Unknown player")}
          </h1>
          {sub ?? (
            <p className="mt-0.5 text-[15px] text-text-secondary">
              {pos && <>{pos} · </>}
              {routeFrom}
              {" → "}
              {routeTo}
              {lgSubExtra && <span className="hidden lg:inline"> · {lgSubExtra}</span>}
            </p>
          )}
        </div>
        {amount != null && (
          <div className="hidden shrink-0 text-right sm:block">
            <p className="text-[22px] font-bold text-text lg:text-2xl">{amount}</p>
            <p className="text-sm text-text-muted">{facts}</p>
          </div>
        )}
        {actions
          ? <div className="hidden shrink-0 self-start lg:flex lg:items-center lg:gap-2">{actions}</div>
          : <div className="hidden lg:block">{moreMenu}</div>}
      </div>

      {amount != null && (
        <p className="mt-2.5 text-[15px] text-text-secondary sm:hidden">
          <span className="text-[17px] font-bold text-text">{amount}</span>
          {" · "}{facts}
        </p>
      )}
    </header>
  );
}
