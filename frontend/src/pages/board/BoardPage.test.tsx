import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, useLocation } from "react-router-dom";
import BoardPage from "./BoardPage";

const api = vi.hoisted(() => ({ get: vi.fn() }));
vi.mock("../../lib/api", () => ({ default: api }));
// The pop-up's conversation fetches its own data; not this page's concern.
vi.mock("../../components/conversation/ConversationPanel", () => ({ default: () => <p>Conversation</p> }));

const card = (side: "BUYING" | "SELLING", name: string, column: string) => ({
  key: `${side}:${name}`, side, column, kind: "offer", entity_id: name, player_id: name, player_name: name,
  player_position: "MID", counterparty: side === "BUYING" ? "Arsenal" : "Leeds", amount: 1_000_000,
  detail: "Waiting on them", whose_move: "theirs", deadline: null, link: `/offers/${name}`, updated_at: null, others: 0,
});

const board = {
  columns: [
    { key: "talking", label: "Listed", cards: [card("BUYING", "K. Havertz", "talking"), card("SELLING", "Á. Pécsi", "talking")] },
    { key: "agreed", label: "Agreed", cards: [] },
  ],
  closed: [],
  counts: { buying: 1, selling: 1, your_move: 0 },
};

let location = "";
function Where() {
  const l = useLocation();
  location = l.pathname + l.search;
  return null;
}

function renderBoard(path: string) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}><MemoryRouter initialEntries={[path]}><BoardPage /><Where /></MemoryRouter></QueryClientProvider>);
}

// ── Below 1280px: the list (jsdom's matchMedia matches nothing) ──────────────

const listBoard = {
  columns: [
    { key: "talking", label: "Listed", cards: [{ ...card("BUYING", "T. Talk", "talking"), kind: "enquiry", link: "/enquiries/t" }] },
    { key: "offers", label: "Offers", cards: [
      { ...card("SELLING", "G. Słonina", "offers"), whose_move: "your", detail: "Countered · your move", link: "/offers/g" },
      { ...card("SELLING", "L. Listed", "offers"), kind: "listing", counterparty: null, detail: "Listed", link: "/sales/l" },
    ] },
    { key: "fee_agreed", label: "Fee agreed", cards: [] },
    { key: "terms", label: "Personal terms", cards: [{ ...card("BUYING", "P. Terms", "terms"), kind: "deal", detail: "Personal terms", link: "/deals/p" }] },
    { key: "paperwork", label: "Paperwork", cards: [] },
    { key: "done", label: "Completed", cards: [{ ...card("BUYING", "D. Done", "done"), kind: "deal", detail: "Transfer complete", link: "/deals/d" }] },
  ],
  closed: [],
  counts: { buying: 3, selling: 2, your_move: 1 },
};

describe("BoardPage list (below 1280px)", () => {
  beforeEach(() => {
    api.get.mockReset().mockResolvedValue({ data: listBoard });
    try { localStorage.clear(); } catch { /* none */ }
  });

  it("groups by whose move it is, in order, with counts, and each row is a link", async () => {
    renderBoard("/board?side=BOTH");
    const headings = await screen.findAllByRole("heading", { level: 2 });
    expect(headings.map((h) => h.textContent)).toEqual([
      "Waiting on you1", "In progress2nothing for you yet", "Listed, no offers yet1", "Completed1"]);
    expect(screen.getByText("Waiting on you").className).toContain("text-danger-text");
    const row = screen.getByRole("link", { name: /^G\. Słonina, Selling to Leeds/ });
    expect(row).toHaveAttribute("href", "/offers/g");
    expect(screen.getByRole("link", { name: /^T\. Talk/ })).toHaveAttribute("href", "/enquiries/t");
    expect(screen.getByRole("img", { name: "Stage 4 of 5: Personal terms" })).toBeInTheDocument();
    // A detail that only repeats the stage isn't shown twice.
    expect(within(screen.getByRole("link", { name: /^P\. Terms/ })).getAllByText(/Personal terms/)).toHaveLength(1);
  });

  it("stage chips show only stages with transfers, filter, and write ?stage=", async () => {
    renderBoard("/board?side=BOTH");
    const chips = await screen.findByRole("radiogroup", { name: "Stage" });
    expect(within(chips).getAllByRole("radio").map((c) => c.textContent)).toEqual(["All5", "Listed1", "Offers2", "Personal terms1"]);
    await userEvent.click(within(chips).getByRole("radio", { name: /Offers/ }));
    expect(location).toContain("stage=offers");
    expect(screen.queryByRole("link", { name: /^T\. Talk/ })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /^G\. Słonina/ })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Show all 5" }));
    expect(location).not.toContain("stage=");
    expect(screen.getByRole("link", { name: /^T\. Talk/ })).toBeInTheDocument();
  });

  it("search filters the rows, and says so when nothing matches", async () => {
    renderBoard("/board?side=BOTH");
    await userEvent.click(await screen.findByRole("button", { name: "Find a player or club" }));
    await userEvent.type(screen.getByRole("searchbox"), "terms");
    expect(screen.getByRole("link", { name: /^P\. Terms/ })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /^G\. Słonina/ })).not.toBeInTheDocument();
    await userEvent.clear(screen.getByRole("searchbox"));
    await userEvent.type(screen.getByRole("searchbox"), "zzz");
    expect(screen.getByText(/No transfers match/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Clear search" }));
    expect(screen.getByRole("link", { name: /^G\. Słonina/ })).toBeInTheDocument();
  });

  it("the side switch is remembered and refetches", async () => {
    renderBoard("/board");
    await screen.findByRole("radiogroup", { name: "Show" });
    await userEvent.click(screen.getByRole("radio", { name: "Selling" }));
    expect(localStorage.getItem("transferx-board-side")).toBe("SELLING");
    expect(api.get).toHaveBeenLastCalledWith("/board", { params: { side: "SELLING" } });
  });

  it("New listing and History are in the ⋯ menu", async () => {
    renderBoard("/board");
    await userEvent.click(await screen.findByRole("button", { name: "More" }));
    expect(screen.getByRole("menuitem", { name: "+ New listing" })).toHaveAttribute("href", "/sales/new");
    expect(screen.getByRole("menuitem", { name: "History" })).toHaveAttribute("href", "/board/history");
  });
});

