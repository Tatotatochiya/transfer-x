import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import type { Player } from "../../types/api";
import PlayerRow, { rowFromPlayer } from "./PlayerRow";

const api = vi.hoisted(() => ({ get: vi.fn().mockResolvedValue({ data: [] }), post: vi.fn() }));
vi.mock("../../lib/api", () => ({ default: api }));
vi.mock("../../store/auth", () => ({ useAuthStore: () => ({ accessToken: "token" }) }));
vi.mock("../../hooks/useClubCapabilities", () => ({
  useClubCapabilities: () => ({ membership: { role: "OWNER" }, can: () => true }),
}));

const PLAYER = {
  id: "p1", name: "A. Isak", age: 26, nationality: "Sweden", position: "FWD", status: "CONTRACTED",
  open_to_offers: false, photo_url: "/isak.png", team_name: null, current_club: { id: "c1", name: "Liverpool", crest_url: null },
  market_value: null,
} as unknown as Player;

function renderRow(player: Player = PLAYER) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/players/market"]}>
        <Routes>
          <Route path="/players/market" element={<ul><PlayerRow row={rowFromPlayer(player, null, 57)} /></ul>} />
          <Route path="/players/market/:id" element={<p>Player page</p>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("PlayerRow", () => {
  it("is a link to the player", () => {
    renderRow();
    const link = screen.getByRole("link");
    expect(link).toHaveAttribute("href", "/players/market/p1");
    expect(link).toHaveTextContent("A. Isak");
    expect(link).toHaveTextContent("Liverpool · 26 · Sweden");
    expect(link).toHaveTextContent("Form 57");
  });

  it("the shortlist button doesn't navigate", async () => {
    renderRow();
    await userEvent.click(screen.getByTitle("Add to shortlist"));
    expect(screen.queryByText("Player page")).toBeNull();
  });

  it("a failed photo shows initials", () => {
    const { container } = renderRow();
    fireEvent.error(container.querySelector("img")!);
    expect(screen.getByText("AI")).toBeInTheDocument();
  });

  it("no Listed badge when he isn't listed", () => {
    renderRow();
    expect(screen.queryByText("Listed")).toBeNull();
  });

  it("says Listed when open_to_offers", () => {
    renderRow({ ...PLAYER, open_to_offers: true });
    expect(screen.getByText("Listed")).toBeInTheDocument();
  });
});
