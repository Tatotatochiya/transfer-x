import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import LiteSentPage, { type HeldActionView } from "./LiteSentPage";

const api = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }));
vi.mock("../../lib/api", () => ({ default: api }));
vi.mock("../../hooks/useLite", () => ({ useLiteHome: () => ({ data: { money: { transfer_remaining: 14e6, transfer_budget: 40e6 } } }) }));

const held = (over: Partial<HeldActionView> = {}): HeldActionView => ({
  id: "a1", kind: "bid", status: "HELD", execute_at: new Date(Date.now() + 8000).toISOString(),
  result: null, error: null,
  progress: {
    title: "Bid sent to Brentwell Town", subline: "£8m for Ellis Varga.", seconds_left: 8,
    steps: [
      { label: "You approved it", state: "done", hint: null },
      { label: "Bid sent", state: "current", hint: "Sending in 8 seconds" },
      { label: "Waiting for Brentwell Town to reply", state: "future", hint: null },
      { label: "Medical and personal terms", state: "future", hint: null },
      { label: "Signed", state: "future", hint: null },
    ],
  },
  ...over,
});

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[{ pathname: "/lite/actions/a1", state: { back: "/lite/bid?player_id=p1&fee=8000000" } }]}>
        <Routes>
          <Route path="/lite/actions/:actionId" element={<LiteSentPage />} />
          <Route path="/lite/bid" element={<p>The card, filled in</p>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("LiteSentPage", () => {
  beforeEach(() => {
    api.get.mockReset();
    api.post.mockReset();
  });

  it("shows the plain steps and an undo bar counting down", async () => {
    api.get.mockResolvedValue({ data: held() });
    renderPage();
    expect(await screen.findByText("Bid sent to Brentwell Town")).toBeInTheDocument();
    expect(screen.getByText("Sending in 8 seconds")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^Undo · \d+s$/ })).toBeInTheDocument();
    expect(screen.getByText("Bid sent").closest("li")).toHaveAttribute("aria-current", "step");
  });

  it("undoes: says nothing was sent, then returns to the filled-in card", async () => {
    api.get.mockResolvedValue({ data: held() });
    api.post.mockResolvedValue({ data: held({ status: "CANCELLED" }) });
    renderPage();
    await userEvent.click(await screen.findByRole("button", { name: /^Undo/ }));
    expect(api.post).toHaveBeenCalledWith("/lite/actions/a1/undo");
    expect(await screen.findByText("Cancelled. Nothing was sent.")).toBeInTheDocument();
    expect(await screen.findByText("The card, filled in", {}, { timeout: 4000 })).toBeInTheDocument();
  });

  it("once sent there's no undo bar, and a failed send says why", async () => {
    api.get.mockResolvedValue({ data: held({ status: "FAILED", error: "This offer has already been withdrawn.",
      progress: { title: "Not sent", subline: "This offer has already been withdrawn.", seconds_left: null,
        steps: [{ label: "You approved it", state: "done", hint: null }, { label: "Not sent: it was refused", state: "ended", hint: null }] } }) });
    renderPage();
    expect(await screen.findByText("Not sent")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^Undo/ })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Back to the card" })).toBeInTheDocument();
  });
});
