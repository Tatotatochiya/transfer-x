import { useEffect, useState } from "react";

export interface FallbackImageProps {
  src?: string | null;
  /** Source of the initials; never shown as alt text. */
  name: string;
  /** Circle for players, rounded square for clubs. */
  kind?: "player" | "club";
  /** The box's final size, e.g. "h-12 w-12 text-lg". */
  sizeClass: string;
  /** Initials colours. */
  colorClass?: string;
  /** Player photos cover from the top; crests sit inside with padding. */
  fit?: "cover" | "contain";
  className?: string;
  /** Decorative by default: the name is always shown beside it. */
  alt?: string;
  loading?: "lazy" | "eager";
}

/** "A. Isak" → "AI", "Arsenal" → "A": first letters of the first and last words. */
export function initialsOf(name: string): string {
  const words = name.replace(/[^\p{L}\p{N}\s]/gu, " ").split(/\s+/).filter(Boolean);
  if (words.length === 0) return "?";
  const first = words[0][0];
  const last = words.length > 1 ? words[words.length - 1][0] : "";
  return (first + last).toUpperCase();
}

/** Below 28px there's no room for 13px initials, the smallest text allowed. */
function tooSmallForInitials(sizeClass: string): boolean {
  const m = sizeClass.match(/(?:^|\s)h-(?:(\d+(?:\.\d+)?)|\[(\d+)px\])(?:\s|$)/);
  if (!m) return false;
  return (m[2] ? Number(m[2]) : Number(m[1]) * 4) < 28;
}

/**
 * A player photo or club crest that falls back to initials when there's no
 * image or it fails to load. The box always has its final size, so nothing
 * shifts when an image errors. A box under 28px shows a plain neutral
 * circle instead of initials.
 */
export default function FallbackImage({
  src,
  name,
  kind = "player",
  sizeClass,
  colorClass = "bg-accent-avatar text-accent-active",
  fit = kind === "club" ? "contain" : "cover",
  className = "",
  alt = "",
  loading = "lazy",
}: FallbackImageProps) {
  const [failed, setFailed] = useState(false);
  useEffect(() => setFailed(false), [src]);

  const shape = kind === "club" ? "rounded-md" : "rounded-full";
  const showImage = !!src && !failed;
  const dot = !showImage && tooSmallForInitials(sizeClass);
  return (
    <span
      className={`inline-flex shrink-0 items-center justify-center overflow-hidden font-bold leading-none ${shape} ${sizeClass} ${
        showImage ? (fit === "cover" ? "bg-surface-inset" : "") : dot ? "bg-border" : colorClass
      } ${className}`}
    >
      {showImage ? (
        <img
          src={src}
          alt={alt}
          loading={loading}
          onError={() => setFailed(true)}
          className={fit === "cover" ? "h-full w-full object-cover object-top" : "h-full w-full object-contain p-[8%]"}
        />
      ) : dot ? null : (
        <span aria-hidden>{initialsOf(name)}</span>
      )}
    </span>
  );
}
