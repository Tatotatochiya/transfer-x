import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import AdminTransferWindowPage from "./AdminTransferWindowPage";

const api = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn(), delete: vi.fn() }));
vi.mock("../../lib/api", () => ({ default: api }));
vi.mock("../../context/ConfirmContext", () => ({ useAskReason: () => vi.fn() }));

const january = {
  id: "w1", name: "January 2027", country: "England", opens_at: "2027-01-01T00:00:00Z", closes_at: "2027-02-02T23:00:00Z",
  source_url: "https://inside.fifa.com/associations/ENG/snapshot", checked_on: "2026-11-07", is_open: false,
  created_at: "2026-11-07T10:00:00Z",
};

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}><MemoryRouter><AdminTransferWindowPage /></MemoryRouter></QueryClientProvider>);
}

function serve(coverage: unknown[], windows: unknown[]) {
  api.get.mockImplementation((url: string) =>
    Promise.resolve({ data: url.endsWith("/coverage") ? coverage : windows }));
}

describe("AdminTransferWindowPage", () => {
  beforeEach(() => { api.get.mockReset(); api.post.mockReset(); });

  it("warns about a country with nothing set up for six months", async () => {
    serve([{ country: "England", own_windows: false, current_window: null, next_window: null, missing: true }], []);
    renderPage();
    expect(await screen.findByRole("alert")).toHaveTextContent("next six months in England");
    expect(screen.getByText(/Deals complete at any time/)).toBeInTheDocument();
  });

  it("lists each window with its country and where the dates came from", async () => {
    serve([{ country: "England", own_windows: true, current_window: null, next_window: january, missing: false }], [january]);
    renderPage();
    expect(await screen.findByText("January 2027")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getAllByText("England").length).toBeGreaterThan(0);
    expect(screen.getByRole("link", { name: "Source" })).toHaveAttribute("href", january.source_url);
  });

  it("creates a window for a country, with its source", async () => {
    serve([], []);
    api.post.mockResolvedValue({ data: january });
    renderPage();
    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Window name"), "January 2027");
    await user.type(screen.getByLabelText("Country"), "England");
    await user.type(screen.getByLabelText("Opens at"), "2027-01-01T00:00");
    await user.type(screen.getByLabelText("Closes at"), "2027-02-02T23:00");
    await user.type(screen.getByLabelText(/Source/), "https://inside.fifa.com/associations/ENG/snapshot");
    await user.click(screen.getByRole("button", { name: "Create Window" }));
    await waitFor(() => expect(api.post).toHaveBeenCalled());
    expect(api.post.mock.calls[0][1]).toMatchObject({
      name: "January 2027", country: "England", source_url: "https://inside.fifa.com/associations/ENG/snapshot",
    });
  });
});
