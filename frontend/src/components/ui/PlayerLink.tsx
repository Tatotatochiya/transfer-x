import { Link } from "react-router-dom";
import FallbackImage from "./FallbackImage";

interface PlayerLinkProps {
  /** Player ID → routes to his profile, /players/market/{id} */
  id?: string | null;
  name?: string | null;
  /** Pass (even as null) to show a small photo, or his initial, before the name. */
  photoUrl?: string | null;
  fallback?: string;
  className?: string;
  /** Hover text, e.g. the full name where the name is truncated. */
  title?: string;
  /** Photo size: sm 20px (inline text), md 32px (rows, cards), lg 44px (headers). */
  size?: "sm" | "md" | "lg";
}

const PHOTO: Record<"sm" | "md" | "lg", { box: string; text: string; gap: string }> = {
  sm: { box: "h-5 w-5", text: "text-[11px]", gap: "gap-1.5" },
  md: { box: "h-8 w-8", text: "text-sm", gap: "gap-2" },
  lg: { box: "h-11 w-11", text: "text-base", gap: "gap-3" },
};

/**
 * A player's name as a link to his profile, the player counterpart of
 * ClubLink. Without an id it renders plain text. Clicks don't bubble, so it
 * is safe inside clickable rows and cards.
 */
export default function PlayerLink({ id, name, photoUrl, fallback = "—", className = "", title, size = "sm" }: PlayerLinkProps) {
  if (!name) return <span className={className}>{fallback}</span>;
  const showPhoto = photoUrl !== undefined;
  const ps = PHOTO[size];
  const content = showPhoto ? (
    <>
      <FallbackImage src={photoUrl} name={name} sizeClass={`${ps.box} ${ps.text}`} colorClass="bg-surface-inset text-text-muted" />
      <span className="truncate">{name}</span>
    </>
  ) : name;
  if (!id) return <span className={`${showPhoto ? `inline-flex min-w-0 items-center ${ps.gap} ` : ""}${className}`}>{content}</span>;
  return (
    <Link
      to={`/players/market/${id}`}
      title={title}
      onClick={(e) => e.stopPropagation()}
      className={`${showPhoto ? `inline-flex min-w-0 items-center ${ps.gap} ` : ""}hover:text-accent transition-colors ${className}`}
    >
      {content}
    </Link>
  );
}
