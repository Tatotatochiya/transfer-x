import type { PlayerSituation } from "../../lib/playerSituation";

/**
 * Why there's no button, or what's going on, in one sentence under the
 * header (player-actions D8): never a disabled button with a tooltip.
 */
export default function PlayerActionNote({ note }: { note: PlayerSituation["note"] }) {
  if (!note) return null;
  return (
    <p
      className={`rounded-xl px-4 py-3 text-body leading-normal ${
        note.tone === "info" ? "bg-accent-bg text-accent-active" : "bg-surface-inset text-text-secondary"
      }`}
    >
      {note.text}
    </p>
  );
}
