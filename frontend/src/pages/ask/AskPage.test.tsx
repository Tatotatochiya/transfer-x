import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import AskPage from "./AskPage";

const api = vi.hoisted(() => ({ post: vi.fn() }));
vi.mock("../../lib/api", () => ({ default: api }));

const answer = {
  answer: "Five of our players are out of contract within 18 months.",
  blocks: [{
    type: "table", title: "Expiring contracts", kind: "squad", columns: ["player", "contract_ends", "wage_weekly"],
    rows: [{ player: "I. Konaté", player_id: "p1", photo_url: null, contract_ends: "2027-06-30", wage_weekly: 62500, path: "/players/market/p1" }],
    total: 5,
    source: { tool: "squad", label: "Your squad", filters: { contract_ends_within_months: 18, sort_by: "wage" }, as_of: "2026-10-06T20:40:00+00:00", note: null },
  }],
  follow_ups: ["Who are our top earners overall?"],
  proposal: null,
  links: [],
};

function renderPage() {
  sessionStorage.clear();
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}><MemoryRouter><AskPage /></MemoryRouter></QueryClientProvider>);
}

describe("AskPage", () => {
  beforeEach(() => api.post.mockReset().mockResolvedValue({ data: answer }));

  it("shows the answer, a table built from the rows, and where it came from", async () => {
    renderPage();
    await userEvent.type(screen.getByLabelText("Your question"), "who is out of contract soon?");
    await userEvent.click(screen.getByRole("button", { name: "Ask" }));
    expect(await screen.findByText(answer.answer)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /I. Konaté/ })).toHaveAttribute("href", "/players/market/p1");
    expect(screen.getByText("£62,500/wk")).toBeInTheDocument();
    expect(screen.getByText("Showing 1 of 5")).toBeInTheDocument();
    expect(screen.getByText(/Your squad · contract ends within 18 months, sorted by wage/)).toBeInTheDocument();
  });

  it("sends the conversation with a follow-up", async () => {
    renderPage();
    await userEvent.click(screen.getByRole("button", { name: /highest earners/ }));
    await userEvent.click(await screen.findByRole("button", { name: "Who are our top earners overall?" }));
    await waitFor(() => expect(api.post).toHaveBeenLastCalledWith("/ai/analyst", {
      question: "Who are our top earners overall?",
      history: [{ question: "Our highest earners whose contract ends within 18 months", answer: answer.answer }],
    }));
  });
});
