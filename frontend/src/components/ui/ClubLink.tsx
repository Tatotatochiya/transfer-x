import { Link } from "react-router-dom";

interface ClubLinkProps {
  /** Registered club ID → routes to /clubs/{id} */
  id?: string | null;
  /** World-team ID → routes to /world/teams/{id} */
  worldTeamId?: string | null;
  name?: string | null;
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
  fallback = "—",
  className = "",
}: ClubLinkProps) {
  if (!name) return <span className={className}>{fallback}</span>;

  const base = `hover:text-emerald-400 transition-colors ${className}`;
  const stop = (e: React.MouseEvent) => e.stopPropagation();

  if (id) {
    return <Link to={`/clubs/${id}`} className={base} onClick={stop}>{name}</Link>;
  }
  if (worldTeamId) {
    return <Link to={`/world/teams/${worldTeamId}`} className={base} onClick={stop}>{name}</Link>;
  }
  return (
    <Link to={`/clubs?search=${encodeURIComponent(name)}`} className={base} onClick={stop}>
      {name}
    </Link>
  );
}
