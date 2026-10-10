/**
 * Browser errors to Admin → Errors (POST /monitoring/client-errors). Each
 * distinct message is sent once per page load, at most 10 a load; only the
 * path is sent, never the query. Failures to report are ignored.
 */
import api from "./api";

const MAX_PER_LOAD = 10;
const sent = new Set<string>();

export function reportError(message: string, stack?: string | null): void {
  const key = message.slice(0, 200);
  if (!message || sent.has(key) || sent.size >= MAX_PER_LOAD) return;
  sent.add(key);
  api.post("/monitoring/client-errors", {
    message: message.slice(0, 2000),
    stack: stack ? stack.slice(0, 8000) : null,
    path: window.location.pathname,
  }).catch(() => { /* reporting is best effort */ });
}

export function installErrorReporting(): void {
  window.addEventListener("error", (e) => {
    // Resource load failures (a broken image) have no error object: skip them.
    if (!e.error && !e.message) return;
    reportError(e.message || String(e.error), e.error?.stack);
  });
  window.addEventListener("unhandledrejection", (e) => {
    const reason = e.reason;
    // API errors are already logged by the server that answered them.
    if (reason?.isAxiosError) return;
    reportError(reason instanceof Error ? `${reason.name}: ${reason.message}` : String(reason), reason?.stack);
  });
}

/** For tests. */
export function _resetReported(): void {
  sent.clear();
}
