import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../../test/utils";
import AdminDemoPage from "./AdminDemoPage";

const api = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn(), patch: vi.fn() }));
vi.mock("../../lib/api", () => ({ default: api }));
const askReason = vi.hoisted(() => vi.fn());
const confirm = vi.hoisted(() => vi.fn());
vi.mock("../../context/ConfirmContext", () => ({ useAskReason: () => askReason, useConfirm: () => confirm }));
vi.mock("../../context/ToastContext", () => ({ useToast: () => ({ addToast: vi.fn() }) }));

const overview = {
  enabled: true,
  runs: [{ id: "r1", status: "ACTIVE", started_at: "2026-10-27T10:00:00Z", resets_on: "2026-11-10", changes: 4, report: null, user: "Luke" }],
  testers: [{ id: "u1", name: "Luke" }],
  clubs: [
    { id: "c1", name: "Chelsea", house_club: false, personality: null, in_use: false },
    { id: "c2", name: "Arsenal", house_club: false, personality: null, in_use: true },
  ],
};

describe("AdminDemoPage", () => {
  beforeEach(() => {
    api.get.mockReset().mockResolvedValue({ data: overview });
    api.patch.mockReset().mockResolvedValue({ data: {} });
    api.post.mockReset().mockResolvedValue({ data: { undone: 4, skipped: [] } });
    askReason.mockReset().mockResolvedValue("For the Friday demo");
    confirm.mockReset().mockResolvedValue(true);
  });

  it("makes an unused club a house club with a reason, and not one people use", async () => {
    renderWithProviders(<AdminDemoPage />);
    const buttons = await screen.findAllByRole("button", { name: "Make house club" });
    expect(buttons[1]).toBeDisabled();  // Arsenal: in use
    await userEvent.click(buttons[0]);
    await waitFor(() => expect(api.patch).toHaveBeenCalledWith("/admin/demo/clubs/c1",
      { id: "c1", house_club: true, personality: "fair", reason: "For the Friday demo" }));
  });

  it("resets a running demo after asking", async () => {
    renderWithProviders(<AdminDemoPage />);
    await userEvent.click(await screen.findByRole("button", { name: "Reset" }));
    await waitFor(() => expect(api.post).toHaveBeenCalledWith("/admin/demo/runs/r1/reset"));
  });

  it("says when demo mode is off on the server", async () => {
    api.get.mockResolvedValue({ data: { ...overview, enabled: false } });
    renderWithProviders(<AdminDemoPage />);
    expect(await screen.findByText(/Demo mode is off on this server/)).toBeInTheDocument();
  });
});
