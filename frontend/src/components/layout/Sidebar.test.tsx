import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { renderWithProviders } from "../../test/utils";
import Sidebar from "./Sidebar";

const api = vi.hoisted(() => ({ get: vi.fn() }));
vi.mock("../../lib/api", () => ({ default: api }));

const auth = vi.hoisted(() => ({
  value: {
    user: { email: "owner@club.test", is_superuser: false },
    isAuthenticated: true as boolean,
    userType: "CLUB" as string | null,
    hasClub: true as boolean,
    isStaffAccount: false as boolean,
    logout: vi.fn(),
  },
}));
vi.mock("../../hooks/useAuth", () => ({ useAuth: () => auth.value }));

const caps = vi.hoisted(() => ({ can: (_c: string): boolean => true, role: "OWNER" }));
vi.mock("../../hooks/useClubCapabilities", () => ({ useClubCapabilities: () => caps }));
vi.mock("../../hooks/useIdentity", () => ({
  useIdentity: () => ({ role: "CLUB", name: "Riverside Athletic", subLabel: null, crestUrl: null, isSuperuser: false }),
}));
const dashboard = vi.hoisted(() => ({ waiting: [] as { kind: string }[] }));
vi.mock("../../hooks/useClubDashboard", async (orig) => ({
  ...(await orig<typeof import("../../hooks/useClubDashboard")>()),
  useClubDashboard: () => ({ data: { waiting_on_you: dashboard.waiting } }),
}));
const toLite = vi.hoisted(() => vi.fn());
vi.mock("../../hooks/usePreferences", () => ({ useUpdatePreferences: () => ({ mutate: toLite, isPending: false }) }));
const navigate = vi.hoisted(() => vi.fn());
vi.mock("react-router-dom", async (orig) => ({
  ...(await orig<typeof import("react-router-dom")>()),
  useNavigate: () => navigate,
}));

function renderSidebar(path = "/dashboard") {
  return renderWithProviders(<Sidebar mobileOpen={false} onMobileClose={() => {}} />, { initialPath: path });
}

