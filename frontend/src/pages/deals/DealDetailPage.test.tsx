import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes, useLocation } from "react-router-dom";
import { renderWithProviders } from "../../test/utils";
import { useAuthStore } from "../../store/auth";
import DealDetailPage from "./DealDetailPage";

const api = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn(), put: vi.fn(), defaults: { baseURL: "" } }));
vi.mock("../../lib/api", () => ({ default: api }));
const confirm = vi.hoisted(() => vi.fn());
vi.mock("../../context/ConfirmContext", () => ({ useConfirm: () => confirm, useAskReason: () => vi.fn() }));
vi.mock("../../context/ToastContext", () => ({ useToast: () => ({ addToast: vi.fn() }) }));
const canWrite = vi.hoisted(() => ({ value: true }));
vi.mock("../../hooks/useClubCapabilities", () => ({ useClubCapabilities: () => ({ can: () => canWrite.value }) }));
// The room's own components are tested elsewhere; here, only where they mount.
const mounts = vi.hoisted(() => ({ messages: 0 }));
vi.mock("../../components/deals/DealRoomPanel", () => ({
  DealMessages: () => { mounts.messages += 1; return <p>MESSAGES</p>; },
  DealDocuments: () => <p>DOCUMENTS</p>,
}));
vi.mock("../../components/deals/DealTimeline", () => ({ default: () => <p>TIMELINE</p> }));
vi.mock("../../components/deals/TermsDiffSpine", () => ({ default: () => null }));

const steps = [
  { key: "agreement_buyer", owner: "buyer", label: "Buying club signs the transfer agreement", done: false },
  { key: "agreement_seller", owner: "seller", label: "Selling club signs the transfer agreement", done: true },
  { key: "medical", owner: "buyer", label: "Buying club records a passed medical", done: false },
  { key: "registration", owner: "buyer", label: "Buying club submits the registration", done: false },
];

function deal(over: Record<string, unknown> = {}) {
  return {
    id: "d1", offer_id: null, buyer_club_id: "b", seller_club_id: "s", player_id: "p", agreed_fee: 5_400_000,
    agreed_wage_weekly: null, status: "IN_PROGRESS", stage: "PAPERWORK", deal_type: "PERMANENT", paperwork: steps,
    agreement_signed_by_buyer_at: null, agreement_signed_by_seller_at: "2026-11-10T09:00:00Z", sla_deadline: null,
    clauses: [], instalments: [], personal_terms: null, medical_check: null, agent: null, commission_agent_id: null,
    agent_commission_pct: null, agent_commission_amount: null, commission_payer: null, sell_on_pct: null,
    signing_bonus: null, contract_length_years: null, is_auction_deal: false, completed_at: null,
    created_at: "2026-11-01T10:00:00Z", updated_at: "2026-11-10T10:00:00Z", deal_notes: [],
    buyer_club: { id: "b", name: "Meridian FC", crest_url: null }, seller_club: { id: "s", name: "Castlebrook", crest_url: null },
    player: { id: "p", name: "Bram Wouters", position: "MID" }, ...over,
  };
}

let current = deal();
function serve(url: string) {
  if (url === "/deals/d1") return { data: current };
  if (url === "/clubs/me") return { data: { id: "b", name: "Meridian FC" } };
  if (url === "/deals/d1/real-world") return { data: { hold: null, note: null, window: null, window_opens_at: null } };
  if (url.startsWith("/valuation/")) return { data: null };
  return { data: [] };
}

function Where() {
  const loc = useLocation();
  return <p data-testid="where">{loc.search}</p>;
}

function renderPage(path = "/deals/d1") {
  return renderWithProviders(
    <Routes><Route path="/deals/:id" element={<><DealDetailPage /><Where /></>} /></Routes>,
    { initialPath: path },
  );
}

function desktop(matches: boolean) {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches, media: query, onchange: null, addListener: vi.fn(), removeListener: vi.fn(),
    addEventListener: vi.fn(), removeEventListener: vi.fn(), dispatchEvent: vi.fn(),
  }));
}

