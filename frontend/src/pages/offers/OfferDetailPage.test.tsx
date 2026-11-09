import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes, useLocation } from "react-router-dom";
import { renderWithProviders } from "../../test/utils";
import { useAuthStore } from "../../store/auth";
import OfferDetailPage from "./OfferDetailPage";

const api = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn(), defaults: { baseURL: "" } }));
vi.mock("../../lib/api", () => ({ default: api }));
const confirm = vi.hoisted(() => vi.fn());
vi.mock("../../context/ConfirmContext", () => ({ useConfirm: () => confirm, useAskReason: () => vi.fn() }));
const addToast = vi.hoisted(() => vi.fn());
vi.mock("../../context/ToastContext", () => ({ useToast: () => ({ addToast }) }));
const canWrite = vi.hoisted(() => ({ value: true }));
vi.mock("../../hooks/useClubCapabilities", () => ({ useClubCapabilities: () => ({ can: () => canWrite.value }) }));
// The page's own sections are tested elsewhere; here, only where they mount.
const unread = vi.hoisted(() => ({ n: 0 }));
vi.mock("../../components/conversation/ConversationPanel", () => ({ default: () => <p>MESSAGES</p>, useConversationUnread: () => unread.n }));
vi.mock("../../components/sales/SellerOrderBook", () => ({ default: () => <p>ORDER BOOK</p> }));
vi.mock("../../components/sales/BuyerOrderBook", () => ({ default: () => <p>RANKING</p> }));
vi.mock("../../components/demo/DemoOfferControls", () => ({ default: () => null }));

const BUYER = "buyer-club";
const SELLER = "seller-club";

function offer(over: Record<string, unknown> = {}) {
  return {
    id: "o1", status: "SENT", deal_type: "PERMANENT", fee_amount: "4200000.00", loan_fee: null, wage_weekly: null,
    contract_years: null, contract_end_date: null, instalments: [], clauses: [], sell_on_pct: null, add_ons: null,
    from_club_id: BUYER, to_club_id: SELLER, last_actor_club_id: BUYER, is_anonymous: false, buyer_league_name: null,
    from_club: { id: BUYER, name: "Meridian FC", crest_url: null }, to_club: { id: SELLER, name: "Ashfield United", crest_url: null },
    player: { id: "p", name: "Marcus Webb", position: "FWD", photo_url: null }, player_id: "p", sale_id: null, deal: null,
    expires_at: null, created_at: "2026-11-03T09:00:00Z", last_action_at: "2026-11-09T08:30:00Z",
    option_to_buy: null, obligation_to_buy: false, obligation_conditions: null, recall_allowed: false,
    loan_start: null, loan_end: null, wage_split_pct: null, messages: [],
    events: [{ id: "e1", offer_id: "o1", event_type: "SENT", actor_club_id: BUYER, payload: { fee_amount: "4200000" }, created_at: "2026-11-03T09:00:00Z" }],
    ...over,
  };
}

let current = offer();
let me = SELLER;
let card: unknown = { other_club: "Meridian FC", your_valuation: 4_800_000, counter_suggestion: 4_600_000, expires_at: null, disabled_reason: null };

function serve(url: string) {
  if (url === "/offers/o1") return Promise.resolve({ data: current });
  if (url === "/clubs/me") return Promise.resolve({ data: { id: me, name: me === SELLER ? "Ashfield United" : "Meridian FC" } });
  if (url === "/lite/offers/o1") return card ? Promise.resolve({ data: card }) : Promise.reject(new Error("404"));
  if (url === "/ai/status") return Promise.resolve({ data: { available: false } });
  return Promise.resolve({ data: [] });
}

function Where() {
  const loc = useLocation();
  return <p data-testid="where">{loc.pathname}{loc.search}</p>;
}

function renderPage(path = "/offers/o1") {
  return renderWithProviders(
    <Routes>
      <Route path="/offers/:id" element={<><OfferDetailPage /><Where /></>} />
      <Route path="/deals/:id" element={<Where />} />
    </Routes>,
    { initialPath: path },
  );
}

function desktop(matches: boolean) {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: query.includes("min-width: 1024px") ? matches : false, media: query, onchange: null,
    addListener: vi.fn(), removeListener: vi.fn(), addEventListener: vi.fn(), removeEventListener: vi.fn(), dispatchEvent: vi.fn(),
  }));
}

const counterPosts = () => api.post.mock.calls.filter(([url]) => url === "/offers/o1/counter");

