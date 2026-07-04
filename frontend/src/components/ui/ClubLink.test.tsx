import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithProviders } from "../../test/utils";
import ClubLink from "./ClubLink";

describe("ClubLink", () => {
  it("renders plain text link with no crest slot when crestUrl is omitted", () => {
    renderWithProviders(<ClubLink id="c1" name="Arsenal FC" />);
    expect(screen.getByRole("link", { name: "Arsenal FC" })).toBeInTheDocument();
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
  });

  it("renders the crest image when crestUrl is set", () => {
    // alt="" is deliberate (decorative — the name text carries the meaning),
    // which gives it no accessible name, so query the DOM directly rather
    // than by role.
    const { container } = renderWithProviders(
      <ClubLink id="c1" name="Arsenal FC" crestUrl="https://example.com/arsenal.png" />
    );
    const img = container.querySelector("img");
    expect(img).toHaveAttribute("src", "https://example.com/arsenal.png");
  });

  it("renders an initials fallback when crestUrl is explicitly null", () => {
    renderWithProviders(<ClubLink id="c1" name="Arsenal FC" crestUrl={null} />);
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
    expect(screen.getByText("A")).toBeInTheDocument();
  });

  it("routes to /clubs/{id} when id is given", () => {
    renderWithProviders(<ClubLink id="c1" name="Arsenal FC" />);
    expect(screen.getByRole("link")).toHaveAttribute("href", "/clubs/c1");
  });

  it("routes to /world/teams/{id} when only worldTeamId is given", () => {
    renderWithProviders(<ClubLink worldTeamId="w1" name="Arsenal FC" />);
    expect(screen.getByRole("link")).toHaveAttribute("href", "/world/teams/w1");
  });

  it("falls back to a search link when neither id is given", () => {
    renderWithProviders(<ClubLink name="Arsenal FC" />);
    expect(screen.getByRole("link")).toHaveAttribute("href", "/clubs?search=Arsenal%20FC");
  });

  it("renders the fallback text when there is no name", () => {
    renderWithProviders(<ClubLink id="c1" name={null} fallback="Unknown club" />);
    expect(screen.getByText("Unknown club")).toBeInTheDocument();
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });
});
