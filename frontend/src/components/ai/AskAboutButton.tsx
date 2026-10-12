import { Link } from "react-router-dom";

import { askAboutPath } from "../../lib/ask";

/**
 * "Ask about this": opens Ask TransferX about one player, offer or deal.
 * In the AI look every assistant control shares (the ✦ mark, the assistant's
 * purple, a light purple fill and ring), sized like the buttons around it.
 */
export default function AskAboutButton({
  about, id, name, size = "md", className = "",
}: {
  about: "player" | "offer" | "deal";
  id: string;
  name: string;
  size?: "sm" | "md";
  className?: string;
}) {
  const sizing = size === "sm"
    ? "min-h-11 lg:min-h-0 px-3 py-1.5 text-xs"
    : "min-h-11 lg:min-h-0 px-[18px] py-2.5 text-sm";
  return (
    <Link
      to={askAboutPath(about, id, name)}
      title={`Ask TransferX about ${name || `this ${about}`}`}
      className={`inline-flex items-center justify-center gap-1.5 rounded-lg bg-role-agent-text/10 font-semibold text-role-agent-text no-underline ring-1 ring-role-agent-text/30 transition-colors hover:bg-role-agent-text/20 ${sizing} ${className}`}
    >
      <span aria-hidden>✦</span> Ask about this
    </Link>
  );
}
