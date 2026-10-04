import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithProviders } from "../../test/utils";
import LiteOfferCardPage from "./LiteOfferCardPage";
import { Route, Routes } from "react-router-dom";

const card = vi.hoisted(() => ({ value: {} as Record<string, unknown> }));
vi.mock("../../hooks/useLite", () => ({
  useLiteOfferCard: () => ({ data: card.value, isLoading: false, error: null }),
  useTeamContact: () => ({ data: { name: "Sam", label: "Sam" } }),
}));
vi.mock("../../context/ToastContext", () => ({ useToast: () => ({ addToast: vi.fn() }) }));
vi.mock("../../hooks/useAssistant", () => ({ useOfferCheck: () => ({ data: undefined, isFetching: false }) }));
vi.mock("../../hooks/useClubDashboard", () => ({
  CLUB_DASHBOARD_KEY: ["clubs", "me", "dashboard"],
  useClubDashboard: () => ({ data: { waiting_on_you: [
    { kind: "offer", id: "o1", link: "/offers/o1", reason: "" },
    { kind: "approval", id: "a9", link: "/club/approvals", reason: "" },
  ] } }),
}));
vi.mock("../../lib/api", () => ({ default: { post: vi.fn(), get: vi.fn() } }));

const base = {
  offer_id: "o1", side: "seller", status: "SENT", player_id: "p1", player_name: "Marcus Webb", other_club: "Ashfield United",
  deal_type: "PERMANENT", fee: 18_000_000, wage_weekly: null, wage_split_pct: null, contract_years: 4, loan_start: null,
  loan_end: null, has_add_ons: false, your_move: true, counter_suggestion: 21_000_000, disabled_reason: null,
  expires_at: new Date(Date.now() + 2 * 86_400_000 + 3_600_000).toISOString(), your_valuation: 21_000_000,
};

function renderCard(path: string) {
  return renderWithProviders(
    <Routes><Route path="/lite/offers/:offerId" element={<LiteOfferCardPage />} /></Routes>,
    { initialPath: path },
  );
}

describe("LiteOfferCardPage as the push decision sheet", () => {
  beforeEach(() => { card.value = { ...base }; });

  it("shows where it is in the queue, the time left, the valuation and the ask", () => {
    renderCard("/lite/offers/o1?from=push");
    expect(screen.getByText(/Waiting on you · 1 of 2/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Next ›" })).toHaveAttribute("href", "/lite/approvals/a9?from=push");
    expect(screen.getByText(/Offer received · 2 days left/)).toBeInTheDocument();
    expect(screen.getByText("Your valuation")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^Ask for £21/ })).toBeInTheDocument();
    expect(screen.getByText("You can undo for 10 seconds after sending.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "See full details" })).toHaveAttribute("href", "/offers/o1");
  });

  it("says when the offer changed since the notification", () => {
    card.value = { ...base, status: "WITHDRAWN", your_move: false, disabled_reason: "This offer has been withdrawn." };
    renderCard("/lite/offers/o1?from=push");
    expect(screen.getByText(/This has changed since we told you: the offer has been withdrawn/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "See what happened" })).toHaveAttribute("href", "/offers/o1");
  });

  it("looks as before when opened from the app", () => {
    renderCard("/lite/offers/o1");
    expect(screen.queryByText(/Waiting on you/)).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "See full details" })).not.toBeInTheDocument();
  });
});
