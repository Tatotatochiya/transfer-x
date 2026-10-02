import { describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn(), delete: vi.fn() }));
vi.mock("./api", () => ({ default: api, API_BASE_URL: "/api" }));

import { isIOS, markOpenedFromUrl, platformOf, pushStateFrom, type PushEnvironment } from "./push";

const IPHONE = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_4 like Mac OS X) AppleWebKit/605.1.15 Version/18.4 Mobile/15E148 Safari/604.1";
const IPAD_AS_MAC = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Version/18.4 Safari/605.1.15";
const ANDROID = "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 Chrome/130.0 Mobile Safari/537.36";
const MAC_CHROME = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/130.0 Safari/537.36";

const env = (over: Partial<PushEnvironment>): PushEnvironment => ({
  userAgent: ANDROID, maxTouchPoints: 5, standalone: false,
  hasServiceWorker: true, hasPushManager: true, hasNotification: true,
  permission: "default", subscribed: false, serverKey: "BKey", ...over,
});

describe("pushStateFrom", () => {
  it.each<[string, Partial<PushEnvironment>, string]>([
    ["iPhone in a Safari tab", { userAgent: IPHONE, hasPushManager: false }, "needs-install"],
    ["iPad (reports as a Mac) in a tab", { userAgent: IPAD_AS_MAC, maxTouchPoints: 5, hasPushManager: false }, "needs-install"],
    ["iPhone Home Screen app, not asked yet", { userAgent: IPHONE, standalone: true }, "default"],
    ["iPhone Home Screen app, subscribed", { userAgent: IPHONE, standalone: true, permission: "granted", subscribed: true }, "granted-subscribed"],
    ["Android, not asked yet", {}, "default"],
    ["Android, allowed but no subscription here", { permission: "granted" }, "granted-unsubscribed"],
    ["Android, blocked", { permission: "denied" }, "denied"],
    ["an old browser", { hasPushManager: false }, "unsupported"],
    ["a desktop Mac (no touch) is not an iPad", { userAgent: MAC_CHROME, maxTouchPoints: 0 }, "default"],
    ["the server sends no pushes", { serverKey: null }, "not-configured"],
  ])("%s → %s", (_name, over, expected) => {
    expect(pushStateFrom(env(over))).toBe(expected);
  });
});

describe("platform", () => {
  it("tells the platforms apart", () => {
    expect(isIOS(IPAD_AS_MAC, 5)).toBe(true);
    expect(isIOS(MAC_CHROME, 0)).toBe(false);
    expect(platformOf(IPHONE, 5, true)).toBe("IOS_HOME_SCREEN");
    expect(platformOf(ANDROID, 5, false)).toBe("ANDROID");
    expect(platformOf(MAC_CHROME, 0, false)).toBe("DESKTOP");
  });
});

describe("markOpenedFromUrl", () => {
  it("marks the notification read only for a push link with a valid id", async () => {
    api.post.mockResolvedValue({ data: {} });
    const nid = "3f2b8c1e-1d2a-4b5c-9e8f-0a1b2c3d4e5f";
    await markOpenedFromUrl(`?from=push&nid=${nid}`);
    expect(api.post).toHaveBeenCalledWith(`/notifications/${nid}/read`);

    api.post.mockClear();
    await markOpenedFromUrl(`?nid=${nid}`);
    await markOpenedFromUrl("?from=push&nid=../../admin");
    expect(api.post).not.toHaveBeenCalled();
  });
});
