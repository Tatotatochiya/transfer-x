import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { renderWithProviders } from "../../../test/utils";
import type { LedgerStats, PlayerLedger } from "../../../types/api";
import { CareerLedger, InjuriesLedger, OverviewLedger } from "./LedgerTabs";

const stats = (over: Partial<LedgerStats>): LedgerStats => ({
  apps: 0, starts: 0, minutes: 0, goals: 0, assists: 0, shots: 0, key_passes: 0, passes: 0, tackles: 0,
  interceptions: 0, duels_won: 0, duels_total: 0, yellow_cards: 0, red_cards: 0, pass_accuracy: null, rating: null, ...over,
});

const LEDGER: PlayerLedger = {
  player_id: "p1",
  seasons: [
    {
      season: "2024", label: "2024/25", club: "Real Betis", club_logo: null, is_loan: false,
      totals: stats({ apps: 22, starts: 18, minutes: 1980, goals: 5, assists: 2, key_passes: 31, pass_accuracy: 81, rating: 7.09 }),
      competitions: [
        { name: "La Liga", logo: null, ...stats({ apps: 20, minutes: 1800, goals: 4, rating: 7.0 }) },
        { name: "Copa del Rey", logo: null, ...stats({ apps: 2, minutes: 180, goals: 1, rating: 8.0 }) },
      ],
    },
    {
      season: "2023", label: "2023/24", club: "Girona", club_logo: null, is_loan: true,
      totals: stats({ apps: 10, starts: 8, minutes: 800, rating: 6.8 }),
      competitions: [{ name: "La Liga", logo: null, ...stats({ apps: 10, minutes: 800 }) }],
    },
  ],
  career: stats({ apps: 32, starts: 26, minutes: 2780, goals: 5, assists: 2, rating: 7.0 }),
  internationals: [],
  transfers: [
    { date: "2024-07-01", season: "2024", type: "Transfer", fee: "€ 8M", from: "Girona", from_logo: null, to: "Real Betis", to_logo: null },
    { date: "2023-08-01", season: "2023", type: "Loan", fee: null, from: "Real Betis", from_logo: null, to: "Girona", to_logo: null },
  ],
  injuries: {
    periods: [{ start: "2025-01-10", end: "2025-01-30", type: "Knee Injury", season: "2024", games_missed: 3, severe: true }],
    by_season: { "2024": { injuries: 1, games_missed: 3, longest: 3, availability: 90 }, "2023": { injuries: 0, games_missed: 0, longest: 0, availability: null } },
  },
  form: { score: 72, trend: 4, recent: [{ date: "2025-05-01", opponent: "Sevilla", opponent_logo: null, home: true, minutes: 90, rating: 7.6, competition: "La Liga" }] },
};

describe("Season ledger", () => {
  it("opens the current season's competitions and switches column sets", async () => {
    let set: "output" | "passing" | "defending" = "output";
    const { rerender } = renderWithProviders(<OverviewLedger ledger={LEDGER} statSet={set} onStatSet={(s) => { set = s; }} />);
    expect(screen.getByText("Copa del Rey")).toBeInTheDocument(); // current season expanded
    expect(screen.getByText("G+A/90")).toBeInTheDocument();
    expect(screen.getByText("LOAN")).toBeInTheDocument();
    expect(screen.getByText("Sev")).toBeInTheDocument(); // last-5 chip (shown in capitals by CSS)

    await userEvent.click(screen.getByRole("tab", { name: "Passing" }));
    expect(set).toBe("passing");
    rerender(<OverviewLedger ledger={LEDGER} statSet="passing" onStatSet={() => undefined} />);
    expect(screen.getByText("Pass %")).toBeInTheDocument();
    expect(screen.getByText("81%")).toBeInTheDocument();
  });

  it("puts each transfer under its season, with the fee or Undisclosed", () => {
    renderWithProviders(<CareerLedger ledger={LEDGER} />);
    expect(screen.getByText("€ 8M")).toBeInTheDocument();
    expect(screen.getByText("Loan")).toBeInTheDocument();
    expect(screen.getByText("2 moves · 1 fee")).toBeInTheDocument();
  });

  it("summarises injuries and shows the season's injury under it", () => {
    renderWithProviders(<InjuriesLedger ledger={LEDGER} />);
    expect(screen.getByText("Knee Injury")).toBeInTheDocument(); // the hurt season starts open
    expect(screen.getAllByText("90%").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Since 2023/24")).toHaveLength(2); // the tile and the career footer
  });

  it("asks a signed-out visitor to sign in for injuries", () => {
    renderWithProviders(<InjuriesLedger ledger={{ ...LEDGER, injuries: null }} />);
    expect(screen.getByText("Sign in to see his injury record.")).toBeInTheDocument();
  });
});
