import { describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithProviders } from "../../test/utils";
import TermRounds from "./TermRounds";
import type { Deal } from "../../types/api";

const api = vi.hoisted(() => ({ get: vi.fn() }));
vi.mock("../../lib/api", () => ({ default: api }));

const deal = { id: "d1", stage: "AGENT_NEGOTIATION", buyer_club: { name: "Tottenham" }, player: { name: "L. Hall" },
  agent: { id: "a", display_name: "Sofia Reyes", agency_name: "SR" } } as unknown as Deal;
const round = (side: string, pct: string, note: string | null = null) => ({
  id: side + pct, kind: "COMMISSION", side, note, created_at: "2026-11-14T10:00:00Z",
  terms: { commission_pct: pct, commission_amount: null, commission_payer: "BUYER" } });

describe("TermRounds", () => {
  it("says who offered, asked, countered and came back", async () => {
    api.get.mockResolvedValue({ data: [round("AGENT", "0.05"), round("BUYER", "0.01", "Our limit"), round("AGENT", "0.03")] });
    renderWithProviders(<TermRounds deal={deal} />);
    const items = await screen.findAllByRole("listitem");
    expect(items.map((li) => li.textContent?.split(" · ")[0])).toEqual([
      "Sofia Reyes asked for 5%, paid by the buying club",
      "Tottenham countered with 1%, paid by the buying club",
      "Sofia Reyes came back with 3%, paid by the buying club",
    ]);
  });

  it("a club's counter on an older deal (no recorded proposal) still reads as a counter", async () => {
    api.get.mockResolvedValue({ data: [round("BUYER", "0.01"), round("AGENT", "0.03")] });
    renderWithProviders(<TermRounds deal={deal} />);
    expect((await screen.findAllByRole("listitem"))[0].textContent).toMatch(/^Tottenham countered with 1%/);
  });
});
