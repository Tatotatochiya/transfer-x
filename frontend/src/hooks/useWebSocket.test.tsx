import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderHook } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useWebSocket } from "./useWebSocket";

vi.mock("../store/auth", () => ({ useAuthStore: () => ({ accessToken: "t" }) }));

class FakeSocket {
  static last: FakeSocket;
  onopen?: () => void;
  onmessage?: (e: { data: string }) => void;
  onclose?: (e: { code: number }) => void;
  onerror?: () => void;
  constructor() { FakeSocket.last = this; }
  close() {}
}

describe("useWebSocket", () => {
  const original = globalThis.WebSocket;
  beforeEach(() => { (globalThis as unknown as { WebSocket: unknown }).WebSocket = FakeSocket; });
  afterEach(() => { (globalThis as unknown as { WebSocket: unknown }).WebSocket = original; });

  it("an offer or deal update also refreshes its reminder line", () => {
    const qc = new QueryClient();
    const spy = vi.spyOn(qc, "invalidateQueries");
    renderHook(() => useWebSocket(), { wrapper: ({ children }) => <QueryClientProvider client={qc}>{children}</QueryClientProvider> });
    FakeSocket.last.onmessage?.({ data: JSON.stringify({ type: "OFFER_UPDATED", id: "o1" }) });
    FakeSocket.last.onmessage?.({ data: JSON.stringify({ type: "DEAL_UPDATED", id: "d1" }) });
    const keys = spy.mock.calls.map(([f]) => JSON.stringify((f as { queryKey: unknown }).queryKey));
    expect(keys).toContain(JSON.stringify(["reminders", "offer", "o1"]));
    expect(keys).toContain(JSON.stringify(["reminders", "deal", "d1"]));
  });
});
