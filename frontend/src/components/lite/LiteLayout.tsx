import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "../../hooks/useAuth";
import { useIdentity } from "../../hooks/useIdentity";
import {
  TEXT_SCALE_PERCENT,
  cachedTextScale,
  usePreferences,
  useUpdatePreferences,
  type TextScale,
} from "../../hooks/usePreferences";
import Icon from "../layout/Icon";

/**
 * The Lite shell (docs/feature_spec/lite-mode, README "Shared: Lite top bar"
 * and "Screen 8"): a plain top bar — logo, club, Home, avatar — and no
 * sidebar, search or bell.
 *
 * Text size applies inside Lite only (decision 5). Lite is sized in rem, so
 * scaling the root font while this layout is mounted scales all of Lite and
 * nothing else; leaving Lite restores the app's size.
 */
export default function LiteLayout({ children }: { children: React.ReactNode }) {
  const { pathname } = useLocation();
  const identity = useIdentity();
  const { data: prefs } = usePreferences();
  const scale: TextScale = prefs?.text_scale ?? cachedTextScale();

  useLayoutEffect(() => {
    const root = document.documentElement;
    const before = root.style.fontSize;
    root.style.fontSize = `${TEXT_SCALE_PERCENT[scale]}%`;
    return () => {
      root.style.fontSize = before;
    };
  }, [scale]);

  const onHome = pathname === "/lite" || pathname === "/lite/";

  return (
    <div className="min-h-screen bg-page text-text">
      <header className="flex h-[4.5rem] items-center justify-between border-b border-border bg-surface px-4 sm:px-8">
        <Link to="/lite" className="flex min-w-0 items-center gap-3 no-underline">
          <span className="flex h-[2.125rem] w-[2.125rem] shrink-0 items-center justify-center rounded-[9px] bg-accent text-white">
            <Icon name="bolt" className="h-5 w-5" />
          </span>
          <span className="text-[1.125rem] font-extrabold text-text">TransferX</span>
          {identity.name && (
            <span className="hidden truncate text-base text-text-muted sm:inline">{identity.name}</span>
          )}
        </Link>
        <div className="flex items-center gap-3">
          {!onHome && (
            <Link
              to="/lite"
              className="flex min-h-[2.75rem] items-center gap-2 rounded-xl bg-surface-inset px-5 text-base font-bold text-text no-underline hover:bg-accent-bg"
            >
              <Icon name="home" className="h-5 w-5" /> Home
            </Link>
          )}
          <ProfileMenu scale={scale} />
        </div>
      </header>
      <main className="mx-auto w-full max-w-[1100px] px-4 py-8 sm:px-14 sm:py-11">{children}</main>
    </div>
  );
}

// ── Profile menu (Screen 8) ──────────────────────────────────────────────────

const SCALES: { key: TextScale; size: string; label: string }[] = [
  { key: "NORMAL", size: "text-[0.9375rem]", label: "Normal text" },
  { key: "LARGE", size: "text-[1.1875rem]", label: "Large text" },
  { key: "LARGER", size: "text-[1.5rem]", label: "Larger text" },
];

function ProfileMenu({ scale }: { scale: TextScale }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();
  const { logout } = useAuth();
  const identity = useIdentity();
  const update = useUpdatePreferences();

  useEffect(() => {
    if (!open) return;
    function onDown(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const initial = (identity.name ?? "?").trim().charAt(0).toUpperCase();

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label="Your account"
        className="flex h-[2.75rem] w-[2.75rem] items-center justify-center overflow-hidden rounded-full bg-accent-bg text-[1.0625rem] font-extrabold text-accent ring-1 ring-border focus:outline-none focus-visible:ring-2 focus-visible:ring-accent"
      >
        {identity.crestUrl ? <img src={identity.crestUrl} alt="" className="h-full w-full object-contain p-1" /> : initial}
      </button>

      {open && (
        <div
          role="menu"
          className="absolute right-0 top-[calc(100%+0.5rem)] z-50 w-[min(23.75rem,calc(100vw-2rem))] rounded-[20px] bg-surface p-5 shadow-2xl ring-1 ring-border"
        >
          <p className="text-[1.125rem] font-extrabold text-text">{identity.name ?? "Your club"}</p>
          {identity.subLabel && <p className="text-[0.9375rem] text-text-muted">{identity.subLabel}</p>}

          {/* Lite mode switch: toggling takes you straight to the other home. */}
          <div className="mt-5 flex items-center justify-between gap-4 border-t border-rule pt-4">
            <div>
              <p className="text-[1.0625rem] font-bold text-text">Lite mode</p>
              <p className="text-[0.9375rem] text-text-muted">Simple home with big buttons</p>
            </div>
            <button
              type="button"
              role="switch"
              aria-checked
              aria-label="Lite mode"
              disabled={update.isPending}
              onClick={() => update.mutate({ lite_mode: false }, { onSuccess: () => navigate("/dashboard") })}
              className="relative h-[1.875rem] w-[3.25rem] shrink-0 rounded-full bg-accent transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2"
            >
              <span className="absolute right-1 top-1 h-[1.375rem] w-[1.375rem] rounded-full bg-white shadow" />
            </button>
          </div>

          {/* Text size: Lite only (decision 5). */}
          <div className="mt-4 border-t border-rule pt-4">
            <p className="mb-2 text-[1.0625rem] font-bold text-text">Text size</p>
            <div className="flex gap-2">
              {SCALES.map((s) => (
                <button
                  key={s.key}
                  type="button"
                  aria-label={s.label}
                  aria-pressed={scale === s.key}
                  onClick={() => update.mutate({ text_scale: s.key })}
                  className={`flex h-[3.25rem] flex-1 items-center justify-center rounded-xl font-bold transition-colors ${s.size} ${
                    scale === s.key
                      ? "bg-accent-bg text-accent ring-[3px] ring-accent"
                      : "bg-surface-inset text-text ring-1 ring-border hover:ring-accent"
                  }`}
                >
                  Aa
                </button>
              ))}
            </div>
          </div>

          <div className="mt-4 space-y-1 border-t border-rule pt-3">
            <Link
              to="/account"
              className="flex min-h-[3.25rem] items-center rounded-xl px-2 text-[1.0625rem] font-semibold text-text no-underline hover:bg-surface-inset"
            >
              Notifications and messages
            </Link>
            <button
              type="button"
              onClick={async () => {
                await logout();
                navigate("/login");
              }}
              className="flex min-h-[3.25rem] w-full items-center rounded-xl px-2 text-left text-[1.0625rem] font-semibold text-text hover:bg-surface-inset"
            >
              Sign out
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
