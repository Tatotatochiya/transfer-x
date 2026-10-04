import { useQuery, useQueryClient } from "@tanstack/react-query";
import api, { API_BASE_URL } from "./api";

/**
 * Phone and desktop notifications (docs/feature_spec/mobile-notifications §7.2).
 *
 * The browser half of Web Push: is it possible here, ask, subscribe, tell the
 * server, and unsubscribe on sign-out. The service worker that shows the
 * pushes is public/sw.js.
 */

export type PushState =
  | "unsupported"           // no service worker / PushManager / Notification
  | "needs-install"         // iPhone or iPad in a Safari tab: only the Home Screen app can subscribe
  | "not-configured"        // this server sends no pushes (no VAPID keys)
  | "default"               // can ask
  | "granted-subscribed"
  | "granted-unsubscribed"  // permission given, but this device has no subscription
  | "denied";

export type PushPlatform = "IOS_HOME_SCREEN" | "ANDROID" | "DESKTOP" | "OTHER";

export interface PushEnvironment {
  userAgent: string;
  maxTouchPoints: number;
  standalone: boolean;
  hasServiceWorker: boolean;
  hasPushManager: boolean;
  hasNotification: boolean;
  permission: NotificationPermission | null;
  subscribed: boolean;
  serverKey: string | null;
}

/** iPadOS reports itself as a Mac; only touch gives it away. */
export function isIOS(userAgent: string, maxTouchPoints: number): boolean {
  return /iPad|iPhone|iPod/.test(userAgent) || (maxTouchPoints > 1 && /Macintosh/.test(userAgent));
}

/** The state, from facts about the browser. Pure, so the matrix is testable. */
export function pushStateFrom(env: PushEnvironment): PushState {
  if (isIOS(env.userAgent, env.maxTouchPoints) && !env.standalone) return "needs-install";
  if (!env.hasServiceWorker || !env.hasPushManager || !env.hasNotification) return "unsupported";
  if (!env.serverKey) return "not-configured";
  if (env.permission === "denied") return "denied";
  if (env.permission === "granted") return env.subscribed ? "granted-subscribed" : "granted-unsubscribed";
  return "default";
}

export function platformOf(userAgent: string, maxTouchPoints: number, standalone: boolean): PushPlatform {
  if (isIOS(userAgent, maxTouchPoints)) return standalone ? "IOS_HOME_SCREEN" : "OTHER";
  if (/Android/.test(userAgent)) return "ANDROID";
  if (/Mobi/.test(userAgent)) return "OTHER";
  return "DESKTOP";
}

function isStandalone(): boolean {
  return (
    (typeof window.matchMedia === "function" && window.matchMedia("(display-mode: standalone)").matches) ||
    (navigator as Navigator & { standalone?: boolean }).standalone === true
  );
}

function supported(): boolean {
  return "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
}

async function currentSubscription(): Promise<PushSubscription | null> {
  if (!supported()) return null;
  const reg = await navigator.serviceWorker.getRegistration();
  return reg ? reg.pushManager.getSubscription() : null;
}

let serverKeyPromise: Promise<string | null> | null = null;

/** The server's VAPID public key, or null when it sends no pushes. Fetched
 *  once: subscribe() must not wait on the network before asking permission. */
export function serverKey(): Promise<string | null> {
  serverKeyPromise ??= api
    .get<{ key: string | null }>("/notifications/push/public-key")
    .then((r) => r.data.key)
    .catch(() => {
      serverKeyPromise = null;
      return null;
    });
  return serverKeyPromise;
}

export async function detectPushState(): Promise<PushState> {
  const hasNotification = "Notification" in window;
  return pushStateFrom({
    userAgent: navigator.userAgent,
    maxTouchPoints: navigator.maxTouchPoints ?? 0,
    standalone: isStandalone(),
    hasServiceWorker: "serviceWorker" in navigator,
    hasPushManager: "PushManager" in window,
    hasNotification,
    permission: hasNotification ? Notification.permission : null,
    subscribed: (await currentSubscription().catch(() => null)) !== null,
    serverKey: supported() ? await serverKey() : null,
  });
}

export const PUSH_STATE_KEY = ["push", "state"] as const;

export function usePushState(enabled = true) {
  return useQuery({ queryKey: PUSH_STATE_KEY, queryFn: detectPushState, enabled, staleTime: 60_000 });
}

/** The current device's subscription endpoint, to tell it apart in the device list. */
export function useThisDeviceEndpoint(enabled = true) {
  return useQuery({
    queryKey: ["push", "endpoint"],
    queryFn: async () => (await currentSubscription().catch(() => null))?.endpoint ?? null,
    enabled,
  });
}

export function useRefreshPush() {
  const queryClient = useQueryClient();
  return () => {
    queryClient.invalidateQueries({ queryKey: ["push"] });
    queryClient.invalidateQueries({ queryKey: ["notifications", "push", "devices"] });
  };
}

function urlBase64ToUint8Array(base64: string): Uint8Array<ArrayBuffer> {
  const padded = (base64 + "=".repeat((4 - (base64.length % 4)) % 4)).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(padded);
  const out = new Uint8Array(new ArrayBuffer(raw.length));
  for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
  return out;
}

async function saveSubscription(sub: PushSubscription): Promise<void> {
  const json = sub.toJSON();
  await api.post("/notifications/push/subscriptions", {
    endpoint: sub.endpoint,
    keys: { p256dh: json.keys?.p256dh, auth: json.keys?.auth },
    platform: platformOf(navigator.userAgent, navigator.maxTouchPoints ?? 0, isStandalone()),
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
  });
}

/**
 * Ask, subscribe and save. Call it straight from a click handler:
 * iOS only shows the permission prompt from a user gesture, so the prompt
 * comes first, before anything else is awaited.
 */
