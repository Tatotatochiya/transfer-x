import { beforeEach, describe, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { useDealRealWorld } from "./DealRealWorldNotice";

const api = vi.hoisted(() => ({ get: vi.fn() }));
vi.mock("../../lib/api", () => ({ default: api }));

function wrapper({ children }: { children: ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

describe("useDealRealWorld", () => {
  beforeEach(() => api.get.mockReset());

  it("reads the hold and window notices for an open deal", async () => {
    api.get.mockResolvedValue({ data: {
      hold: "API-Football has B. Saka playing for Arsenal.", note: null,
      window: "The transfer window in England is closed.", window_opens_at: "2027-01-01T00:00:00Z",
    } });
    const { result } = renderHook(() => useDealRealWorld("d1", true), { wrapper });
    await waitFor(() => expect(result.current.data).toBeDefined());
    expect(result.current.data!.hold).toContain("playing for Arsenal");
    expect(result.current.data!.window).toContain("closed");
    expect(api.get).toHaveBeenCalledWith("/deals/d1/real-world");
  });

  it("asks nothing for a closed deal", () => {
    const { result } = renderHook(() => useDealRealWorld("d1", false), { wrapper });
    expect(api.get).not.toHaveBeenCalled();
    expect(result.current.data).toBeUndefined();
  });
});
