import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import OtherItems from "./OtherItems";
import type { BoardCard } from "./types";

const card = {
  key: "SELLING:p", side: "SELLING", column: "offers", kind: "offer", entity_id: "leeds", player_id: "p",
  player_name: "J. Bynoe-Gittens", player_position: "MID", counterparty: "Leeds", amount: 19_000_000,
  detail: "Countered · your move", whose_move: "your", deadline: null, link: "/offers/leeds", updated_at: null, others: 1,
  other_items: [{ kind: "offer", entity_id: "bou", counterparty: "Bournemouth", amount: 16_500_000,
    detail: "Offer received · your move", whose_move: "your", link: "/offers/bou" }],
} as BoardCard;

describe("OtherItems", () => {
  it("lists each other offer as a link to its own page", () => {
    render(<MemoryRouter><OtherItems card={card} /></MemoryRouter>);
    const link = screen.getByRole("link", { name: /Also Bournemouth · £16.5M · Offer received · your move/ });
    expect(link).toHaveAttribute("href", "/offers/bou");
  });

  it("renders nothing without other items", () => {
    const { container } = render(<MemoryRouter><OtherItems card={{ ...card, other_items: [] }} /></MemoryRouter>);
    expect(container).toBeEmptyDOMElement();
  });
});
