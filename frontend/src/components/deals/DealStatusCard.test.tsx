import { describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../../test/utils";
import DealStatusCard from "./DealStatusCard";
import type { DealActions } from "../../hooks/useDealActions";
import type { DealStatusView } from "./dealStatus";
import type { Deal } from "../../types/api";

vi.mock("../../lib/api", () => ({ default: { get: vi.fn().mockResolvedValue({ data: [] }) } }));
vi.mock("../../context/ConfirmContext", () => ({ useConfirm: () => vi.fn() }));

const m = () => ({ mutate: vi.fn(), isPending: false, isError: false, error: null });
const actions = () => ({
  advance: m(), collapse: m(), paperwork: m(), recordMedical: m(), commissionRespond: m(), commissionCounter: m(),
  agentAccept: m(), setPersonalTerms: m(), termsRespond: m(), playerConsent: m(), recordAgreement: m(),
}) as unknown as DealActions;

const deal = {
  id: "d1", stage: "AGENT_NEGOTIATION", status: "IN_PROGRESS", paperwork: [], personal_terms: null,
  seller_club_id: "s", buyer_club: { name: "Meridian FC" }, seller_club: { name: "Castlebrook" },
  player: { name: "Bram Wouters" }, agent: { id: "a", display_name: "Luka Brandt", agency_name: "LB" },
} as unknown as Deal;

const view: DealStatusView = {
  tone: "you", overline: "Your move", headline: "Luka Brandt asks for 6.0%", showChecklist: false, strips: [],
  primary: { kind: "commission-respond", agreement: "AGREED", label: "Accept proposal" },
  secondary: { kind: "commission-counter", label: "Counter" },
  tertiary: { kind: "commission-respond", agreement: "DECLINED", label: "Decline", danger: true },
};

function card(a = actions()) {
  renderWithProviders(<DealStatusCard view={view} deal={deal} viewerSide="buyer" actions={a}
    onOpenMessages={vi.fn()} onShowSchedule={vi.fn()} onRecordMedical={vi.fn()} />);
  return a;
}

describe("DealStatusCard: counters and declines", () => {
  it("declining asks first, says the transfer ends, and sends the reason", async () => {
    const a = card();
    await userEvent.click(screen.getByRole("button", { name: "Decline" }));
    expect(a.commissionRespond.mutate).not.toHaveBeenCalled();
    expect(screen.getByText(/This ends the transfer/)).toHaveTextContent("Luka Brandt and Castlebrook are told.");
    await userEvent.type(screen.getByLabelText(/Reason/), "Too far apart");
    await userEvent.click(screen.getByRole("button", { name: "Decline and end the transfer" }));
    expect(a.commissionRespond.mutate).toHaveBeenCalledWith({ agreement: "DECLINED", reason: "Too far apart" }, expect.anything());
  });

  it("Counter instead opens the counter, which sends a share of the fee", async () => {
    const a = card();
    await userEvent.click(screen.getByRole("button", { name: "Decline" }));
    await userEvent.click(screen.getByRole("button", { name: "Counter instead" }));
    await userEvent.type(screen.getByLabelText("Commission (% of the fee)"), "4");
    await userEvent.selectOptions(screen.getByLabelText("Paid by"), "PLAYER");
    await userEvent.click(screen.getByRole("button", { name: "Send counter" }));
    expect(a.commissionCounter.mutate).toHaveBeenCalledWith({ commission_pct: 0.04, commission_payer: "PLAYER", note: null }, expect.anything());
    expect(a.commissionRespond.mutate).not.toHaveBeenCalled();
  });

  it("accepting goes straight through", async () => {
    const a = card();
    await userEvent.click(screen.getByRole("button", { name: "Accept proposal" }));
    expect(a.commissionRespond.mutate).toHaveBeenCalledWith({ agreement: "AGREED" });
  });
});

describe("DealStatusCard: the counter form", () => {
  it("closes once the counter is sent", async () => {
    const a = actions();
    (a.commissionCounter.mutate as ReturnType<typeof vi.fn>).mockImplementation((_v, opts) => opts?.onSuccess?.());
    card(a);
    await userEvent.click(screen.getByRole("button", { name: "Counter" }));
    await userEvent.type(screen.getByLabelText("Commission (% of the fee)"), "3");
    await userEvent.click(screen.getByRole("button", { name: "Send counter" }));
    expect(screen.queryByLabelText("Commission (% of the fee)")).toBeNull();
  });
});
