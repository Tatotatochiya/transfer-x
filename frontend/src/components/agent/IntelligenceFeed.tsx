import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "../../lib/api";
import type { ClientAlert } from "../../types/api";
import Spinner from "../ui/Spinner";
import { ALERT_SEVERITY_DOT, ALERT_TYPE_LABELS } from "../../lib/badges";
import { formatDateTime } from "../../lib/utils";

function AlertRow({ alert }: { alert: ClientAlert }) {
  const queryClient = useQueryClient();

  const markReadMutation = useMutation({
    mutationFn: () => api.post(`/agents/me/alerts/${alert.id}/read`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["agents", "me", "alerts"] }),
  });

  return (
    <Link
      to={`/agent/clients/${alert.mandate_id}`}
      onClick={() => { if (!alert.is_read) markReadMutation.mutate(); }}
      className={`block rounded-lg px-4 py-3 ring-1 transition-colors hover:ring-white/20 ${
        alert.is_read ? "bg-slate-900 ring-white/[0.06] opacity-70" : "bg-slate-800/60 ring-white/[0.1]"
      }`}
    >
      <div className="flex items-start gap-3">
        <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${ALERT_SEVERITY_DOT[alert.severity]}`} />
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-2">
            <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
              {ALERT_TYPE_LABELS[alert.alert_type]}
            </span>
            <span className="shrink-0 text-[11px] text-slate-600">{formatDateTime(alert.created_at)}</span>
          </div>
          <p className="mt-0.5 text-sm text-slate-200">{alert.message}</p>
        </div>
      </div>
    </Link>
  );
}

export default function IntelligenceFeed() {
  const { data: alerts = [], isLoading } = useQuery<ClientAlert[]>({
    queryKey: ["agents", "me", "alerts"],
    queryFn: () => api.get<ClientAlert[]>("/agents/me/alerts").then((r) => r.data),
    refetchInterval: 60_000,
  });

  const unreadCount = alerts.filter((a) => !a.is_read).length;

  if (isLoading) {
    return <div className="flex justify-center py-8"><Spinner size="md" /></div>;
  }

  if (alerts.length === 0) {
    return (
      <div className="rounded-xl bg-slate-900 px-5 py-8 text-center ring-1 ring-white/[0.08]">
        <p className="text-sm font-medium text-white">No alerts yet</p>
        <p className="mt-1 text-xs text-slate-500">
          Contract-expiry windows, valuation moves, and club interest will show up here.
        </p>
      </div>
    );
  }

  return (
    <div>
      <div className="mb-3 flex items-center justify-between">
        <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
          Client Intelligence
        </p>
        {unreadCount > 0 && (
          <span className="rounded-full bg-sky-500/20 px-2 py-0.5 text-[10px] font-bold text-sky-400">
            {unreadCount} new
          </span>
        )}
      </div>
      <div className="space-y-2">
        {alerts.map((alert) => (
          <AlertRow key={alert.id} alert={alert} />
        ))}
      </div>
    </div>
  );
}