describe("Sidebar", () => {
  beforeEach(() => {
    api.get.mockReset();
    api.get.mockResolvedValue({ data: { count: 0 } });
    auth.value = { ...auth.value, userType: "CLUB", isAuthenticated: true, hasClub: true, isStaffAccount: false };
    caps.can = () => true;
    caps.role = "OWNER";
    dashboard.waiting = [];
    toLite.mockReset();
    navigate.mockReset();
    auth.value.logout = vi.fn().mockResolvedValue(undefined);
  });

  it("keeps every club item and its label, and hides gated ones without the capability", () => {
    renderSidebar();
    for (const label of ["Dashboard", "Transfers in progress", "Enquiries", "Browse Players", "Listings", "Shortlists",
      "My Offers", "Recent Transfers", "My Listings", "Offers Received", "My Club", "Finance", "Team", "Approvals"]) {
      expect(screen.getByRole("link", { name: new RegExp(`^${label}`) })).toBeInTheDocument();
    }
    // The Notifications row became the bell; Settings and Lite moved into the account menu.
    expect(screen.queryByRole("link", { name: "Settings" })).not.toBeInTheDocument();
  });

  it("hides Team and Approvals for a scout", () => {
    caps.can = () => false;
    caps.role = "SCOUT";
    renderSidebar();
    expect(screen.queryByRole("link", { name: "Team" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Approvals" })).not.toBeInTheDocument();
  });

  it("puts waiting counts on the route each kind belongs to", () => {
    dashboard.waiting = [{ kind: "offer" }, { kind: "offer" }, { kind: "approval" }];
    renderSidebar();
    expect(screen.getByRole("link", { name: /Offers Received/ })).toContainElement(screen.getByLabelText("2 waiting on you"));
    expect(screen.getByRole("link", { name: /Approvals/ })).toContainElement(screen.getByLabelText("1 waiting on you"));
  });

  describe("bell", () => {
    it("shows the unread count, capped at 99+, and says it in its label", async () => {
      api.get.mockResolvedValue({ data: { count: 150 } });
      renderSidebar();
      const bell = await screen.findByRole("link", { name: "Notifications, 150 unread" });
      expect(bell).toHaveTextContent("99+");
      expect(api.get).toHaveBeenCalledWith("/notifications/unread-count");
    });

    it("has no badge at zero, and is active on /notifications", async () => {
      renderSidebar("/notifications");
      const bell = await screen.findByRole("link", { name: "Notifications" });
      expect(bell.textContent).toBe("");
      expect(bell).toHaveAttribute("aria-current", "page");
    });
  });

  describe("account menu", () => {
    it("opens on click, closes on Escape and returns focus to the button", async () => {
      renderSidebar();
      const button = screen.getByRole("button", { name: /Riverside Athletic/ });
      await userEvent.click(button);
      expect(screen.getByRole("menu")).toBeInTheDocument();
      expect(button).toHaveAttribute("aria-expanded", "true");
      screen.getAllByRole("menuitem")[0].focus();
      await userEvent.keyboard("{Escape}");
      expect(screen.queryByRole("menu")).not.toBeInTheDocument();
      expect(button).toHaveFocus();
    });

    it("closes on an outside click", async () => {
      renderSidebar();
      await userEvent.click(screen.getByRole("button", { name: /Riverside Athletic/ }));
      fireEvent.mouseDown(document.body);
      expect(screen.queryByRole("menu")).not.toBeInTheDocument();
    });

    it("opens from the keyboard on the first item, and arrows, Home and End move", async () => {
      renderSidebar();
      screen.getByRole("button", { name: /Riverside Athletic/ }).focus();
      await userEvent.keyboard("{ArrowUp}");
      const items = screen.getAllByRole("menuitem");
      expect(items.map((i) => i.textContent)).toEqual(["Settings", "Notification settings", "Switch to Lite mode", "Log out"]);
      await waitFor(() => expect(items[0]).toHaveFocus());
      await userEvent.keyboard("{ArrowDown}");
      expect(items[1]).toHaveFocus();
      await userEvent.keyboard("{End}");
      expect(items[3]).toHaveFocus();
      await userEvent.keyboard("{ArrowDown}");
      expect(items[0]).toHaveFocus();
      await userEvent.keyboard("{ArrowUp}");
      expect(items[3]).toHaveFocus();
      await userEvent.keyboard("{Home}");
      expect(items[0]).toHaveFocus();
    });

    it("stops Escape there, so the drawer behind it stays open", async () => {
      // The drawer's focus trap listens on the document, like this.
      const drawerEscape = vi.fn();
      const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") drawerEscape(); };
      document.addEventListener("keydown", onKey);
      try {
        renderSidebar();
        await userEvent.click(screen.getByRole("button", { name: /Riverside Athletic/ }));
        screen.getAllByRole("menuitem")[0].focus();
        await userEvent.keyboard("{Escape}");
        expect(drawerEscape).not.toHaveBeenCalled();
        // With the menu closed, Escape reaches the drawer as before.
        await userEvent.keyboard("{Escape}");
        expect(drawerEscape).toHaveBeenCalledTimes(1);
      } finally {
        document.removeEventListener("keydown", onKey);
      }
    });

    it("links notification settings to the section on the account page", async () => {
      renderSidebar();
      await userEvent.click(screen.getByRole("button", { name: /Riverside Athletic/ }));
      expect(screen.getByRole("menuitem", { name: "Notification settings" })).toHaveAttribute("href", "/account#notifications");
    });

    it("switches a club to Lite mode", async () => {
      renderSidebar();
      await userEvent.click(screen.getByRole("button", { name: /Riverside Athletic/ }));
      await userEvent.click(screen.getByRole("menuitem", { name: "Switch to Lite mode" }));
      expect(toLite).toHaveBeenCalledWith({ lite_mode: true }, expect.anything());
    });

    it("offers no Lite mode to an agent", async () => {
      auth.value = { ...auth.value, userType: "AGENT" };
      renderSidebar();
      await userEvent.click(screen.getByRole("button", { name: /Riverside Athletic/ }));
      expect(screen.queryByRole("menuitem", { name: "Switch to Lite mode" })).not.toBeInTheDocument();
    });

    it("logs out and goes to the login page", async () => {
      renderSidebar();
      await userEvent.click(screen.getByRole("button", { name: /Riverside Athletic/ }));
      await userEvent.click(screen.getByRole("menuitem", { name: "Log out" }));
      expect(auth.value.logout).toHaveBeenCalled();
      await waitFor(() => expect(navigate).toHaveBeenCalledWith("/login"));
    });
  });

  it("shows Login instead of the account menu when signed out", () => {
    auth.value = { ...auth.value, isAuthenticated: false, userType: null };
    renderSidebar("/players/market");
    expect(screen.getByRole("link", { name: "Login" })).toHaveAttribute("href", "/login");
    expect(screen.queryByRole("button", { name: /Riverside Athletic/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Notifications/ })).not.toBeInTheDocument();
  });

  it("gives a TransferX staff account the admin pages, not a club's nav", async () => {
    auth.value = { ...auth.value, hasClub: false, isStaffAccount: true };
    renderSidebar("/admin");
    for (const label of ["Overview", "Users", "Clubs", "Audit log", "Health", "Verification"]) {
      expect(screen.getByRole("link", { name: new RegExp(`^${label}`) })).toBeInTheDocument();
    }
    expect(screen.queryByRole("link", { name: /^My Club/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /^Finance/ })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Riverside Athletic/ }));
    expect(screen.queryByRole("menuitem", { name: "Switch to Lite mode" })).not.toBeInTheDocument();
  });
});
