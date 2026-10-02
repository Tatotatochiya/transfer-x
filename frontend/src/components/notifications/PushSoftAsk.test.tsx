import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { renderWithProviders } from "../../test/utils";
import PushSoftAsk, { askBody } from "./PushSoftAsk";
import type { Notification } from "../../types/api";

const api = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }));
vi.mock("../../lib/api", () => ({ default: api, API_BASE_URL: "/api" }));
vi.mock("../../lib/analytics", () => ({ trackClick: vi.fn() }));
vi.mock("../../hooks/useAuth", () => ({ useAuth: () => ({ isAuthenticated: true, userType: "CLUB" }) }));
vi.mock("../../context/ToastContext", () => ({ useToast: () => ({ addToast: vi.fn() }) }));
const push = vi.hoisted(() => ({ state: "default", sessions: 3, subscribe: vi.fn(), dismiss: vi.fn() }));
vi.mock("../../lib/push", async (orig) => ({
  ...(await orig<typeof import("../../lib/push")>()),
  usePushState: () => ({ data: push.state }),
  useRefreshPush: () => () => {},
  countSession: () => push.sessions,
  readAskRecord: () => ({ dismissedAt: null, dismissals: 0 }),
  recordDismissal: push.dismiss,
  subscribe: push.subscribe,
}));

const offer = (over: Partial<Notification> = {}): Notification => ({
  id: "n1", recipient_user_id: "u1", type: "OFFER_RECEIVED", message: "You have received a new offer", link: "/offers/o1",
  is_read: false, related_player_id: "p1", related_club_id: null, created_at: "2026-10-02T09:00:00Z",
  tier: "YOUR_MOVE", player: { id: "p1", name: "Marcus Webb", image_url: null }, club: null, ...over,
} as Notification);

function setNarrow(narrow: boolean) {
  window.matchMedia = vi.fn().mockImplementation(() => ({
    matches: narrow, addEventListener: vi.fn(), removeEventListener: vi.fn(),
  })) as unknown as typeof window.matchMedia;
}

describe("PushSoftAsk", () => {
  beforeEach(() => {
    setNarrow(true);
    push.state = "default";
    push.sessions = 3;
    push.subscribe.mockReset();
    push.dismiss.mockReset();
    api.get.mockReset();
    api.get.mockImplementation((url: string) => Promise.resolve({
      data: url === "/notifications/unread-count" ? { count: 1 } : { items: [offer()], total: 1, page: 1, page_size: 5 },
    }));
  });

  it("asks when something is the person's move, on a phone", async () => {
    renderWithProviders(<PushSoftAsk />);
    expect(await screen.findByRole("dialog", { name: "Get offers on this phone" })).toBeInTheDocument();
    expect(screen.getByText(/There's a new offer for Marcus Webb/)).toBeInTheDocument();
  });

  it("doesn't ask on a desktop, in the first session, or for an FYI", async () => {
    setNarrow(false);
    const { unmount } = renderWithProviders(<PushSoftAsk />);
    await new Promise((r) => setTimeout(r, 50));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    unmount();

    setNarrow(true);
    push.sessions = 1;
    const second = renderWithProviders(<PushSoftAsk />);
    await new Promise((r) => setTimeout(r, 50));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    second.unmount();

    push.sessions = 3;
    api.get.mockImplementation((url: string) => Promise.resolve({
      data: url === "/notifications/unread-count" ? { count: 1 } : { items: [offer({ type: "DEAL_COMPLETED", tier: "FYI" })] },
    }));
    renderWithProviders(<PushSoftAsk />);
    await waitFor(() => expect(api.get).toHaveBeenCalledWith("/notifications", expect.anything()));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("Not now records the dismissal and closes", async () => {
    renderWithProviders(<PushSoftAsk />);
    await userEvent.click(await screen.findByRole("button", { name: "Not now" }));
    expect(push.dismiss).toHaveBeenCalled();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("turns notifications on, or says they're blocked", async () => {
    push.subscribe.mockResolvedValue("denied");
    renderWithProviders(<PushSoftAsk />);
    await userEvent.click(await screen.findByRole("button", { name: "Turn on notifications" }));
    expect(push.subscribe).toHaveBeenCalled();
    expect(await screen.findByText(/Notifications are blocked for TransferX/)).toBeInTheDocument();
  });

  it("on an iPhone tab, opens the Home Screen guide instead of asking the browser", async () => {
    push.state = "needs-install";
    renderWithProviders(<PushSoftAsk />);
    await userEvent.click(await screen.findByRole("button", { name: "Turn on notifications" }));
    expect(push.subscribe).not.toHaveBeenCalled();
    expect(screen.getByRole("dialog", { name: "Add TransferX to your Home Screen" })).toBeInTheDocument();
  });
});

describe("askBody", () => {
  it("names the club only when the API gave one (never an anonymous buyer)", () => {
    expect(askBody(offer({ club: { id: "c", name: "Ashfield United", image_url: null } })))
      .toMatch(/^Ashfield United just made an offer for Marcus Webb\./);
    expect(askBody(offer())).toMatch(/^There's a new offer for Marcus Webb\./);
    expect(askBody(offer({ type: "APPROVAL_REQUESTED", player: null }))).toMatch(/^We can tell you straight away/);
  });
});
