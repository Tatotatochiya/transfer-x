import { describe, expect, it, vi } from "vitest";
import { fireEvent, screen } from "@testing-library/react";
import { Route, Routes } from "react-router-dom";
import { renderWithProviders } from "../../test/utils";
import LiteLayout from "./LiteLayout";

const mutate = vi.hoisted(() => vi.fn((_body: unknown, opts?: { onSuccess?: () => void }) => opts?.onSuccess?.()));
vi.mock("../../hooks/usePreferences", () => ({
  TEXT_SCALE_PERCENT: { NORMAL: 100, LARGE: 112.5, LARGER: 125 },
  cachedTextScale: () => "NORMAL",
  usePreferences: () => ({ data: { text_scale: "NORMAL", lite_mode: true } }),
  useUpdatePreferences: () => ({ mutate, isPending: false }),
}));
vi.mock("../../hooks/useAuth", () => ({ useAuth: () => ({ logout: vi.fn() }) }));
vi.mock("../../hooks/useIdentity", () => ({ useIdentity: () => ({ name: "Bournemouth", subLabel: "Owner", crestUrl: null }) }));

describe("LiteLayout", () => {
  it("shows a Switch to full app button that leaves Lite and remembers it", () => {
    renderWithProviders(
      <Routes>
        <Route path="/lite" element={<LiteLayout><p>Lite home</p></LiteLayout>} />
        <Route path="/dashboard" element={<p>Full app dashboard</p>} />
      </Routes>,
      { initialPath: "/lite" },
    );
    const button = screen.getByRole("button", { name: /full app/i });
    expect(button).toHaveTextContent("Switch to full app");
    fireEvent.click(button);
    expect(mutate).toHaveBeenCalledWith({ lite_mode: false }, expect.anything());
    expect(screen.getByText("Full app dashboard")).toBeInTheDocument();
  });
});
