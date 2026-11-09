import type { FairValueSignal, Player } from "../types/api";
import { formatCompactCurrency } from "./utils";

/**
 * The asking price a list shows for a player: the server's reference price
 * (an open fixed-price listing's asking price, D7 excludes auctions), else
 * the legacy `market_value`. Null when there is neither.
 */
export function askingPrice(
  player: Pick<Player, "market_value">,
  signal?: FairValueSignal | null,
): number | null {
  return signal?.divergence?.reference_price ?? player.market_value ?? null;
}

export type PlayerPriceBasis = "free agent" | "asking" | "model" | null;

export interface PlayerPrice {
  amount: number | null;
  basis: PlayerPriceBasis;
  /** The figure to print: "Free", "£7.4m", or "—". */
  text: string;
}

/**
 * "What would he cost?": nothing for a free agent, else the asking price,
 * else the fee model's value (marked "model"), else nothing known.
 */
export function playerPrice(
  player: Pick<Player, "market_value" | "status">,
  signal?: FairValueSignal | null,
): PlayerPrice {
  if (player.status === "FREE_AGENT") return { amount: 0, basis: "free agent", text: "Free" };
  const asking = askingPrice(player, signal);
  if (asking != null) return { amount: asking, basis: "asking", text: formatCompactCurrency(asking) };
  if (signal) return { amount: signal.fair_value, basis: "model", text: formatCompactCurrency(signal.fair_value) };
  return { amount: null, basis: null, text: "—" };
}
