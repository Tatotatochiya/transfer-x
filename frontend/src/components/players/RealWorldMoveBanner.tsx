import type { RealWorldMove } from "../../types/api";
import { describeMove } from "../../lib/realWorld";

/**
 * API-Football has the player at another club than the one TransferX has him
 * registered to (a real-world move TransferX doesn't have yet). Says so, and
 * changes nothing: a registration changes only through a deal or a staff
 * correction.
 */
export default function RealWorldMoveBanner({ move, isMyPlayer }: { move: RealWorldMove; isMyPlayer: boolean }) {
  return (
    <div role="note" className="mb-3 flex items-start gap-3 rounded-[14px] bg-warning-fill/10 px-4 py-3 ring-1 ring-warning-fill/30">
      {move.real_club_logo ? (
        <img src={move.real_club_logo} alt="" className="mt-0.5 h-8 w-8 shrink-0 object-contain" />
      ) : (
        <span aria-hidden className="mt-0.5 text-lg">⇄</span>
      )}
      <div className="min-w-0 text-sm">
        <p className="font-semibold text-text">Moved in real life: {describeMove(move)}</p>
        <p className="mt-0.5 text-text-secondary">
          On TransferX he&rsquo;s still registered to {move.registered_club ?? "his old club"}. Source: API-Football.
          {isMyPlayer && " If this is right, TransferX staff can update his registration."}
        </p>
      </div>
    </div>
  );
}