export async function subscribe(): Promise<PushState> {
  if (!supported()) return "unsupported";
  const permission = await Notification.requestPermission();
  if (permission !== "granted") return permission === "denied" ? "denied" : "default";
  const key = await serverKey();
  if (!key) return "not-configured";
  const reg = await navigator.serviceWorker.ready;
  const sub =
    (await reg.pushManager.getSubscription()) ??
    (await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: urlBase64ToUint8Array(key) }));
  await saveSubscription(sub);
  return "granted-subscribed";
}

/** Stop pushes to this device: on the server, then in the browser. */
export async function unsubscribe(): Promise<void> {
  const sub = await currentSubscription().catch(() => null);
  if (!sub) return;
  await api.delete("/notifications/push/subscriptions", { data: { endpoint: sub.endpoint } }).catch(() => {});
  synced = false;
  await sub.unsubscribe().catch(() => false);
}

/**
 * On app start, signed in: send this device's subscription again. It renews
 * one the browser replaced (the service worker can't, having no login) and
 * keeps the timezone current. Does nothing if this device never said yes.
 */
let synced = false;

export async function syncSubscription(): Promise<void> {
  if (synced || !supported() || Notification.permission !== "granted") return;
  synced = true; // once per page load: the layout can remount
  const sub = await currentSubscription().catch(() => null);
  if (sub) await saveSubscription(sub).catch(() => {});
}

/** The service worker, registered after load. It is told the API's address
 *  in its URL, since public/ files are served as they are. */
export function registerServiceWorker(): void {
  if (!("serviceWorker" in navigator)) return;
  window.addEventListener("load", () => {
    navigator.serviceWorker.register(`/sw.js?api=${encodeURIComponent(API_BASE_URL)}`).catch(() => {});
  });
}

/**
 * A push opened without the service worker (iOS 18.4+ shows declarative
 * pushes itself) arrives as ?from=push&nid=…&ot=…: report the tap with the
 * push's own token (which also marks it read, and works signed out), then
 * take nid and ot out of the address bar. Without a token, mark it read.
 */
export async function markOpenedFromUrl(search: string): Promise<void> {
  const params = new URLSearchParams(search);
  const nid = params.get("nid");
  if (params.get("from") !== "push" || !nid || !/^[0-9a-f-]{36}$/i.test(nid)) return;
  const token = params.get("ot");
  if (token) {
    params.delete("ot");
    params.delete("nid");
    const rest = params.toString();
    try {
      window.history.replaceState(window.history.state, "", `${window.location.pathname}${rest ? `?${rest}` : ""}${window.location.hash}`);
    } catch { /* the report still goes */ }
    await api.post(`/notifications/${nid}/opened`, null, { params: { token } }).catch(() => {});
    return;
  }
  await api.post(`/notifications/${nid}/read`).catch(() => {});
}

/** The app icon's badge: what is waiting on this person. */
export function setAppBadge(count: number): void {
  const nav = navigator as Navigator & { setAppBadge?: (n?: number) => Promise<void>; clearAppBadge?: () => Promise<void> };
  if (!nav.setAppBadge) return;
  (count > 0 ? nav.setAppBadge(count) : nav.clearAppBadge?.())?.catch(() => {});
}

// ── The soft ask (mobile notifications §7.3, 5a) ─────────────────────────────

/** How often the "Get offers on this phone" sheet may appear: never in the
 *  first session, again 14 days after "Not now", and at most three times.
 *  Opening the Home Screen app for the first time skips these rules. */
export const ASK_GAP_DAYS = 14;
export const ASK_MAX = 3;

export interface AskRecord {
  dismissedAt: number | null;
  dismissals: number;
}

export function canAsk({ record, sessions, now, fromHomeScreen }: {
  record: AskRecord; sessions: number; now: number; fromHomeScreen: boolean;
}): boolean {
  if (fromHomeScreen) return true;
  if (sessions < 2) return false;
  if (record.dismissals >= ASK_MAX) return false;
  if (record.dismissedAt != null && now - record.dismissedAt < ASK_GAP_DAYS * 86_400_000) return false;
  return true;
}

const ASK_KEY = "push_ask";
const SESSIONS_KEY = "push_sessions";

export function readAskRecord(): AskRecord {
  try {
    const raw = JSON.parse(localStorage.getItem(ASK_KEY) ?? "null");
    return { dismissedAt: Number(raw?.dismissedAt) || null, dismissals: Number(raw?.dismissals) || 0 };
  } catch {
    return { dismissedAt: null, dismissals: 0 };
  }
}

export function recordDismissal(now = Date.now()): void {
  const r = readAskRecord();
  try {
    localStorage.setItem(ASK_KEY, JSON.stringify({ dismissedAt: now, dismissals: r.dismissals + 1 }));
  } catch { /* private mode: it may ask again next time */ }
}

/** Sessions seen on this device, counted once per browser session. */
export function countSession(): number {
  try {
    let n = Number(localStorage.getItem(SESSIONS_KEY)) || 0;
    if (!sessionStorage.getItem(SESSIONS_KEY)) {
      n += 1;
      localStorage.setItem(SESSIONS_KEY, String(n));
      sessionStorage.setItem(SESSIONS_KEY, "1");
    }
    return n;
  } catch {
    return 0;
  }
}

/** iPad shows Safari's Share button at the top right; iPhone at the bottom. */
export function isIPad(userAgent = navigator.userAgent, maxTouchPoints = navigator.maxTouchPoints ?? 0): boolean {
  return /iPad/.test(userAgent) || (maxTouchPoints > 1 && /Macintosh/.test(userAgent));
}
