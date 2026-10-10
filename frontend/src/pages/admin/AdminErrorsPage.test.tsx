import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import AdminErrorsPage from "./AdminErrorsPage";

const api = vi.hoisted(() => ({ get: vi.fn(), patch: vi.fn() }));
vi.mock("../../lib/api", () => ({ default: api }));

const issue = {
  id: "i1", service: "api", level: "ERROR", logger: "app.offers.service", title: "KeyError: 'fee'", status: "open",
  first_seen: "2026-10-09T10:00:00Z", last_seen: "2026-10-10T10:00:00Z", count: 12, last_24h: Array(24).fill(0),
};

function renderPage(path = "/admin/errors") {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}><MemoryRouter initialEntries={[path]}><AdminErrorsPage /></MemoryRouter></QueryClientProvider>);
}

describe("AdminErrorsPage", () => {
  beforeEach(() => {
    api.get.mockReset().mockImplementation((url: string) => Promise.resolve({
      data: url === "/admin/errors" ? { items: [issue], total: 1, counts: { open: 1 } }
        : { ...issue, events: [{ id: 1, at: "2026-10-10T10:00:00Z", level: "ERROR", message: "KeyError: 'fee'",
            traceback: "Traceback (most recent call last)", context: { method: "POST", path: "/offers/1", status: 500 } }] },
    }));
    api.patch.mockReset().mockResolvedValue({ data: { ...issue, status: "resolved" } });
  });

  it("lists open issues and filters by service", async () => {
    renderPage();
    expect(await screen.findByText("KeyError: 'fee'")).toBeInTheDocument();
    expect(screen.getByText("12")).toBeInTheDocument();
    await userEvent.selectOptions(screen.getByLabelText("Service"), "worker");
    await waitFor(() => expect(api.get).toHaveBeenLastCalledWith("/admin/errors", { params: { status: "open", service: "worker" } }));
  });

  it("opens an issue from the link and resolves it", async () => {
    renderPage("/admin/errors?issue=i1");
    expect(await screen.findByText(/path \/offers\/1/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Resolve" }));
    await waitFor(() => expect(api.patch).toHaveBeenCalledWith("/admin/errors/i1", { status: "resolved" }));
  });
});
