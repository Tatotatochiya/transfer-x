import { useNavigate } from "react-router-dom";
import Badge from "../ui/Badge";
import Card from "../ui/Card";
import { WHOSE_MOVE_LABEL, type WhoseMove } from "../../lib/whoseMove";
import PlayerLink from "../ui/PlayerLink";
import { StalledBadge, stalledDays } from "../transfer/ReminderBadges";

function WhoseMoveTag({ move }: { move: WhoseMove }) {
  if (move === "neither") return null;
  return <Badge variant={move === "your" ? "move-your" : "move-their"}>{WHOSE_MOVE_LABEL[move]}</Badge>;
}

/** Tier-3 working panel — shared by the club and agent dashboards. */
export default function WorkingPanel({ title, linkTo, rows }: {
  title: string; linkTo: string;
  rows: {
    key: string; onClick: () => void; name: string; sub: string; value: string; move: WhoseMove;
    /** When it last moved: waiting on the other side for 3+ days reads "Stalled", in amber. */
    idleSince?: string | null;
    /** The player, for a link to his profile and his photo. */
    player?: { id: string | null | undefined; photoUrl: string | null | undefined };
  }[];
}) {
  const navigate = useNavigate();
  return (
    <Card tier={3} noPadding>
      <div className="flex items-center justify-between border-b border-rule px-[18px] py-[15px]">
        <p className="text-body font-bold text-text">{title}</p>
        <button onClick={() => navigate(linkTo)} className="text-small font-semibold text-accent hover:text-accent-hover">
          View all →
        </button>
      </div>
      <div className="px-[18px] py-1.5">
        {rows.length === 0 && <p className="py-4 text-small text-text-muted">Nothing here right now.</p>}
        {rows.slice(0, 3).map((row) => (
          <div key={row.key} onClick={row.onClick} className="flex items-center gap-3 border-b border-rule-faint py-2.5 last:border-b-0 cursor-pointer">
            <div className="flex-1 basis-[130px] min-w-0">
              <p className="truncate text-body font-semibold text-text">
                {row.player ? <PlayerLink id={row.player.id} name={row.name} photoUrl={row.player.photoUrl ?? null} /> : row.name}
              </p>
              <p className="truncate text-small text-text-muted">{row.sub}</p>
            </div>
            <div className="text-right shrink-0">
              <p className="text-body font-bold text-text">{row.value}</p>
              {row.move === "their" && stalledDays(row.idleSince) != null
                ? <StalledBadge since={row.idleSince} />
                : <WhoseMoveTag move={row.move} />}
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}
