import { useState } from "react";
import { Link, useLocation } from "react-router-dom";

import { useAuthStore } from "../../store/auth";

const DISMISSED_KEY = "transferx-name-prompt-dismissed";

/** Accounts made before names existed are asked once per session for theirs, on the Dashboard. */
export default function NamePrompt() {
  const user = useAuthStore((s) => s.user);
  const { pathname } = useLocation();
  const [dismissed, setDismissed] = useState(() => {
    try { return sessionStorage.getItem(DISMISSED_KEY) === "1"; } catch { return false; }
  });
  // On the Dashboard only (README_TRANSFERS §6): elsewhere it pushes the
  // page's content down a phone screen and has nothing to do with it.
  if (!user || user.full_name || user.viewed_by || dismissed || pathname !== "/dashboard") return null;

  function dismiss() {
    setDismissed(true);
    try { sessionStorage.setItem(DISMISSED_KEY, "1"); } catch { /* still hidden for this page */ }
  }

  return (
    <div className="mb-4 flex flex-wrap items-center gap-x-4 gap-y-2 rounded-xl bg-accent-bg px-4 py-3 text-small text-text ring-1 ring-accent-ring">
      <p className="flex-1">Add your name so your team and the audit trail show who did what.</p>
      <Link to="/account#name" className="font-semibold text-accent hover:underline">Add your name</Link>
      <button type="button" onClick={dismiss} className="text-text-muted hover:text-text">Not now</button>
    </div>
  );
}
