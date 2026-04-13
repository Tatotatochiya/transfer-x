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
  if (!name) return <span className="text-slate-600 text-xs">{label}: —</span>;
  return (
    <div className="flex items-center gap-1.5">
      <span className="text-[10px] text-slate-500 uppercase tracking-wide">{label}</span>
      {crest ? (
        <img src={crest} alt={name} className="h-4 w-4 object-contain shrink-0" />
      ) : (
        <div className="h-4 w-4 rounded-full bg-slate-700 flex items-center justify-center text-[9px] font-bold text-slate-400 shrink-0">
          {name[0]?.toUpperCase()}
        </div>
      )}
      <span className="text-sm font-medium text-white truncate">{name}</span>
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
    ? "bg-amber-500/10 text-amber-400 ring-amber-500/20"
    : "bg-sky-500/10 text-sky-400 ring-sky-500/20";

  return (
    <div className="grid grid-cols-[56px_1fr] gap-3 py-3 border-b border-white/[0.04] last:border-0">
      {/* Date */}
      <div className="text-right">
        {year && <p className="text-sm font-bold text-white tabular-nums">{year}</p>}
        {month && <p className="text-[11px] text-slate-500">{month}</p>}
      </div>

      {/* Transfer detail */}
      <div className="min-w-0 space-y-1.5">
        <div className="flex items-center gap-2 flex-wrap">
          <TeamChip name={t.team_out_name} crest={t.team_out_crest_url} label="From" />
          <span className="text-slate-600">→</span>
          <TeamChip name={t.team_in_name} crest={t.team_in_crest_url} label="To" />
        </div>
        <div className="flex items-center gap-2">
          {t.transfer_type && (
            <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ring-1 ${typeCls}`}>
              {t.transfer_type}
            </span>
          )}
          {t.fee_display && (
            <span className="text-xs font-medium text-emerald-400">{t.fee_display}</span>
          )}
          {!t.fee_display && !isLoan && (
            <span className="text-[11px] text-slate-600">Fee undisclosed</span>
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
      <div className="rounded-xl bg-red-500/10 px-4 py-3 text-sm text-red-400 ring-1 ring-red-500/20">
        Could not load transfer history.
      </div>
    );
  }

  if (!transfers || transfers.length === 0) {
    return (
      <div className="rounded-xl bg-slate-800/40 px-4 py-3 text-sm text-slate-500 ring-1 ring-white/[0.06]">
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
