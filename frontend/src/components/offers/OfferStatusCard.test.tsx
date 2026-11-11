import { describe, expect, it, vi } from "vitest";
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../../test/utils";
import type { Offer } from "../../types/api";
import type { OfferActions } from "../../hooks/useOfferActions";
import type { OfferStatusView } from "./offerStatus";
import OfferStatusCard from "./OfferStatusCard";

vi.mock("../../context/ConfirmContext", () => ({ useConfirm: () => vi.fn() }));

const idle = { isError: false, isPending: false, error: null, mutate: vi.fn() };
const actions = { accept: idle, reject: idle, withdraw: idle } as unknown as OfferActions;

const view = (n: number): OfferStatusView => ({
  tone: "you", overline: "Your move", headline: "Meridian FC countered at £4,200,000",
  changes: Array.from({ length: n }, (_, i) => ({ label: `Term ${i + 1}`, was: "None", now: `£${i + 1}` })),
});

function renderCard(n: number, onShowAllChanges = vi.fn()) {
  renderWithProviders(
    <OfferStatusCard view={view(n)} offer={{ deal_type: "PERMANENT" } as Offer} actions={actions} desktop={false}
      onCounter={vi.fn()} onRaise={vi.fn()} onOpenMessages={vi.fn()} onShowAllChanges={onShowAllChanges} />,
  );
  return onShowAllChanges;
}

describe("OfferStatusCard: what they changed", () => {
  it("shows four changes, then a link to the rest that opens the terms", async () => {
    const onShowAll = renderCard(6);
    const list = screen.getByRole("list", { name: "What they changed" });
    expect(within(list).getAllByText(/^Term \d$/)).toHaveLength(4);
    await userEvent.click(within(list).getByRole("button", { name: "and 2 more changes" }));
    expect(onShowAll).toHaveBeenCalled();
  });

  it("no link when four or fewer changed", () => {
    renderCard(4);
    expect(screen.queryByRole("button", { name: /more change/ })).toBeNull();
  });

  it("one more is singular", () => {
    renderCard(5);
    expect(screen.getByRole("button", { name: "and 1 more change" })).toBeInTheDocument();
  });
});
