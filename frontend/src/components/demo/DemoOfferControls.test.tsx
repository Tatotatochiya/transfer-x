import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../../test/utils";
import DemoOfferControls from "./DemoOfferControls";

const api = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }));
vi.mock("../../lib/api", () => ({ default: api }));
vi.mock("../../hooks/useAuth", () => ({ useAuth: () => ({ canDemo: true }) }));
vi.mock("../../context/ToastContext", () => ({ useToast: () => ({ addToast: vi.fn() }) }));

describe("DemoOfferControls", () => {
  beforeEach(() => { api.get.mockReset(); api.post.mockReset().mockResolvedValue({ data: { done: "counter" } }); });

  it("makes the house club counter at the fee given", async () => {
    api.get.mockResolvedValue({ data: { in_demo: true, house_club: "Man City", side: "seller", house_move: true, actions: ["accept", "counter", "reject"] } });
    renderWithProviders(<DemoOfferControls offerId="o1" />);
    expect(await screen.findByText("Demo: make Man City answer now")).toBeInTheDocument();
    await userEvent.type(screen.getByRole("spinbutton", { name: /Counter fee/ }), "55");
    await userEvent.click(screen.getByRole("button", { name: "Counter" }));
    await waitFor(() => expect(api.post).toHaveBeenCalledWith("/demo/offers/o1/make", { action: "counter", fee_amount: 55_000_000 }));
  });

  it("is hidden when it isn't the house club's move, or not a demo offer", async () => {
    api.get.mockResolvedValue({ data: { in_demo: true, house_club: "Man City", side: "seller", house_move: false, actions: [] } });
    const { unmount } = renderWithProviders(<DemoOfferControls offerId="o1" />);
    await waitFor(() => expect(api.get).toHaveBeenCalled());
    expect(screen.queryByRole("region", { name: "Demo controls" })).not.toBeInTheDocument();
    unmount();
    api.get.mockResolvedValue({ data: { in_demo: false } });
    renderWithProviders(<DemoOfferControls offerId="o2" />);
    await waitFor(() => expect(api.get).toHaveBeenCalledTimes(2));
    expect(screen.queryByRole("region", { name: "Demo controls" })).not.toBeInTheDocument();
  });
});
