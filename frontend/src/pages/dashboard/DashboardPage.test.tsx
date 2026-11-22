import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { renderWithProviders } from "../../test/utils";
import DashboardPage from "./DashboardPage";

const api = vi.hoisted(() => ({ get: vi.fn() }));
vi.mock("../../lib/api", () => ({ default: api }));

const caps = vi.hoisted(() => ({ list: ["CLUB_ADMIN", "MARKET_WRITE", "APPROVE_ACTIONS"] as string[] }));
vi.mock("../../hooks/useClubCapabilities", () => ({
  useClubCapabilities: () => ({ membership: null, role: "OWNER", isLoading: false, can: (c: string) => caps.list.includes(c) }),
}));
vi.mock("../../hooks/useAuth", () => ({
  useAuth: () => ({ user: { id: "u1", first_name: "Sam" }, isAuthenticated: true, isClub: true, hasClub: true }),
}));
vi.mock("../../components/ai/Assistant", () => ({ BriefingCard: () => null }));
vi.mock("../../components/ai/ScoutReportPanel", () => ({ ScoutReportPanel: () => null }));
vi.mock("../../components/transfers/TransferWindowBanner", () => ({ default: () => null }));
vi.mock("../../components/deadline/DeadlineBanner", () => ({ default: () => null }));
vi.mock("../../components/sales/ListPlayerModal", () => ({
  default: ({ open, player }: { open: boolean; player?: { name: string } }) => (open ? <p>Listing {player?.name}</p> : null),
}));
vi.mock("../../components/OnboardingChecklist", () => ({
  useOnboardingSteps: () => ({ userId: "u1", title: "Get your club set up", steps: [{}, {}, {}, {}, {}, {}], done: 3, dismiss: vi.fn() }),
  ClubChecklist: () => <p>The full checklist</p>,
}));
vi.mock("../../components/account/NamePrompt", () => ({ useNamePrompt: () => ({ show: true, dismiss: vi.fn() }) }));

const finance = {
  transfer_budget_total: 260_000_000, wage_budget_total_weekly: 50_000_000 / 52, transfer_reserved: 10_000_000,
  wage_reserved_weekly: 0, transfer_committed: 17_500_000, transfer_spent: 0, wage_committed_weekly: 0,
  transfer_remaining: 232_500_000, wage_remaining_weekly: 900_000, approval_threshold: null, updated_at: "",
};
const club = (over: object = {}) => ({
  id: "c1", name: "Arsenal", country: "England", city: "London", league_name: "Premier League",
  crest_url: null, role: "BOTH", verified: true, created_at: "", finance, my_role: "OWNER",
  brand_primary: "#DB0007", brand_secondary: "#FFFFFF", ...over,
});
const players = [
  ...Array.from({ length: 2 }, (_, i) => ({ id: `gk${i}`, position: "GK", age: 25 })),
  ...Array.from({ length: 4 }, (_, i) => ({ id: `d${i}`, position: "DEF", age: 20 })),
  ...Array.from({ length: 4 }, (_, i) => ({ id: `m${i}`, position: "MID", age: 28 })),
  ...Array.from({ length: 2 }, (_, i) => ({ id: `f${i}`, position: "FWD", age: 31 })),
];
const card = (name: string, column: string, whose_move = "their", side = "BUYING") => ({
  key: `${side}:${name}`, side, column, kind: "deal", entity_id: name, player_id: name, player_name: name,
  player_position: "MID", counterparty: "Chelsea", amount: 13_200_000, detail: "", whose_move,
  deadline: null, link: `/deals/${name}`, updated_at: null, others: 0,
});
const board = {
  columns: [
    { key: "talking", label: "Listed", cards: [card("R. Calafiori", "talking", "neither", "SELLING")] },
    { key: "offers", label: "Offers", cards: [card("A. Offer", "offers")] },
    { key: "fee_agreed", label: "Fee agreed", cards: [card("R. Gravenberch", "fee_agreed")] },
    { key: "terms", label: "Personal terms", cards: [card("M. Caicedo", "terms", "your")] },
    { key: "paperwork", label: "Paperwork", cards: [] },
    { key: "done", label: "Completed", cards: [card("B. Saka", "done", "neither", "SELLING")] },
  ],
  closed: [], counts: { buying: 3, selling: 2, your_move: 1 },
};
const waiting = [
  { kind: "deal", id: "d1", player_name: "M. Caicedo", club_name: "Chelsea", amount: 13_200_000,
    reason: "Agent commission to answer", link: "/deals/caicedo", deadline: null },
];

function serve(clubData = club()) {
  api.get.mockReset().mockImplementation((url: string) => {
    const data: Record<string, unknown> = {
      "/clubs/me": clubData,
      "/transfers/window/status": { enforced: false, is_open: false, country: null, current_window: null, next_window: null },
      "/board": board,
      "/deals": { items: [], total: 0 },
      "/clubs/c1/players": { items: players, total: players.length },
      "/scouting/market-hits": [],
      "/clubs/me/expiring-contracts": [{ player_id: "p9", player_name: "J. Jorginho", position: "MID", end_date: "", days_remaining: 45 }],
      "/clubs/me/approvals": [],
      "/clubs/me/dashboard": { waiting_on_you: waiting },
      "/sales": { items: [], total: 0 },
    };
    return Promise.resolve({ data: data[url] ?? null });
  });
}

beforeEach(() => {
  caps.list = ["CLUB_ADMIN", "MARKET_WRITE", "APPROVE_ACTIONS"];
  serve();
});

