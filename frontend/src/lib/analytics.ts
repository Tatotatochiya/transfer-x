/**
 * Client-side analytics — session management, event buffering, and flush.
 *
 * Events are buffered locally and sent in batches to POST /api/analytics/events.
 * The session ID is a UUID generated once per browser and persisted in localStorage.
 */

const SESSION_KEY = "transferx-session-id";
const FLUSH_INTERVAL_MS = 5_000;
const MAX_BUFFER = 50;

export type EventType = "PAGE_VIEW" | "PAGE_LEAVE" | "CLICK";

export interface AnalyticsEventIn {
  session_id: string;
  event_type: EventType;
  path: string;
  referrer?: string;
  element?: string;
  duration_ms?: number;
  meta?: Record<string, unknown>;
}

// ── Session ID ────────────────────────────────────────────────────────────────

function generateUUID(): string {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  // Fallback for older environments
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    return (c === "x" ? r : (r & 0x3) | 0x8).toString(16);
  });
}

export function getSessionId(): string {
  let id = localStorage.getItem(SESSION_KEY);
  if (!id) {
    id = generateUUID();
    localStorage.setItem(SESSION_KEY, id);
  }
  return id;
}

// ── Event buffer ──────────────────────────────────────────────────────────────

const buffer: AnalyticsEventIn[] = [];
let flushTimer: ReturnType<typeof setInterval> | null = null;

async function flush(): Promise<void> {
  if (buffer.length === 0) return;
  const batch = buffer.splice(0, buffer.length);
  try {
    await fetch("/api/analytics/events", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ events: batch }),
      keepalive: true, // allows the request to outlive the page
    });
  } catch {
    // Analytics must never break the app — silently discard on failure
  }
}

function ensureFlushTimer(): void {
  if (flushTimer !== null) return;
  flushTimer = setInterval(flush, FLUSH_INTERVAL_MS);
}

// Flush remaining events on page unload
if (typeof window !== "undefined") {
  window.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") {
      void flush();
    }
  });
  window.addEventListener("beforeunload", () => {
    void flush();
  });
}

// ── Public API ────────────────────────────────────────────────────────────────

function push(event: Omit<AnalyticsEventIn, "session_id">): void {
  ensureFlushTimer();
  buffer.push({ session_id: getSessionId(), ...event });
  if (buffer.length >= MAX_BUFFER) {
    void flush();
  }
}

export function trackPageView(path: string, referrer?: string): void {
  push({ event_type: "PAGE_VIEW", path, referrer });
}

export function trackPageLeave(path: string, duration_ms: number): void {
  push({ event_type: "PAGE_LEAVE", path, duration_ms });
}

export function trackClick(element: string, path: string): void {
  push({ event_type: "CLICK", path, element });
}
