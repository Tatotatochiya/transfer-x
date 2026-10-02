import { Link } from "react-router-dom";

interface PlayerLinkProps {
  /** Player ID → routes to his profile, /players/market/{id} */
  id?: string | null;
  name?: string | null;
  /** Pass (even as null) to show a small photo, or his initial, before the name. */
  photoUrl?: string | null;
  fallback?: string;
  className?: string;
}

/**
 * A player's name as a link to his profile, the player counterpart of
 * ClubLink. Without an id it renders plain text. Clicks don't bubble, so it
 * is safe inside clickable rows and cards.
 */
export default function PlayerLink({ id, name, photoUrl, fallback = "—", className = "" }: PlayerLinkProps) {
  if (!name) return <span className={className}>{fallback}</span>;
  const showPhoto = photoUrl !== undefined;
  const content = showPhoto ? (
    <>
      {photoUrl ? (
        <img src={photoUrl} alt="" loading="lazy" className="h-5 w-5 shrink-0 rounded-full object-cover object-top" />
      ) : (
        <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-surface-inset text-[11px] font-bold text-text-muted">
          {name[0]?.toUpperCase()}
        </span>
      )}
      <span className="truncate">{name}</span>
    </>
  ) : name;
  if (!id) return <span className={`${showPhoto ? "inline-flex items-center gap-1.5 " : ""}${className}`}>{content}</span>;
  return (
    <Link
      to={`/players/market/${id}`}
      onClick={(e) => e.stopPropagation()}
      className={`${showPhoto ? "inline-flex items-center gap-1.5 " : ""}hover:text-accent transition-colors ${className}`}
    >
      {content}
    </Link>
  );
}
