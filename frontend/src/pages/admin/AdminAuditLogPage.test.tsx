import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../../test/utils";
import AdminAuditLogPage, { actionLabel } from "./AdminAuditLogPage";

const api = vi.hoisted(() => ({ get: vi.fn() }));
vi.mock("../../lib/api", () => ({ default: api }));

const ROW = {
  id: "e1", created_at: "2026-10-03T09:00:00Z", actor_user_id: "u1", actor_email: "admin@transferx.com",
  action: "admin.sale.cancelled", entity_type: "sale", entity_id: "s1", description: "Cancelled the sale of Kepa",
  reason: "Listed by mistake", payload: { admin_action: true, reason: "Listed by mistake" }, link: "/sales/s1", by_staff: true,
};

describe("AdminAuditLogPage", () => {
  beforeEach(() => {
    api.get.mockReset();
    api.get.mockImplementation((url: string) => Promise.resolve({
      data: url.endsWith("/facets") ? { actions: ["admin.sale.cancelled", "OFFER_SENT"], entity_types: ["sale"] }
        : { items: [ROW], total: 1, page: 1, page_size: 50 },
      headers: {},
    }));
  });

  it("shows who did what, the reason, and a link to the thing", async () => {
    renderWithProviders(<AdminAuditLogPage />);
    // The table renders a desktop row and a phone card for each event.
    expect((await screen.findAllByText("Cancelled the sale of Kepa")).length).toBeGreaterThan(0);
    expect(screen.getAllByText("Listed by mistake").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Staff").length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: "Open sale" })[0]).toHaveAttribute("href", "/sales/s1");
    // Staff actions only by default.
    expect(api.get).toHaveBeenCalledWith("/admin/audit-log", { params: expect.objectContaining({ admin_only: true, page: 1 }) });
  });

  it("exports the current view to Excel", async () => {
    api.get.mockImplementation((url: string, config?: { responseType?: string }) => Promise.resolve(
      config?.responseType === "blob"
        ? { data: new Blob(["x"]), headers: { "content-disposition": 'attachment; filename="transferx-audit-log-2026-10-03.xlsx"' } }
        : { data: url.endsWith("/facets") ? { actions: [], entity_types: [] } : { items: [ROW], total: 1, page: 1, page_size: 50 }, headers: {} },
    ));
    URL.createObjectURL = vi.fn(() => "blob:x");
    URL.revokeObjectURL = vi.fn();
    renderWithProviders(<AdminAuditLogPage />);
    await userEvent.click(await screen.findByRole("button", { name: "Export to Excel" }));
    await waitFor(() => expect(api.get).toHaveBeenCalledWith(
      "/admin/audit-log/export.xlsx", { params: expect.objectContaining({ admin_only: true }), responseType: "blob" },
    ));
    expect(URL.createObjectURL).toHaveBeenCalled();
  });

  it("reads action codes as words", () => {
    expect(actionLabel("admin.club.finances_updated")).toBe("Club finances updated");
    expect(actionLabel("OFFER_SENT")).toBe("Offer sent");
  });
});
