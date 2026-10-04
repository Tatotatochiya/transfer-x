import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import ConversationPanel from "./ConversationPanel";

const api = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }));
vi.mock("../../lib/api", () => ({ default: api }));
const caps = vi.hoisted(() => ({ allowed: true }));
vi.mock("../../hooks/useClubCapabilities", () => ({ useClubCapabilities: () => ({ can: () => caps.allowed }) }));

const conversation = {
  messages: [
    { id: "1", source: "enquiry", audience: "both_clubs", audience_label: "Both clubs", author: "A Premier League club",
      mine: false, body: "Would you sell?", created_at: "2026-10-01T10:00:00Z", context: "Enquiry" },
    { id: "2", source: "deal", audience: "our_club", audience_label: "Only your club", author: "You",
      mine: true, body: "Hold at 20", created_at: "2026-10-02T10:00:00Z", context: "Deal" },
  ],
  can_post_to: [
    { key: "deal_everyone", label: "Both clubs, the agent and the player" },
    { key: "our_club", label: "Only your club" },
  ],
};

function renderPanel() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}><ConversationPanel context={{ dealId: "d1" }} /></QueryClientProvider>);
}

describe("ConversationPanel", () => {
  beforeEach(() => {
    api.get.mockReset().mockResolvedValue({ data: conversation });
    api.post.mockReset().mockResolvedValue({ data: conversation });
    caps.allowed = true;
  });

  it("shows the whole transfer in order, and says who can read private messages", async () => {
    renderPanel();
    expect(await screen.findByText("Would you sell?")).toBeInTheDocument();
    expect(screen.getByText(/A Premier League club/)).toBeInTheDocument();
    expect(screen.getByText("Hold at 20").parentElement).toHaveTextContent("Only your club");
    expect(api.get).toHaveBeenCalledWith("/conversation", { params: { deal_id: "d1" } });
  });

  it("sends to the chosen audience", async () => {
    renderPanel();
    await screen.findByText("Would you sell?");
    await userEvent.type(screen.getByLabelText("Message"), "Note to self");
    await userEvent.selectOptions(screen.getByRole("combobox"), "our_club");
    await userEvent.click(screen.getByRole("button", { name: "Send" }));
    await waitFor(() => expect(api.post).toHaveBeenCalledWith("/conversation",
      { deal_id: "d1", audience: "our_club", body: "Note to self" }));
  });

  it("has no composer without permission to write", async () => {
    caps.allowed = false;
    renderPanel();
    await screen.findByText("Would you sell?");
    expect(screen.queryByLabelText("Message")).not.toBeInTheDocument();
  });
});
