import { useState } from "react";

import { useAuthStore } from "../../store/auth";

const DISMISSED_KEY = "transferx-name-prompt-dismissed";

/**
 * Accounts made before names existed are asked once per session for theirs,
 * as a row in the Dashboard's "Needs you" card (feature_spec/club-dashboard
 * §4.2). `show` is false once they have a name, while viewing as someone
 * else, or after "Not now" this session.
 */
export function useNamePrompt(): { show: boolean; dismiss: () => void } {
  const user = useAuthStore((s) => s.user);
  const [dismissed, setDismissed] = useState(() => {
    try { return sessionStorage.getItem(DISMISSED_KEY) === "1"; } catch { return false; }
  });
  function dismiss() {
    setDismissed(true);
    try { sessionStorage.setItem(DISMISSED_KEY, "1"); } catch { /* still hidden for this page */ }
  }
  return { show: !!user && !user.full_name && !user.viewed_by && !dismissed, dismiss };
}
