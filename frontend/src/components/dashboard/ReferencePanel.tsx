import { useNavigate } from "react-router-dom";
import Card from "../ui/Card";

/** Tier-4 reference panel — shared by the club and agent dashboards. Renders
 * nothing when there's nothing to reference (no empty state — Tier 4 is
 * glanceable background info, not a section that needs to announce its own
 * absence). */
export default function ReferencePanel({ title, linkTo, linkLabel, rows }: {
  title: string; linkTo?: string; linkLabel?: string;
  rows: { key: string; onClick: () => void; label: string; sub: string; value: string; valueColour: string }[];
}) {
  const navigate = useNavigate();
  if (rows.length === 0) return null;
  return (
    <Card tier={4} noPadding>
      <div className="flex items-center justify-between px-[18px] py-[13px]">
        <p className="text-[13px] font-semibold text-text-secondary">{title}</p>
        {linkTo && (
          <button onClick={() => navigate(linkTo)} className="text-xs text-text-muted hover:text-text-secondary">
            {linkLabel}
          </button>
        )}
      </div>
      <div className="px-[18px] pb-2">
        {rows.map((row) => (
          <div key={row.key} onClick={row.onClick} className="flex items-center justify-between py-[9px] cursor-pointer">
            <div className="min-w-0">
              <p className="truncate text-[13px] text-text">{row.label}</p>
              <p className="truncate text-[11px] text-text-muted">{row.sub}</p>
            </div>
            <span className={`shrink-0 text-[13px] font-semibold ${row.valueColour}`}>{row.value}</span>
          </div>
        ))}
      </div>
    </Card>
  );
}
