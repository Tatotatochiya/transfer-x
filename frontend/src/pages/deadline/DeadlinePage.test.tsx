import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, within } from "@testing-library/react";
import { renderWithProviders } from "../../test/utils";
import DeadlinePage from "./DeadlinePage";
import DeadlineBanner from "../../components/deadline/DeadlineBanner";
import type { DeadlineView } from "../../hooks/useDeadline";

const state = vi.hoisted(() => ({ data: undefined as unknown }));
vi.mock("../../hooks/useDeadline", async (orig) => ({
  ...(await orig<typeof import("../../hooks/useDeadline")>()),
  useDeadline: () => ({ data: state.data, isLoading: false, isError: false }),
}));

const closes = new Date(Date.now() + 5 * 3600_000).toISOString();
const view: DeadlineView = {
  window: { state: "open", name: "Summer window", closes_at: closes, hours_left: 5, deadline_mode: true },
  counts: { open: 2, needs_you: 1, at_risk: 2, talking: 3 },
  hours_per_step: 6,
  items: [
    { kind: "offer", id: "o1", side: "SELLING", player_id: "p1", player_name: "Waiting Wes", player_photo_url: null,
      counterparty: "an undisclosed club", amount: 4_000_000, stage: "Offers", detail: "", steps_left: 4,
      next_step: { label: "Answer the offer", owner: "you" }, needs_you: true, at_risk: true, link: "/offers/o1" },
    { kind: "deal", id: "d1", side: "BUYING", player_id: "p2", player_name: "Paper Pete", player_photo_url: null,
      counterparty: "Brentford", amount: 9_000_000, stage: "Paperwork", detail: "", steps_left: 2,
      next_step: { label: "Record the medical", owner: "them" }, needs_you: false, at_risk: true, link: "/deals/d1" },
  ],
};

describe("Deadline day", () => {
  beforeEach(() => { state.data = view; });

  it("lists each open transfer with its next step, whose move and the risk", () => {
    renderWithProviders(<DeadlinePage />);
    expect(screen.getByRole("heading", { name: "Deadline day" })).toBeInTheDocument();
    const [wes, pete] = within(screen.getByRole("list", { name: "Open transfers" })).getAllByRole("listitem");
    expect(wes).toHaveTextContent("Selling to an undisclosed club");
    expect(wes).toHaveTextContent("next: Answer the offer");
    expect(wes).toHaveTextContent("Your move");
    expect(within(wes).getByRole("link", { name: "Do it now" })).toHaveAttribute("href", "/offers/o1");
    expect(pete).toHaveTextContent("Their move");
    expect(pete).toHaveTextContent("At risk · 2 steps left");
    expect(within(pete).getByRole("link", { name: "Open" })).toHaveAttribute("href", "/deals/d1");
    expect(screen.getByText(/still at the talking stage/)).toHaveTextContent("3 more");
  });

  it("in Lite, an offer waiting on you opens its Lite card", () => {
    renderWithProviders(<DeadlinePage lite />);
    expect(screen.getByRole("link", { name: "Do it now" })).toHaveAttribute("href", "/lite/offers/o1");
  });

  it("says so when nothing is open, and when the window is closed", () => {
    state.data = { ...view, items: [], counts: { open: 0, needs_you: 0, at_risk: 0, talking: 0 } };
    renderWithProviders(<DeadlinePage />);
    expect(screen.getByText("No transfers are open before the window closes.")).toBeInTheDocument();
  });

  it("the banner shows only in deadline mode with transfers open", () => {
    const { rerender } = renderWithProviders(<DeadlineBanner />);
    expect(screen.getByRole("status")).toHaveTextContent("2 transfers still open, 1 waiting on you, 2 at risk.");
    expect(screen.getByRole("link", { name: "Open deadline day" })).toHaveAttribute("href", "/deadline");
    state.data = { ...view, window: { ...view.window, deadline_mode: false } };
    rerender(<DeadlineBanner />);
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });
});
