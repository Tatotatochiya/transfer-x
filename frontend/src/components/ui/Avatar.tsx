import type { IdentityRole } from "../../hooks/useIdentity";

const ROLE_STYLE: Record<IdentityRole, string> = {
  CLUB: "bg-role-club-bg text-role-club-text",
  AGENT: "bg-role-agent-bg text-role-agent-text",
  // Player reuses warning (amber) rather than adding a third role token.
  PLAYER: "bg-warning-fill/15 text-warning-text",
};

interface AvatarProps {
  name?: string | null;
  crestUrl?: string | null;
  role?: IdentityRole | null;
  /** Staff/superuser reuses the danger family — a heightened-privilege
   * signal, not literally "danger", but the same visual weight applies. */
  isSuperuser?: boolean;
  size?: "sm" | "md";
  className?: string;
}

const SIZE_CLASSES: Record<"sm" | "md", string> = {
  sm: "h-7 w-7 text-xs",
  md: "h-9 w-9 text-sm",
};

/** Club crest, or role-coloured initials. Shared by the sidebar footer and
 * the mobile top bar so identity rendering can't drift between the two. */
export default function Avatar({ name, crestUrl, role, isSuperuser, size = "md", className = "" }: AvatarProps) {
  const roleClass = role ? ROLE_STYLE[role] : "bg-accent-avatar text-accent";
  const ringClass = isSuperuser ? "ring-2 ring-danger-ring" : "";

  return (
    <div
      className={`flex shrink-0 items-center justify-center overflow-hidden font-bold ${
        role === "CLUB" ? "rounded-lg" : "rounded-full"
      } ${SIZE_CLASSES[size]} ${roleClass} ${ringClass} ${className}`}
    >
      {crestUrl ? (
        <img src={crestUrl} alt="" className="h-full w-full object-contain p-1" />
      ) : (
        (name ?? "?")[0]?.toUpperCase() ?? "?"
      )}
    </div>
  );
}
