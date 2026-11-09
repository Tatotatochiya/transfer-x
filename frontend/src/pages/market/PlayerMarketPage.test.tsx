import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../../test/utils";
import { useAuthStore } from "../../store/auth";
import PlayerMarketPage from "./PlayerMarketPage";

const api = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn(), defaults: { baseURL: "" } }));
vi.mock("../../lib/api", () => ({ default: api }));
const confirm = vi.hoisted(() => vi.fn());
vi.mock("../../context/ConfirmContext", () => ({ useConfirm: () => confirm, useAskReason: () => vi.fn() }));
vi.mock("../../hooks/useClubCapabilities", () => ({ useClubCapabilities: () => ({ membership: null, can: () => false }) }));

type Params = Record<string, unknown>;

const player = (n: number, over: Record<string, unknown> = {}) => ({
  id: `p${n}`, name: `Player ${String(n).padStart(2, "0")}`, age: 20 + (n % 10), nationality: "Sweden", position: "MID",
  status: "CONTRACTED", open_to_offers: false, photo_url: null, team_name: "Elsewhere FC", current_club: null,
  world_team: null, market_value: null, wage_weekly: null, ...over,
});

const TOTAL = 60;
let views: unknown[] = [];

function marketPage(params: Params) {
  const page = Number(params.page);
  const size = Number(params.page_size);
  const total = params.position === "MID" ? 12 : TOTAL;
  const start = (page - 1) * size;
  const items = Array.from({ length: Math.max(0, Math.min(size, total - start)) }, (_, i) => player(start + i + 1));
  // Server order for the price sort: reversed, so a client-side sort would show.
  if (params.sort_by === "price") items.reverse();
  return { items, total, page, page_size: size };
}

function serve(url: string, config?: { params?: Params }) {
  const params = config?.params ?? {};
  if (url === "/players/market") return Promise.resolve({ data: marketPage(params) });
  if (url === "/clubs/me/search-views") return Promise.resolve({ data: views });
  if (url === "/clubs/me") {
    return Promise.resolve({ data: { id: "c1", name: "Ashfield United", finance: { transfer_remaining: 232_500_000, wage_remaining_weekly: 49_900_000 } } });
  }
  if (url === "/players/form/batch") return Promise.resolve({ data: {} });
  if (url === "/valuation/players") return Promise.resolve({ data: { valuations: {} } });
  return Promise.resolve({ data: [] });
}

const marketCalls = () => api.get.mock.calls.filter(([url, c]) => url === "/players/market" && (c?.params?.page_size ?? 0) > 1).map(([, c]) => c.params as Params);
const countCalls = () => api.get.mock.calls.filter(([url, c]) => url === "/players/market" && c?.params?.page_size === 1).map(([, c]) => c.params as Params);

const lastOf = <T,>(xs: T[]): T | undefined => xs[xs.length - 1];

/** The viewport width the page's media queries see. */
function viewport(width: number) {
  window.matchMedia = vi.fn().mockImplementation((query: string) => {
    const min = Number(/min-width:\s*(\d+)px/.exec(query)?.[1] ?? 0);
    return {
      matches: width >= min, media: query, onchange: null,
      addListener: vi.fn(), removeListener: vi.fn(), addEventListener: vi.fn(), removeEventListener: vi.fn(), dispatchEvent: vi.fn(),
    };
  });
}

function signIn(user_type: "CLUB" | "PLAYER" | null) {
  useAuthStore.setState(user_type
    ? { accessToken: "t", user: { id: "u", email: "sd@ashfield.test", user_type, is_superuser: false } as never }
    : { accessToken: null, user: null } as never);
}

