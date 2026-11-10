import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import Button, { buttonClasses } from "../ui/Button";
import type { ActionKey, SituationAction } from "../../lib/playerSituation";

export interface ActionHandlers {
  /** Runs an action that isn't a link (list, sign, pre-contract, ask). */
  onAction: (key: ActionKey) => void;
  /** The action whose request is in flight, for its spinner. */
  pending?: ActionKey | null;
}

/** One situation action: a Link when it goes somewhere, else a Button. */
export function ActionButton({ action, variant, handlers, className = "", size = "md" }: {
  action: SituationAction;
  variant: "primary" | "secondary";
  handlers: ActionHandlers;
  className?: string;
  size?: "md" | "lg";
}) {
  if (action.to) {
    return <Link to={action.to} className={`${buttonClasses(variant, size)} ${className}`}>{action.label}</Link>;
  }
  return (
    <Button
      variant={variant}
      size={size}
      className={className}
      loading={handlers.pending === action.key}
      onClick={() => handlers.onAction(action.key)}
    >
      {action.label}
    </Button>
  );
}

/**
 * The player page's actions from 1024px (player-actions D5), beside his
 * name: Shortlist · the secondary · the one primary · More.
 */
export default function PlayerActions({ primary, secondary, handlers, shortlist, more }: {
  primary?: SituationAction;
  secondary?: SituationAction;
  handlers: ActionHandlers;
  shortlist?: ReactNode;
  more?: ReactNode;
}) {
  return (
    <>
      {shortlist}
      {secondary && <ActionButton action={secondary} variant="secondary" handlers={handlers} className="lg:min-h-10" />}
      {primary && <ActionButton action={primary} variant="primary" handlers={handlers} className="lg:min-h-10" />}
      {more}
    </>
  );
}
