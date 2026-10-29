import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../../test/utils";
import AdminDealsPage from "./AdminDealsPage";

const api = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }));
vi.mock("../../lib/api", () => ({ default: api }));
const askReason = vi.hoisted(() => vi.fn());
vi.mock("../../context/ConfirmContext", () => ({ useAskReason: () => askReason, useConfirm: () => vi.fn() }));
vi.mock("../../components/admin/ObligationDecisionsPanel", () => ({ default: () => null }));

const deal = (over: Record<string, unknown>) => ({
  id: "d1", player: { id: "p", name: "D. Rice", position: "MID" }, buyer_club: { id: "l", name: "Liverpool" },
  seller_club: { id: "a", name: "Arsenal" }, agreed_fee: 45_000_000, status: "COMPLETED", stage: "COMPLETED",
  created_at: "2026-09-30T10:00:00Z", completed_at: "2026-09-30T12:00:00Z", is_test: false, ...over,
});

describe("AdminDealsPage test transfers", () => {
  beforeEach(() => {
    api.get.mockReset().mockResolvedValue({ data: { items: [deal({}), deal({ id: "d2", status: "IN_PROGRESS", stage: "PAPERWORK" }),
      deal({ id: "d3", is_test: true, player: { id: "q", name: "B. Saka", position: "FWD" } })], total: 3, page: 1, page_size: 30 } });
    api.post.mockReset().mockResolvedValue({ data: {} });
    askReason.mockReset().mockResolvedValue("Made while testing");
  });

  it("marks a completed transfer as a test, with a reason, and shows which are", async () => {
    renderWithProviders(<AdminDealsPage />);
    const rice = (await screen.findAllByText("D. Rice"))[0].closest("tr")!;
    await userEvent.click(within(rice).getByRole("button", { name: "Mark as test" }));
    await waitFor(() => expect(api.post).toHaveBeenCalledWith("/admin/deals/d1/test", { is_test: true, reason: "Made while testing" }));
    const saka = screen.getByText("B. Saka").closest("tr")!;
    expect(within(saka).getByText("Test")).toBeInTheDocument();
    expect(within(saka).getByRole("button", { name: "Not a test" })).toBeInTheDocument();
    // Only completed transfers can be marked.
    const open = screen.getAllByText("D. Rice")[1].closest("tr")!;
    expect(within(open).queryByRole("button", { name: "Mark as test" })).not.toBeInTheDocument();
  });
});
