import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import api from "../../lib/api";
import type { RealWorldMove } from "../../types/api";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import PageHeader from "../../components/ui/PageHeader";
import Spinner from "../../components/ui/Spinner";
import { formatDate, getApiError } from "../../lib/utils";
import { useAskReason } from "../../context/ConfirmContext";
import { useToast } from "../../context/ToastContext";
import { MOVE_KIND_LABEL } from "../../lib/realWorld";

interface MoveRow extends RealWorldMove {
  player_id: string;
  name: string;
  photo_url: string | null;
  position: string | null;
  /** Why staff can't apply it (in a deal, on loan, a loan move); null when they can. */
  apply_blocked: string | null;
}

interface ApplyResult {
  applied: { player_id: string; name: string }[];
  skipped: { player_id: string; reason: string }[];
}

interface MovesResponse {
  season: string;
  checked: number;
  mismatches: MoveRow[];
  counts: Record<RealWorldMove["kind"] | "to_transferx_club", number>;
}

type KindFilter = RealWorldMove["kind"] | "ALL";
const KINDS: KindFilter[] = ["ALL", "transfer", "loan", "loan_return", "playing"];

const KIND_VARIANT: Record<RealWorldMove["kind"], "info" | "warning" | "neutral" | "success"> = {
  transfer: "info",
  loan: "warning",
  loan_return: "neutral",
  playing: "success",
};

/**
 * Contracted players whose club in API-Football's data isn't the one
 * TransferX has them registered to: real-world moves TransferX doesn't have
 * yet. Staff can apply a move (his registration follows it: open offers and
 * listings close, his contract ends, and he joins the TransferX club he went
 * to or becomes an outside player) or dismiss it. Both ask for a reason and
 * are audited; neither moves money.
 */