describe("OfferDetailPage, answer first", () => {
  beforeEach(() => {
    current = offer();
    me = SELLER;
    card = { other_club: "Meridian FC", your_valuation: 4_800_000, counter_suggestion: 4_600_000, expires_at: null, disabled_reason: null };
    canWrite.value = true;
    unread.n = 0;
    desktop(false);
    api.get.mockReset().mockImplementation(serve);
    api.post.mockReset().mockImplementation((url: string) =>
      Promise.resolve({ data: url === "/ai/offer-check" ? { warnings: [] } : current }));
    confirm.mockReset().mockResolvedValue(true);
    addToast.mockReset();
    useAuthStore.setState({ accessToken: "t", user: { id: "u", email: "sd@ashfield.test", user_type: "CLUB", is_superuser: false } as never });
  });

  it("names the player as the heading, and offers Accept and Counter", async () => {
    renderPage();
    expect(await screen.findByRole("heading", { level: 1, name: "Marcus Webb" })).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Accept £4,200,000" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Counter" })).toBeInTheDocument();
    expect(await screen.findByText("That's £600,000 under your £4,800,000 valuation.")).toBeInTheDocument();
  });

  it("below 1024px, Counter opens a sheet; a one-tap amount sets the fee and Send posts only the fee", async () => {
    renderPage();
    await screen.findByText(/under your £4,800,000 valuation/);
    await userEvent.click(screen.getByRole("button", { name: "Counter" }));
    const sheet = screen.getByRole("dialog", { name: "Counter Meridian FC" });
    const fee = within(sheet).getByLabelText("Fee you'll accept");
    expect(fee).toHaveFocus();
    await userEvent.click(within(sheet).getByRole("button", { name: /Your valuation/ }));
    expect(fee).toHaveValue("4,800,000");
    expect(within(sheet).getByRole("button", { name: /Your valuation/ })).toHaveAttribute("aria-pressed", "true");
    expect(within(sheet).getByText("£4,800,000: £600,000 more than their offer, at your valuation")).toBeInTheDocument();
    await userEvent.click(within(sheet).getByRole("button", { name: "Send counter" }));
    await waitFor(() => expect(counterPosts()).toHaveLength(1));
    // The same body as before for a fee-only change on an offer with no wage or contract set.
    expect(counterPosts()[0][1]).toEqual({ fee_amount: 4_800_000 });
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    await waitFor(() => expect(screen.getByRole("heading", { level: 2, name: /Meridian FC bid/ })).toHaveFocus());
  });

  it("asks before discarding a changed counter", async () => {
    confirm.mockResolvedValue(false);
    renderPage();
    await userEvent.click(await screen.findByRole("button", { name: "Counter" }));
    const sheet = screen.getByRole("dialog");
    await userEvent.type(within(sheet).getByLabelText("Fee you'll accept"), "5");
    await userEvent.click(within(sheet).getByRole("button", { name: "Close without sending" }));
    expect(confirm).toHaveBeenCalledWith(expect.objectContaining({ title: "Discard your counter?" }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("from 1024px, Counter turns the status card into the form, with what they will see", async () => {
    desktop(true);
    renderPage();
    await userEvent.click(await screen.findByRole("button", { name: "Counter" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Counter Meridian FC" })).toBeInTheDocument();
    const fee = screen.getByLabelText("Fee you'll accept");
    await userEvent.clear(fee);
    await userEvent.type(fee, "5000000");
    const panel = screen.getByRole("heading", { name: "What Meridian FC will see" }).parentElement!;
    expect(within(panel).getByText("Transfer fee")).toBeInTheDocument();
    expect(within(panel).getByText("£5,000,000")).toBeInTheDocument();
  });

  it("from a push: the counter opens with its amount, and Accept is highlighted", async () => {
    desktop(true);
    renderPage("/offers/o1?from=push&action=counter&amount=21000000");
    expect(await screen.findByLabelText("Fee you'll accept")).toHaveValue("21,000,000");
  });

  it("from a push: action=accept highlights Accept", async () => {
    desktop(true);
    renderPage("/offers/o1?from=push&action=accept");
    expect(await screen.findByText("From your notification: accept this offer?")).toBeInTheDocument();
  });

  it("accepting a loan with an obligation says so; a 202 tells the club it needs approval", async () => {
    current = offer({ deal_type: "LOAN", fee_amount: null, loan_fee: "450000", option_to_buy: "18000000", obligation_to_buy: true,
      loan_start: "2027-01-01", loan_end: "2027-06-30" });
    api.post.mockImplementation((url: string) => Promise.resolve({ data: url.endsWith("/accept") ? { approval_id: "a1" } : current }));
    renderPage();
    await userEvent.click(await screen.findByRole("button", { name: "Accept the loan" }));
    expect(confirm).toHaveBeenCalledWith(expect.objectContaining({
      title: "Accept loan", message: expect.stringContaining("This includes an obligation: he transfers permanently for £18,000,000"),
    }));
    await waitFor(() => expect(addToast).toHaveBeenCalledWith(expect.stringContaining("sent for approval"), "info"));
    expect(screen.getByTestId("where")).toHaveTextContent("/offers/o1");
  });

  it("reject asks with the danger confirm", async () => {
    renderPage();
    await userEvent.click(await screen.findByRole("button", { name: "Reject this offer" }));
    expect(confirm).toHaveBeenCalledWith({ message: "Reject this offer?", confirmLabel: "Reject", variant: "danger" });
    await waitFor(() => expect(api.post).toHaveBeenCalledWith("/offers/o1/reject"));
  });

  it("withdraw is in More, and only for the buyer", async () => {
    renderPage();
    await screen.findByRole("heading", { level: 1 });
    await userEvent.click(screen.getAllByRole("button", { name: "More ⋯" })[0]);
    expect(screen.queryByRole("menuitem", { name: "Withdraw offer…" })).not.toBeInTheDocument();
  });

  it("the waiting buyer can raise the offer, upward only, with a confirm naming the reserve", async () => {
    me = BUYER;
    card = { other_club: "Ashfield United", your_valuation: null, counter_suggestion: null, expires_at: null, disabled_reason: null };
    renderPage();
    expect(await screen.findByText("Ashfield United are considering your £4,200,000 offer")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Withdraw offer" })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Raise your offer" }));
    const sheet = screen.getByRole("dialog", { name: "Raise your offer to Ashfield United" });
    const fee = within(sheet).getByLabelText("New fee");
    await userEvent.clear(fee);
    await userEvent.type(fee, "4000000");
    await userEvent.click(within(sheet).getByRole("button", { name: "Raise offer" }));
    expect(within(sheet).getByText("Your new offer must be higher than £4,200,000.")).toBeInTheDocument();
    expect(confirm).not.toHaveBeenCalled();
    await userEvent.clear(fee);
    await userEvent.type(fee, "4500000");
    await userEvent.click(within(sheet).getByRole("button", { name: "Raise offer" }));
    expect(confirm).toHaveBeenCalledWith(expect.objectContaining({
      title: "Raise your offer?",
      message: "Ashfield United is told straight away. The extra £300,000 is reserved from your transfer budget.",
    }));
    await waitFor(() => expect(api.post).toHaveBeenCalledWith("/offers/o1/improve", { fee_amount: 4_500_000 }));

    await userEvent.click(screen.getAllByRole("button", { name: "More ⋯" })[0]);
    expect(screen.getByRole("menuitem", { name: "Withdraw offer…" })).toBeInTheDocument();
  });

  it("still works when the Lite card fails: no gap line and no suggested amounts", async () => {
    card = null;
    renderPage();
    expect(await screen.findByRole("button", { name: "Accept £4,200,000" })).toBeInTheDocument();
    expect(screen.queryByText(/valuation/)).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Counter" }));
    expect(screen.queryByRole("group", { name: "Amounts to use" })).not.toBeInTheDocument();
  });

  it("a non-party sees the read-only layout", async () => {
    me = "someone-else";
    renderPage();
    expect(await screen.findByText("Meridian FC offered £4,200,000 for Marcus Webb")).toBeInTheDocument();
    expect(screen.queryByRole("tablist")).not.toBeInTheDocument();
    expect(screen.queryByRole("complementary")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "More ⋯" })).not.toBeInTheDocument();
    expect(api.get.mock.calls.some(([url]) => url === "/lite/offers/o1")).toBe(false);
  });

  it("never names an anonymous buyer on the seller's page", async () => {
    current = offer({ from_club: null, from_club_id: null, is_anonymous: true, buyer_league_name: "Premier League",
      events: [{ id: "e1", offer_id: "o1", event_type: "SENT", actor_club_id: null, payload: { fee_amount: "4200000" }, created_at: "2026-11-03T09:00:00Z" }],
      last_actor_club_id: null });
    card = { other_club: "an undisclosed Premier League club", your_valuation: null, counter_suggestion: null, expires_at: null, disabled_reason: null };
    const { container } = renderPage();
    expect(await screen.findByText("An undisclosed Premier League club bid £4,200,000 for Marcus Webb")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Counter" }));
    expect(screen.getByRole("dialog", { name: "Counter an undisclosed Premier League club" })).toBeInTheDocument();
    expect(container.textContent + document.body.textContent).not.toMatch(/Meridian/);
  });

  it("the Messages tab counts unread messages", async () => {
    unread.n = 3;
    renderPage();
    expect(await screen.findByRole("tab", { name: "Messages, 3 unread" })).toBeInTheDocument();
  });
});
