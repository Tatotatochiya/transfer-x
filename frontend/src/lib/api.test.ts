import { afterEach, describe, expect, it, vi } from "vitest";

const post = vi.hoisted(() => vi.fn());
vi.mock("axios", () => {
  const instance = { interceptors: { request: { use: vi.fn() }, response: { use: vi.fn() } } };
  return { default: { create: () => instance, post }, AxiosError: class {} };
});

import { refreshAccessToken } from "./api";
import { useAuthStore } from "../store/auth";

describe("refreshAccessToken across tabs", () => {
  afterEach(() => {
    post.mockReset();
    localStorage.clear();
    useAuthStore.setState({ refreshToken: null, accessToken: null, viewAs: false });
  });

  it("uses the token another tab rotated in, instead of signing out", async () => {
    localStorage.setItem("transferx-refresh", "T1");
    useAuthStore.setState({ refreshToken: "T1" });
    post.mockImplementation(async (_url: string, body: { refresh_token: string }) => {
      if (body.refresh_token === "T1") {
        // The other tab won the race and stored its new token meanwhile.
        localStorage.setItem("transferx-refresh", "T2");
        throw Object.assign(new Error("401"), { response: { status: 401 } });
      }
      return { data: { access_token: "A3", refresh_token: "T3" } };
    });
    await expect(refreshAccessToken()).resolves.toBe("A3");
    expect(post.mock.calls.map((c) => c[1].refresh_token)).toEqual(["T1", "T2"]);
    expect(localStorage.getItem("transferx-refresh")).toBe("T3");
  });

  it("reads the stored token first, as it is the freshest", async () => {
    localStorage.setItem("transferx-refresh", "FRESH");
    useAuthStore.setState({ refreshToken: "STALE" });
    post.mockResolvedValue({ data: { access_token: "A", refresh_token: "R" } });
    await refreshAccessToken();
    expect(post.mock.calls[0][1].refresh_token).toBe("FRESH");
  });

  it("still fails when no other tab saved a newer token", async () => {
    vi.useFakeTimers();
    localStorage.setItem("transferx-refresh", "T1");
    post.mockRejectedValue(Object.assign(new Error("401"), { response: { status: 401 } }));
    const result = refreshAccessToken();
    const assertion = expect(result).rejects.toThrow("401");
    await vi.advanceTimersByTimeAsync(2000);
    await assertion;
    vi.useRealTimers();
  });
});
