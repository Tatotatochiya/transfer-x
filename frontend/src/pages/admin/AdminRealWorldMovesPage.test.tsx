import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../../test/utils";
import AdminRealWorldMovesPage from "./AdminRealWorldMovesPage";

const api = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }));
vi.mock("../../lib/api", () => ({ default: api }));
const askReason = vi.hoisted(() => vi.fn());
vi.mock("../../context/ConfirmContext", () => ({ useAskReason: () => askReason }));
const addToast = vi.hoisted(() => vi.fn());
vi.mock("../../context/ToastContext", () => ({ useToast: () => ({ addToast }) }));

const move = (over: Record<string, unknown>) => ({
  player_id: "p", name: "Someone", photo_url: null, position: "DEF", kind: "transfer",
  registered_club_id: "b", registered_club: "Bournemouth", real_team_vendor_id: "47", real_club: "Tottenham",
  real_club_logo: null, real_club_on_transferx_id: "t", moved_on: "2026-06-30", fee: "Free",
  last_played: "2026-09-19", season: "2026", apply_blocked: null, ...over,
});

const listing = {
  season: "2026", checked: 680,
  counts: { transfer: 2, loan: 1, loan_return: 0, playing: 0, to_transferx_club: 1 },
  mismatches: [
    move({ player_id: "senesi", name: "M. Senesi" }),
    move({ player_id: "gone", name: "Gone Abroad", real_club: "Al-Hilal Saudi FC", real_club_on_transferx_id: null, fee: "€ 40M" }),
    move({ player_id: "loan", name: "On Loan", kind: "loan", fee: null,
           apply_blocked: "A loan to a club outside TransferX doesn't change his registration." }),
  ],
};

describe("AdminRealWorldMovesPage", () => {
  beforeEach(() => {
    api.get.mockReset().mockResolvedValue({ data: listing });
    api.post.mockReset().mockResolvedValue({ data: { applied: [{ player_id: "senesi", name: "M. Senesi" }], skipped: [] } });
    askReason.mockReset().mockResolvedValue("Confirmed summer transfers");
    addToast.mockReset();
  });

  it("lists each move with what happened, and why a loan can't be applied", async () => {
    renderWithProviders(<AdminRealWorldMovesPage />);
    expect(await screen.findByText("3 of 680 contracted players moved in the 2026/27 season", { exact: false })).toBeInTheDocument();
    const loanRow = screen.getByText("On Loan").closest("tr")!;
    expect(within(loanRow).getByText(/doesn't change his registration/)).toBeInTheDocument();
    expect(within(loanRow).queryByRole("button", { name: "Apply" })).not.toBeInTheDocument();
    expect(within(loanRow).getByRole("checkbox")).toBeDisabled();
    expect(within(screen.getByText("Gone Abroad").closest("tr")!).getByText(/€ 40M/)).toBeInTheDocument();
  });

  it("applies every selectable move at once, with the reason", async () => {
    renderWithProviders(<AdminRealWorldMovesPage />);
    await screen.findByText("M. Senesi");
    await userEvent.click(screen.getByRole("checkbox", { name: /Select every move/ }));
    await userEvent.click(screen.getByRole("button", { name: "Apply 2 selected" }));
    await waitFor(() => expect(api.post).toHaveBeenCalledWith("/admin/real-world-moves/apply",
      { player_ids: ["senesi", "gone"], reason: "Confirmed summer transfers" }));
    expect(addToast).toHaveBeenCalledWith("1 registration updated", "success");
  });

  it("dismisses a move with a reason, and does nothing if cancelled", async () => {
    renderWithProviders(<AdminRealWorldMovesPage />);
    const row = (await screen.findByText("On Loan")).closest("tr")!;
    askReason.mockResolvedValueOnce(null);
    await userEvent.click(within(row).getByRole("button", { name: "Dismiss" }));
    expect(api.post).not.toHaveBeenCalled();
    await userEvent.click(within(row).getByRole("button", { name: "Dismiss" }));
    await waitFor(() => expect(api.post).toHaveBeenCalledWith("/admin/real-world-moves/loan/dismiss", { reason: "Confirmed summer transfers" }));
  });
});
