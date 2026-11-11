import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes, useLocation } from "react-router-dom";
import { renderWithProviders } from "../../test/utils";
import { useAuthStore } from "../../store/auth";
import PlayerMarketDetailPage from "./PlayerMarketDetailPage";

const api = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn(), patch: vi.fn(), defaults: { baseURL: "" } }));
vi.mock("../../lib/api", () => ({ default: api }));
const confirm = vi.hoisted(() => vi.fn());
vi.mock("../../context/ConfirmContext", () => ({ useConfirm: () => confirm, useAskReason: () => vi.fn() }));
vi.mock("../../context/ToastContext", () => ({ useToast: () => ({ addToast: vi.fn() }) }));
const caps = vi.hoisted(() => ({ marketWrite: true }));
vi.mock("../../hooks/useClubCapabilities", () => ({
  useClubCapabilities: () => ({ can: (c: string) => (c === "MARKET_WRITE" ? caps.marketWrite : false), membership: { role: "OWNER" } }),
}));
const listings = vi.hoisted(() => ({ map: new Map<string, string>(), known: true }));
vi.mock("../../hooks/useListing", () => ({ useOpenListings: () => ({ byPlayer: listings.map, isSuccess: listings.known }) }));
// The page's own panels are tested elsewhere; here, only the actions.
vi.mock("../../components/players/ledger/FactsStrip", () => ({ default: () => null }));
vi.mock("../../components/players/ledger/LedgerTabs", () => ({ OverviewLedger: () => null, CareerLedger: () => null, InjuriesLedger: () => null }));
vi.mock("../../components/ai/PlayerFitCard", () => ({ PlayerFitCard: () => null }));
vi.mock("../../components/ai/Assistant", () => ({ PotentialBuyersPanel: () => null }));
vi.mock("../../components/players/PlayerAccountCard", () => ({ default: () => null }));
vi.mock("../../components/scouting/AddToShortlistButton", () => ({
  default: ({ label }: { label?: string }) => <button type="button" aria-label={label}>Shortlist</button>,
}));
vi.mock("../../components/enquiries/AskAboutPlayerModal", () => ({
  default: ({ open, ownerName }: { open: boolean; ownerName: string }) => (open ? <div role="dialog" aria-label={`Ask ${ownerName}`} /> : null),
}));
vi.mock("../../components/sales/ListPlayerModal", () => ({
  default: ({ open }: { open: boolean }) => (open ? <div role="dialog" aria-label="List for sale" /> : null),
}));

const ME = { id: "us", name: "Meridian FC" };

function playerFixture(over: Record<string, unknown> = {}) {
  return {
    id: "p1", name: "João Pedro", position: "FWD", status: "CONTRACTED", age: 24, nationality: "Brazil",
    photo_url: null, current_club: { id: "chelsea", name: "Chelsea", crest_url: null }, world_team: null, team_name: null,
    open_to_offers: false, is_verified_player: false, active_deal: null, active_loan: null, contract_expiry: null,
    active_contract: { release_clause: null, end_date: "2030-06-30" }, ...over,
  };
}

let player = playerFixture();
let myOffer: Record<string, unknown> | null = null;

function serve(url: string) {
  if (url === "/players/market/p1") return Promise.resolve({ data: player });
  if (url === "/clubs/me") return Promise.resolve({ data: ME });
  if (url === "/offers/active-for-player/p1") return Promise.resolve({ data: myOffer });
  if (url.startsWith("/offers/competition")) return Promise.resolve({ data: { entries: [], active_count: 0 } });
  return Promise.reject(new Error("not needed"));
}

function Where() {
  const loc = useLocation();
  return <p data-testid="where">{loc.pathname}{loc.search}</p>;
}

function renderPage() {
  return renderWithProviders(
    <Routes>
      <Route path="/players/market/:id" element={<PlayerMarketDetailPage />} />
      <Route path="*" element={<Where />} />
    </Routes>,
    { initialPath: "/players/market/p1" },
  );
}

function viewport(width: number) {
  window.matchMedia = vi.fn().mockImplementation((query: string) => {
    const min = Number(/min-width:\s*(\d+)px/.exec(query)?.[1] ?? 0);
    return {
      matches: width >= min, media: query, onchange: null,
      addListener: vi.fn(), removeListener: vi.fn(), addEventListener: vi.fn(), removeEventListener: vi.fn(), dispatchEvent: vi.fn(),
    };
  });
}

function signIn(user_type: "CLUB" | "AGENT" | "PLAYER" | null) {
  useAuthStore.setState(user_type
    ? { accessToken: "t", user: { id: "u", email: "sd@meridian.test", user_type, is_superuser: false } as never }
    : { accessToken: null, user: null } as never);
}

