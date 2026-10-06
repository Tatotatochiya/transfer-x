import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import BoardPage from "./BoardPage";

const api = vi.hoisted(() => ({ get: vi.fn() }));
vi.mock("../../lib/api", () => ({ default: api }));

const card = (side: "BUYING" | "SELLING", name: string, column: string) => ({
  key: `${side}:${name}`, side, column, kind: "offer", entity_id: name, player_id: name, player_name: name,
  player_position: "MID", counterparty: side === "BUYING" ? "Arsenal" : "Leeds", amount: 1_000_000,
  detail: "Waiting on them", whose_move: "theirs", deadline: null, link: "/offers/x", updated_at: null, others: 0,
});

const board = {
  columns: [
    { key: "talking", label: "Talking", cards: [card("BUYING", "K. Havertz", "talking"), card("SELLING", "Á. Pécsi", "talking")] },
    { key: "agreed", label: "Agreed", cards: [] },
  ],
  closed: [],
  counts: { buying: 1, selling: 1, your_move: 0 },
};

function renderBoard(path: string) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}><MemoryRouter initialEntries={[path]}><BoardPage /></MemoryRouter></QueryClientProvider>);
}

describe("BoardPage", () => {
  beforeEach(() => api.get.mockReset().mockResolvedValue({ data: board }));

  it("splits both sides into a Buying lane and a Selling lane", async () => {
    renderBoard("/board?side=BOTH");
    const buying = await screen.findByRole("region", { name: "Buying" });
    const selling = screen.getByRole("region", { name: "Selling" });
    expect(within(buying).getByText("K. Havertz")).toBeInTheDocument();
    expect(within(buying).queryByText("Á. Pécsi")).not.toBeInTheDocument();
    expect(within(selling).getByText("Á. Pécsi")).toBeInTheDocument();
    expect(within(selling).queryByText("K. Havertz")).not.toBeInTheDocument();
  });

  it("shows one set of columns for a single side", async () => {
    api.get.mockResolvedValue({ data: { ...board, columns: [{ ...board.columns[0], cards: [board.columns[0].cards[0]] }, board.columns[1]] } });
    renderBoard("/board?side=BUYING");
    expect(await screen.findByText("K. Havertz")).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Buying" })).not.toBeInTheDocument();
  });
});
