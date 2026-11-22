import { describe, expect, it, vi } from "vitest";
import { act, renderHook } from "@testing-library/react";
import { useNamePrompt } from "./NamePrompt";

let user: { id: string; full_name: string | null; viewed_by: string | null } | null = null;
vi.mock("../../store/auth", () => ({
  useAuthStore: (pick: (s: unknown) => unknown) => pick({ user }),
}));

describe("useNamePrompt", () => {
  it("asks an account without a name, until Not now", () => {
    sessionStorage.clear();
    user = { id: "u", full_name: null, viewed_by: null };
    const { result } = renderHook(() => useNamePrompt());
    expect(result.current.show).toBe(true);
    act(() => result.current.dismiss());
    expect(result.current.show).toBe(false);
    // The rest of this session too.
    expect(renderHook(() => useNamePrompt()).result.current.show).toBe(false);
  });

  it("doesn't ask once there's a name, or while viewing as someone else", () => {
    sessionStorage.clear();
    user = { id: "u", full_name: "Sam Lee", viewed_by: null };
    expect(renderHook(() => useNamePrompt()).result.current.show).toBe(false);
    user = { id: "u", full_name: null, viewed_by: "staff" };
    expect(renderHook(() => useNamePrompt()).result.current.show).toBe(false);
  });
});
