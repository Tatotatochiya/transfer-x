import { afterEach, describe, expect, it, vi } from "vitest";
import { act, render, screen } from "@testing-library/react";
import ExpiryLine from "./ExpiryLine";
import { countdownLeft } from "../../lib/timeLeft";

const NOW = new Date("2026-08-29T12:00:00Z").getTime();

describe("ExpiryLine", () => {
  afterEach(() => vi.useRealTimers());

  it("shows the exact time and counts down every second", () => {
    vi.useFakeTimers({ now: NOW });
    const at = new Date(NOW + (3 * 86_400 + 4 * 3600) * 1000).toISOString();
    render(<ExpiryLine at={at} label="Offer expires" />);
    expect(screen.getByText("Offer expires")).toBeInTheDocument();
    expect(screen.getByRole("timer")).toHaveTextContent("3d 4h left");
    expect(screen.getByText((_, el) => el?.tagName === "TIME")).toHaveAttribute("dateTime", at);
  });

  it("in the last hour counts minutes and seconds, then says time's up", () => {
    vi.useFakeTimers({ now: NOW });
    render(<ExpiryLine at={new Date(NOW + 90_000).toISOString()} label="Collapses unless completed by" />);
    expect(screen.getByRole("timer")).toHaveTextContent("1m 30s left");
    act(() => { vi.advanceTimersByTime(30_000); });
    expect(screen.getByRole("timer")).toHaveTextContent("1m 0s left");
    act(() => { vi.advanceTimersByTime(61_000); });
    expect(screen.getByRole("timer")).toHaveTextContent("Time's up");
  });
});

describe("countdownLeft", () => {
  it("reads days and hours, then hours and minutes, urgent in the last day", () => {
    const at = (s: number) => new Date(NOW + s * 1000).toISOString();
    expect(countdownLeft(at(3 * 86_400 + 4 * 3600), NOW)).toEqual({ text: "3d 4h left", urgent: false });
    expect(countdownLeft(at(5 * 3600 + 12 * 60), NOW)).toEqual({ text: "5h 12m left", urgent: true });
    expect(countdownLeft(at(12 * 60 + 30), NOW)).toEqual({ text: "12m left", urgent: true });
    expect(countdownLeft(at(-1), NOW)).toEqual({ text: "time's up", urgent: true });
    expect(countdownLeft(null, NOW)).toBeNull();
  });
});
