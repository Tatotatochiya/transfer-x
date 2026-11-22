import { describe, expect, it } from "vitest";
import { squadSummary } from "./squadSummary";

const p = (position: string | null, age: number | null) => ({ position, age });

describe("squadSummary", () => {
  it("averages ages to one decimal, ignoring unknown ones", () => {
    const s = squadSummary([p("GK", 24), p("DEF", 25), p("MID", null), p("FWD", 20)], []);
    expect(s.count).toBe(4);
    expect(s.averageAge).toBe(23);
    expect(squadSummary([p("GK", 24), p("DEF", 25)], []).averageAge).toBe(24.5);
    expect(squadSummary([p("GK", null)], []).averageAge).toBeNull();
  });

  it("counts positions, the 21-and-unders and contracts ending within 180 days", () => {
    const s = squadSummary([p("GK", 21), p("GK", 30), p("DEF", 19), p(null, 22)],
      [{ days_remaining: 45 }, { days_remaining: 180 }, { days_remaining: 181 }]);
    expect(s.byPosition).toEqual({ GK: 2, DEF: 1, MID: 0, FWD: 0 });
    expect(s.under21).toBe(2);
    expect(s.endingSoon).toBe(2);
  });

  it("lists the positions short of their minimum", () => {
    const squad = [...Array(2)].map(() => p("GK", 25))
      .concat([...Array(2)].map(() => p("DEF", 25)), [...Array(4)].map(() => p("MID", 25)), [...Array(3)].map(() => p("FWD", 25)));
    expect(squadSummary(squad, []).gaps).toEqual([{ pos: "DEF", need: 2 }]);
    expect(squadSummary(squad.concat([p("DEF", 25), p("DEF", 25)]), []).gaps).toEqual([]);
  });
});
