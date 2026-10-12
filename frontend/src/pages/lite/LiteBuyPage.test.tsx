import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, screen } from "@testing-library/react";
import { Route, Routes } from "react-router-dom";
import { renderWithProviders } from "../../test/utils";
import { LiteBuyPositionPage, LiteBuyResultsPage } from "./LiteBuyPage";

const state = vi.hoisted(() => ({
  search: { players: [] as Record<string, unknown>[] },
  pages: [] as Record<string, unknown>[][],
  hasNextPage: false,
  fetchNextPage: vi.fn(),
  searchedFor: [] as string[],
}));
vi.mock("../../hooks/useDebounce", () => ({ useDebounce: (v: string) => v }));
vi.mock("../../hooks/useLite", () => ({
  useLiteSquadCounts: () => ({ data: { counts: { GK: 2, DEF: 0, MID: 5, FWD: 3 } } }),
  useLiteHome: () => ({ data: undefined }),
  useTeamContact: () => ({ data: { name: "Sam", label: "Sam" } }),
  useLiteBuySearch: (q: string) => {
    state.searchedFor.push(q);
    return q.trim().length >= 2 ? { data: { q, ...state.search }, isFetching: false, isError: false } : { data: undefined };
  },
  useLiteCandidates: () => ({
    data: { pages: state.pages.map((players) => ({ players })) },
    isLoading: false, isError: false, hasNextPage: state.hasNextPage,
    fetchNextPage: state.fetchNextPage, isFetchingNextPage: false,
  }),
}));
vi.mock("../../context/ToastContext", () => ({ useToast: () => ({ addToast: vi.fn() }) }));
vi.mock("../../lib/api", () => ({ default: { put: vi.fn(() => Promise.resolve()), post: vi.fn(), get: vi.fn() } }));

const row = (over: Record<string, unknown>) => ({
  player_id: "p", name: "Someone", age: 25, position: "DEF", club: "Selling FC", state: "buyable",
  price: 7_000_000, price_basis: "model", offer_id: null, note: null, ...over,
});

const candidate = (i: number) => ({
  player_id: `c${i}`, name: `Candidate ${i}`, age: 24, position: "DEF", club: "Selling FC", free_agent: false,
  price: 4_000_000, price_basis: "listed", sale_id: null, wage_weekly: null, reason: "Fits.",
});

describe("Lite Buy step 1: search by name", () => {
  beforeEach(() => { state.searchedFor = []; });

  it("asks who you're looking for, with the positions still below", () => {
    renderWithProviders(<Routes><Route path="/lite/buy" element={<LiteBuyPositionPage />} /></Routes>, { initialPath: "/lite/buy" });
    expect(screen.getByRole("heading", { name: "Who are you looking for?" })).toBeInTheDocument();
    expect(screen.getByRole("searchbox", { name: /search players by name/i })).toBeInTheDocument();
    expect(screen.getByText("Or tell us what you need")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Defender/ })).toHaveTextContent("You have none");
  });

  it("shows what can be done with each player, or why not", () => {
    state.search = { players: [
      row({ player_id: "b", name: "Buyable Ben" }),
      row({ player_id: "o", name: "Offered Olly", state: "offer_in", price: null, offer_id: "off1", note: "You already have an offer in for him." }),
      row({ player_id: "f", name: "Free Fred", state: "free_agent", club: null, price: 0, price_basis: "free agent" }),
      row({ player_id: "x", name: "Elsewhere Eddie", state: "outside", club: "Real Somewhere", price: null, note: "His club isn't on TransferX, so there's no one to send an offer to." }),
      row({ player_id: "y", name: "My Own Man", state: "yours", price: null, note: "He's already your player." }),
    ] };
    renderWithProviders(<Routes><Route path="/lite/buy" element={<LiteBuyPositionPage />} /></Routes>, { initialPath: "/lite/buy?q=man" });
    const items = screen.getAllByRole("listitem");
    expect(items).toHaveLength(5);
    expect(items[0]).toHaveTextContent("£7m (our estimate)");
    expect(items[0]).toHaveTextContent("Make an offer");
    expect(screen.getByRole("link", { name: "See your offer" })).toHaveAttribute("href", "/lite/offers/off1");
    expect(screen.getByRole("link", { name: "See how to sign him" })).toHaveAttribute("href", "/players/market/f");
    expect(items[3]).toHaveTextContent("Real Somewhere");
    expect(items[3]).toHaveTextContent("Ask Sam about him");
    expect(items[4]).toHaveTextContent("He's already your player.");
    expect(items[4].querySelector("button")).toBeNull();
  });

  it("keeps the search in the URL and says when no one matches", () => {
    state.search = { players: [] };
    renderWithProviders(<Routes><Route path="/lite/buy" element={<LiteBuyPositionPage />} /></Routes>, { initialPath: "/lite/buy" });
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "Zzz" } });
    expect(screen.getByRole("searchbox")).toHaveValue("Zzz");
    expect(state.searchedFor).toContain("Zzz");
    expect(screen.getByText(/No one called/)).toHaveTextContent("No one called “Zzz”");
  });
});

describe("Lite Buy results: Show more", () => {
  beforeEach(() => { state.fetchNextPage.mockClear(); });

  it("lists every page fetched and offers the next three while there are more", () => {
    state.pages = [[candidate(1), candidate(2), candidate(3)], [candidate(4)]];
    state.hasNextPage = true;
    renderWithProviders(<Routes><Route path="/lite/buy/results" element={<LiteBuyResultsPage />} /></Routes>,
      { initialPath: "/lite/buy/results?position=DEF&budget=0-5" });
    expect(screen.getByRole("heading", { name: "4 players who fit" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Show 3 more" }));
    expect(state.fetchNextPage).toHaveBeenCalledTimes(1);
  });

  it("hides Show more at the end of the list", () => {
    state.pages = [[candidate(1)]];
    state.hasNextPage = false;
    renderWithProviders(<Routes><Route path="/lite/buy/results" element={<LiteBuyResultsPage />} /></Routes>,
      { initialPath: "/lite/buy/results?position=DEF&budget=0-5" });
    expect(screen.queryByRole("button", { name: "Show 3 more" })).not.toBeInTheDocument();
  });
});
