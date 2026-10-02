import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import api from "../../lib/api";
import type { Enquiry } from "../../types/api";
import PageHeader from "../../components/ui/PageHeader";
import EmptyState from "../../components/ui/EmptyState";
import { ListSkeleton } from "../../components/ui/Skeleton";
import { formatDate } from "../../lib/utils";
import ClubLink from "../../components/ui/ClubLink";
import PlayerLink from "../../components/ui/PlayerLink";

type Box = "" | "received" | "sent";

const BOXES: { value: Box; label: string }[] = [
  { value: "", label: "All" },
  { value: "received", label: "About your players" },
  { value: "sent", label: "You asked" },
];

/** Every enquiry this club is part of — asked, or asked about. Yours-to-answer first. */
export default function EnquiriesPage() {
  const navigate = useNavigate();
  const [box, setBox] = useState<Box>("");
  const { data, isLoading, isError } = useQuery<Enquiry[]>({
    queryKey: ["enquiries", { box }],
    queryFn: () => api.get<Enquiry[]>("/enquiries", { params: box ? { box } : {} }).then((r) => r.data),
  });
  const rows = [...(data ?? [])].sort((a, b) => Number(b.whose_move === "your") - Number(a.whose_move === "your"));

  return (
    <div>
      <PageHeader title="Enquiries" subtitle="Informal questions about players, before anyone makes an offer" />
      <div className="mb-5 flex flex-wrap gap-2">
        {BOXES.map((b) => (
          <button
            key={b.value}
            onClick={() => setBox(b.value)}
            className={`rounded-lg px-3 py-1.5 text-sm transition-colors ${
              box === b.value ? "bg-accent-bg text-accent-active ring-1 ring-accent/40" : "bg-surface-inset text-text-muted hover:text-text"
            }`}
          >
            {b.label}
          </button>
        ))}
      </div>
      {isLoading && <ListSkeleton count={5} />}
      {isError && <p className="text-sm text-danger-text">Could not load enquiries.</p>}
      {data && rows.length === 0 && (
        <EmptyState
          title="No enquiries"
          body="Ask about a player from his page — it commits you to nothing."
        />
      )}
      {rows.length > 0 && (
        <div className="overflow-hidden rounded-xl bg-surface ring-1 ring-border">
          {rows.map((e) => {
            const other = e.role === "owning" ? e.asking_club : e.owning_club;
            return (
              <button
                key={e.id}
                onClick={() => navigate(`/enquiries/${e.id}`)}
                className="flex w-full flex-wrap items-center justify-between gap-3 border-b border-rule-faint px-5 py-3.5 text-left last:border-b-0 hover:bg-surface-inset"
              >
                <div className="min-w-0 flex-1">
                  <p className="flex flex-wrap items-center gap-x-2 text-sm font-semibold text-text">
                    <PlayerLink id={e.player_id} name={e.player_name ?? "Player"} />
                    <span className="inline-flex items-center gap-1.5 font-normal text-text-muted">
                      {e.role === "owning" ? "asked by" : "asked of"}
                      <ClubLink id={other.id} name={other.name} crestUrl={other.id ? other.crest_url ?? null : undefined} />
                    </span>
                  </p>
                  {e.last_message && <p className="mt-0.5 truncate text-[13px] text-text-muted">{e.last_message}</p>}
                </div>
                <div className="flex shrink-0 items-center gap-4 text-[13px]">
                  {e.status === "CLOSED" ? (
                    <span className="text-text-muted">Closed</span>
                  ) : (
                    <span className={e.whose_move === "your" ? "font-semibold text-danger-text" : "text-text-secondary"}>
                      {e.whose_move === "your" ? "Your move" : "Their move"}
                    </span>
                  )}
                  <span className="text-text-muted">{formatDate(e.updated_at)}</span>
                </div>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
