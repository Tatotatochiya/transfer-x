import type { ClubPublic } from "../../types/api";
import Badge from "../ui/Badge";

const ROLE_LABEL: Record<string, string> = {
  SELLER: "Selling Club",
  BUYER: "Buying Club",
  BOTH: "Buying & Selling",
  ADMIN: "Admin",
};

export default function ClubInfoPanel({
  club,
  squadSize,
  openListings,
}: {
  club: ClubPublic;
  squadSize: number | null;
  openListings: number | null;
}) {
  const memberSince = new Date(club.created_at).getFullYear();

  const items = [
    club.league_name && { icon: "🏆", label: "League",        value: club.league_name },
    club.city        && { icon: "📍", label: "City",          value: club.city },
    club.country     && { icon: "🌍", label: "Country",       value: club.country },
    squadSize != null && squadSize > 0
                     && { icon: "👥", label: "Squad",         value: `${squadSize} players` },
    openListings != null && openListings > 0
                     && { icon: "🏷️", label: "Open Listings", value: String(openListings) },
                        { icon: "📅", label: "Member Since",  value: String(memberSince) },
  ].filter(Boolean) as { icon: string; label: string; value: string }[];

  return (
    <div className="rounded-xl bg-slate-900/60 ring-1 ring-white/[0.06] px-5 py-4">
      <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-500">Club Info</p>
      <div className="space-y-2">
        {items.map((item) => (
          <div key={item.label} className="flex items-center justify-between gap-4">
            <span className="flex items-center gap-2 text-sm text-slate-400">
              <span>{item.icon}</span>
              {item.label}
            </span>
            <span className="text-sm font-medium text-white text-right">{item.value}</span>
          </div>
        ))}
        <div className="flex items-center justify-between gap-4 pt-1">
          <span className="flex items-center gap-2 text-sm text-slate-400">
            <span>🔖</span>
            Role
          </span>
          <Badge variant={club.role === "SELLER" ? "warning" : club.role === "BUYER" ? "info" : "success"}>
            {ROLE_LABEL[club.role] ?? club.role}
          </Badge>
        </div>
      </div>
    </div>
  );
}
