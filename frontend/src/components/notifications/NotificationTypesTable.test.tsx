import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { renderWithProviders } from "../../test/utils";
import NotificationTypesTable from "./NotificationTypesTable";

const api = vi.hoisted(() => ({ get: vi.fn(), patch: vi.fn() }));
vi.mock("../../lib/api", () => ({ default: api }));

const prefs = [
  { type: "OFFER_RECEIVED", enabled: true, email_enabled: true, push_enabled: true, tier: "YOUR_MOVE" },
  { type: "DEAL_COMPLETED", enabled: true, email_enabled: true, push_enabled: true, tier: "FYI" },
  { type: "OUTBID", enabled: false, email_enabled: true, push_enabled: true, tier: "HEADS_UP" },
];

async function showEveryType() {
  await userEvent.click(await screen.findByRole("button", { name: "Show every type" }));
}

describe("NotificationTypesTable", () => {
  beforeEach(() => {
    api.get.mockReset();
    api.patch.mockReset();
    api.get.mockResolvedValue({ data: { preferences: prefs } });
  });

  it("has a Push column, disabled for FYI types", async () => {
    renderWithProviders(<NotificationTypesTable />);
    expect(await screen.findByText("Push")).toBeInTheDocument();
    await showEveryType();
    const fyi = screen.getByRole("switch", { name: "Push: Deal completed" });
    expect(fyi).toBeDisabled();
    expect(fyi).toHaveAttribute("aria-checked", "false");
    expect(fyi).toHaveAttribute("title", "Not pushed: these stay in the app");
    // In-app off means no notification at all, so no push either.
    expect(screen.getByRole("switch", { name: "Push: Outbid on an auction" })).toBeDisabled();
  });

  it("switches push off for one type", async () => {
    api.patch.mockResolvedValue({ data: { preferences: prefs } });
    renderWithProviders(<NotificationTypesTable />);
    await showEveryType();
    await userEvent.click(await screen.findByRole("switch", { name: "Push: Offer received" }));
    expect(api.patch).toHaveBeenCalledWith("/notifications/preferences/OFFER_RECEIVED", { push_enabled: false });
  });

  it("shows the email and daily summary switches that were unreachable before", async () => {
    renderWithProviders(<NotificationTypesTable />);
    expect(await screen.findByText("Daily summary")).toBeInTheDocument();
    await showEveryType();
    expect(screen.getByRole("switch", { name: "Email: Offer received" })).toBeInTheDocument();
  });

  it("starts with three tier rows, each switching its whole tier", async () => {
    api.patch.mockResolvedValue({ data: { preferences: prefs } });
    renderWithProviders(<NotificationTypesTable />);
    expect(await screen.findByText("Your move")).toBeInTheDocument();
    expect(screen.getByText("Heads-up")).toBeInTheDocument();
    expect(screen.queryByRole("switch", { name: "Email: Offer received" })).not.toBeInTheDocument();
    expect(screen.getByRole("switch", { name: "Push: For your information" })).toBeDisabled();
    // Heads-up's only type has in-app off, so its in-app switch reads off.
    expect(screen.getByRole("switch", { name: "In-app: Heads-up" })).toHaveAttribute("aria-checked", "false");
    await userEvent.click(screen.getByRole("switch", { name: "Email: Your move" }));
    expect(api.patch).toHaveBeenCalledWith("/notifications/preferences/tier/YOUR_MOVE", { email_enabled: false });
  });
});
