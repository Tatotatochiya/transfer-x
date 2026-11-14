import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { ChasedBadge, SentBadge, StalledBadge, stalledDays } from "./ReminderBadges";

const NOW = new Date("2026-11-12T12:00:00Z");
const ago = (days: number) => new Date(NOW.getTime() - days * 86_400_000).toISOString();

describe("reminder colours", () => {
  it("stalled from three days, amber", () => {
    expect(stalledDays(ago(2.9), NOW)).toBeNull();
    expect(stalledDays(ago(5.2), NOW)).toBe(5);
    render(<StalledBadge since={ago(5.2)} now={NOW} />);
    expect(screen.getByText("Stalled · 5 days").className).toContain("bg-warning-bg");
  });

  it("nothing before three days", () => {
    const { container } = render(<StalledBadge since={ago(1)} now={NOW} />);
    expect(container.textContent).toBe("");
  });

  it("the waiting side: grey while fresh, amber once stalled or escalated; never red", () => {
    const { rerender } = render(<SentBadge escalated={false} stalled={false} />);
    expect(screen.getByText("Reminded").className).toContain("bg-surface-inset");
    rerender(<SentBadge escalated={false} stalled />);
    expect(screen.getByText("Reminded").className).toContain("bg-warning-bg");
    rerender(<SentBadge escalated stalled={false} />);
    expect(screen.getByText("Escalated").className).toContain("bg-warning-bg");
    expect(screen.getByText("Escalated").className).not.toContain("danger");
  });

  it("the side being chased: red", () => {
    render(<ChasedBadge escalated />);
    expect(screen.getByText("Escalated").className).toContain("bg-danger-bg");
  });
});
