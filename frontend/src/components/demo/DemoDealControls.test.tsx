import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../../test/utils";
import DemoDealControls from "./DemoDealControls";

const api = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }));
vi.mock("../../lib/api", () => ({ default: api }));
vi.mock("../../hooks/useAuth", () => ({ useAuth: () => ({ canDemo: true }) }));
vi.mock("../../context/ToastContext", () => ({ useToast: () => ({ addToast: vi.fn() }) }));

describe("DemoDealControls", () => {
  beforeEach(() => { api.get.mockReset(); api.post.mockReset().mockResolvedValue({ data: { done: "terms_proposed" } }); });

  it("makes the other side move now on a demo deal that's waiting on them", async () => {
    api.get.mockResolvedValue({ data: { in_demo: true } });
    renderWithProviders(<DemoDealControls dealId="d1" waiting waitingOn="Waiting on the agent" />);
    expect(await screen.findByText("Demo: waiting on the agent")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Make them move now" }));
    await waitFor(() => expect(api.post).toHaveBeenCalledWith("/demo/deals/d1/make"));
  });

  it("is hidden on your own move, and on a deal outside your demo", async () => {
    api.get.mockResolvedValue({ data: { in_demo: true } });
    const { unmount } = renderWithProviders(<DemoDealControls dealId="d1" waiting={false} waitingOn="Your move" />);
    await waitFor(() => expect(api.get).toHaveBeenCalled());
    expect(screen.queryByRole("region", { name: "Demo controls" })).not.toBeInTheDocument();
    unmount();
    api.get.mockResolvedValue({ data: { in_demo: false } });
    renderWithProviders(<DemoDealControls dealId="d2" waiting waitingOn="Waiting on the agent" />);
    await waitFor(() => expect(api.get).toHaveBeenCalledTimes(2));
    expect(screen.queryByRole("region", { name: "Demo controls" })).not.toBeInTheDocument();
  });

  it("offers to add a deal outside the demo, and adds it", async () => {
    api.get.mockResolvedValue({ data: { in_demo: false, can_adopt: true, adopt_reason: null } });
    api.post.mockResolvedValue({ data: { in_demo: true } });
    renderWithProviders(<DemoDealControls dealId="d3" waiting waitingOn="Waiting on the agent" />);
    expect(await screen.findByText("Demo: play the other side of this deal")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Add to my demo" }));
    await waitFor(() => expect(api.post).toHaveBeenCalledWith("/demo/deals/d3/adopt"));
  });

  it("says why a deal can't be added, without a button", async () => {
    api.get.mockResolvedValue({ data: { in_demo: false, can_adopt: false, adopt_reason: "He's in another tester's demo right now." } });
    renderWithProviders(<DemoDealControls dealId="d4" waiting waitingOn="Waiting on the agent" />);
    expect(await screen.findByText("He's in another tester's demo right now.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Add to my demo" })).toBeNull();
  });
});
