import { useQuery } from "@tanstack/react-query";
import api from "../../lib/api";
import type { PlayerTransfer } from "../../types/api";
import Spinner from "../ui/Spinner";

function TeamChip({
  name,
  crest,
  label,
}: {
  name: string | null;
  crest: string | null;
  label: string;
}) {
  if (!name) return <span className="text-text-muted text-xs">{label}: —</span>;
  return (
    <div className="flex items-center gap-1.5">
      <span className="text-[10px] text-text-muted uppercase tracking-wide">{label}</span>
      {crest ? (
        <img src={crest} alt={name} className="h-4 w-4 object-contain shrink-0" />
      ) : (
        <div className="h-4 w-4 rounded-full bg-surface-inset flex items-center justify-center text-[9px] font-bold text-text-muted shrink-0">
          {name[0]?.toUpperCase()}
        </div>
      )}
      <span className="text-sm font-medium text-text truncate">{name}</span>
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
    ? "bg-warning-fill/10 text-warning-text ring-warning-fill/20"
    : "bg-accent/10 text-accent ring-accent/20";

  return (
    <div className="grid grid-cols-[56px_1fr] gap-3 py-3 border-b border-rule-faint last:border-0">
      {/* Date */}
      <div className="text-right">
        {year && <p className="text-sm font-bold text-text tabular-nums">{year}</p>}
        {month && <p className="text-[11px] text-text-muted">{month}</p>}
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
            <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ring-1 ${typeCls}`}>
              {t.transfer_type}
            </span>
          )}
          {t.fee_display && (
            <span className="text-xs font-medium text-success-text">{t.fee_display}</span>
          )}
          {!t.fee_display && !isLoan && (
            <span className="text-[11px] text-text-muted">Fee undisclosed</span>
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
      <div className="rounded-xl bg-danger-bg px-4 py-3 text-sm text-danger-text ring-1 ring-danger-border">
        Could not load transfer history.
      </div>
    );
  }

  if (!transfers || transfers.length === 0) {
    return (
      <div className="rounded-xl bg-surface-inset px-4 py-3 text-sm text-text-muted ring-1 ring-border">
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
