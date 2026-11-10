import { useEffect } from "react";
import { useMediaQuery } from "../../hooks/useMediaQuery";
import type { SituationAction } from "../../lib/playerSituation";
import { ActionButton, type ActionHandlers } from "./PlayerActions";

/** The bar's height above the safe area; the page pads by it and CompareBar sits on it. */
export const ACTION_BAR_HEIGHT = 74;

/**
 * Below 1024px the player page's actions are pinned to the bottom of the
 * screen, above the iOS home indicator (player-actions D6): the secondary
 * on the left, the primary on the right and wider. Nothing without actions.
 */
export default function PlayerActionBar({ name, primary, secondary, handlers }: {
  name: string;
  primary?: SituationAction;
  secondary?: SituationAction;
  handlers: ActionHandlers;
}) {
  const isDesktop = useMediaQuery("(min-width: 1024px)");
  const shown = !isDesktop && !!(primary || secondary);

  // Lift CompareBar (fixed to the bottom, from App) above this bar.
  useEffect(() => {
    if (!shown) return;
    const root = document.documentElement;
    root.style.setProperty("--action-bar-h", `calc(${ACTION_BAR_HEIGHT}px + env(safe-area-inset-bottom))`);
    return () => { root.style.removeProperty("--action-bar-h"); };
  }, [shown]);

  if (!shown) return null;
  const two = !!(primary && secondary);
  return (
    <div
      role="region"
      aria-label={`Actions for ${name}`}
      className="fixed inset-x-0 bottom-0 z-30 border-t border-border bg-surface px-4 pb-[max(14px,env(safe-area-inset-bottom))] pt-2.5 shadow-[0_-4px_12px_rgba(16,24,40,0.06)] lg:hidden"
    >
      <div className={`grid gap-2 ${two ? "grid-cols-[1fr_1.3fr]" : "grid-cols-1"}`}>
        {secondary && <ActionButton action={secondary} variant="secondary" size="lg" handlers={handlers} className="w-full" />}
        {primary && <ActionButton action={primary} variant="primary" size="lg" handlers={handlers} className="w-full" />}
      </div>
    </div>
  );
}
