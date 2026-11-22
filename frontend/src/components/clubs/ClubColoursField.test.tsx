import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { renderWithProviders } from "../../test/utils";
import ClubColoursField, { colourError } from "./ClubColoursField";

vi.mock("../../lib/crestPalette", async (orig) => ({
  ...(await orig<typeof import("../../lib/crestPalette")>()),
  crestPalette: vi.fn(async () => [
    { primary: "#DB0007", secondary: "#FFFFFF", label: "Red and white" },
  ]),
}));

const club = { name: "Arsenal", crest_url: "https://crests.test/a.png", league_name: "Premier League", city: "London" };

function Harness({ initial = ["", ""], spy }: { initial?: [string, string]; spy?: (p: string, s: string) => void }) {
  const [[p, s], set] = useState(initial);
  return <ClubColoursField club={club} primary={p} secondary={s} onChange={(a, b) => { set([a, b]); spy?.(a, b); }} />;
}

describe("ClubColoursField", () => {
  it("fills both colours from a crest suggestion and previews the band", async () => {
    const spy = vi.fn();
    renderWithProviders(<Harness spy={spy} />);
    await userEvent.setup().click(await screen.findByRole("button", { name: /Red and white/ }));
    expect(spy).toHaveBeenCalledWith("#DB0007", "#FFFFFF");
    expect(screen.getByLabelText("Primary")).toHaveValue("#DB0007");
    expect(screen.getByTestId("club-band")).toHaveStyle({ backgroundColor: "#DB0007" });
    // The preview is not a second h1 on My Club.
    expect(screen.queryByRole("heading", { level: 1 })).toBeNull();
  });

  it("says how the band's text reads", async () => {
    const { unmount } = renderWithProviders(<Harness initial={["#DB0007", "#FFFFFF"]} />);
    expect(screen.getByText(/White text reads clearly on your primary \(5\.2 : 1\)/)).toBeInTheDocument();
    unmount();
    renderWithProviders(<Harness initial={["#F5C400", "#14171F"]} />);
    expect(screen.getByText(/Text on your primary will be dark, so it reads clearly \(10\.9 : 1\)/)).toBeInTheDocument();
  });

  it("shows an inline error for a colour that isn't #RRGGBB", async () => {
    renderWithProviders(<Harness />);
    await userEvent.setup().type(screen.getByLabelText("Primary"), "red");
    expect(screen.getByText("Use a colour like #DB0007")).toBeInTheDocument();
    expect(screen.getByLabelText("Primary")).toHaveAttribute("aria-invalid", "true");
    expect(colourError("")).toBeNull();
    expect(colourError("#db0007")).toBeNull();
    expect(colourError("#FFF")).not.toBeNull();
  });

  it("removes both colours with empty values", async () => {
    const spy = vi.fn();
    renderWithProviders(<Harness initial={["#DB0007", "#FFFFFF"]} spy={spy} />);
    await userEvent.setup().click(screen.getByRole("button", { name: "Remove colours" }));
    await waitFor(() => expect(spy).toHaveBeenCalledWith("", ""));
    expect(screen.queryByTestId("club-band")).toBeNull();
  });
});