describe("DashboardPage", () => {
  it("opens with the club's band: its name is the h1, in its colours", async () => {
    renderWithProviders(<DashboardPage />);
    // The file's first render also loads its modules: allow more than the default second.
    expect(await screen.findByRole("heading", { level: 1, name: "Arsenal" }, { timeout: 5000 })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Dashboard" })).toBeNull();
    const band = screen.getByTestId("club-band");
    expect(band).toHaveStyle({ backgroundColor: "#DB0007", color: "#FFFFFF" });
    expect(within(band).getByText("1 waiting on you")).toBeInTheDocument();
  });

  it("uses ink on a light primary", async () => {
    serve(club({ brand_primary: "#F5C400", brand_secondary: "#14171F" }));
    renderWithProviders(<DashboardPage />);
    expect(await screen.findByTestId("club-band")).toHaveStyle({ color: "#14171F" });
  });

  it("is a plain card with no colours, offering an admin to add them", async () => {
    serve(club({ brand_primary: null, brand_secondary: null }));
    const { unmount } = renderWithProviders(<DashboardPage />);
    const band = await screen.findByTestId("club-band");
    expect(band.getAttribute("style")).toBeNull();
    expect(within(band).getByRole("link", { name: "Add club colours" })).toHaveAttribute("href", "/club#club-colours");
    unmount();
    caps.list = ["MARKET_WRITE"];
    renderWithProviders(<DashboardPage />);
    expect(within(await screen.findByTestId("club-band")).queryByText("Add club colours")).toBeNull();
  });

  it("counts only waiting_on_you in Needs you; housekeeping sits under Also", async () => {
    renderWithProviders(<DashboardPage />);
    const card = (await screen.findByRole("heading", { name: "Needs you" })).closest("section")!;
    expect(within(card).getByTestId("needs-you-count")).toHaveTextContent(String(waiting.length));
    expect(within(card).getByRole("link", { name: /M\. Caicedo/ })).toHaveAttribute("href", "/deals/caicedo");
    expect(within(card).getByText("Also")).toBeInTheDocument();
    expect(within(card).getByText(/Finish setting up your club · 3 of 6/)).toBeInTheDocument();
    expect(within(card).getByText(/Add your name/)).toBeInTheDocument();
    expect(within(card).getByText(/J\. Jorginho.s contract ends in 45 days/)).toBeInTheDocument();
  });

  it("opens the checklist in a sheet from the setup row", async () => {
    renderWithProviders(<DashboardPage />);
    await userEvent.setup().click(await screen.findByRole("button", { name: "Continue" }));
    expect(screen.getByText("The full checklist")).toBeInTheDocument();
  });

  it("offers List on an expiring contract only with MARKET_WRITE", async () => {
    const { unmount } = renderWithProviders(<DashboardPage />);
    await userEvent.setup().click(await screen.findByRole("button", { name: "List" }));
    expect(screen.getByText("Listing J. Jorginho")).toBeInTheDocument();
    unmount();
    caps.list = ["SCOUTING_WRITE"];
    renderWithProviders(<DashboardPage />);
    await screen.findByText(/J\. Jorginho.s contract ends/);
    expect(screen.queryByRole("button", { name: "List" })).toBeNull();
  });

  it("lists each open transfer once, your move first, not the completed ones", async () => {
    renderWithProviders(<DashboardPage />);
    const section = (await screen.findByRole("heading", { name: "Transfers in progress" })).closest("section")!;
    const rows = within(section).getAllByRole("listitem");
    expect(rows).toHaveLength(3); // phone: three, then "+N more"
    expect(rows[0]).toHaveTextContent("M. Caicedo");
    expect(within(section).queryByText("B. Saka")).toBeNull();
    expect(within(section).getByRole("link", { name: "+1 more →" })).toHaveAttribute("href", "/board");
    expect(within(rows[0]).getByRole("link")).toHaveAttribute("href", "/deals/M. Caicedo");
  });

  it("summarises the squad", async () => {
    renderWithProviders(<DashboardPage />);
    const section = (await screen.findByRole("heading", { name: "Your squad" })).closest("section")!;
    expect(within(section).getByText("First team")).toBeInTheDocument();
    expect(within(section).getByText("12")).toBeInTheDocument();
    expect(within(section).getByText("25.3")).toBeInTheDocument();
    expect(within(section).getByText("Need")).toBeInTheDocument();
    expect(within(section).getByRole("link", { name: "1 FWD" })).toHaveAttribute("href", "/players/market?position=FWD");
  });

  it("shows money free, and turns a bar to warning under 10% left", async () => {
    renderWithProviders(<DashboardPage />);
    const section = (await screen.findByRole("heading", { name: "Money" })).closest("section")!;
    expect(within(section).getByText("Transfer budget free")).toBeInTheDocument();
    expect(within(section).getByTestId("Transfer budget-remaining").className).toContain("bg-text");
    // £900k of about £962k a week left: over 90%, neutral.
    expect(within(section).getByTestId("Wage room-remaining").className).not.toContain("bg-warning-fill");
  });

  it("warns on a nearly spent budget", async () => {
    serve(club({ finance: { ...finance, transfer_remaining: 20_000_000 } }));
    renderWithProviders(<DashboardPage />);
    const section = (await screen.findByRole("heading", { name: "Money" })).closest("section")!;
    expect(within(section).getByTestId("Transfer budget-remaining").className).toContain("bg-warning-fill");
  });

  it("keeps the club's colour inside the band", async () => {
    const { container } = renderWithProviders(<DashboardPage />);
    const band = await screen.findByTestId("club-band");
    const outside = Array.from(container.querySelectorAll<HTMLElement>("[style]")).filter((el) => !band.contains(el));
    for (const el of outside) {
      expect(el.getAttribute("style") ?? "").not.toMatch(/219,\s*0,\s*7|#DB0007/i);
    }
  });
});