describe("DealDetailPage, answer first", () => {
  beforeEach(() => {
    current = deal();
    canWrite.value = true;
    mounts.messages = 0;
    desktop(false);
    api.get.mockReset().mockImplementation((url: string) => Promise.resolve(serve(url)));
    api.post.mockReset().mockResolvedValue({ data: current });
    confirm.mockReset().mockResolvedValue(true);
    useAuthStore.setState({ accessToken: "t", user: { id: "u", email: "sd@meridian.test", user_type: "CLUB", is_superuser: false } as never });
  });

  it("names the player as the page's heading, with none of the old blocks", async () => {
    renderPage();
    expect(await screen.findByRole("heading", { level: 1, name: "Bram Wouters" })).toBeInTheDocument();
    expect(screen.queryByText(/Blocked on/)).not.toBeInTheDocument();
    expect(screen.queryByText("Next steps")).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Actions" })).not.toBeInTheDocument();
  });

  it("signs the agreement from the status card, through the existing confirm", async () => {
    renderPage();
    await userEvent.click(await screen.findByRole("button", { name: "Mark the agreement signed" }));
    expect(confirm).toHaveBeenCalledWith(expect.objectContaining({ title: "Sign the transfer agreement" }));
    await waitFor(() => expect(api.post).toHaveBeenCalledWith("/deals/d1/paperwork/sign-agreement"));
  });

  it("asks before completing the transfer (D9)", async () => {
    current = deal({ stage: "CONFIRMED", status: "PENDING_COMPLETION", paperwork: steps.map((s) => ({ ...s, done: true })) });
    confirm.mockResolvedValueOnce(false);
    renderPage();
    const complete = await screen.findByRole("button", { name: "Complete transfer" });
    await userEvent.click(complete);
    expect(confirm).toHaveBeenCalledWith(expect.objectContaining({ title: "Complete the transfer?" }));
    expect(api.post).not.toHaveBeenCalled();
    await userEvent.click(complete);
    await waitFor(() => expect(api.post).toHaveBeenCalledWith("/deals/d1/advance"));
  });

  it("below 1024px, the sections are tabs written to ?tab=", async () => {
    renderPage();
    const tabs = await screen.findByRole("tablist", { name: "Deal sections" });
    await userEvent.click(within(tabs).getByRole("tab", { name: "Messages" }));
    expect(screen.getByText("MESSAGES")).toBeInTheDocument();
    expect(screen.getByTestId("where")).toHaveTextContent("?tab=messages");
  });

  it("opens Documents from the link", async () => {
    renderPage("/deals/d1?tab=documents");
    expect(await screen.findByText("DOCUMENTS")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Documents" })).toHaveAttribute("aria-selected", "true");
  });

  it("from 1024px, messages sit in a rail and mount once", async () => {
    desktop(true);
    renderPage();
    const rail = await screen.findByRole("complementary", { name: "Messages and documents" });
    expect(within(rail).getByText("MESSAGES")).toBeInTheDocument();
    expect(screen.getAllByText("MESSAGES")).toHaveLength(1);
    expect(screen.queryByRole("tablist", { name: "Deal sections" })).not.toBeInTheDocument();
  });

  it("collapse is in the More menu only, for a club that can write, and opens the dialog", async () => {
    renderPage();
    await screen.findByRole("heading", { level: 1 });
    expect(screen.queryByRole("button", { name: /Collapse deal/ })).not.toBeInTheDocument();
    await userEvent.click(screen.getAllByRole("button", { name: "More ⋯" })[0]);
    await userEvent.click(screen.getByRole("menuitem", { name: "Collapse deal…" }));
    expect(screen.getByRole("dialog", { name: "Collapse this deal?" })).toBeInTheDocument();
  });

  it("without DEAL_WRITE there is nothing to do, and no collapse", async () => {
    canWrite.value = false;
    renderPage();
    expect(await screen.findByText("Your club's move")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Mark the agreement signed" })).not.toBeInTheDocument();
    await userEvent.click(screen.getAllByRole("button", { name: "More ⋯" })[0]);
    expect(screen.queryByRole("menuitem", { name: "Collapse deal…" })).not.toBeInTheDocument();
  });

  it("never asks for fair value for a player identity", async () => {
    useAuthStore.setState({ user: { id: "u2", email: "bram@test", user_type: "PLAYER", is_superuser: false } as never });
    renderPage();
    await screen.findByRole("heading", { level: 1 });
    expect(api.get.mock.calls.some(([url]) => String(url).startsWith("/valuation/"))).toBe(false);
  });
});
