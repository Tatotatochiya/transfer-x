/* TransferX service worker: shows pushes and opens them. No caching.
 *
 * docs/feature_spec/mobile-notifications §7.1. Registered from main.tsx as
 * /sw.js?api=<API base URL>, because this file is served as-is (Vite does
 * not process public/) and the API lives on another origin in production.
 *
 * iOS 18.4+ shows a declarative push ("web_push": 8030) without running
 * this file; the app then marks the notification read when it opens with
 * ?nid= (lib/push.ts, markOpenedFromUrl).
 */
const API = new URL(new URL(self.location.href).searchParams.get("api") || "/api", self.location.origin)
  .href.replace(/\/$/, "");

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) => event.waitUntil(self.clients.claim()));

self.addEventListener("push", (event) => {
  let payload = null;
  try {
    payload = event.data ? event.data.json() : null;
  } catch (e) {
    payload = null;
  }
  const n = payload && payload.notification;
  if (!n || !n.title) return;
  const data = Object.assign({}, n.data || {}, { navigate: n.navigate, actions: n.actions || [] });
  const tasks = [
    self.registration.showNotification(n.title, {
      body: n.body,
      tag: n.tag,
      // A newer push about the same subject replaces the old one; only
      // "your move" makes the phone sound again when it does.
      renotify: Boolean(n.tag && data.renotify),
      silent: Boolean(n.silent),
      lang: n.lang || "en-GB",
      icon: "/icons/icon-192.png",
      badge: "/icons/badge-72.png",
      actions: (n.actions || []).map((a) => ({ action: a.action, title: a.title })),
      data,
    }),
  ];
  if (n.app_badge != null && self.navigator.setAppBadge) {
    const count = Number(n.app_badge);
    tasks.push((count > 0 ? self.navigator.setAppBadge(count) : self.navigator.clearAppBadge()).catch(() => {}));
  }
  event.waitUntil(Promise.all(tasks));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const data = event.notification.data || {};
  // An action button only ever opens a page (ADR 0006): its own URL, or the
  // notification's when the tap was on the body.
  const action = (data.actions || []).find((a) => a.action === event.action);
  const url = (action && action.navigate) || data.navigate || "/notifications";

  const report = data.nid && data.open_token
    ? fetch(`${API}/notifications/${data.nid}/opened?token=${encodeURIComponent(data.open_token)}`, { method: "POST" })
        .catch(() => {})
    : Promise.resolve();

  const open = self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((windows) => {
    const target = new URL(url, self.location.origin);
    const same = windows.find((w) => new URL(w.url).origin === target.origin);
    if (same) {
      return same.focus().then((w) => (w && w.navigate ? w.navigate(target.href) : null))
        .catch(() => self.clients.openWindow(target.href));
    }
    return self.clients.openWindow(target.href);
  });

  event.waitUntil(Promise.all([report, open]));
});

// The browser replaced the subscription. Subscribe again with the same key;
// the app sends the new one to the server the next time it opens (the worker
// has no login to send it with).
self.addEventListener("pushsubscriptionchange", (event) => {
  const old = event.oldSubscription;
  if (!old || !old.options || !old.options.applicationServerKey) return;
  event.waitUntil(
    self.registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: old.options.applicationServerKey,
    }).catch(() => {}),
  );
});
