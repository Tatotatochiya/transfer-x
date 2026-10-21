import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithProviders } from "../../test/utils";
import RealWorldMoveBanner from "./RealWorldMoveBanner";
import { describeMove } from "../../lib/realWorld";
import { formatDate } from "../../lib/utils";
import type { RealWorldMove } from "../../types/api";

const senesi: RealWorldMove = {
  kind: "transfer", registered_club_id: "b", registered_club: "Bournemouth", real_team_vendor_id: "47",
  real_club: "Tottenham", real_club_logo: null, real_club_on_transferx_id: "t", moved_on: "2026-06-30",
  fee: "Free", last_played: "2026-09-19", season: "2026", case: "moved", transferx_move: null, open_deal: null,
};

describe("real-world moves", () => {
  it("says what happened in one sentence, for each kind", () => {
    expect(describeMove(senesi)).toBe("Joined Tottenham on 30 Jun 2026 (free transfer).");
    expect(describeMove({ ...senesi, fee: "€ 40M" })).toBe("Joined Tottenham on 30 Jun 2026 (€ 40M).");
    expect(describeMove({ ...senesi, kind: "loan", fee: null })).toBe("Joined Tottenham on loan on 30 Jun 2026.");
    expect(describeMove({ ...senesi, kind: "loan_return" })).toBe("Went back to Tottenham at the end of his loan on 30 Jun 2026.");
    // Month names follow the browser's en-GB data ("Sep" or "Sept").
    expect(describeMove({ ...senesi, kind: "playing", moved_on: null })).toBe(
      `Has been playing for Tottenham this season (last game ${formatDate("2026-09-19")}).`);
  });

  it("names both clubs, and tells his own club staff can correct it", () => {
    const { rerender } = renderWithProviders(<RealWorldMoveBanner move={senesi} isMyPlayer={false} />);
    expect(screen.getByRole("note")).toHaveTextContent("Moved in real life: Joined Tottenham on 30 Jun 2026 (free transfer).");
    expect(screen.getByRole("note")).toHaveTextContent("still registered to Bournemouth");
    expect(screen.getByRole("note")).not.toHaveTextContent("TransferX staff");
    rerender(<RealWorldMoveBanner move={senesi} isMyPlayer />);
    expect(screen.getByRole("note")).toHaveTextContent("TransferX staff can update his registration");
  });

  it("for staff, says when he plays on for the club TransferX moved him from", () => {
    const rice: RealWorldMove = {
      ...senesi, kind: "playing", registered_club: "Liverpool", real_club: "Arsenal", moved_on: null,
      last_played: "2026-10-13", case: "behind_transferx",
      transferx_move: { from_club: "Arsenal", on: "2026-09-30", fee: 45_000_000, deal_id: "d" },
    };
    renderWithProviders(<RealWorldMoveBanner move={rice} isMyPlayer={false} />);
    const note = screen.getByRole("note");
    expect(note).toHaveTextContent(
      `API-Football still has him playing for Arsenal (last game ${formatDate("2026-10-13")}), after his TransferX move to Liverpool on ${formatDate("2026-09-30")}.`);
    expect(note).toHaveTextContent("Staff only");
    expect(note).not.toHaveTextContent("Moved in real life");
  });
});
