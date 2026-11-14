/** The Transfers board's API shapes (backend app/board/schemas.py). */
export type Side = "BOTH" | "BUYING" | "SELLING";
export type WhoseMove = "your" | "their" | "neither";

export interface BoardCard {
  key: string;
  side: "BUYING" | "SELLING";
  column: string;
  kind: "enquiry" | "listing" | "offer" | "deal";
  entity_id: string;
  player_id: string;
  player_name: string;
  player_position: string | null;
  player_photo_url?: string | null;
  counterparty: string | null;
  amount: string | number | null;
  detail: string;
  whose_move: WhoseMove;
  deadline: string | null;
  link: string;
  updated_at: string | null;
  /** Your move, and the other side has chased it since it last moved. */
  chased?: "REMINDED" | "ESCALATED" | null;
  others: number;
}

export interface Board {
  columns: { key: string; label: string; cards: BoardCard[] }[];
  closed: BoardCard[];
  counts: { buying: number; selling: number; your_move: number };
}
