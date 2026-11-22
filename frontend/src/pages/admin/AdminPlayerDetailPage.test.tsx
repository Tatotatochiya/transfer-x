import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import AdminPlayerDetailPage from "./AdminPlayerDetailPage";
import { ConfirmProvider } from "../../context/ConfirmContext";

const api = vi.hoisted(() => ({
  get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn(),
}));
vi.mock("../../lib/api", () => ({ default: api }));

const player = {
  id: "p1", name: "Fee Player", position: "FWD", age: 25, nationality: "England",
  status: "EXTERNAL", visibility: "PUBLIC", open_to_offers: false, photo_url: null,
  created_at: "2026-11-01T00:00:00Z", contracts: [], current_club: null,
};

const fees = [
  {
    id: "f-manual", transfer_date: "2023-07-15", transfer_type: "Transfer",
    from_club: "Ajax", to_club: "Arsenal", fee_display: "£ 105M", fee_gbp: 105_000_000,
    vendor: "manual", fee_basis: "PERMANENT", source_note: "BBC Sport, 15 Jul 2023",
    source_url: null, entered_by_user_id: "su",
  },
  {
    id: "f-vendor", transfer_date: "2019-07-01", transfer_type: "Transfer",
    from_club: "Chelsea", to_club: "Ajax", fee_display: "€ 40M", fee_gbp: 34_188_034,
    vendor: "api_sports_v3", fee_basis: null, source_note: null,
    source_url: null, entered_by_user_id: null,
  },
];

function serve(feeRows = fees) {
  api.get.mockImplementation((url: string) => {
    if (url.endsWith("/transfer-fees")) return Promise.resolve({ data: feeRows });
    if (url.endsWith("/account")) return Promise.resolve({ data: { has_account: false, invitation: null } });
    return Promise.resolve({ data: player });
  });
}

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <ConfirmProvider>
        <MemoryRouter initialEntries={["/admin/players/p1"]}>
          <Routes>
            <Route path="/admin/players/:id" element={<AdminPlayerDetailPage />} />
          </Routes>
        </MemoryRouter>
      </ConfirmProvider>
    </QueryClientProvider>,
  );
}

describe("AdminPlayerDetailPage transfer fees", () => {
  beforeEach(() => {
    api.get.mockReset();
    api.post.mockReset();
    api.delete.mockReset();
  });

  it("lists every fee and only lets staff remove their own rows", async () => {
    serve();
    renderPage();
    expect(await screen.findByText("BBC Sport, 15 Jul 2023")).toBeInTheDocument();
    expect(screen.getByText("£ 105M")).toBeInTheDocument();
    expect(screen.getByText("€ 40M")).toBeInTheDocument();
    expect(screen.getByText("Staff-entered")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /Remove the fee/ })).toHaveLength(1);
  });

  it("records a fee with the source it came from", async () => {
    serve();
    renderPage();
    await screen.findByText("£ 105M");
    api.post.mockResolvedValue({ data: fees[0] });

    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Amount"), "105000000");
    fireEvent.change(screen.getByLabelText("Transfer date"), { target: { value: "2023-07-15" } });
    await user.type(screen.getByLabelText("From club"), "Ajax");
    await user.type(screen.getByLabelText("To club"), "Arsenal");
    await user.type(screen.getByLabelText("Source note (staff only)"), "BBC Sport, 15 Jul 2023");
    await user.click(screen.getByRole("button", { name: "Record fee" }));

    await waitFor(() => expect(api.post).toHaveBeenCalledWith("/admin/players/p1/transfer-fees", {
      amount: 105_000_000,
      currency: "GBP",
      transfer_date: "2023-07-15",
      from_club: "Ajax",
      to_club: "Arsenal",
      basis: "PERMANENT",
      source_note: "BBC Sport, 15 Jul 2023",
      source_url: undefined,
    }));
  });

  it("removes a staff-entered fee only after the confirmation step, with a reason", async () => {
    serve();
    renderPage();
    await screen.findByText("£ 105M");
    api.delete.mockResolvedValue({ data: null });
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Remove the fee from 2023-07-15" }));
    expect(api.delete).not.toHaveBeenCalled();
    expect(screen.getByText("His model value is recalculated straight away.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Remove" })).toBeDisabled();  // no reason yet
    await user.type(screen.getByRole("textbox", { name: /^Why\?/ }), "Wrong figure, see statement");
    await user.click(screen.getByRole("button", { name: "Remove" }));
    await waitFor(() =>
      expect(api.delete).toHaveBeenCalledWith("/admin/players/p1/transfer-fees/f-manual",
        { data: { reason: "Wrong figure, see statement" } }));
  });
});
