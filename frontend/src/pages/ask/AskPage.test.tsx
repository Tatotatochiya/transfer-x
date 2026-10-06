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

const chart = {
  ...answer,
  answer: "Isak scores more often; Havertz creates more.",
  blocks: [{
    type: "chart", kind: "bar", title: "Isak vs Havertz", x: "player", y: ["goals_per90", "assists_per90"],
    rows: [{ player: "A. Isak", goals_per90: 0.62, assists_per90: 0.12 }, { player: "K. Havertz", goals_per90: 0.41, assists_per90: 0.2 }],
    source: { tool: "compare_players", label: "Player comparison", filters: {}, as_of: "2026-10-06T20:40:00+00:00", note: null },
  }],
};

function renderPage(path = "/ask") {
  sessionStorage.clear();
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}><MemoryRouter initialEntries={[path]}><AskPage /></MemoryRouter></QueryClientProvider>);
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

  it("draws a chart block as bars with a legend", async () => {
    api.post.mockResolvedValue({ data: chart });
    renderPage();
    await userEvent.type(screen.getByLabelText("Your question"), "compare Isak and Havertz");
    await userEvent.click(screen.getByRole("button", { name: "Ask" }));
    expect(await screen.findByText("Isak vs Havertz")).toBeInTheDocument();
    expect(screen.getByText("Goals/90")).toBeInTheDocument();
    expect(screen.getByText("K. Havertz")).toBeInTheDocument();
    expect(screen.getByText("0.62")).toBeInTheDocument();
  });

  it("exports a table to Excel through the server", async () => {
    renderPage();
    URL.createObjectURL = vi.fn(() => "blob:x");
    URL.revokeObjectURL = vi.fn();
    await userEvent.type(screen.getByLabelText("Your question"), "who is out of contract soon?");
    await userEvent.click(screen.getByRole("button", { name: "Ask" }));
    api.post.mockResolvedValueOnce({ data: new Blob(["x"]) });
    await userEvent.click(await screen.findByRole("button", { name: "Excel" }));
    await waitFor(() => expect(api.post).toHaveBeenLastCalledWith("/ai/analyst/export", expect.objectContaining({
      title: "Expiring contracts", columns: ["player", "contract_ends", "wage_weekly"],
    }), { responseType: "blob" }));
  });

  it("asks about the page it was opened from", async () => {
    renderPage("/ask?about=player&id=p9&name=K.%20Havertz");
    expect(screen.getByText("About K. Havertz")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Tell me about K. Havertz" }));
    await waitFor(() => expect(api.post).toHaveBeenLastCalledWith("/ai/analyst", {
      question: "Tell me about K. Havertz", history: [], context: { type: "player", id: "p9" },
    }));
  });
});
