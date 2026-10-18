import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, screen, within } from "@testing-library/react";
import { Route, Routes } from "react-router-dom";
import { renderWithProviders } from "../../test/utils";
import { LiteBuyPage } from "./LiteBuyPage";

const state = vi.hoisted(() => ({
  search: { players: [] as Record<string, unknown>[] },
  targets: { players: [] as Record<string, unknown>[], total: 0 },
  searchedFor: [] as string[],
  shortlist: vi.fn(),
}));
vi.mock("../../hooks/useDebounce", () => ({ useDebounce: (v: string) => v }));
vi.mock("../../hooks/useLite", () => ({
  useTeamContact: () => ({ data: { name: "Sam", label: "Sam" } }),
  useLiteBuySearch: (q: string) => {
    state.searchedFor.push(q);
    return q.trim().length >= 2 ? { data: { q, ...state.search }, isFetching: false, isError: false } : { data: undefined };
  },
  useLiteBuyTargets: () => ({ data: state.targets, isLoading: false, isError: false }),
  useLiteShortlist: () => ({ mutate: state.shortlist, isPending: false }),
}));
vi.mock("../../context/ToastContext", () => ({ useToast: () => ({ addToast: vi.fn() }) }));
vi.mock("../../lib/api", () => ({ default: { put: vi.fn(() => Promise.resolve()), post: vi.fn(), get: vi.fn() } }));

const row = (over: Record<string, unknown>) => ({
  player_id: "p", name: "Someone", age: 25, position: "DEF", club: "Selling FC", state: "buyable",
  price: 7_000_000, price_basis: "model", offer_id: null, note: null, shortlisted: false, ...over,
});

const page = (path = "/lite/buy") =>
  renderWithProviders(<Routes><Route path="/lite/buy" element={<LiteBuyPage />} /></Routes>, { initialPath: path });

describe("Lite Buy: search by name", () => {
  beforeEach(() => { state.searchedFor = []; state.shortlist.mockClear(); });

  it("asks who you're looking for, with no guided steps", () => {
    page();
    expect(screen.getByRole("heading", { name: "Who are you looking for?" })).toBeInTheDocument();
    expect(screen.getByRole("searchbox", { name: /search players by name/i })).toBeInTheDocument();
    expect(screen.queryByText("Or tell us what you need")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Ask TransferX/ })).toHaveAttribute("href", "/lite/ask");
    expect(screen.getByRole("link", { name: /Browse all players/ })).toHaveAttribute("href", "/players/market");
  });

  it("shows what can be done with each player, or why not", () => {
    state.search = { players: [
      row({ player_id: "b", name: "Buyable Ben" }),
      row({ player_id: "o", name: "Offered Olly", state: "offer_in", price: null, offer_id: "off1", note: "You already have an offer in for him." }),
      row({ player_id: "f", name: "Free Fred", state: "free_agent", club: null, price: 0, price_basis: "free agent" }),
      row({ player_id: "x", name: "Elsewhere Eddie", state: "outside", club: "Real Somewhere", price: null, note: "His club isn't on TransferX, so there's no one to send an offer to." }),
      row({ player_id: "y", name: "My Own Man", state: "yours", price: null, note: "He's already your player." }),
    ] };
    page("/lite/buy?q=man");
    const items = within(screen.getByRole("list", { name: "Players found" })).getAllByRole("listitem");
    expect(items).toHaveLength(5);
    expect(items[0]).toHaveTextContent("£7m (our estimate)");
    expect(items[0]).toHaveTextContent("Make an offer");
    expect(screen.getByRole("link", { name: "See your offer" })).toHaveAttribute("href", "/lite/offers/off1");
    expect(screen.getByRole("link", { name: "See how to sign him" })).toHaveAttribute("href", "/players/market/f");
    expect(items[3]).toHaveTextContent("Real Somewhere");
    expect(items[3]).toHaveTextContent("Ask Sam about him");
    expect(items[4]).toHaveTextContent("He's already your player.");
    expect(items[4].querySelector("button")).toBeNull();  // no shortlisting your own player
    // The shortlist hides while searching.
    expect(screen.queryByRole("heading", { name: "Your shortlist" })).not.toBeInTheDocument();
  });

  it("puts a player on the shortlist from the search", () => {
    state.search = { players: [row({ player_id: "b", name: "Buyable Ben" })] };
    page("/lite/buy?q=ben");
    fireEvent.click(screen.getByRole("button", { name: "Shortlist" }));
    expect(state.shortlist).toHaveBeenCalledWith({ playerId: "b", on: true }, expect.anything());
  });

  it("keeps the search in the URL and says when no one matches", () => {
    state.search = { players: [] };
    page();
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "Zzz" } });
    expect(screen.getByRole("searchbox")).toHaveValue("Zzz");
    expect(state.searchedFor).toContain("Zzz");
    expect(screen.getByText(/No one called/)).toHaveTextContent("No one called “Zzz”");
  });
});

describe("Lite Buy: your shortlist", () => {
  beforeEach(() => { state.shortlist.mockClear(); });

  it("lists the club's targets, each with what it can do, and takes one off", () => {
    state.targets = { players: [row({ player_id: "t", name: "Target Tom", shortlisted: true, on_shortlists: ["Shortlist"] })], total: 1 };
    page();
    const list = screen.getByRole("list", { name: "Your shortlist" });
    expect(list).toHaveTextContent("Target Tom");
    expect(list).toHaveTextContent("Make an offer");
    const off = screen.getByRole("button", { name: /On your shortlist/ });
    expect(off).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(off);
    expect(state.shortlist).toHaveBeenCalledWith({ playerId: "t", on: false }, expect.anything());
  });

  it("says how to fill an empty shortlist", () => {
    state.targets = { players: [], total: 0 };
    page();
    expect(screen.getByText(/No one on it yet/)).toBeInTheDocument();
  });

  it("points to Scouting when there are more than it shows", () => {
    state.targets = { players: [row({ player_id: "t", name: "Target Tom", shortlisted: true })], total: 60 };
    page();
    expect(screen.getByRole("link", { name: /See all 60 in Scouting/ })).toHaveAttribute("href", "/scouting/shortlists");
  });
});
