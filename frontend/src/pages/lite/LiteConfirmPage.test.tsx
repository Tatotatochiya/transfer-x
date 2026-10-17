import { describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import { Route, Routes } from "react-router-dom";
import { renderWithProviders } from "../../test/utils";
import LiteConfirmPage from "./LiteConfirmPage";

const api = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }));
vi.mock("../../lib/api", () => ({ default: api }));
vi.mock("../../store/auth", () => ({ useAuthStore: (pick: (s: object) => unknown) => pick({ accessToken: null, refreshToken: null }) }));

describe("LiteConfirmPage", () => {
  it("asks a signed-out visitor to sign in before saying no", async () => {
    api.get.mockResolvedValue({ data: {
      state: "ready", action: "reject", amount: null, label: "Say no", needs_sign_in: true, signed_in_as_recipient: false,
      card: { offer_id: "o1", player_name: "Marcus Webb", other_club: "an undisclosed club", fee: 18_000_000,
              deal_type: "PERMANENT", expires_at: null },
    } });
    renderWithProviders(<Routes><Route path="/lite/confirm/:token" element={<LiteConfirmPage />} /></Routes>,
      { initialPath: "/lite/confirm/t1?action=reject" });
    const link = await screen.findByRole("link", { name: "Sign in to say no" });
    expect(link.getAttribute("href")).toContain("/login?next=");
    expect(screen.getByText("To answer, sign in with the account this email was sent to.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Confirm/ })).not.toBeInTheDocument();
    expect(screen.queryByText(/Your valuation/)).not.toBeInTheDocument();
  });
});
