import api from "./api";
import type { Paginated, Player } from "../types/api";
import type { PlayerFilterState } from "../components/players/PlayerFilters";

/** GET /players/market's query params for a filter state (page aside). */
export function marketParams(filters: PlayerFilterState): Record<string, string | number | boolean> {
  return {
    sort_by: filters.sort_by,
    sort_dir: filters.sort_dir,
    ...(filters.search         && { search: filters.search }),
    ...(filters.position       && { position: filters.position }),
    ...(filters.status         && { status: filters.status }),
    ...(filters.open_to_offers && { open_to_offers: true }),
    ...(filters.buyable        && { buyable: true }),
    ...(filters.min_age        && { min_age: Number(filters.min_age) }),
    ...(filters.max_age        && { max_age: Number(filters.max_age) }),
    ...(filters.nationality    && { nationality: filters.nationality }),
    ...(filters.club_search    && { club_search: filters.club_search }),
    ...(filters.min_goals        && { min_goals: Number(filters.min_goals) }),
    ...(filters.min_assists      && { min_assists: Number(filters.min_assists) }),
    ...(filters.min_appearances  && { min_appearances: Number(filters.min_appearances) }),
    ...(filters.min_avg_rating   && { min_avg_rating: Number(filters.min_avg_rating) }),
    // The outside market estimate, in € millions on screen.
    ...(filters.min_value        && { min_market_value: Number(filters.min_value) * 1_000_000 }),
    ...(filters.max_value        && { max_market_value: Number(filters.max_value) * 1_000_000 }),
    ...(filters.contract_expiry_months && { contract_expiry_within_months: Number(filters.contract_expiry_months) }),
    ...(filters.min_form_score   && { min_form_score: Number(filters.min_form_score) }),
  };
}

export function fetchMarket(filters: PlayerFilterState, page: number, pageSize: number): Promise<Paginated<Player>> {
  return api
    .get<Paginated<Player>>("/players/market", { params: { page, page_size: pageSize, ...marketParams(filters) } })
    .then((r) => r.data);
}