describe("PlayerMarketPage, players first", () => {
  beforeEach(() => {
    views = [];
    viewport(390);
    signIn("CLUB");
    try { localStorage.clear(); } catch { /* none */ }
    api.get.mockReset().mockImplementation(serve);
    api.post.mockReset();
    confirm.mockReset().mockResolvedValue(true);
  });

  it("below 1024px: no rail; Filters opens a sheet with a live count, applying adds a chip and refetches page 1", async () => {
    renderWithProviders(<PlayerMarketPage />);
    expect(await screen.findByText("60 players")).toBeInTheDocument();
    expect(screen.queryByRole("complementary", { name: "Filters" })).toBeNull();

    await userEvent.click(screen.getByRole("button", { name: /^Filters/ }));
    const sheet = screen.getByRole("dialog", { name: "Filters" });
    expect(await within(sheet).findByRole("button", { name: "Show 60 players" })).toBeInTheDocument();

    await userEvent.click(within(sheet).getByRole("button", { name: "MID" }));
    expect(await within(sheet).findByRole("button", { name: "Show 12 players" }, { timeout: 2000 })).toBeInTheDocument();
    expect(lastOf(countCalls())).toMatchObject({ position: "MID", page_size: 1 });

    await userEvent.click(within(sheet).getByRole("button", { name: "Show 12 players" }));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(screen.getByRole("button", { name: "Remove filter MID" })).toBeInTheDocument();
    await waitFor(() => expect(lastOf(marketCalls())).toMatchObject({ position: "MID", page: 1 }));
  });

  it("closing the sheet with unapplied changes asks to discard them", async () => {
    confirm.mockResolvedValue(false);
    renderWithProviders(<PlayerMarketPage />);
    await userEvent.click(await screen.findByRole("button", { name: /^Filters/ }));
    const sheet = screen.getByRole("dialog", { name: "Filters" });
    await userEvent.click(within(sheet).getByRole("button", { name: "GK" }));
    await userEvent.click(within(sheet).getByRole("button", { name: "Close without applying" }));
    expect(confirm).toHaveBeenCalledWith(expect.objectContaining({ title: "Discard filter changes?" }));
    expect(screen.getByRole("dialog", { name: "Filters" })).toBeInTheDocument();
  });

  it("removing a chip refetches without that filter", async () => {
    views = [{ id: "v1", name: "Midfielders", is_default: true, filters: { position: "MID" } }];
    renderWithProviders(<PlayerMarketPage />);
    await userEvent.click(await screen.findByRole("button", { name: "Remove filter MID" }));
    await waitFor(() => expect(lastOf(marketCalls())).not.toHaveProperty("position"));
  });

  it("Sort → Cheapest asks the server for sort_by=price and shows its order unchanged", async () => {
    renderWithProviders(<PlayerMarketPage />);
    await screen.findByText("60 players");
    await userEvent.click(screen.getByRole("button", { name: /Sort: Name/ }));
    await userEvent.click(screen.getByRole("menuitemradio", { name: /Cheapest/ }));
    await waitFor(() => expect(lastOf(marketCalls())).toMatchObject({ sort_by: "price", sort_dir: "asc", page: 1 }));
    expect(screen.getByRole("button", { name: /Sort: Cheapest/ })).toBeInTheDocument();
    await waitFor(() => {
      const names = screen.getAllByRole("link").map((l) => l.textContent ?? "").filter((t) => t.includes("Player"));
      expect(names[0]).toContain("Player 40");
      expect(names[1]).toContain("Player 39");
    });
  });

  it("below 640px opens in list view; picking grid sticks on this device", async () => {
    const first = renderWithProviders(<PlayerMarketPage />);
    expect(await screen.findByRole("link", { name: /Player 01/ })).toHaveAttribute("href", "/players/market/p1");
    await userEvent.click(screen.getByRole("button", { name: "Switch to grid view" }));
    expect(localStorage.getItem("playerMarketView.phone")).toBe("grid");
    first.unmount();

    renderWithProviders(<PlayerMarketPage />);
    expect(await screen.findByRole("button", { name: "Switch to list view" })).toBeInTheDocument();
  });

  it("Show more requests page 2 and appends it", async () => {
    renderWithProviders(<PlayerMarketPage />);
    expect(await screen.findByText("Showing 40 of 60")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Show 20 more" }));
    expect(await screen.findByText("Showing 60 of 60")).toBeInTheDocument();
    expect(lastOf(marketCalls())).toMatchObject({ page: 2, page_size: 40 });
    expect(screen.getByRole("link", { name: /Player 01/ })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Player 60/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /more$/ })).toBeNull();
  });

  it("✦ Describe runs the AI search, shows how it read it, and Back restores the list", async () => {
    api.post.mockResolvedValue({ data: {
      total: 1,
      filters: { position: "DEF", min_age: null, max_age: 23, min_form_score: null, nationalities: null, min_height_cm: null, open_to_offers: null, interpreted_as: "young defenders" },
      players: [{ player_id: "n1", name: "Young Fullback", age: 21, position: "DEF", nationality: "Spain", current_club: "Valencia", form_score: 64, open_to_offers: false, price: 9_000_000, price_basis: "model", why: ["age 21", "defender"] }],
    } });
    renderWithProviders(<PlayerMarketPage />);
    await screen.findByText("60 players");
    await userEvent.click(screen.getByRole("button", { name: "✦ Describe" }));
    await userEvent.type(screen.getByRole("searchbox", { name: "Search players" }), "young left-back{Enter}");

    expect(api.post).toHaveBeenCalledWith("/ai/player-search", { query: "young left-back", buyable: true });
    expect(await screen.findByText("Interpreted as:")).toBeInTheDocument();
    expect(screen.getByText("age 21 · defender")).toBeInTheDocument();
    expect(screen.getByText("1 player found")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "← Back to all players" }));
    expect(await screen.findByRole("link", { name: /Player 01/ })).toBeInTheDocument();
  });

  it("from 1024px: a rail with saved views and filters, pagination, and no Filters button", async () => {
    viewport(1280);
    renderWithProviders(<PlayerMarketPage />);
    const rail = await screen.findByRole("complementary", { name: "Filters" });
    expect(within(rail).getByText("Saved views")).toBeInTheDocument();
    expect(within(rail).getByRole("button", { name: "MID" })).toBeInTheDocument();
    expect(await screen.findByText("1–24 of 60")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^Filters/ })).toBeNull();
    expect(screen.getByText("£232.5M")).toBeInTheDocument();
  });

  it("signed out: no budget, no picks row, no valuation call", async () => {
    signIn(null);
    renderWithProviders(<PlayerMarketPage />);
    await screen.findByText("Showing 40 of 60");
    expect(screen.queryByText(/to spend/)).toBeNull();
    expect(screen.queryByText(/Picks for your squad gaps/)).toBeNull();
    expect(api.get.mock.calls.some(([url]) => url === "/valuation/players")).toBe(false);
  });

  it("a player account never fires the valuation call", async () => {
    signIn("PLAYER");
    renderWithProviders(<PlayerMarketPage />);
    await screen.findByText("Showing 40 of 60");
    await waitFor(() => expect(api.get.mock.calls.some(([url]) => url === "/players/form/batch")).toBe(true));
    expect(api.get.mock.calls.some(([url]) => url === "/valuation/players")).toBe(false);
    expect(screen.queryByText(/Picks for your squad gaps/)).toBeNull();
  });

  it("a club sees its budget and the picks row after the fifth player", async () => {
    renderWithProviders(<PlayerMarketPage />);
    expect(await screen.findByText(/a week in wages/)).toHaveTextContent("£232.5M to spend · £49.9M a week in wages");
    const picks = await screen.findByRole("button", { name: /Picks for your squad gaps/ });
    const items = within(picks.closest("ul")!).getAllByRole("listitem");
    expect(items.indexOf(picks.closest("li")!)).toBe(5);
  });

  it("the default saved view sets the filters and the sort label on load", async () => {
    views = [{ id: "v1", name: "Bargains", is_default: true, filters: { position: "MID", sort_by: "value", sort_dir: "desc" } }];
    renderWithProviders(<PlayerMarketPage />);
    expect(await screen.findByRole("button", { name: /Sort: Best value/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Remove filter MID" })).toBeInTheDocument();
    await waitFor(() => expect(lastOf(marketCalls())).toMatchObject({ position: "MID", sort_by: "value", sort_dir: "desc" }));
  });
});
