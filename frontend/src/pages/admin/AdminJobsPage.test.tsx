import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import AdminJobsPage from "./AdminJobsPage";

const api = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }));
vi.mock("../../lib/api", () => ({ default: api }));

const overview = {
  scheduled: [
    { id: "daily_refresh", label: "Data refresh from API-Football", where: "worker", schedule: "17:00 and 22:00 UK",
      last_run_at: "2026-10-10T16:00:00Z", last_status: "partial", last_error: "Stopped at stats",
      next_run_at: "2026-10-10T21:00:00Z", running: false, overdue_since: "2026-10-10T16:00:00Z" },
    { id: "deal_sla", label: "Flag deals past their paperwork deadline", where: "web app", schedule: "every 24 hours",
      last_run_at: null, last_status: null, last_error: null, next_run_at: null, running: false, overdue_since: null },
  ],
  running: [],
};
const runs = {
  items: [{ id: "r1", job: "daily_refresh", trigger: "cron", service: "worker", status: "partial",
            started_at: "2026-10-10T16:00:00Z", duration_ms: 240000 }],
  total: 1, jobs: ["daily_refresh"],
};
const detail = {
  ...runs.items[0], error: "Stopped at stats: API-Football quota reserve reached",
  summary: { leagues: 7, players_updated: 3444, api_calls: 290, failures: ["stats · La Liga: ApiFootballError"] },
  steps: [{ id: "s1", job: "daily_refresh.stats", status: "partial", duration_ms: 189000, trigger: "cron", service: "worker", started_at: "2026-10-10T16:00:00Z" }],
  log_lines: 2,
};
const logs = { lines: [{ id: 1, at: "2026-10-10T16:00:01Z", level: "WARNING", logger: "x", message: "Stats for La Liga failed" }], running: false };

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}><MemoryRouter><AdminJobsPage /></MemoryRouter></QueryClientProvider>);
}

describe("AdminJobsPage", () => {
  beforeEach(() => {
    api.get.mockReset().mockImplementation((url: string) => Promise.resolve({
      data: url === "/admin/jobs" ? overview : url === "/admin/jobs/runs" ? runs
        : url.endsWith("/logs") ? logs : detail,
    }));
    api.post.mockReset().mockResolvedValue({ data: { started: true } });
  });

  it("lists scheduled jobs with where they run, and flags a missed refresh", async () => {
    renderPage();
    expect(await screen.findByText("Data refresh from API-Football")).toBeInTheDocument();
    expect(screen.getByText("17:00 and 22:00 UK")).toBeInTheDocument();
    expect(screen.getByText(/Didn't run at/)).toBeInTheDocument();
    expect(screen.getAllByText("Partial").length).toBeGreaterThan(0);
  });

  it("opens a run: summary, what wasn't done, steps and its log", async () => {
    renderPage();
    await userEvent.click(await screen.findByRole("button", { name: "Details" }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText("3,444")).toBeInTheDocument();
    expect(within(dialog).getByText("stats · La Liga: ApiFootballError")).toBeInTheDocument();
    expect(within(dialog).getByText("stats")).toBeInTheDocument();
    expect(await within(dialog).findByText("Stats for La Liga failed")).toBeInTheDocument();
  });

  it("starts a refresh after confirming, with valuations when ticked", async () => {
    renderPage();
    await userEvent.click(await screen.findByRole("button", { name: "Run refresh now" }));
    await userEvent.click(screen.getByLabelText(/Also recompute valuations/));
    await userEvent.click(screen.getByRole("button", { name: "Start refresh" }));
    await waitFor(() => expect(api.post).toHaveBeenCalledWith("/admin/jobs/refresh", { valuations: true }));
  });
});
