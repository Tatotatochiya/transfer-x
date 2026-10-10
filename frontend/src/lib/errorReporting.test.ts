import { beforeEach, describe, expect, it, vi } from "vitest";
import { _resetReported, reportError } from "./errorReporting";

const api = vi.hoisted(() => ({ post: vi.fn() }));
vi.mock("./api", () => ({ default: api }));

describe("reportError", () => {
  beforeEach(() => {
    _resetReported();
    api.post.mockReset().mockResolvedValue({});
  });

  it("sends the path only, and each message once per page load", () => {
    window.history.pushState({}, "", "/offers/1?token=secret");
    reportError("TypeError: x is undefined", "stack");
    reportError("TypeError: x is undefined", "stack");
    expect(api.post).toHaveBeenCalledTimes(1);
    expect(api.post).toHaveBeenCalledWith("/monitoring/client-errors",
      { message: "TypeError: x is undefined", stack: "stack", path: "/offers/1" });
  });

  it("stops after ten distinct errors", () => {
    for (let i = 0; i < 15; i++) reportError(`Error ${i}`);
    expect(api.post).toHaveBeenCalledTimes(10);
  });
});
