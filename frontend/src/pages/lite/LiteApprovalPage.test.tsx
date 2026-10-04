import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import LiteApprovalPage from "./LiteApprovalPage";

const api = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }));
vi.mock("../../lib/api", () => ({ default: api }));
const caps = vi.hoisted(() => ({ decide: true }));
vi.mock("../../hooks/useClubCapabilities", () => ({ useClubCapabilities: () => ({ can: () => caps.decide }) }));
vi.mock("../../hooks/useClubDashboard", () => ({
  CLUB_DASHBOARD_KEY: ["clubs", "me", "dashboard"],
  useClubDashboard: () => ({ data: { waiting_on_you: [
    { kind: "approval", id: "a1", link: "/club/approvals?id=a1", reason: "" },
    { kind: "offer", id: "o2", link: "/offers/o2", reason: "" },
  ] } }),
}));

const approval = {
  id: "a1", club_id: "c", action_type: "PLACE_BID", amount: 6000000, requested_by_user_id: "u2",
  requested_by_email: "mia@club.test", requested_by_name: "Mia Lopez", status: "PENDING", decided_by_user_id: null,
  decided_at: null, failure_reason: null, created_at: "2026-10-04T08:00:00Z",
  expires_at: new Date(Date.now() + 5 * 3600_000).toISOString(), summary: "Bid on Ellis Varga — £6,000,000",
  player_id: "p1", player_name: "Ellis Varga", budget_after: 12000000,
};

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/lite/approvals/a1?from=push"]}>
        <Routes><Route path="/lite/approvals/:id" element={<LiteApprovalPage />} /></Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("LiteApprovalPage", () => {
  beforeEach(() => {
    api.get.mockReset().mockResolvedValue({ data: approval });
    api.post.mockReset().mockResolvedValue({ data: {} });
    caps.decide = true;
  });

  it("shows what is asked, who asked, the budget after and the queue", async () => {
    renderPage();
    expect(await screen.findByText("Bid on Ellis Varga — £6,000,000")).toBeInTheDocument();
    expect(screen.getByText("Mia Lopez")).toBeInTheDocument();
    expect(screen.getByText("£12m")).toBeInTheDocument();
    expect(screen.getByText(/5 hours left|4 hours left/)).toBeInTheDocument();
    expect(screen.getByText("Waiting on you · 1 of 2")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Next ›" })).toHaveAttribute("href", "/lite/offers/o2?from=push");
  });

  it("asks once more before approving, and declines with a reason", async () => {
    renderPage();
    await userEvent.click(await screen.findByRole("button", { name: "Approve" }));
    expect(screen.getByText(/no undo/)).toBeInTheDocument();
    expect(api.post).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Back" }));
    await userEvent.click(screen.getByRole("button", { name: "Decline" }));
    await userEvent.type(screen.getByRole("textbox"), "Too much for a backup");
    await userEvent.click(screen.getByRole("button", { name: "Decline" }));
    await waitFor(() => expect(api.post).toHaveBeenCalledWith("/clubs/me/approvals/a1/reject", { reason: "Too much for a backup" }));
    expect(await screen.findByText("Declined")).toBeInTheDocument();
  });

  it("says who decides when you can't", async () => {
    caps.decide = false;
    renderPage();
    expect(await screen.findByText(/Waiting for the owner or sporting director/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Approve" })).not.toBeInTheDocument();
  });
});
