import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../../test/utils";
import MoveReminder, { type ReminderState } from "./MoveReminder";

const api = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }));
vi.mock("../../lib/api", () => ({ default: api }));
const addToast = vi.hoisted(() => vi.fn());
vi.mock("../../context/ToastContext", () => ({ useToast: () => ({ addToast }) }));

const base: ReminderState = {
  holder: { kind: "agent", name: "Sofia Reyes" },
  waiting_since: "2026-11-09T10:00:00Z",
  can_send: true, reason: null, next_allowed_at: null, would_escalate: false,
  preview: "Tottenham is waiting for your commission proposal for L. Hall (£34.5M) · 3 days",
  last: null,
};

beforeEach(() => {
  api.get.mockReset();
  api.post.mockReset();
  addToast.mockReset();
});

describe("MoveReminder", () => {
  it("shows nothing while it's the viewer's own move, or to a non-party", async () => {
    api.get.mockResolvedValueOnce({ data: { ...base, can_send: false, reason: "It's your move." } });
    const { container, unmount } = renderWithProviders(<MoveReminder subjectType="deal" subjectId="d1" />);
    await waitFor(() => expect(api.get).toHaveBeenCalled());
    expect(container.textContent).toBe("");
    unmount();

    api.get.mockRejectedValueOnce({ response: { status: 404 } });
    const second = renderWithProviders(<MoveReminder subjectType="deal" subjectId="d1" />);
    await waitFor(() => expect(api.get).toHaveBeenCalledTimes(2));
    expect(second.container.textContent).toBe("");
  });

  it("sends a reminder with a note, after showing the exact message", async () => {
    api.get.mockResolvedValue({ data: base });
    api.post.mockResolvedValue({ data: { ...base, can_send: false, reason: "You reminded them just now. You can send another from 14:30.",
      next_allowed_at: "2026-11-14T14:30:00Z", last: { at: new Date().toISOString(), by: "Tottenham", escalated: false, note: "By Friday", by_you: true } } });
    renderWithProviders(<MoveReminder subjectType="deal" subjectId="d1" />);

    expect(await screen.findByText("Waiting on Sofia Reyes since 9 Nov 2026.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Send a reminder" }));
    expect(screen.getByText(base.preview!)).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("Add a note (optional)"), "By Friday");
    await userEvent.click(screen.getByRole("button", { name: "Send reminder" }));

    expect(api.post).toHaveBeenCalledWith("/reminders/deal/d1", { note: "By Friday" });
    expect(addToast).toHaveBeenCalledWith("Reminder sent to Sofia Reyes.", "success");
    expect(await screen.findByText("You reminded Sofia Reyes today.", { exact: false })).toBeInTheDocument();
    expect(screen.getByText("You can send another from 14:30.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Send a reminder" })).toBeNull();
  });

  it("offers Escalate once reminders were ignored, and says who else is told", async () => {
    api.get.mockResolvedValue({ data: { ...base, would_escalate: true,
      last: { at: "2026-11-10T09:00:00Z", by: "TransferX", escalated: false, note: null } } });
    renderWithProviders(<MoveReminder subjectType="deal" subjectId="d1" />);
    expect(await screen.findByText("TransferX reminded Sofia Reyes on 10 Nov 2026.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Escalate" }));
    expect(screen.getByText("The player and the other club are told too.")).toBeInTheDocument();
  });

  it("the side being chased sees who reminded them, in red, and no button", async () => {
    api.get.mockResolvedValue({ data: { ...base, holder: null, can_send: false, reason: "It's your move.",
      to_you: { at: new Date().toISOString(), by: "An undisclosed club", escalated: true, note: "Please answer" } } });
    renderWithProviders(<MoveReminder subjectType="offer" subjectId="o1" />);
    expect(await screen.findByText("An undisclosed club escalated this to you today.", { exact: false })).toBeInTheDocument();
    expect(screen.getByText("Escalated").className).toContain("bg-danger-bg");
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("the waiting side: amber Stalled before anyone reminds them", async () => {
    api.get.mockResolvedValue({ data: { ...base, waiting_since: new Date(Date.now() - 4 * 86_400_000).toISOString() } });
    renderWithProviders(<MoveReminder subjectType="deal" subjectId="d1" />);
    expect((await screen.findByText("Stalled · 4 days")).className).toContain("bg-warning-bg");
  });

  it("Lite says Remind them", async () => {
    api.get.mockResolvedValue({ data: base });
    renderWithProviders(<MoveReminder lite subjectType="offer" subjectId="o1" />);
    expect(await screen.findByRole("button", { name: "Remind them" })).toBeInTheDocument();
  });
});
