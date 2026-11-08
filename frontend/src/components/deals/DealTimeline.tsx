import { useQuery } from "@tanstack/react-query";
import api from "../../lib/api";
import type { AuditEvent } from "../../types/api";
import Spinner from "../ui/Spinner";

// ── Deal timeline (real audit log — visible to every deal participant) ────────

const AUDIT_DOT: Record<string, "success" | "accent" | "danger"> = {
  DEAL_CREATED: "success",
  DEAL_COMPLETED: "success",
  DEAL_COLLAPSED: "danger",
};

export default function DealTimeline({ dealId }: { dealId: string }) {
  const { data: events = [], isLoading } = useQuery<AuditEvent[]>({
    queryKey: ["deals", dealId, "audit-log"],
    queryFn: () => api.get(`/deals/${dealId}/audit-log`).then((r) => r.data),
  });

  const dotClass: Record<"success" | "accent" | "danger", string> = {
    success: "bg-success",
    accent:  "bg-accent",
    danger:  "bg-danger",
  };

  if (isLoading) {
    return <Spinner size="sm" />;
  }
  if (events.length === 0) {
    return <p className="text-sm text-text-muted">No activity yet.</p>;
  }

  return (
    <div className="relative pl-4">
      {/* Vertical line */}
      <div className="absolute left-[7px] top-2 bottom-2 w-px bg-rule" />

      <div className="space-y-5">
        {events.map((ev) => (
          <div key={ev.id} className="relative flex gap-3">
            <div className={`mt-1 h-3 w-3 shrink-0 rounded-full ring-2 ring-surface ${dotClass[AUDIT_DOT[ev.action] ?? "accent"]}`} />
            <div className="min-w-0">
              <div className="flex items-baseline gap-2">
                <span className="text-sm font-medium text-text">{ev.description ?? ev.action}</span>
                <span className="text-[13px] text-text-muted shrink-0">
                  {new Date(ev.created_at).toLocaleString("en-GB", {
                    day: "numeric", month: "short", year: "numeric",
                    hour: "2-digit", minute: "2-digit",
                  })}
                </span>
              </div>
              {ev.actor_label && (
                <p className="mt-0.5 text-xs text-text-muted">{ev.actor_label}</p>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
