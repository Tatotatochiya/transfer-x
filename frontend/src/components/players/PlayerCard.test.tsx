import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithProviders } from "../../test/utils";
import PlayerCard from "./PlayerCard";
import type { Player } from "../../types/api";

const BASE_PLAYER: Player = {
  id: "p1",
  name: "Mohamed Salah",
  age: 32,
  nationality: "Egypt",
  position: "FWD",
  status: "CONTRACTED",
  visibility: "PUBLIC",
  open_to_offers: false,
  photo_url: null,
  team_name: "Liverpool",
  current_club: null,
  created_at: "2025-01-01T00:00:00Z",
  updated_at: "2025-01-01T00:00:00Z",
};

describe("PlayerCard", () => {
  it("renders player name", () => {
    renderWithProviders(<PlayerCard player={BASE_PLAYER} />);
    expect(screen.getByText("Mohamed Salah")).toBeInTheDocument();
  });

  it("shows team_name when current_club is null", () => {
    renderWithProviders(<PlayerCard player={BASE_PLAYER} />);
    expect(screen.getByText("Liverpool")).toBeInTheDocument();
  });

  it("prefers current_club.name over team_name when both present", () => {
    const player: Player = {
      ...BASE_PLAYER,
      current_club: { id: "c1", name: "Liverpool FC", crest_url: null },
      team_name: "Liverpool",
    };
    renderWithProviders(<PlayerCard player={player} />);
    expect(screen.getByText("Liverpool FC")).toBeInTheDocument();
  });

  it("shows Free Agent when both current_club and team_name are null", () => {
    // Must also be FREE_AGENT status — vendor players have team_name set even with status=FREE_AGENT.
    // "Free Agent" appears twice: once as club name fallback text, once as the status badge.
    const player: Player = { ...BASE_PLAYER, current_club: null, team_name: null, status: "FREE_AGENT" };
    renderWithProviders(<PlayerCard player={player} />);
    expect(screen.getAllByText("Free Agent").length).toBeGreaterThanOrEqual(1);
  });

  it("shows Contracted badge when team_name is set (vendor player)", () => {
    // Vendor players have status=FREE_AGENT in DB but should display as Contracted
    const player: Player = { ...BASE_PLAYER, status: "FREE_AGENT", team_name: "Manchester City" };
    renderWithProviders(<PlayerCard player={player} />);
    expect(screen.getByText("Contracted")).toBeInTheDocument();
    expect(screen.queryByText("Free Agent")).not.toBeInTheDocument();
  });

  it("shows Open badge when player is open to offers", () => {
    const player: Player = { ...BASE_PLAYER, open_to_offers: true };
    renderWithProviders(<PlayerCard player={player} />);
    expect(screen.getByText("Open")).toBeInTheDocument();
  });

  it("does not show Open badge when player is not open to offers", () => {
    renderWithProviders(<PlayerCard player={BASE_PLAYER} />);
    expect(screen.queryByText("Open")).not.toBeInTheDocument();
  });

  it("shows position badge", () => {
    renderWithProviders(<PlayerCard player={BASE_PLAYER} />);
    expect(screen.getByText("FWD")).toBeInTheDocument();
  });

  it("shows age and nationality", () => {
    renderWithProviders(<PlayerCard player={BASE_PLAYER} />);
    expect(screen.getByText(/32 yrs/)).toBeInTheDocument();
    expect(screen.getByText(/Egypt/)).toBeInTheDocument();
  });

  it("shows initial letter avatar when no photo", () => {
    renderWithProviders(<PlayerCard player={BASE_PLAYER} />);
    expect(screen.getByText("M")).toBeInTheDocument(); // first letter of "Mohamed"
  });

  it("renders photo img when photo_url is set", () => {
    const player: Player = { ...BASE_PLAYER, photo_url: "https://example.com/salah.jpg" };
    renderWithProviders(<PlayerCard player={player} />);
    const img = screen.getByRole("img", { name: "Mohamed Salah" });
    expect(img).toHaveAttribute("src", "https://example.com/salah.jpg");
  });

  it("renders form badge when formScore provided", () => {
    renderWithProviders(<PlayerCard player={BASE_PLAYER} formScore={72} formTrend={3} />);
    expect(screen.getByText(/72/)).toBeInTheDocument();
  });

  it("does not render form badge when formScore is null", () => {
    renderWithProviders(<PlayerCard player={BASE_PLAYER} formScore={null} />);
    // Form badge content would be a number — should not appear
    expect(screen.queryByTitle(/Form score/)).not.toBeInTheDocument();
  });
});
