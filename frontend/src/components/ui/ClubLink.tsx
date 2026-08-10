import { Link } from "react-router-dom";

interface ClubLinkProps {
  /** Registered club ID → routes to /clubs/{id} */
  id?: string | null;
  /** World-team ID → routes to /world/teams/{id} */
  worldTeamId?: string | null;
  name?: string | null;
  /** Pass (even as null) to render a crest — or an initials fallback when
   * unset — before the name. Omit entirely to keep the old text-only look. */
  crestUrl?: string | null;
  fallback?: string;
  className?: string;
}

/**
 * Renders a clickable club/team name.
 * - Registered club (id)      → /clubs/{id}
 * - Vendor world team          → /world/teams/{worldTeamId}
 * - Name-only (no id)          → /clubs?search={name}
 * - No name                    → plain fallback span
 */
export default function ClubLink({
  id,
  worldTeamId,
  name,
  crestUrl,
  fallback = "—",
  className = "",
}: ClubLinkProps) {
  if (!name) return <span className={className}>{fallback}</span>;

  const showCrestSlot = crestUrl !== undefined;
  const base = `${showCrestSlot ? "inline-flex items-center gap-1.5 " : ""}hover:text-accent transition-colors ${className}`;
  const stop = (e: React.MouseEvent) => e.stopPropagation();

  const content = showCrestSlot ? (
    <>
      {crestUrl ? (
        <img src={crestUrl} alt="" loading="lazy" className="h-4 w-4 shrink-0 object-contain" />
      ) : (
        <span className="h-4 w-4 shrink-0 rounded-full bg-surface-inset flex items-center justify-center text-[9px] font-bold text-text-muted">
          {name[0]?.toUpperCase()}
        </span>
      )}
      <span className="truncate">{name}</span>
    </>
  ) : (
    name
  );

  if (id) {
    return <Link to={`/clubs/${id}`} className={base} onClick={stop}>{content}</Link>;
  }
  if (worldTeamId) {
    return <Link to={`/world/teams/${worldTeamId}`} className={base} onClick={stop}>{content}</Link>;
  }
  return (
    <Link to={`/clubs?search=${encodeURIComponent(name)}`} className={base} onClick={stop}>
      {content}
    </Link>
  );
}
