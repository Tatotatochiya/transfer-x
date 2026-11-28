import { useState } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import ExclusionsField, { NO_EXCLUSIONS, type Exclusions } from "./ExclusionsField";

const api = vi.hoisted(() => ({ get: vi.fn() }));
vi.mock("../../lib/api", () => ({ default: api }));

const club = (id: string, name: string, league_name: string | null = null) => ({
  id, name, league_name, country: null, city: null, crest_url: null, role: "BOTH", verified: false, created_at: "",
});

let latest: Exclusions = NO_EXCLUSIONS;
function Harness() {
  const [value, setValue] = useState<Exclusions>(NO_EXCLUSIONS);
  latest = value;
  return <ExclusionsField value={value} onChange={setValue} ownClubId="me" />;
}

function renderField() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}><Harness /></QueryClientProvider>);
}

describe("ExclusionsField", () => {
  beforeEach(() => {
    api.get.mockReset().mockImplementation((url: string) => Promise.resolve({
      data: url === "/clubs/leagues"
        ? ["La Liga", "Premier League"]
        : { items: [club("me", "Our FC"), club("r1", "Rival FC", "Premier League")], total: 2, page: 1, page_size: 8 },
    }));
  });

  it("is closed until asked for, then adds clubs (never your own) and leagues", async () => {
    const user = userEvent.setup();
    renderField();
    expect(screen.queryByLabelText("Clubs")).toBeNull();
    await user.click(screen.getByRole("button", { name: "Keep him from certain clubs or leagues" }));

    await user.type(screen.getByLabelText("Clubs"), "fc");
    await user.click(await screen.findByRole("button", { name: /Rival FC/ }));
    expect(screen.queryByRole("button", { name: /Our FC/ })).toBeNull();

    await user.selectOptions(await screen.findByLabelText("Leagues"), await screen.findByRole("option", { name: "La Liga" }));
    expect(latest).toEqual({ clubs: [{ id: "r1", name: "Rival FC" }], leagues: ["La Liga"] });

    await user.click(screen.getByRole("button", { name: "Remove Rival FC" }));
    expect(latest.clubs).toEqual([]);
  });
});
