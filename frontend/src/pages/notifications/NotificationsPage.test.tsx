import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../../test/utils";
import NotificationsPage, { dayLabel } from "./NotificationsPage";

const api = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }));
vi.mock("../../lib/api", () => ({ default: api }));

const now = new Date();
const iso = (daysAgo: number) => new Date(now.getTime() - daysAgo * 86_400_000).toISOString();
const note = (id: string, daysAgo: number, over: Record<string, unknown> = {}) => ({
  id, recipient_user_id: "u", type: "OFFER_RECEIVED", message: `Offer ${id}`, link: `/offers/${id}`, is_read: false,
  related_player_id: "p1", related_club_id: "c1", created_at: iso(daysAgo), title: null, body: null, tier: "YOUR_MOVE",
  player: { id: "p1", name: "J. Bynoe-Gittens", image_url: null }, club: { id: "c1", name: "Leeds", image_url: null }, ...over,
});

function listCalls() {
  return api.get.mock.calls.filter(([url]) => url === "/notifications").map(([, cfg]) => cfg.params);
}
const last = () => { const calls = listCalls(); return calls[calls.length - 1]; };

beforeEach(() => {
  api.get.mockReset().mockImplementation((url: string, cfg?: { params?: { page?: number } }) => {
    if (url === "/notifications/unread-count") return Promise.resolve({ data: { count: 3 } });
    const page = cfg?.params?.page ?? 1;
    const items = page === 1 ? [note("a", 0), note("b", 1), note("c", 9)] : [note("d", 20)];
    return Promise.resolve({ data: { items, total: 4, page, page_size: 3 } });
  });
  api.post.mockReset().mockResolvedValue({ data: { count: 0 } });
});

describe("NotificationsPage", () => {
  it("groups by day and shows more on request", async () => {
    renderWithProviders(<NotificationsPage />);
    expect(await screen.findByRole("region", { name: "Today" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Yesterday" })).toBeInTheDocument();
    expect(screen.getByText("Showing 3 of 4")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Show 1 more" }));
    expect(await screen.findByText("Offer d")).toBeInTheDocument();
    expect(last()).toMatchObject({ page: 2 });
  });

  it("filters by search, unread, whose move and category", async () => {
    renderWithProviders(<NotificationsPage />);
    await screen.findByText("Offer a");
    await userEvent.type(screen.getByLabelText("Search notifications"), "leeds");
    await waitFor(() => expect(last()).toMatchObject({ q: "leeds" }));
    await userEvent.click(screen.getByRole("button", { name: "Unread" }));
    await waitFor(() => expect(last()).toMatchObject({ q: "leeds", unread: true }));
    await userEvent.click(within(screen.getByRole("radiogroup", { name: "Whose move" })).getByRole("radio", { name: "Your move" }));
    await userEvent.click(within(screen.getByRole("radiogroup", { name: "Category" })).getByRole("radio", { name: "Offers" }));
    await waitFor(() => expect(last()).toMatchObject({ tier: "YOUR_MOVE", category: "offers" }));
  });

  it("a row's player filters to him, removable, and Mark these read follows the filters", async () => {
    renderWithProviders(<NotificationsPage />);
    await screen.findByText("Offer a");
    await userEvent.click(screen.getAllByRole("button", { name: "Show only notifications about J. Bynoe-Gittens" })[0]);
    await waitFor(() => expect(last()).toMatchObject({ player_id: "p1" }));
    await userEvent.click(screen.getByRole("button", { name: "Mark these read" }));
    expect(api.post).toHaveBeenCalledWith("/notifications/read-all", null, { params: { player_id: "p1" } });
    await userEvent.click(screen.getByRole("button", { name: "Remove filter J. Bynoe-Gittens" }));
    await waitFor(() => expect(last()?.player_id).toBeUndefined());
  });

  it("names the days", () => {
    const at = new Date(2026, 10, 15, 12);
    expect(dayLabel(new Date(2026, 10, 15, 8).toISOString(), at)).toBe("Today");
    expect(dayLabel(new Date(2026, 10, 14, 23).toISOString(), at)).toBe("Yesterday");
    expect(dayLabel(new Date(2026, 10, 11, 9).toISOString(), at)).toBe("Earlier this week");
    expect(dayLabel(new Date(2026, 10, 1, 9).toISOString(), at)).toBe("1 Nov 2026");
  });
});
