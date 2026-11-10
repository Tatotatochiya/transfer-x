import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithProviders } from "../../test/utils";
import MarketActions from "./MarketActions";

const auth = vi.hoisted(() => ({ value: { isAuthenticated: true, userType: "CLUB", hasClub: true, viewedBy: null as string | null } }));
vi.mock("../../hooks/useAuth", () => ({ useAuth: () => auth.value }));
const caps = vi.hoisted(() => ({ marketWrite: true }));
vi.mock("../../hooks/useClubCapabilities", () => ({ useClubCapabilities: () => ({ can: () => caps.marketWrite }) }));

describe("MarketActions", () => {
  beforeEach(() => {
    auth.value = { isAuthenticated: true, userType: "CLUB", hasClub: true, viewedBy: null };
    caps.marketWrite = true;
  });

  it("offers Find players and Sell a player to a club member who can trade, never in blue", () => {
    renderWithProviders(<MarketActions />);
    const find = screen.getByRole("link", { name: "Find players" });
    const sell = screen.getByRole("link", { name: "Sell a player" });
    expect(find).toHaveAttribute("href", "/players/market");
    expect(sell).toHaveAttribute("href", "/sales/new");
    for (const l of [find, sell]) expect(l.className).not.toMatch(/\bbg-accent\b/);
  });

  it("is short on a phone, with the same names", () => {
    renderWithProviders(<MarketActions compact />);
    const find = screen.getByRole("link", { name: "Find players" });
    const sell = screen.getByRole("link", { name: "Sell a player" });
    expect(find).toHaveTextContent("Players");
    expect(sell).toHaveTextContent("Sell");
    expect(find).toHaveAttribute("href", "/players/market");
    expect(sell).toHaveAttribute("href", "/sales/new");
    for (const l of [find, sell]) expect(l.className).not.toMatch(/\bbg-accent\b/);
  });

  it("isn't there for a role that can't trade, an agent, or a view-as tab", () => {
    caps.marketWrite = false;
    const { unmount } = renderWithProviders(<MarketActions />);
    expect(screen.queryByRole("link", { name: /Find players/ })).not.toBeInTheDocument();
    unmount();
    caps.marketWrite = true;
    auth.value = { ...auth.value, userType: "AGENT" };
    const second = renderWithProviders(<MarketActions />);
    expect(screen.queryByRole("link", { name: /Find players/ })).not.toBeInTheDocument();
    second.unmount();
    auth.value = { isAuthenticated: true, userType: "CLUB", hasClub: true, viewedBy: "staff@transferx" };
    renderWithProviders(<MarketActions />);
    expect(screen.queryByRole("link", { name: /Sell/ })).not.toBeInTheDocument();
  });
});
