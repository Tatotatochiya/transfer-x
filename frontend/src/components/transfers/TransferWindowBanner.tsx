import { useQuery } from "@tanstack/react-query";
import api from "../../lib/api";
import type { TransferWindowStatus } from "../../types/api";
import { formatDate } from "../../lib/utils";
import { useDeadlineCountdown } from "../../hooks/useDeadlineCountdown";

function WindowCountdown({ closesAt }: { closesAt: string }) {
  const result = useDeadlineCountdown(closesAt);
  if (result.state === "expired") return <span className="text-text-muted">Closing soon</span>;
  const colour = result.state === "danger" ? "text-danger-text" : result.state === "warning" ? "text-warning-text" : "text-success-text";
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
      <div className="mb-6 flex items-center justify-between rounded-xl bg-success-bg px-5 py-3 ring-1 ring-success-ring">
        <div className="flex items-center gap-3">
          <span className="h-2 w-2 rounded-full bg-success animate-pulse shrink-0" />
          <div>
            <span className="text-body font-semibold text-success-text">{w.name}</span>
            <span className="ml-2 text-small text-success-text-alt">is open</span>
          </div>
        </div>
        <WindowCountdown closesAt={w.closes_at} />
      </div>
    );
  }

  // Closed: deals go ahead, and complete once the window opens.
  const next = windowStatus.next_window;
  return (
    <div className="mb-6 flex flex-wrap items-center justify-between gap-x-4 gap-y-1 rounded-xl bg-surface-inset px-5 py-3 ring-1 ring-border">
      <div className="flex items-center gap-3">
        <span className="h-2 w-2 rounded-full bg-text-muted shrink-0" />
        <span className="text-small text-text-secondary">
          <span className="font-semibold text-text">The transfer window is closed.</span>{" "}
          You can still make offers and agree deals. They complete when it opens.
        </span>
      </div>
      {next ? (
        <span className="text-caption text-text-muted">
          Next: <span className="text-text">{next.name}</span> opens {formatDate(next.opens_at)}
        </span>
      ) : (
        <span className="text-caption text-text-muted">No date set for the next one</span>
      )}
    </div>
  );
}
