import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../../test/utils";
import DemoControl, { DemoPlayAsBanner } from "./DemoControl";

const api = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }));
vi.mock("../../lib/api", () => ({ default: api }));
const auth = vi.hoisted(() => ({ canDemo: true, demoPlayedBy: null as string | null, viewedBy: null }));
vi.mock("../../hooks/useAuth", () => ({ useAuth: () => auth }));
const confirm = vi.hoisted(() => vi.fn());
vi.mock("../../context/ConfirmContext", () => ({ useConfirm: () => confirm }));
const addToast = vi.hoisted(() => vi.fn());
vi.mock("../../context/ToastContext", () => ({ useToast: () => ({ addToast }) }));

const run = { id: "r1", status: "ACTIVE", started_at: "2026-10-27T10:00:00Z", resets_on: "2026-11-10", changes: 12, report: null };

describe("DemoControl", () => {
  beforeEach(() => {
    Object.assign(auth, { canDemo: true, demoPlayedBy: null, viewedBy: null });
    api.get.mockReset();
    api.post.mockReset();
    confirm.mockReset();
    addToast.mockReset();
  });

  it("shows nothing to someone who can't demo", () => {
    auth.canDemo = false;
    renderWithProviders(<DemoControl />);
    expect(screen.queryByRole("button", { name: /demo/i })).not.toBeInTheDocument();
    expect(api.get).not.toHaveBeenCalled();
  });

  it("starts a demo", async () => {
    api.get.mockResolvedValue({ data: { can_demo: true, run: null } });
    api.post.mockResolvedValue({ data: run });
    renderWithProviders(<DemoControl />);
    await userEvent.click(await screen.findByRole("button", { name: "Start demo" }));
    await waitFor(() => expect(api.post).toHaveBeenCalledWith("/demo/run"));
  });

  it("while running, counts the changes, plays a house club in a tab, and resets after asking", async () => {
    api.get.mockImplementation((url: string) => Promise.resolve({
      data: url === "/demo/run" ? { can_demo: true, run } : [{ id: "h1", name: "House United", crest_url: null, personality: "fair" }],
    }));
    api.post.mockImplementation((url: string) => Promise.resolve({
      data: url.endsWith("/play-as") ? { access_token: "tok" } : { undone: 12, skipped: [] },
    }));
    const open = vi.spyOn(window, "open").mockImplementation(() => null);
    renderWithProviders(<DemoControl />);
    await userEvent.click(await screen.findByRole("button", { name: /Demo · 12 changes/ }));
    await userEvent.click(await screen.findByRole("button", { name: /Play as House United/ }));
    await waitFor(() => expect(open).toHaveBeenCalledWith("/view-as#view_as=tok", "_blank", "noopener"));

    await userEvent.click(screen.getByRole("button", { name: /Demo · 12 changes/ }));
    confirm.mockResolvedValueOnce(false);
    await userEvent.click(screen.getByRole("button", { name: "Reset demo" }));
    expect(api.post).not.toHaveBeenCalledWith("/demo/run/reset");
    confirm.mockResolvedValueOnce(true);
    await userEvent.click(screen.getByRole("button", { name: "Reset demo" }));
    await waitFor(() => expect(api.post).toHaveBeenCalledWith("/demo/run/reset"));
    expect(addToast).toHaveBeenCalledWith("Demo reset. Everything is back as it was.", "success");
  });

  it("in a play-as tab, shows whose demo it is instead", () => {
    auth.demoPlayedBy = "Luke";
    renderWithProviders(<><DemoPlayAsBanner /><DemoControl /></>);
    expect(screen.getByRole("status")).toHaveTextContent("in Luke’s demo");
    expect(screen.queryByRole("button", { name: /demo/i })).not.toBeInTheDocument();
  });
});
