import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { renderWithProviders } from "../../test/utils";
import AddToShortlistButton from "./AddToShortlistButton";

const api = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }));
vi.mock("../../lib/api", () => ({ default: api }));
vi.mock("../../store/auth", () => ({ useAuthStore: () => ({ accessToken: "token" }) }));
vi.mock("../../hooks/useClubCapabilities", () => ({
  useClubCapabilities: () => ({ membership: { role: "OWNER" }, can: () => true }),
}));

const list = (id: string, name: string, contains = false) => ({
  id, club_id: "c1", name, description: null, item_count: 2,
  created_at: "2026-10-01T00:00:00Z", updated_at: "2026-10-01T00:00:00Z", contains_player: contains,
});

describe("AddToShortlistButton", () => {
  beforeEach(() => {
    api.get.mockReset();
    api.post.mockReset();
  });

  it("asks which lists already hold the player, ticks them and won't add him twice", async () => {
    api.get.mockResolvedValue({ data: [list("s1", "Left-backs", true), list("s2", "Strikers")] });
    renderWithProviders(<AddToShortlistButton playerId="p1" />);
    await userEvent.click(screen.getByTitle("Add to shortlist"));

    expect(await screen.findByText("Already on it")).toBeInTheDocument();
    expect(api.get).toHaveBeenCalledWith("/scouting/shortlists", { params: { player_id: "p1" } });
    expect(screen.getByRole("menuitem", { name: /Left-backs/ })).toBeDisabled();
    expect(screen.getByRole("menuitem", { name: /Strikers/ })).toBeEnabled();
  });

  it("creates a new shortlist and adds the player in the same menu", async () => {
    api.get.mockResolvedValue({ data: [list("s2", "Strikers")] });
    api.post.mockImplementation((url: string) =>
      url === "/scouting/shortlists"
        ? Promise.resolve({ data: { id: "s9", name: "Summer targets" } })
        : Promise.resolve({ data: {} }),
    );
    renderWithProviders(<AddToShortlistButton playerId="p1" />);
    await userEvent.click(screen.getByTitle("Add to shortlist"));
    await userEvent.click(await screen.findByRole("menuitem", { name: /New shortlist/ }));
    await userEvent.type(screen.getByPlaceholderText(/Left-backs for the summer/), "Summer targets{Enter}");

    expect(await screen.findByText("Added to Summer targets")).toBeInTheDocument();
    expect(api.post).toHaveBeenNthCalledWith(1, "/scouting/shortlists", { name: "Summer targets" });
    expect(api.post).toHaveBeenNthCalledWith(2, "/scouting/shortlists/s9/items", { player_id: "p1", priority: 3 });
  });

  it("opens straight to naming the first shortlist when there are none", async () => {
    api.get.mockResolvedValue({ data: [] });
    renderWithProviders(<AddToShortlistButton playerId="p1" />);
    await userEvent.click(screen.getByTitle("Add to shortlist"));
    expect(await screen.findByText("No shortlists yet. Name your first:")).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/Left-backs for the summer/)).toHaveFocus();
  });

  it("keeps a created list when adding fails, and retries the add rather than creating it again", async () => {
    api.get.mockResolvedValue({ data: [] });
    let adds = 0;
    api.post.mockImplementation((url: string) => {
      if (url === "/scouting/shortlists") return Promise.resolve({ data: { id: "s9", name: "Summer targets" } });
      adds += 1;
      return adds === 1
        ? Promise.reject({ response: { data: { detail: "Something went wrong" } } })
        : Promise.resolve({ data: {} });
    });
    renderWithProviders(<AddToShortlistButton playerId="p1" />);
    await userEvent.click(screen.getByTitle("Add to shortlist"));
    await userEvent.type(await screen.findByPlaceholderText(/Left-backs for the summer/), "Summer targets{Enter}");

    expect(await screen.findByRole("alert")).toHaveTextContent('Created "Summer targets", but couldn\'t add him');
    await userEvent.click(screen.getByRole("button", { name: "Try adding again" }));
    await waitFor(() => expect(screen.getByText("Added to Summer targets")).toBeInTheDocument());
    expect(api.post.mock.calls.filter(([url]) => url === "/scouting/shortlists")).toHaveLength(1);
  });
});
