import { useQuery } from "@tanstack/react-query";
import api from "../../lib/api";
import type { PlayerTransfer } from "../../types/api";
import Spinner from "../ui/Spinner";
import FallbackImage from "../ui/FallbackImage";

function TeamChip({
  name,
  crest,
  label,
}: {
  name: string | null;
  crest: string | null;
  label: string;
}) {
  if (!name) return <span className="text-text-muted text-caption">{label}: —</span>;
  return (
    <div className="flex items-center gap-1.5">
      <span className="text-caption text-text-secondary font-semibold">{label}</span>
      <FallbackImage src={crest} name={name} kind="club" sizeClass="h-4 w-4 text-caption" colorClass="bg-surface-inset text-text-muted" />
      <span className="text-body font-medium text-text truncate">{name}</span>
    </div>
  );
}

function TransferRow({ t }: { t: PlayerTransfer }) {
  const year = t.transfer_date ? new Date(t.transfer_date).getFullYear() : null;
  const month = t.transfer_date
    ? new Date(t.transfer_date).toLocaleDateString("en-GB", { month: "short" })
    : null;

  const isLoan = t.transfer_type?.toLowerCase().includes("loan");
  const typeCls = isLoan
    ? "bg-warning-bg text-warning-text ring-warning-ring"
    : "bg-accent-bg text-accent ring-accent-ring";

  return (
    <div className="grid grid-cols-[56px_1fr] gap-3 py-3 border-b border-rule-faint last:border-0">
      {/* Date */}
      <div className="text-right">
        {year && <p className="text-body font-bold text-text tabular-nums">{year}</p>}
        {month && <p className="text-caption text-text-muted">{month}</p>}
      </div>

      {/* Transfer detail */}
      <div className="min-w-0 space-y-1.5">
        <div className="flex items-center gap-2 flex-wrap">
          <TeamChip name={t.team_out_name} crest={t.team_out_crest_url} label="From" />
          <span className="text-text-muted">→</span>
          <TeamChip name={t.team_in_name} crest={t.team_in_crest_url} label="To" />
        </div>
        <div className="flex items-center gap-2">
          {t.transfer_type && (
            <span className={`rounded-full px-2 py-0.5 text-caption font-semibold ring-1 ${typeCls}`}>
              {t.transfer_type}
            </span>
          )}
          {t.fee_display && (
            <span className="text-caption font-medium text-success-text">{t.fee_display}</span>
          )}
          {!t.fee_display && !isLoan && (
            <span className="text-caption text-text-muted">Fee undisclosed</span>
          )}
        </div>
      </div>
    </div>
  );
}

interface Props {
  playerId: string;
}

export default function CareerHistoryPanel({ playerId }: Props) {
  const { data: transfers, isLoading, isError } = useQuery<PlayerTransfer[]>({
    queryKey: ["players", playerId, "transfers"],
    queryFn: () =>
      api.get<PlayerTransfer[]>(`/players/market/${playerId}/transfers`).then((r) => r.data),
    staleTime: 1000 * 60 * 60, // 1h — backend caches for 24h
  });

  if (isLoading) {
    return <div className="flex justify-center py-6"><Spinner /></div>;
  }

  if (isError) {
    return (
      <div className="rounded-xl bg-danger-bg px-4 py-3 text-small text-danger-text ring-1 ring-danger-border">
        Could not load transfer history.
      </div>
    );
  }

  if (!transfers || transfers.length === 0) {
    return (
      <div className="rounded-xl bg-surface-inset px-4 py-3 text-small text-text-muted ring-1 ring-border">
        No transfer history available.
      </div>
    );
  }

  return (
    <div>
      {transfers.map((t, i) => (
        <TransferRow key={i} t={t} />
      ))}
    </div>
  );
}
