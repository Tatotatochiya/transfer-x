import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithProviders } from "../../test/utils";
import AskAboutButton from "./AskAboutButton";

describe("AskAboutButton", () => {
  it("opens Ask TransferX about the thing, in the AI look", () => {
    renderWithProviders(<AskAboutButton about="offer" id="o1" name="M. Senesi" size="sm" />);
    const link = screen.getByRole("link", { name: /Ask about this/ });
    expect(link).toHaveAttribute("href", "/ask?about=offer&id=o1&name=M.+Senesi");
    expect(link).toHaveTextContent("✦");
    expect(link.className).toContain("text-role-agent-text");
    expect(link).toHaveAttribute("title", "Ask TransferX about M. Senesi");
  });
});
