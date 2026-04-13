import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import StatsPanel from "./StatsPanel";
import type { PlayerStats, PlayerForm } from "../../types/api";

const BASE_STATS: PlayerStats = {
  id: "s1",
  player_id: "p1",
  vendor: "api_sports_v3",
  league_id: "39",
  season: "2025",
  goals: 5,
  assists: 3,
  appearances: 20,
  avg_rating: 7.1,
  form_score: null,
  minutes: 1800,
  team_vendor_id: "40",
  team_name: "Liverpool",
  lineups: 18,
  shirt_number: 11,
  shots_total: 40,
  shots_on_target: 22,
  key_passes: 35,
  pass_accuracy: 82,
  tackles_total: 10,
  interceptions: 8,
  blocks: 3,
  duels_total: 80,
  duels_won: 45,
  dribbles_attempts: 50,
  dribbles_success: 30,
  yellow_cards: 2,
  red_cards: 0,
  fouls_committed: 15,
  fouls_drawn: 20,
  saves: null,
  goals_conceded: null,
  penalty_scored: null,
  penalty_missed: null,
  updated_at: "2025-01-01T00:00:00Z",
};

const BASE_FORM: PlayerForm = {
  id: "f1",
  player_id: "p1",
  form_score: 68,
  games_considered: 5,
  key_metrics: null,
  trend: 4.2,
  last_updated: "2025-01-01T00:00:00Z",
};

describe("StatsPanel", () => {
  it("shows empty state when no stats and no form", () => {
    render(<StatsPanel stats={[]} form={null} />);
    expect(screen.getByText(/No performance data/i)).toBeInTheDocument();
  });

  it("renders core grid (goals, assists, apps, rating)", () => {
    // Use a stats object with all position-specific fields nulled out so no
    // section panels render — avoids duplicate text nodes like "3" (assists vs blocks).
    const coreOnly = {
      ...BASE_STATS,
      shots_total: null, shots_on_target: null, fouls_drawn: null,
      key_passes: null, pass_accuracy: null, dribbles_attempts: null, dribbles_success: null,
      tackles_total: null, interceptions: null, blocks: null,
      saves: null, goals_conceded: null,
    };
    render(<StatsPanel stats={[coreOnly]} form={null} />);
    expect(screen.getByText("5")).toBeInTheDocument();   // goals
    expect(screen.getByText("3")).toBeInTheDocument();   // assists
    expect(screen.getByText("20")).toBeInTheDocument();  // apps
    expect(screen.getByText("7.1")).toBeInTheDocument(); // rating
  });

  it("shows team name and season header", () => {
    render(<StatsPanel stats={[BASE_STATS]} form={null} />);
    expect(screen.getByText("Liverpool")).toBeInTheDocument();
    expect(screen.getByText("2025")).toBeInTheDocument();
  });

  it("shows FWD-specific stats for FWD position", () => {
    render(<StatsPanel stats={[BASE_STATS]} form={null} position="FWD" />);
    expect(screen.getByText(/Attack/i)).toBeInTheDocument();
    // getByText exact match — avoids matching both "Shots" and "Shots on Target" labels
    expect(screen.getByText("Shots")).toBeInTheDocument();
  });

  it("shows DEF-specific stats for DEF position", () => {
    render(<StatsPanel stats={[BASE_STATS]} form={null} position="DEF" />);
    // "Defending" is the exact DEFStats section title; MIDStats has "Defending & Discipline"
    expect(screen.getByText("Defending")).toBeInTheDocument();
    // "Tackles" appears in both DEFStats and MIDStats — use getAllByText
    expect(screen.getAllByText("Tackles").length).toBeGreaterThan(0);
  });

  it("shows MID-specific stats for MID position", () => {
    render(<StatsPanel stats={[BASE_STATS]} form={null} position="MID" />);
    expect(screen.getByText(/Passing/i)).toBeInTheDocument();
    expect(screen.getByText(/Key Passes/i)).toBeInTheDocument();
  });

  it("shows GK-specific stats for GK position", () => {
    const gkStats = { ...BASE_STATS, saves: 56, goals_conceded: 18 };
    render(<StatsPanel stats={[gkStats]} form={null} position="GK" />);
    expect(screen.getByText(/Goalkeeping/i)).toBeInTheDocument();
    expect(screen.getByText("56")).toBeInTheDocument(); // saves
  });

  it("renders form block when form is provided", () => {
    render(<StatsPanel stats={[BASE_STATS]} form={BASE_FORM} />);
    expect(screen.getByText(/Form Score/i)).toBeInTheDocument();
    expect(screen.getByText(/68/)).toBeInTheDocument();
  });

  it("does not crash when form_score is a string (Decimal regression)", () => {
    const stringForm = { ...BASE_FORM, form_score: "68.00" as unknown as number };
    expect(() =>
      render(<StatsPanel stats={[BASE_STATS]} form={stringForm} />)
    ).not.toThrow();
  });

  it("prefers record with team_name over higher appearances", () => {
    const noTeamRecord: PlayerStats = {
      ...BASE_STATS,
      team_name: null,
      appearances: 5,   // higher
      goals: 99,
    };
    const teamRecord: PlayerStats = {
      ...BASE_STATS,
      team_name: "Liverpool",
      appearances: 0,  // lower
      goals: 5,
    };
    render(<StatsPanel stats={[noTeamRecord, teamRecord]} form={null} />);
    // The Liverpool record (goals=5) should be selected, not the no-team one (goals=99)
    expect(screen.getByText("5")).toBeInTheDocument();
    expect(screen.queryByText("99")).not.toBeInTheDocument();
  });

  it("shows multiple-seasons notice when more than 1 stats record", () => {
    const secondRecord = { ...BASE_STATS, id: "s2", league_id: "140" };
    render(<StatsPanel stats={[BASE_STATS, secondRecord]} form={null} />);
    expect(screen.getByText(/2 league records/i)).toBeInTheDocument();
  });

  it("shows minutes played", () => {
    render(<StatsPanel stats={[BASE_STATS]} form={null} />);
    expect(screen.getByText(/1,800 minutes played/i)).toBeInTheDocument();
  });
});