const primaries = () => document.querySelectorAll(".bg-accent.text-on-accent");
const bar = () => screen.queryByRole("region", { name: /^Actions for/ });

async function openMore() {
  const triggers = screen.getAllByRole("button", { name: "More ⋯" });
  await userEvent.click(triggers[triggers.length - 1]);
  return screen.getByRole("menu");
}

describe("PlayerMarketDetailPage actions", () => {
  beforeEach(() => {
    player = playerFixture();
    myOffer = null;
    caps.marketWrite = true;
    listings.map = new Map();
    listings.known = true;
    viewport(1280);
    signIn("CLUB");
    api.get.mockReset().mockImplementation(serve);
    api.post.mockReset().mockResolvedValue({ data: { id: "d9" } });
    confirm.mockReset().mockResolvedValue(true);
  });

  it("another club's player from 1024px: Shortlist, Ask his club, one primary Make an offer, and More", async () => {
    renderPage();
    const offer = await screen.findByRole("link", { name: "Make an offer" });
    expect(offer).toHaveAttribute("href", "/offers/new?player_id=p1");
    expect(screen.getByRole("button", { name: "Ask his club" })).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /Shortlist/ }).length).toBeGreaterThan(0);
    expect(primaries()).toHaveLength(1);
    expect(bar()).toBeNull();
    const menu = await openMore();
    expect(within(menu).getByRole("menuitem", { name: "Compare with others" })).toBeInTheDocument();
    expect(within(menu).getByRole("menuitem", { name: "✦ Ask TransferX about him" })).toBeInTheDocument();
    expect(within(menu).getByRole("menuitem", { name: "View Chelsea" })).toHaveAttribute("href", "/clubs/chelsea");
    expect(screen.queryByText("Ask about him")).toBeNull();
  });

  it("below 1024px the actions sit in the bottom bar, and the header has only Shortlist and More", async () => {
    viewport(390);
    renderPage();
    const region = await screen.findByRole("region", { name: "Actions for João Pedro" });
    expect(within(region).getByRole("button", { name: "Ask his club" })).toBeInTheDocument();
    expect(within(region).getByRole("link", { name: "Make an offer" })).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "Make an offer" })).toHaveLength(2); // the bar; the header's copy is hidden below lg
    expect(screen.getByRole("button", { name: "Shortlist João Pedro" })).toBeInTheDocument();
    await userEvent.click(within(region).getByRole("button", { name: "Ask his club" }));
    expect(screen.getByRole("dialog", { name: "Ask Chelsea" })).toBeInTheDocument();
  });

  it("the release clause is a More item that opens today's confirm and posts", async () => {
    player = playerFixture({ active_contract: { release_clause: 40_000_000, end_date: "2030-06-30" } });
    renderPage();
    await screen.findByRole("link", { name: "Make an offer" });
    expect(screen.queryByRole("button", { name: /release clause/i })).toBeNull();
    const menu = await openMore();
    await userEvent.click(within(menu).getByRole("menuitem", { name: "Pay the release clause (£40,000,000)…" }));
    expect(confirm).toHaveBeenCalledWith(expect.objectContaining({ title: "Trigger release clause?", confirmLabel: "Trigger clause", variant: "danger" }));
    await waitFor(() => expect(api.post).toHaveBeenCalledWith("/players/p1/trigger-release-clause"));
  });

  it("a free agent: the sentence, and Sign him with today's confirm", async () => {
    player = playerFixture({ status: "FREE_AGENT", current_club: null, active_contract: null });
    const first = renderPage();
    expect(await screen.findByText("Free agent. There's no fee: you agree his wage and contract.")).toBeInTheDocument();
    first.unmount();
    renderPage();
    await userEvent.click(await screen.findByRole("button", { name: "Sign him" }));
    expect(confirm).toHaveBeenCalledWith(expect.objectContaining({ title: "Sign free agent?", confirmLabel: "Sign player" }));
    await waitFor(() => expect(api.post).toHaveBeenCalledWith("/players/p1/sign-free-agent"));
    // Then on to the deal, as today.
    await waitFor(() => expect(screen.getByTestId("where")).toHaveTextContent("/deals/d9"));
  });

  it("pre-contract: Make an offer, and Offer a pre-contract with today's confirm and the end date", async () => {
    const soon = new Date(Date.now() + 90 * 86_400_000).toISOString().slice(0, 10);
    player = playerFixture({ active_contract: { release_clause: null, end_date: soon } });
    renderPage();
    expect(await screen.findByRole("link", { name: "Make an offer" })).toBeInTheDocument();
    expect(screen.getByText(/^His contract ends .*You can agree a free move for then, or buy him now\.$/)).toBeInTheDocument();
    const menu = await openMore();
    expect(within(menu).getByRole("menuitem", { name: "Ask his club" })).toBeInTheDocument();
    await userEvent.keyboard("{Escape}");
    await userEvent.click(screen.getByRole("button", { name: "Offer a pre-contract" }));
    expect(confirm).toHaveBeenCalledWith(expect.objectContaining({ title: "Offer a pre-contract?", confirmLabel: "Offer pre-contract" }));
    await waitFor(() => expect(api.post).toHaveBeenCalledWith("/players/p1/pre-contract"));
  });

  it("a deal in progress: the buyer gets View the deal and a sentence; anyone else today's banner and no link", async () => {
    const deal = { id: "d1", status: "IN_PROGRESS", stage: "PAPERWORK", agreed_fee: 1, completed_at: null,
      buyer_club: { id: "us", name: "Meridian FC" }, seller_club: { id: "chelsea", name: "Chelsea" } };
    player = playerFixture({ active_deal: deal });
    const first = renderPage();
    expect(await screen.findByRole("link", { name: "View the deal" })).toHaveAttribute("href", "/deals/d1");
    expect(screen.getByText("Your deal with Chelsea is at paperwork. New offers are paused until it finishes or falls through.")).toBeInTheDocument();
    expect(screen.queryByText("Transfer in progress")).toBeNull();
    first.unmount();

    player = playerFixture({ active_deal: { ...deal, buyer_club: { id: "arsenal", name: "Arsenal" } } });
    renderPage();
    expect(await screen.findByText("Transfer in progress")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "View the deal" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Make an offer" })).toBeNull();
    expect(primaries()).toHaveLength(0);
  });

  it("without MARKET_WRITE: no primary, the role sentence, and no disabled button", async () => {
    caps.marketWrite = false;
    renderPage();
    expect(await screen.findByText("Your role can't send offers. Ask your club's owner or sporting director.")).toBeInTheDocument();
    expect(primaries()).toHaveLength(0);
    expect(document.querySelectorAll("button[disabled]")).toHaveLength(0);
  });

  it("his own club: List for sale opens the modal; listed, View listing", async () => {
    player = playerFixture({ current_club: { id: "us", name: "Meridian FC", crest_url: null } });
    const first = renderPage();
    await userEvent.click(await screen.findByRole("button", { name: "List for sale" }));
    expect(screen.getByRole("dialog", { name: "List for sale" })).toBeInTheDocument();
    first.unmount();

    listings.map = new Map([["p1", "s9"]]);
    renderPage();
    expect(await screen.findByRole("link", { name: "View listing" })).toHaveAttribute("href", "/sales/s9");
  });

  it("at a club off TransferX: no primary, today's sentence, Shortlist still there", async () => {
    player = playerFixture({ status: "EXTERNAL", current_club: null, world_team: { id: "w1", name: "Hamburger SV", crest_url: null } });
    renderPage();
    expect(await screen.findByText("Hamburger SV is not on TransferX, so an offer could not be answered. Shortlist him to follow his form and contract.")).toBeInTheDocument();
    expect(primaries()).toHaveLength(0);
    expect(screen.getAllByRole("button", { name: /Shortlist/ }).length).toBeGreaterThan(0);
  });

  it.each(["AGENT", "PLAYER"] as const)("a %s account: no bar and no transfer action", async (type) => {
    signIn(type);
    viewport(390);
    renderPage();
    await screen.findByRole("heading", { level: 1, name: "João Pedro" });
    expect(bar()).toBeNull();
    expect(screen.queryByRole("link", { name: "Make an offer" })).toBeNull();
    // An agent's one blue button is his own: "Represent this player".
    expect(primaries().length).toBeLessThanOrEqual(1);
  });

  it("signed out: Sign in to make an offer goes to /login", async () => {
    signIn(null);
    renderPage();
    expect(await screen.findByRole("link", { name: "Sign in to make an offer" })).toHaveAttribute("href", "/login");
  });

  it("with our offer open: View your offer, and where it stands, never a second Make an offer", async () => {
    myOffer = {
      id: "o7", status: "COUNTERED", deal_type: "PERMANENT", fee_amount: "34000000", loan_fee: null,
      last_actor_club_id: "chelsea", to_club: { id: "chelsea", name: "Chelsea" },
    };
    renderPage();
    const view = await screen.findByRole("link", { name: "View your offer" });
    expect(view).toHaveAttribute("href", "/offers/o7");
    expect(screen.getByText("Chelsea countered at £34M. It's your move.")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Make an offer" })).toBeNull();
    expect(primaries()).toHaveLength(1);
  });
});
