import { describe, it, expect, vi } from "vitest";
import { fireEvent, screen } from "@testing-library/react";
import { renderWithProviders } from "../../test/utils";
import SquadTable from "./SquadTable";
import type { Contract, Player } from "../../types/api";

const inMonths = (m: number) => new Date(Date.now() + m * 30 * 86_400_000).toISOString().slice(0, 10);

function contract(endMonths: number, extra: Partial<Contract> = {}): Contract {
  return {
    id: "c", club_id: "club", start_date: null, end_date: inMonths(endMonths),
    wage_weekly: 120_000, release_clause: null, club_valuation: null,
    is_active: true, notes: null, created_at: "2025-01-01T00:00:00Z", ...extra,
  };
}

function player(id: string, name: string, position: Player["position"], active_contract: Contract | null): Player & { active_contract: Contract | null } {
  return {
    id, name, firstname: null, lastname: null, age: 27, nationality: "England", position,
    status: "CONTRACTED", visibility: "PUBLIC", open_to_offers: false, photo_url: null,
    team_name: null, current_club: null, created_at: "2025-01-01T00:00:00Z", updated_at: "2025-01-01T00:00:00Z",
    active_contract,
  } as Player & { active_contract: Contract | null };
}

const SQUAD = [
  player("gk1", "Keeper Long", "GK", contract(30)),
  player("gk2", "Keeper Short", "GK", contract(4)),
  player("d1", "Defender One", "DEF", contract(9, { club_valuation: 18_000_000 })),
  player("f1", "Loanee Striker", "FWD", contract(8)),
];

describe("SquadTable", () => {
  it("sorts each group by contract months, soonest first", () => {
    renderWithProviders(<SquadTable players={SQUAD} showContractDetails />);
    const names = screen.getAllByRole("link").map((a) => a.textContent);
    expect(names.indexOf("Keeper Short")).toBeLessThan(names.indexOf("Keeper Long"));
  });

  it("counts chips and group minimums from the whole squad, not the filter", () => {
    renderWithProviders(<SquadTable players={SQUAD} showContractDetails />);
    fireEvent.click(screen.getByRole("button", { name: /Contract risk 3/ }));
    // Keeper Long is filtered out, but the band still counts both keepers.
    expect(screen.getByText("2 of 2 minimum — covered")).toBeInTheDocument();
    expect(screen.queryByText("Keeper Long")).not.toBeInTheDocument();
    expect(screen.getByText("No midfielders in the squad.")).toBeInTheDocument();
  });

  it("reads a typed '18' as £18m when setting a valuation", () => {
    const onSetValuation = vi.fn();
    renderWithProviders(<SquadTable players={SQUAD} showContractDetails onSetValuation={onSetValuation} />);
    fireEvent.click(screen.getAllByRole("button", { name: "+ set" })[0]);
    const input = screen.getByRole("textbox");
    fireEvent.change(input, { target: { value: "18" } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onSetValuation).toHaveBeenCalledWith("gk2", 18_000_000);
  });

  it("keeps the old valuation when the text is not a figure", () => {
    const onSetValuation = vi.fn();
    renderWithProviders(<SquadTable players={SQUAD} showContractDetails onSetValuation={onSetValuation} />);
    fireEvent.click(screen.getByRole("button", { name: /18\.0m/ }));
    const input = screen.getByRole("textbox");
    fireEvent.change(input, { target: { value: "about 20m" } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onSetValuation).not.toHaveBeenCalled();
  });

  it("never offers List or a valuation edit for a loaned-in player", () => {
    const onList = vi.fn();
    renderWithProviders(
      <SquadTable
        players={[SQUAD[3]]}
        showContractDetails
        onList={onList}
        onUnlist={vi.fn()}
        onSetValuation={vi.fn()}
        openListings={new Map()}
        loanedIn={new Map([["f1", { endDate: inMonths(8), parentClubName: "Leeds" }]])}
      />,
    );
    expect(screen.getByText("On loan")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "List" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "+ set" })).not.toBeInTheDocument();
  });

  it("disables List with the reason as its tooltip", () => {
    renderWithProviders(
      <SquadTable players={[SQUAD[0]]} showContractDetails onList={vi.fn()} onUnlist={vi.fn()} listBlockedReason="The window is closed." />,
    );
    const list = screen.getByRole("button", { name: "List" });
    expect(list).toBeDisabled();
    expect(list).toHaveAttribute("title", "The window is closed.");
  });

  it("says how far a player's sale has got, links to it, and filters to players in play", () => {
    const inPlay = new Map([
      ["d1", { label: "Offer £6.0m", detail: "Offer received · your reply", link: "/offers/o1", yourMove: true, listingOnly: false }],
      ["gk1", { label: "Deal: Paperwork", detail: "Waiting on Leeds", link: "/deals/x1", yourMove: false, listingOnly: false }],
    ]);
    renderWithProviders(
      <SquadTable players={SQUAD} showContractDetails onList={vi.fn()} onUnlist={vi.fn()} openListings={new Map()} inPlay={inPlay} />,
    );
    const offer = screen.getByRole("link", { name: /Offer £6.0m/ });
    expect(offer).toHaveAttribute("href", "/offers/o1");
    expect(offer).toHaveAttribute("title", "Offer received · your reply");
    expect(screen.getByLabelText("Your move")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Deal: Paperwork/ })).toHaveAttribute("href", "/deals/x1");
    fireEvent.click(screen.getByRole("button", { name: "In play 2" }));
    expect(screen.queryByText("Keeper Short")).not.toBeInTheDocument();
    expect(screen.getByText("Defender One")).toBeInTheDocument();
  });

  it("keeps Listed and Unlist for a listing with nothing on it yet", () => {
    renderWithProviders(
      <SquadTable
        players={[SQUAD[0]]} showContractDetails onList={vi.fn()} onUnlist={vi.fn()}
        openListings={new Map([["gk1", "s1"]])}
        inPlay={new Map([["gk1", { label: "Listed", detail: "Listed", link: "/sales/s1", yourMove: false, listingOnly: true }]])}
      />,
    );
    expect(screen.getByRole("link", { name: "Listed →" })).toHaveAttribute("href", "/sales/s1");
    expect(screen.getByRole("button", { name: "Unlist" })).toBeInTheDocument();
  });
});
