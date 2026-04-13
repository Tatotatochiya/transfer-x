import { formatDateTime } from "../../lib/utils";

export interface TimelineEvent {
  id: string;
  label: string;
  body?: string;
  timestamp: string;
}

interface TimelineProps {
  events: TimelineEvent[];
}

export default function Timeline({ events }: TimelineProps) {
  if (events.length === 0) return null;

  return (
    <ol className="space-y-4">
      {events.map((event, i) => (
        <li key={event.id} className="relative flex gap-4">
          {/* Vertical line */}
          {i < events.length - 1 && (
            <span className="absolute left-[9px] top-5 h-full w-px bg-white/[0.08]" />
          )}
          {/* Dot */}
          <span className="mt-1 flex h-[18px] w-[18px] shrink-0 items-center justify-center rounded-full bg-slate-800 ring-1 ring-white/[0.08]">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
          </span>
          <div className="min-w-0 flex-1 pb-1">
            <p className="text-sm font-medium text-white">{event.label}</p>
            {event.body && <p className="mt-0.5 text-sm text-slate-400">{event.body}</p>}
            <p className="mt-1 text-xs text-slate-500">{formatDateTime(event.timestamp)}</p>
          </div>
        </li>
      ))}
    </ol>
  );
}
