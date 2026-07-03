import { useQuery } from "@tanstack/react-query";
import api from "../../lib/api";
import type { TransferWindowStatus } from "../../types/api";
import { formatDate } from "../../lib/utils";
import { useDeadlineCountdown } from "../../hooks/useDeadlineCountdown";

function WindowCountdown({ closesAt }: { closesAt: string }) {
  const result = useDeadlineCountdown(closesAt);
  if (result.state === "expired") return <span className="text-slate-400">Closing soon</span>;
  const colour = result.state === "danger" ? "text-red-400" : result.state === "warning" ? "text-amber-400" : "text-emerald-400";
  return <span className={`font-bold tabular-nums ${colour}`}>{result.label} remaining</span>;
}

export default function TransferWindowBanner() {
  const { data: windowStatus } = useQuery<TransferWindowStatus>({
    queryKey: ["transfer-window", "status"],
    queryFn: () => api.get<TransferWindowStatus>("/transfers/window/status").then((r) => r.data),
    staleTime: 60_000,
    refetchInterval: 60_000,
  });

  if (!windowStatus?.enforced) return null;

  if (windowStatus.is_open && windowStatus.current_window) {
    const w = windowStatus.current_window;
    return (
      <div className="mb-6 flex items-center justify-between rounded-xl bg-emerald-500/10 px-5 py-3 ring-1 ring-emerald-500/20">
        <div className="flex items-center gap-3">
          <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse shrink-0" />
          <div>
            <span className="text-sm font-semibold text-emerald-300">{w.name}</span>
            <span className="ml-2 text-sm text-emerald-400/70">is open</span>
          </div>
        </div>
        <WindowCountdown closesAt={w.closes_at} />
      </div>
    );
  }

  // Window enforced but closed
  const next = windowStatus.next_window;
  return (
    <div className="mb-6 flex items-center justify-between rounded-xl bg-red-500/10 px-5 py-3 ring-1 ring-red-500/20">
      <div className="flex items-center gap-3">
        <span className="h-2 w-2 rounded-full bg-red-400 shrink-0" />
        <span className="text-sm font-semibold text-red-300">Transfer window is closed</span>
      </div>
      {next ? (
        <span className="text-xs text-slate-400">
          Next: <span className="text-white">{next.name}</span> opens {formatDate(next.opens_at)}
        </span>
      ) : (
        <span className="text-xs text-slate-500">No upcoming window scheduled</span>
      )}
    </div>
  );
}
