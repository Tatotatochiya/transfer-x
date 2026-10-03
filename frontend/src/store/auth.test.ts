import { afterEach, describe, expect, it, vi } from "vitest";

describe("auth store in a view-as tab", () => {
  afterEach(() => {
    vi.resetModules();
    window.history.replaceState(null, "", "/");
    localStorage.clear();
  });

  it("takes the token from the URL fragment, keeps it in memory, and leaves the stored session alone", async () => {
    localStorage.setItem("transferx-refresh", "the-staff-members-own-session");
    window.history.replaceState(null, "", "/view-as#view_as=abc.def-ghi");
    const { useAuthStore } = await import("./auth");
    const s = useAuthStore.getState();
    expect(s.viewAs).toBe(true);
    expect(s.accessToken).toBe("abc.def-ghi");
    expect(s.refreshToken).toBeNull();
    expect(window.location.hash).toBe("");  // not left in the address bar or history
    s.logout();
    // Exiting must not sign the staff member out of their other tabs.
    expect(localStorage.getItem("transferx-refresh")).toBe("the-staff-members-own-session");
  });

  it("behaves as before in a normal tab", async () => {
    localStorage.setItem("transferx-refresh", "rt");
    const { useAuthStore } = await import("./auth");
    expect(useAuthStore.getState().viewAs).toBe(false);
    expect(useAuthStore.getState().refreshToken).toBe("rt");
    useAuthStore.getState().logout();
    expect(localStorage.getItem("transferx-refresh")).toBeNull();
  });
});
