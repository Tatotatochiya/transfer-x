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

  it("offers Buy and Sell to a club member who can trade", () => {
    renderWithProviders(<MarketActions />);
    expect(screen.getByRole("link", { name: "Buy a player" })).toHaveAttribute("href", "/players/market");
    expect(screen.getByRole("link", { name: "Sell a player" })).toHaveAttribute("href", "/sales/new");
  });

  it("is short on a phone", () => {
    renderWithProviders(<MarketActions compact />);
    expect(screen.getByRole("link", { name: "Buy" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Sell" })).toBeInTheDocument();
  });

  it("isn't there for a role that can't trade, an agent, or a view-as tab", () => {
    caps.marketWrite = false;
    const { unmount } = renderWithProviders(<MarketActions />);
    expect(screen.queryByRole("link", { name: /Buy/ })).not.toBeInTheDocument();
    unmount();
    caps.marketWrite = true;
    auth.value = { ...auth.value, userType: "AGENT" };
    const second = renderWithProviders(<MarketActions />);
    expect(screen.queryByRole("link", { name: /Buy/ })).not.toBeInTheDocument();
    second.unmount();
    auth.value = { isAuthenticated: true, userType: "CLUB", hasClub: true, viewedBy: "staff@transferx" };
    renderWithProviders(<MarketActions />);
    expect(screen.queryByRole("link", { name: /Sell/ })).not.toBeInTheDocument();
  });
});
