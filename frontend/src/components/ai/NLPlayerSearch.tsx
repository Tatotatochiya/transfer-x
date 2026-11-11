import type { NLParsedFilters } from "../../types/api";
import { formatCompact } from "../../lib/utils";

/**
 * How the AI player search read a description: the quoted interpretation and
 * a chip per filter it applied. The search itself lives in Browse Players'
 * search box (MarketSearch, "✦ Describe").
 */
export function FilterChips({ filters }: { filters: NLParsedFilters }) {
  const chips: string[] = [];
  if (filters.position) chips.push(filters.position);
  if (filters.min_age != null && filters.max_age != null)
    chips.push(`age ${filters.min_age}–${filters.max_age}`);
  else if (filters.min_age != null) chips.push(`age ≥${filters.min_age}`);
  else if (filters.max_age != null) chips.push(`age ≤${filters.max_age}`);
  if (filters.min_height_cm != null) chips.push(`≥${filters.min_height_cm}cm`);
  if (filters.min_form_score != null) chips.push(`form ≥${filters.min_form_score}`);
  if (filters.nationalities?.length) chips.push(filters.nationalities.join(" / "));
  if (filters.open_to_offers) chips.push("listed");
  if (filters.buyable) chips.push("buyable on TransferX");
  const m = formatCompact;
  if (filters.max_value === 0) chips.push("free");
  else if (filters.min_value != null && filters.max_value != null) chips.push(`${m(filters.min_value)}–${m(filters.max_value)}`);
  else if (filters.max_value != null) chips.push(`under ${m(filters.max_value)}`);
  else if (filters.min_value != null) chips.push(`over ${m(filters.min_value)}`);
  if (filters.contract_ends_within_months != null) chips.push(`contract ends within ${filters.contract_ends_within_months} months`);
  if (filters.max_wage_weekly != null) chips.push(`wage ≤ ${m(filters.max_wage_weekly)}/wk`);
  if (filters.league) chips.push(filters.league);

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <span className="text-small text-text-muted italic">"{filters.interpreted_as}"</span>
      {chips.map((c) => (
        <span
          key={c}
          className="rounded-md bg-ai-bg px-2 py-0.5 text-caption font-medium text-ai-text ring-1 ring-ai-ring"
        >
          {c}
        </span>
      ))}
    </div>
  );
}
