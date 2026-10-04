import { useState } from "react";
import { Link, useLocation } from "react-router-dom";

import { useAuthStore } from "../../store/auth";

const DISMISSED_KEY = "transferx-name-prompt-dismissed";

/** Accounts made before names existed are asked once per session for theirs. */
export default function NamePrompt() {
  const user = useAuthStore((s) => s.user);
  const { pathname } = useLocation();
  const [dismissed, setDismissed] = useState(() => {
    try { return sessionStorage.getItem(DISMISSED_KEY) === "1"; } catch { return false; }
  });
  if (!user || user.full_name || user.viewed_by || dismissed || pathname.startsWith("/account")) return null;

  function dismiss() {
    setDismissed(true);
    try { sessionStorage.setItem(DISMISSED_KEY, "1"); } catch { /* still hidden for this page */ }
  }

  return (
    <div className="mb-4 flex flex-wrap items-center gap-x-4 gap-y-2 rounded-xl bg-accent/10 px-4 py-3 text-sm text-text ring-1 ring-accent/20">
      <p className="flex-1">Add your name so your team and the audit trail show who did what.</p>
      <Link to="/account#name" className="font-semibold text-accent hover:underline">Add your name</Link>
      <button type="button" onClick={dismiss} className="text-text-muted hover:text-text">Not now</button>
    </div>
  );
}
