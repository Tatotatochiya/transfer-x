import { useNavigate } from "react-router-dom";
import Badge from "../ui/Badge";
import Card from "../ui/Card";
import { WHOSE_MOVE_LABEL, type WhoseMove } from "../../lib/whoseMove";

function WhoseMoveTag({ move }: { move: WhoseMove }) {
  if (move === "neither") return null;
  return <Badge variant={move === "your" ? "move-your" : "move-their"}>{WHOSE_MOVE_LABEL[move]}</Badge>;
}

/** Tier-3 working panel — shared by the club and agent dashboards. */
export default function WorkingPanel({ title, linkTo, rows }: {
  title: string; linkTo: string;
  rows: { key: string; onClick: () => void; name: string; sub: string; value: string; move: WhoseMove }[];
}) {
  const navigate = useNavigate();
  return (
    <Card tier={3} noPadding>
      <div className="flex items-center justify-between border-b border-rule px-[18px] py-[15px]">
        <p className="text-sm font-bold text-text">{title}</p>
        <button onClick={() => navigate(linkTo)} className="text-xs font-semibold text-accent hover:text-accent-hover">
          View all →
        </button>
      </div>
      <div className="px-[18px] py-1.5">
        {rows.length === 0 && <p className="py-4 text-sm text-text-muted">Nothing here right now.</p>}
        {rows.slice(0, 3).map((row) => (
          <div key={row.key} onClick={row.onClick} className="flex items-center gap-3 border-b border-rule-faint py-2.5 last:border-b-0 cursor-pointer">
            <div className="flex-1 basis-[130px] min-w-0">
              <p className="truncate text-sm font-semibold text-text">{row.name}</p>
              <p className="truncate text-xs text-text-muted">{row.sub}</p>
            </div>
            <div className="text-right shrink-0">
              <p className="text-sm font-bold text-text">{row.value}</p>
              <WhoseMoveTag move={row.move} />
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}