export default function AdminRealWorldMovesPage() {
  const [kind, setKind] = useState<KindFilter>("ALL");
  const [club, setClub] = useState("");
  const [q, setQ] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const queryClient = useQueryClient();
  const askReason = useAskReason();
  const { addToast } = useToast();

  const { data, isLoading, isError } = useQuery<MovesResponse>({
    queryKey: ["admin", "real-world-moves"],
    queryFn: () => api.get<MovesResponse>("/admin/real-world-moves").then((r) => r.data),
    staleTime: 60_000,
  });

  const clubs = useMemo(
    () => [...new Set((data?.mismatches ?? []).map((m) => m.registered_club ?? ""))].filter(Boolean).sort(),
    [data],
  );
  const rows = (data?.mismatches ?? []).filter((m) =>
    (kind === "ALL" || m.kind === kind)
    && (!club || m.registered_club === club)
    && (!q.trim() || m.name.toLowerCase().includes(q.trim().toLowerCase())),
  );
  const applicable = rows.filter((m) => !m.apply_blocked);
  const chosen = applicable.filter((m) => selected.has(m.player_id));

  const refresh = () => {
    setSelected(new Set());
    queryClient.invalidateQueries({ queryKey: ["admin", "real-world-moves"] });
  };
  const apply = useMutation({
    mutationFn: (body: { player_ids: string[]; reason: string }) =>
      api.post<ApplyResult>("/admin/real-world-moves/apply", body).then((r) => r.data),
    onSuccess: (r) => {
      refresh();
      const done = `${r.applied.length} registration${r.applied.length === 1 ? "" : "s"} updated`;
      addToast(r.skipped.length ? `${done}; ${r.skipped.length} skipped: ${r.skipped[0].reason}` : done,
        r.skipped.length ? "warning" : "success");
    },
    onError: (err) => addToast(getApiError(err, "Couldn't apply the moves."), "error"),
  });
  const dismiss = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      api.post(`/admin/real-world-moves/${id}/dismiss`, { reason }),
    onSuccess: () => { refresh(); addToast("Dismissed. It won't be reported again unless he moves somewhere else.", "success"); },
    onError: (err) => addToast(getApiError(err, "Couldn't dismiss it."), "error"),
  });

  async function applyMoves(moves: MoveRow[]) {
    const one = moves.length === 1 ? moves[0] : null;
    const reason = await askReason({
      title: one ? `Move ${one.name} to ${one.real_club ?? "his new club"}` : `Apply ${moves.length} real-world moves`,
      message: (one ? `${one.name} comes off ${one.registered_club ?? "his club"}'s squad. ` : "Each player comes off his TransferX squad. ")
        + "Open offers, listings and enquiries for him close, and any budget they held is released. "
        + "A player who joined a TransferX club gets a contract there for that club to confirm; anyone else becomes an outside player. "
        + "Both clubs are told. No money moves.",
      reasonLabel: "Why?",
      placeholder: "e.g. Confirmed summer transfers, 2026/27",
      confirmLabel: one ? "Apply move" : `Apply ${moves.length} moves`,
    });
    if (reason) apply.mutate({ player_ids: moves.map((m) => m.player_id), reason });
  }

  async function dismissMove(m: MoveRow) {
    const reason = await askReason({
      title: `Keep ${m.name} at ${m.registered_club ?? "his club"}`,
      message: `His move to ${m.real_club ?? "another club"} stops being reported. It comes back only if he turns up at a different club.`,
      reasonLabel: "Why leave it?",
      placeholder: "e.g. Loan abroad; still their player",
      confirmLabel: "Dismiss",
    });
    if (reason) dismiss.mutate({ id: m.player_id, reason });
  }

  function toggle(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }

  return (
    <div>
      <PageHeader
        title="Real-world moves"
        subtitle="Players API-Football has at another club than the one TransferX has them registered to. Apply a move to update his registration, or dismiss it."
      />

      {isLoading ? (
        <div className="flex justify-center py-12"><Spinner size="lg" /></div>
      ) : isError || !data ? (
        <p className="text-sm text-danger-text">Couldn&rsquo;t load the check. Try again in a moment.</p>
      ) : (
        <>
          <p className="mb-4 text-sm text-text-secondary">
            {data.mismatches.length} of {data.checked} contracted players moved in the {data.season}/{String((Number(data.season) + 1) % 100).padStart(2, "0")} season
            {" · "}{data.counts.to_transferx_club} to another TransferX club.
          </p>

          <div className="mb-4 flex flex-wrap items-center gap-3">
            <div className="flex w-fit max-w-full gap-1 overflow-x-auto rounded-xl bg-surface-inset p-1">
              {KINDS.map((k) => (
                <button
                  key={k}
                  type="button"
                  onClick={() => setKind(k)}
                  className={`whitespace-nowrap rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
                    kind === k ? "bg-surface text-text shadow-sm" : "text-text-muted hover:text-text"
                  }`}
                >
                  {k === "ALL" ? `All (${data.mismatches.length})` : `${MOVE_KIND_LABEL[k]} (${data.counts[k] ?? 0})`}
                </button>
              ))}
            </div>
            <select
              value={club}
              onChange={(e) => setClub(e.target.value)}
              aria-label="TransferX club"
              className="rounded-lg bg-surface px-3 py-1.5 text-sm text-text ring-1 ring-input-border"
            >
              <option value="">All clubs</option>
              {clubs.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
            <input
              type="search"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Search players"
              aria-label="Search players"
              className="rounded-lg bg-surface px-3 py-1.5 text-sm text-text ring-1 ring-input-border placeholder:text-text-muted"
            />
            <Button
              variant="primary"
              size="sm"
              disabled={chosen.length === 0}
              loading={apply.isPending}
              onClick={() => applyMoves(chosen)}
              className="sm:ml-auto"
            >
              {chosen.length ? `Apply ${chosen.length} selected` : "Apply selected"}
            </Button>
          </div>

          {rows.length === 0 ? (
            <div className="rounded-xl bg-surface px-5 py-12 text-center ring-1 ring-border">
              <p className="text-sm font-medium text-text">No moves</p>
              <p className="mt-1 text-sm text-text-muted">Every registration in this filter matches API-Football.</p>
            </div>
          ) : (
            <div className="overflow-x-auto rounded-xl ring-1 ring-border">
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="border-b border-rule bg-surface-header text-left text-xs font-semibold uppercase tracking-wider text-text-muted">
                    <th className="w-10 px-4 py-3">
                      <input
                        type="checkbox"
                        aria-label="Select every move that can be applied"
                        checked={applicable.length > 0 && chosen.length === applicable.length}
                        disabled={applicable.length === 0}
                        onChange={(e) => setSelected(e.target.checked ? new Set(applicable.map((m) => m.player_id)) : new Set())}
                      />
                    </th>
                    <th className="px-4 py-3">Player</th>
                    <th className="px-4 py-3">On TransferX</th>
                    <th className="px-4 py-3">In real life</th>
                    <th className="px-4 py-3">What happened</th>
                    <th className="px-4 py-3">Last game there</th>
                    <th className="px-4 py-3">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((m) => (
                    <tr key={m.player_id} className="border-t border-rule-faint align-top">
                      <td className="px-4 py-3">
                        <input
                          type="checkbox"
                          aria-label={`Select ${m.name}`}
                          checked={selected.has(m.player_id)}
                          disabled={!!m.apply_blocked}
                          onChange={() => toggle(m.player_id)}
                        />
                      </td>
                      <td className="px-4 py-3">
                        <Link to={`/players/market/${m.player_id}`} className="font-medium text-text hover:text-accent">{m.name}</Link>
                        {m.position && <span className="ml-2 text-xs text-text-muted">{m.position}</span>}
                      </td>
                      <td className="px-4 py-3 text-text">{m.registered_club ?? "—"}</td>
                      <td className="px-4 py-3">
                        <span className="flex items-center gap-2 text-text">
                          {m.real_club_logo && <img src={m.real_club_logo} alt="" className="h-5 w-5 object-contain" />}
                          {m.real_club ?? "—"}
                        </span>
                        {m.real_club_on_transferx_id && <span className="text-xs text-text-muted">on TransferX</span>}
                      </td>
                      <td className="px-4 py-3">
                        <Badge variant={KIND_VARIANT[m.kind]}>{MOVE_KIND_LABEL[m.kind]}</Badge>
                        <span className="ml-2 text-text-secondary">
                          {m.moved_on ? formatDate(m.moved_on) : "No transfer on record"}{m.fee ? ` · ${m.fee}` : ""}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-text-muted">{m.last_played ? formatDate(m.last_played) : "—"}</td>
                      <td className="px-4 py-3">
                        <div className="flex gap-2">
                          {!m.apply_blocked && (
                            <Button variant="secondary" size="sm" disabled={apply.isPending} onClick={() => applyMoves([m])}>Apply</Button>
                          )}
                          <Button variant="ghost" size="sm" disabled={dismiss.isPending} onClick={() => dismissMove(m)}>Dismiss</Button>
                        </div>
                        {m.apply_blocked && <p className="mt-1 max-w-[260px] text-xs text-text-muted">{m.apply_blocked}</p>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}
