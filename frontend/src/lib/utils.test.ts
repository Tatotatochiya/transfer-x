import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  formatCurrency,
  formatWage,
  formatDate,
  formatDeadline,
  cn,
  getApiError,
} from "./utils";

describe("formatCurrency", () => {
  it("formats large numbers with £ and commas", () => {
    expect(formatCurrency(50000000)).toBe("£50,000,000");
  });

  it("rounds decimal values", () => {
    expect(formatCurrency(1234.56)).toBe("£1,235");
  });

  it("returns — for null", () => {
    expect(formatCurrency(null)).toBe("—");
  });

  it("returns — for undefined", () => {
    expect(formatCurrency(undefined)).toBe("—");
  });

  it("handles zero", () => {
    expect(formatCurrency(0)).toBe("£0");
  });
});

describe("formatWage", () => {
  it("formats weekly wage with /wk suffix", () => {
    expect(formatWage(200000)).toBe("£200,000/wk");
  });

  it("returns — for null", () => {
    expect(formatWage(null)).toBe("—");
  });
});

describe("formatDate", () => {
  it("formats ISO date to readable string", () => {
    const result = formatDate("2026-06-30T00:00:00Z");
    expect(result).toMatch(/Jun/);
    expect(result).toMatch(/2026/);
  });

  it("returns — for null", () => {
    expect(formatDate(null)).toBe("—");
  });

  it("returns — for empty string", () => {
    expect(formatDate("")).toBe("—");
  });
});

describe("formatDeadline", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2025-01-01T12:00:00Z"));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("returns expired state for past date", () => {
    const result = formatDeadline("2024-12-31T00:00:00Z");
    expect(result.state).toBe("expired");
    expect(result.label).toBe("Expired");
  });

  it("returns No deadline for null", () => {
    const result = formatDeadline(null);
    expect(result.label).toBe("No deadline");
    expect(result.state).toBe("ok");
  });

  it("returns danger state for deadline < 15 minutes away", () => {
    const soon = new Date("2025-01-01T12:10:00Z").toISOString();
    const result = formatDeadline(soon);
    expect(result.state).toBe("danger");
    expect(result.label).toMatch(/m/);
  });

  it("returns warning state for deadline < 1 hour away", () => {
    const warning = new Date("2025-01-01T12:45:00Z").toISOString();
    const result = formatDeadline(warning);
    expect(result.state).toBe("warning");
  });

  it("returns ok state for deadline > 1 hour away", () => {
    const ok = new Date("2025-01-02T12:00:00Z").toISOString();
    const result = formatDeadline(ok);
    expect(result.state).toBe("ok");
    expect(result.label).toMatch(/d/);
  });

  it("shows hours and minutes when less than 1 day remains", () => {
    const hours = new Date("2025-01-01T18:30:00Z").toISOString();
    const result = formatDeadline(hours);
    expect(result.label).toMatch(/h/);
  });
});

describe("cn", () => {
  it("joins class names", () => {
    expect(cn("a", "b", "c")).toBe("a b c");
  });

  it("filters out falsy values", () => {
    expect(cn("a", false, null, undefined, "b")).toBe("a b");
  });

  it("returns empty string for all falsy", () => {
    expect(cn(false, null, undefined)).toBe("");
  });
});

describe("getApiError", () => {
  it("extracts detail from axios error response", () => {
    const err = { response: { data: { detail: "Not found" } } };
    expect(getApiError(err)).toBe("Not found");
  });

  it("returns fallback when no detail present", () => {
    expect(getApiError({})).toBe("Something went wrong.");
  });

  it("returns custom fallback message", () => {
    expect(getApiError({}, "Custom error")).toBe("Custom error");
  });
});
