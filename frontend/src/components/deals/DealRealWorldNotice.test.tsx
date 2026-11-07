import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithProviders } from "../../test/utils";
import DealRealWorldNotice from "./DealRealWorldNotice";

const api = vi.hoisted(() => ({ get: vi.fn() }));
vi.mock("../../lib/api", () => ({ default: api }));

describe("DealRealWorldNotice", () => {
  beforeEach(() => api.get.mockReset());

  it("says completion is on hold, and that the rest carries on", async () => {
    api.get.mockResolvedValue({ data: { hold: "API-Football has B. Saka playing for Arsenal. TransferX staff are checking his registration before this deal can complete.", note: null } });
    renderWithProviders(<DealRealWorldNotice dealId="d1" open />);
    expect(await screen.findByText("Completion on hold: moved in real life")).toBeInTheDocument();
    expect(screen.getByRole("note")).toHaveTextContent("playing for Arsenal");
    expect(screen.getByRole("note")).toHaveTextContent("Talks and paperwork carry on as normal");
    expect(api.get).toHaveBeenCalledWith("/deals/d1/real-world");
  });

  it("shows a loan elsewhere as a note, without a hold", async () => {
    api.get.mockResolvedValue({ data: { hold: null, note: "API-Football has him on loan at Al-Hilal." } });
    renderWithProviders(<DealRealWorldNotice dealId="d1" open />);
    expect(await screen.findByText("Moved in real life")).toBeInTheDocument();
    expect(screen.getByRole("note")).not.toHaveTextContent("Talks and paperwork");
  });

  it("says the deal completes when the transfer window opens", async () => {
    api.get.mockResolvedValue({ data: {
      hold: null, note: null, window_opens_at: "2027-01-01T00:00:00Z",
      window: "The transfer window in England is closed. The deal can complete when the January 2027 window opens on 1 January 2027.",
    } });
    renderWithProviders(<DealRealWorldNotice dealId="d1" open />);
    expect(await screen.findByText("Completes when the transfer window opens")).toBeInTheDocument();
    expect(screen.getByRole("note")).toHaveTextContent("opens on 1 January 2027");
    expect(screen.getByRole("note")).toHaveTextContent("Both clubs are told when it opens");
    expect(screen.queryByText(/moved in real life/i)).not.toBeInTheDocument();
  });

  it("asks nothing for a closed deal", () => {
    renderWithProviders(<DealRealWorldNotice dealId="d1" open={false} />);
    expect(api.get).not.toHaveBeenCalled();
    expect(screen.queryByRole("note")).not.toBeInTheDocument();
  });
});
