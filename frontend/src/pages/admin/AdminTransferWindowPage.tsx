import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "../../lib/api";
import type { TransferWindowResponse, WindowCoverage } from "../../types/api";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Spinner from "../../components/ui/Spinner";
import { useAskReason } from "../../context/ConfirmContext";
import { formatDate, getApiError } from "../../lib/utils";

/** FIFA's registration period calendar: every association's windows, kept by
 *  the associations. No feed publishes them, so admins copy them from here. */
const FIFA_CALENDAR = "https://inside.fifa.com/transfer-system/news/fifa-launches-interactive-tool-to-keep-fans-on-ball-over-global-transfer-windows";

const INPUT = "w-full rounded-lg bg-surface px-3 py-2 text-small text-text placeholder-text-muted ring-1 ring-input-border focus:outline-none focus:ring-success";

function today(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

/** Each country with clubs on TransferX: its window now or next, and a
 *  warning when nothing is set up for the next six months. */
function Coverage({ rows }: { rows: WindowCoverage[] }) {
  if (rows.length === 0) return null;
  const missing = rows.filter((r) => r.missing);
  return (
    <div className="mb-6 rounded-xl bg-surface px-5 py-4 ring-1 ring-border">
      <p className="text-body font-semibold text-text">Countries with clubs on TransferX</p>
      {missing.length > 0 && (
        <p role="alert" className="mt-2 rounded-lg bg-warning-bg px-3 py-2 text-body text-text ring-1 ring-warning-ring">
          No window open or set up for the next six months in {missing.map((r) => r.country).join(", ")}.
          Deals there would complete at any time. Add the dates from FIFA&rsquo;s calendar below.
        </p>
      )}
      <ul className="mt-3 divide-y divide-border">
        {rows.map((r) => (
          <li key={r.country} className="flex flex-wrap items-center justify-between gap-2 py-2 text-body">
            <span className="font-medium text-text">{r.country}</span>
            <span className="text-text-muted">
              {r.current_window
                ? <>Open now: {r.current_window.name}, closes {formatDate(r.current_window.closes_at)}</>
                : r.next_window
                  ? <>Closed. {r.next_window.name} opens {formatDate(r.next_window.opens_at)}</>
                  : "No window set up"}
              {!r.own_windows && (r.current_window || r.next_window) && " (a window for every country)"}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function AdminTransferWindowPage() {
  const qc = useQueryClient();
  const [name, setName]       = useState("");
  const [country, setCountry] = useState("");
  const [opensAt, setOpensAt] = useState("");
  const [closesAt, setClosesAt] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");
  const [checkedOn, setCheckedOn] = useState(today());
  const [formError, setFormError] = useState<string | null>(null);

  const { data: coverage } = useQuery<WindowCoverage[]>({
    queryKey: ["admin", "transfer-windows", "coverage"],
    queryFn: () => api.get<WindowCoverage[]>("/transfers/window/coverage").then((r) => r.data),
    staleTime: 30_000,
  });

  const { data: windows, isLoading: listLoading } = useQuery<TransferWindowResponse[]>({
    queryKey: ["admin", "transfer-windows"],
    queryFn: () => api.get<TransferWindowResponse[]>("/transfers/window").then((r) => r.data),
    staleTime: 30_000,
  });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["admin", "transfer-windows"] });
    qc.invalidateQueries({ queryKey: ["transfer-window", "status"] });
  };

  const createMutation = useMutation({
    mutationFn: (body: Record<string, string | null>) =>
      api.post<TransferWindowResponse>("/transfers/window", body).then((r) => r.data),
    onSuccess: () => {
      invalidate();
      setName(""); setOpensAt(""); setClosesAt(""); setSourceUrl(""); setFormError(null);
    },
    onError: (err) => setFormError(getApiError(err, "Failed to create window.")),
  });

  const askReason = useAskReason();
  const deleteMutation = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) => api.delete(`/transfers/window/${id}`, { data: { reason } }),
    onSuccess: invalidate,
  });

  function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setFormError(null);
    if (!name.trim() || !opensAt || !closesAt) {
      setFormError("Name, opens and closes are required.");
      return;
    }
    createMutation.mutate({
      name: name.trim(), country: country.trim() || null, opens_at: opensAt, closes_at: closesAt,
      source_url: sourceUrl.trim() || null, checked_on: checkedOn || null,
    });
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-title-sm sm:text-title font-bold text-text">Transfer Windows</h1>
        <p className="mt-1 text-small text-text-muted">
          Clubs make offers and agree deals all year. A transfer between two clubs completes only while the
          buying club&rsquo;s country has its window open. Free agents and pre-contracts complete at any time.
          Each country sets its own dates; see{" "}
          <a href={FIFA_CALENDAR} target="_blank" rel="noreferrer" className="font-medium text-text underline">
            FIFA&rsquo;s registration period calendar
          </a>.
        </p>
      </div>

      {coverage && <Coverage rows={coverage} />}

      {/* Create form */}
      <div className="mb-8 rounded-xl bg-surface ring-1 ring-border px-6 py-5">
        <p className="mb-4 text-body font-semibold text-text">Create Transfer Window</p>
        <form onSubmit={handleCreate} className="grid gap-4 sm:grid-cols-3">
          <div className="sm:col-span-2">
            <label htmlFor="tw-name" className="mb-1 block text-caption text-text-muted">Window name</label>
            <input id="tw-name" value={name} onChange={(e) => setName(e.target.value)}
                   placeholder="e.g. January 2027" className={INPUT} />
          </div>
          <div>
            <label htmlFor="tw-country" className="mb-1 block text-caption text-text-muted">Country</label>
            <input id="tw-country" list="tw-countries" value={country} onChange={(e) => setCountry(e.target.value)}
                   placeholder="Empty: every country" className={INPUT} />
            <datalist id="tw-countries">
              {(coverage ?? []).map((c) => <option key={c.country} value={c.country} />)}
            </datalist>
          </div>
          <div>
            <label htmlFor="tw-opens" className="mb-1 block text-caption text-text-muted">Opens at</label>
            <input id="tw-opens" type="datetime-local" value={opensAt} onChange={(e) => setOpensAt(e.target.value)}
                   className={INPUT} />
          </div>
          <div>
            <label htmlFor="tw-closes" className="mb-1 block text-caption text-text-muted">Closes at</label>
            <input id="tw-closes" type="datetime-local" value={closesAt} onChange={(e) => setClosesAt(e.target.value)}
                   className={INPUT} />
          </div>
          <div>
            <label htmlFor="tw-checked" className="mb-1 block text-caption text-text-muted">Dates checked on</label>
            <input id="tw-checked" type="date" value={checkedOn} onChange={(e) => setCheckedOn(e.target.value)}
                   className={INPUT} />
          </div>
          <div className="sm:col-span-2">
            <label htmlFor="tw-source" className="mb-1 block text-caption text-text-muted">Source (where the dates come from)</label>
            <input id="tw-source" type="url" value={sourceUrl} onChange={(e) => setSourceUrl(e.target.value)}
                   placeholder="https://inside.fifa.com/associations/ENG/snapshot" className={INPUT} />
          </div>
          <div className="flex items-end">
            <Button type="submit" variant="primary" loading={createMutation.isPending} className="w-full">
              Create Window
            </Button>
          </div>
          {formError && (
            <p className="sm:col-span-3 text-caption text-danger-text">{formError}</p>
          )}
        </form>
      </div>

      {/* Window list */}
      <div>
        <p className="mb-3 text-caption font-semibold text-text-secondary">All windows</p>
        {listLoading && <div className="flex justify-center py-6"><Spinner /></div>}
        {windows && windows.length === 0 && (
          <p className="text-small text-text-muted">No windows created yet. Deals complete at any time.</p>
        )}
        {windows && windows.length > 0 && (
          <div className="space-y-2">
            {windows.map((w) => (
              <div key={w.id} className="flex items-center justify-between gap-3 rounded-xl bg-surface px-5 py-3 ring-1 ring-border">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="text-body font-semibold text-text">{w.name}</p>
                    <Badge variant="neutral">{w.country ?? "Every country"}</Badge>
                    <Badge variant={w.is_open ? "success" : "neutral"}>
                      {w.is_open ? "Open" : "Closed"}
                    </Badge>
                  </div>
                  <p className="mt-0.5 text-caption text-text-muted">
                    {formatDate(w.opens_at)} → {formatDate(w.closes_at)}
                  </p>
                  <p className="mt-0.5 truncate text-caption text-text-muted">
                    {w.source_url
                      ? <a href={w.source_url} target="_blank" rel="noreferrer" className="underline">Source</a>
                      : "No source recorded"}
                    {w.checked_on && <>, checked {formatDate(w.checked_on)}</>}
                  </p>
                </div>
                <button
                  onClick={async () => {
                    const reason = await askReason({
                      title: `Delete ${w.name}`,
                      message: `Deals at ${w.country ? `clubs in ${w.country}` : "every club"} follow this window to complete. Delete it?`,
                      reasonLabel: "Why are you deleting it?",
                      confirmLabel: "Delete window", danger: true,
                    });
                    if (reason) deleteMutation.mutate({ id: w.id, reason });
                  }}
                  disabled={deleteMutation.isPending}
                  className="shrink-0 rounded px-2 py-1 text-caption text-danger-text hover:brightness-95 transition-colors disabled:opacity-40"
                >
                  Delete
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
