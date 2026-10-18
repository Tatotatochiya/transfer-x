import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { renderWithProviders } from "../../test/utils";
import DealStaffTools from "./DealStaffTools";
import type { Deal } from "../../types/api";

const api = vi.hoisted(() => ({ post: vi.fn(() => Promise.resolve({ data: {} })) }));
vi.mock("../../lib/api", () => ({ default: api }));
const askReason = vi.hoisted(() => vi.fn());
vi.mock("../../context/ConfirmContext", () => ({ useAskReason: () => askReason }));
vi.mock("../../context/ToastContext", () => ({ useToast: () => ({ addToast: vi.fn() }) }));

const paperwork = [
  { key: "agreement_buyer", owner: "buyer", label: "Buying club signs the agreement", done: true },
  { key: "agreement_seller", owner: "seller", label: "Selling club signs the agreement", done: false },
  { key: "medical", owner: "buyer", label: "Medical", done: false },
  { key: "registration", owner: "buyer", label: "Registration", done: false },
];
const deal = (over: Partial<Deal>) => ({ id: "d1", status: "IN_PROGRESS", stage: "PAPERWORK", paperwork, medical_check: null,
  sla_deadline: null, ...over }) as unknown as Deal;

describe("DealStaffTools", () => {
  beforeEach(() => { api.post.mockClear(); askReason.mockReset().mockResolvedValue("Signed on paper, copy received"); });

  it("offers the outstanding paperwork for each club and records it with the reason", async () => {
    renderWithProviders(<DealStaffTools deal={deal({})} />);
    expect(screen.queryByRole("button", { name: "Buying club signed the agreement" })).not.toBeInTheDocument();  // done
    fireEvent.click(screen.getByRole("button", { name: "Selling club signed the agreement" }));
    await waitFor(() => expect(api.post).toHaveBeenCalledWith("/admin/deals/d1/paperwork",
      { step: "seller_signs_agreement", reason: "Signed on paper, copy received" }));
    expect(screen.getByRole("button", { name: "Passed" })).toBeInTheDocument();  // the medical, at paperwork
    expect(screen.queryByRole("button", { name: "Move on" })).not.toBeInTheDocument();  // paperwork moves on by its checklist
  });

  it("does nothing when the reason is cancelled", async () => {
    askReason.mockResolvedValueOnce(null);
    renderWithProviders(<DealStaffTools deal={deal({})} />);
    fireEvent.click(screen.getByRole("button", { name: "Collapse deal" }));
    await waitFor(() => expect(askReason).toHaveBeenCalled());
    expect(api.post).not.toHaveBeenCalled();
  });

  it("moves the completion deadline only for a deal awaiting completion", async () => {
    const { rerender } = renderWithProviders(<DealStaffTools deal={deal({})} />);
    expect(screen.queryByRole("button", { name: "Move deadline" })).not.toBeInTheDocument();
    rerender(<DealStaffTools deal={deal({ status: "PENDING_COMPLETION", stage: "CONFIRMED", sla_deadline: "2026-11-01T12:00:00Z" } as Partial<Deal>)} />);
    fireEvent.change(screen.getByLabelText("New completion deadline"), { target: { value: "2026-11-10T18:00" } });
    fireEvent.click(screen.getByRole("button", { name: "Move deadline" }));
    await waitFor(() => expect(api.post).toHaveBeenCalledWith("/admin/deals/d1/deadline",
      expect.objectContaining({ until: new Date("2026-11-10T18:00").toISOString() })));
  });

  it("says there is nothing to change once the deal is over", () => {
    renderWithProviders(<DealStaffTools deal={deal({ status: "COLLAPSED" } as Partial<Deal>)} />);
    expect(screen.getByText(/nothing to change/)).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});
