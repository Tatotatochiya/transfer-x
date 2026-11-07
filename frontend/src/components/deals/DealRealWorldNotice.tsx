import { useQuery } from "@tanstack/react-query";

import api from "../../lib/api";

interface Notice {
  /** The deal can't complete until TransferX staff check his registration. */
  hold: string | null;
  /** A loan elsewhere in real life: worth knowing, nothing waits. */
  note: string | null;
  /** The buying club's transfer window is closed: it completes once it opens. */
  window: string | null;
  window_opens_at: string | null;
}

/**
 * What completion waits on besides the deal's own steps, shown to both clubs
 * on an open deal: API-Football has the player at another club than the
 * selling one (players/real_world.deal_notice), or the buying club's
 * transfer window is closed (transfer_window/service.completion_hold).
 * Completion is refused while either holds; talks and paperwork carry on.
 */
export default function DealRealWorldNotice({ dealId, open }: { dealId: string; open: boolean }) {
  const { data } = useQuery<Notice>({
    queryKey: ["deals", dealId, "real-world"],
    queryFn: () => api.get<Notice>(`/deals/${dealId}/real-world`).then((r) => r.data),
    enabled: open,
    staleTime: 5 * 60_000,
  });
  if (!open || !data) return null;
  return (
    <>
      {data.window && (
        <div role="note" className="mb-6 rounded-xl bg-surface-inset px-5 py-4 text-sm ring-1 ring-border">
          <p className="font-semibold text-text">Completes when the transfer window opens</p>
          <p className="mt-1 text-text-secondary">{data.window}</p>
          <p className="mt-1 text-text-muted">
            Talks and paperwork carry on as normal. Both clubs are told when it opens.
          </p>
        </div>
      )}
      <RealWorld hold={data.hold} note={data.note} />
    </>
  );
}

function RealWorld({ hold, note }: { hold: string | null; note: string | null }) {
  if (!hold && !note) return null;
  const held = !!hold;
  return (
    <div
      role="note"
      className={`mb-6 rounded-xl px-5 py-4 text-sm ring-1 ${
        held ? "bg-warning-fill/10 ring-warning-fill/30" : "bg-surface-inset ring-border"
      }`}
    >
      <p className="font-semibold text-text">{held ? "Completion on hold: moved in real life" : "Moved in real life"}</p>
      <p className="mt-1 text-text-secondary">{hold ?? note}</p>
      {held && (
        <p className="mt-1 text-text-muted">
          Talks and paperwork carry on as normal. Only completing the transfer waits. Source: API-Football.
        </p>
      )}
    </div>
  );
}