// ── From 1280px: the board ────────────────────────────────────────────────────

describe("BoardPage board (from 1280px)", () => {
  const original = window.matchMedia;
  beforeEach(() => {
    window.matchMedia = vi.fn().mockImplementation((query: string) => ({
      matches: query === "(min-width: 1280px)" || query === "(min-width: 640px)", media: query, onchange: null,
      addListener: vi.fn(), removeListener: vi.fn(), addEventListener: vi.fn(), removeEventListener: vi.fn(), dispatchEvent: vi.fn(),
    })) as unknown as typeof window.matchMedia;
    api.get.mockReset().mockResolvedValue({ data: board });
  });
  afterEach(() => { window.matchMedia = original; });

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

  it("a column empty in every lane collapses to a strip; one with a card in either lane doesn't", async () => {
    renderBoard("/board?side=BOTH");
    await screen.findByRole("region", { name: "Buying" });
    expect(screen.getAllByRole("region", { name: "Agreed: none" })).toHaveLength(2);
    // Talking has a card in each lane, and stays open in both.
    expect(screen.getAllByRole("region", { name: "Listed" })).toHaveLength(2);
    const oneLane = { ...board, columns: [{ ...board.columns[0], cards: [board.columns[0].cards[0]] }, board.columns[1]] };
    api.get.mockResolvedValue({ data: oneLane });
    await userEvent.click(screen.getByRole("radio", { name: "Buying" }));
    await userEvent.click(screen.getByRole("radio", { name: "Both" }));
    expect(await screen.findAllByRole("region", { name: "Listed" })).toHaveLength(2);
  });

  it("the waiting strip lists your-move cards and opens the pop-up; it's absent with none", async () => {
    const mine = { ...card("SELLING", "D. Mukasa", "talking"), whose_move: "your", detail: "Offer received · your move" };
    api.get.mockResolvedValue({ data: { ...board, columns: [{ key: "talking", label: "Listed", cards: [mine] }], counts: { buying: 0, selling: 1, your_move: 1 } } });
    renderBoard("/board?side=BOTH");
    const strip = await screen.findByRole("region", { name: "Waiting on you" });
    expect(strip).toHaveTextContent("D. Mukasa · Offer received");
    await userEvent.click(within(strip).getByRole("button"));
    expect(await screen.findByRole("dialog")).toHaveTextContent("Open the offer");
  });

  it("has no waiting strip when nothing is your move, and no Filters-style list controls", async () => {
    renderBoard("/board?side=BOTH");
    await screen.findByRole("region", { name: "Buying" });
    expect(screen.queryByRole("region", { name: "Waiting on you" })).not.toBeInTheDocument();
    expect(screen.queryByRole("radiogroup", { name: "Stage" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "History" })).toBeInTheDocument();
  });
});

describe("BoardPage colours", () => {
  const original = window.matchMedia;
  beforeEach(() => {
    window.matchMedia = vi.fn().mockImplementation((query: string) => ({
      matches: true, media: query, onchange: null,
      addListener: vi.fn(), removeListener: vi.fn(), addEventListener: vi.fn(), removeEventListener: vi.fn(), dispatchEvent: vi.fn(),
    })) as unknown as typeof window.matchMedia;
  });
  afterEach(() => { window.matchMedia = original; });

  it("your move is red, chased cards say so in red, and the other side's stalled cards are amber", async () => {
    const mine = { ...card("SELLING", "D. Mukasa", "talking"), whose_move: "your", detail: "Offer received · your move", chased: "ESCALATED" };
    const stalled = { ...card("BUYING", "L. Hall", "talking"), whose_move: "their", updated_at: new Date(Date.now() - 5 * 86_400_000).toISOString() };
    api.get.mockReset().mockResolvedValue({ data: { ...board, columns: [{ key: "talking", label: "Listed", cards: [mine, stalled] }] } });
    render(<QueryClientProvider client={new QueryClient()}><MemoryRouter initialEntries={["/board?side=BOTH"]}><BoardPage /></MemoryRouter></QueryClientProvider>);

    expect((await screen.findByText("Offer received · your move")).className).toContain("text-danger-text");
    expect(screen.getByLabelText("Your move").className).toContain("bg-danger");
    expect(screen.getByText("Escalated").className).toContain("bg-danger-bg");
    expect(screen.getByText("Stalled · 5 days").className).toContain("bg-warning-bg");
    expect(document.querySelector(".text-accent.font-semibold")).toBeNull();
  });
});

describe("BoardPage ⋯ menu", () => {
  it("New listing is accent text: something you can do", async () => {
    api.get.mockReset().mockResolvedValue({ data: board });
    renderBoard("/board");
    await userEvent.click(await screen.findByRole("button", { name: "More" }));
    const item = screen.getByRole("menuitem", { name: "+ New listing" });
    expect(item.className).toContain("text-accent");
    expect(item.className).not.toMatch(/(^|\s)text-text(\s|$)/);
  });
});
