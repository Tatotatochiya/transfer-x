import { describe, expect, it } from "vitest";
import { boardRows, detailAfterStage, groupOf, groupRows, stageCounts, stageStep, yourMoveRows } from "./boardList";
import type { Board, BoardCard } from "./types";

const card = (over: Partial<BoardCard>): BoardCard => ({
  key: over.player_name ?? "k", side: "BUYING", column: "offers", kind: "offer", entity_id: "e", player_id: "p",
  player_name: "P", player_position: "MID", counterparty: "Leeds", amount: 1_000_000, detail: "Offer sent",
  whose_move: "their", deadline: null, link: "/offers/e", updated_at: "2026-11-10T10:00:00Z", others: 0, ...over,
});

const labels = { talking: "Listed", offers: "Offers", fee_agreed: "Fee agreed", terms: "Personal terms", paperwork: "Paperwork", done: "Completed" };

describe("groupOf", () => {
  it("your move → yours; a listing → listed; done → done, even if yours; else in progress", () => {
    expect(groupOf(card({ whose_move: "your" }))).toBe("yours");
    expect(groupOf(card({ kind: "listing", column: "talking" }))).toBe("listed");
    expect(groupOf(card({ column: "done", whose_move: "your" }))).toBe("done");
    expect(groupOf(card({}))).toBe("progress");
  });
});

describe("stageStep", () => {
  it("talking 1 … paperwork 5, done 6", () => {
    expect(["talking", "offers", "fee_agreed", "terms", "paperwork", "done"].map(stageStep)).toEqual([1, 2, 3, 4, 5, 6]);
  });
});

describe("groupRows", () => {
  it("orders the groups, sorts inside each, and drops empty ones", () => {
    const rows = [
      card({ player_name: "late", whose_move: "your", deadline: "2026-11-20T00:00:00Z" }),
      card({ player_name: "none", whose_move: "your", deadline: null }),
      card({ player_name: "soon", whose_move: "your", deadline: "2026-11-15T00:00:00Z" }),
      card({ player_name: "talk", column: "talking" }),
      card({ player_name: "terms old", column: "terms", updated_at: "2026-11-01T00:00:00Z" }),
      card({ player_name: "terms new", column: "terms", updated_at: "2026-11-12T00:00:00Z" }),
      card({ player_name: "done", column: "done" }),
    ];
    const groups = groupRows(rows);
    expect(groups.map((g) => g.key)).toEqual(["yours", "progress", "done"]);
    expect(groups[0].rows.map((r) => r.player_name)).toEqual(["soon", "late", "none"]);
    expect(groups[1].rows.map((r) => r.player_name)).toEqual(["terms new", "terms old", "talk"]);
    expect(groups[1]).toMatchObject({ label: "In progress", hint: "nothing for you yet" });
    expect(yourMoveRows(rows).map((r) => r.player_name)).toEqual(["soon", "late", "none"]);
  });
});

describe("stageCounts", () => {
  it("counts the open stages in order, omitting zero and done", () => {
    const rows = [card({ column: "terms" }), card({ column: "talking" }), card({ column: "terms" }), card({ column: "done" })];
    expect(stageCounts(rows, labels)).toEqual([
      { key: "talking", label: "Listed", count: 1 }, { key: "terms", label: "Personal terms", count: 2 }]);
  });

  it("follows the rows it's given (after the side and search filters)", () => {
    const rows = [card({ column: "terms", player_name: "A" }), card({ column: "talking", player_name: "B" })];
    expect(stageCounts(rows.filter((r) => r.player_name === "A"), labels)).toEqual([{ key: "terms", label: "Personal terms", count: 1 }]);
  });
});

describe("detailAfterStage", () => {
  it("drops a detail that only repeats the stage, keeps one that adds something", () => {
    expect(detailAfterStage(card({ column: "fee_agreed", detail: "Fee agreed" }), "Fee agreed")).toBeNull();
    expect(detailAfterStage(card({ column: "terms", detail: "Agent commission · your move" }), "Personal terms"))
      .toBe("Agent commission · your move");
  });
});

describe("boardRows", () => {
  it("keeps the API's order inside each column", () => {
    const board: Board = { columns: [{ key: "talking", label: "Listed", cards: [card({ player_name: "b" }), card({ player_name: "a" })] },
      { key: "offers", label: "Offers", cards: [card({ player_name: "c" })] }], closed: [], counts: { buying: 3, selling: 0, your_move: 0 } };
    expect(boardRows(board).map((r) => r.player_name)).toEqual(["b", "a", "c"]);
  });
});
