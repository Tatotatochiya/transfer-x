import { describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithProviders } from "../../../test/utils";
import FactsStrip from "./FactsStrip";
import type { PlayerDetail } from "../../../types/api";

const player = { id: "p", name: "D. Rice", market_value: null, wage_weekly: null, active_contract: null } as unknown as PlayerDetail;

describe("FactsStrip last transfer", () => {
  it("shows what a club last paid for him beside the model's value", () => {
    renderWithProviders(<FactsStrip player={player} fairValue={null} form={{ score: null, trend: null }} isMyPlayer={false}
      valuationPending={false} onSaveValuation={vi.fn()}
      lastTransfer={{ fee_gbp: 99_700_000, fee_display: "€ 116.6M", date: "2023-07-15", from: "West Ham", to: "Arsenal", source: "API-Football" }} />);
    const cell = screen.getByText("Last transfer").parentElement!;
    expect(cell).toHaveTextContent("West Ham → Arsenal");
    expect(cell).toHaveTextContent("2023");
  });

  it("says when there's no fee on record", () => {
    renderWithProviders(<FactsStrip player={player} fairValue={null} form={{ score: null, trend: null }} isMyPlayer={false}
      valuationPending={false} onSaveValuation={vi.fn()} lastTransfer={null} />);
    expect(screen.getByText("No fee on record")).toBeInTheDocument();
  });
});
