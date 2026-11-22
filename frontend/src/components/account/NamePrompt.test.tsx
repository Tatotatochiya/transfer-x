import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import NamePrompt from "./NamePrompt";

vi.mock("../../store/auth", () => ({
  useAuthStore: (pick: (s: unknown) => unknown) => pick({ user: { id: "u", full_name: null, viewed_by: null } }),
}));

function at(path: string) {
  return render(<MemoryRouter initialEntries={[path]}><NamePrompt /></MemoryRouter>);
}

describe("NamePrompt", () => {
  it("asks for a name on the Dashboard", () => {
    at("/dashboard");
    expect(screen.getByText(/Add your name so your team/)).toBeInTheDocument();
  });

  it("isn't shown on other pages, such as the board", () => {
    const { container } = at("/board");
    expect(container).toBeEmptyDOMElement();
  });
});
