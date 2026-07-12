import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "../../lib/api";
import type { TransferWindowResponse, TransferWindowStatus } from "../../types/api";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Spinner from "../../components/ui/Spinner";
import { useConfirmWithReason } from "../../context/ConfirmContext";
import { formatDate, getApiError } from "../../lib/utils";

function WindowStatusBanner({ status }: { status: TransferWindowStatus }) {
  if (!status.enforced) {
    return (
      <div className="mb-6 rounded-xl bg-slate-800/50 px-5 py-4 ring-1 ring-white/[0.08]">
        <p className="text-sm font-semibold text-slate-300">Open market</p>
        <p className="mt-0.5 text-xs text-slate-500">
          No transfer windows configured. Create one below to enable enforcement.
        </p>
      </div>
    );
  }
  if (status.is_open && status.current_window) {
    return (
      <div className="mb-6 rounded-xl bg-emerald-500/10 px-5 py-4 ring-1 ring-emerald-500/20">
        <p className="text-sm font-semibold text-emerald-300">
          Window open — {status.current_window.name}
        </p>
        <p className="mt-0.5 text-xs text-emerald-400/70">
          Closes {formatDate(status.current_window.closes_at)}
        </p>
      </div>
    );
  }
  return (
    <div className="mb-6 rounded-xl bg-red-500/10 px-5 py-4 ring-1 ring-red-500/20">
      <p className="text-sm font-semibold text-red-300">Window closed — transfers blocked</p>
      {status.next_window && (
        <p className="mt-0.5 text-xs text-red-400/70">
          Next: {status.next_window.name} opens {formatDate(status.next_window.opens_at)}
        </p>
      )}
    </div>
  );
}

// datetime-local inputs need "YYYY-MM-DDTHH:mm" with no timezone suffix.
function toLocalInputValue(iso: string): string {
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

interface EditState {
  name: string;
  association: string;
  opensAt: string;
  closesAt: string;
  gracePeriodHours: string;
}

function WindowRow({ w, onChanged }: { w: TransferWindowResponse; onChanged: () => void }) {
  const [editing, setEditing] = useState(false);
  const [edit, setEdit] = useState<EditState | null>(null);
  const [rowError, setRowError] = useState<string | null>(null);

  const updateMutation = useMutation({
    mutationFn: (body: Partial<{ name: string; association: string | null; opens_at: string; closes_at: string; grace_period_hours: number }>) =>
      api.patch<TransferWindowResponse>(`/transfers/window/${w.id}`, body).then((r) => r.data),
    onSuccess: () => {
      setEditing(false);
      setRowError(null);
      onChanged();
    },
    onError: (err) => setRowError(getApiError(err, "Failed to update window.")),
  });

  const deleteMutation = useMutation({
    mutationFn: (reason: string) =>
      api.delete(`/transfers/window/${w.id}`, { params: { reason } }),
    onSuccess: onChanged,
  });

  const confirmWithReason = useConfirmWithReason();

  async function handleDelete() {
    const { confirmed, reason } = await confirmWithReason({
      title: "Delete transfer window",
      message: `Permanently delete "${w.name}"? Any transfer/deal enforcement that relies on this window's dates disappears immediately.`,
      confirmLabel: "Delete window",
    });
    if (confirmed) deleteMutation.mutate(reason);
  }

  function startEdit() {
    setEdit({
      name: w.name,
      association: w.association ?? "",
      opensAt: toLocalInputValue(w.opens_at),
      closesAt: toLocalInputValue(w.closes_at),
      gracePeriodHours: String(w.grace_period_hours),
    });
    setRowError(null);
    setEditing(true);
  }

  function saveEdit() {
    if (!edit) return;
    if (!edit.name.trim() || !edit.opensAt || !edit.closesAt) {
      setRowError("Name, opens at, and closes at are required.");
      return;
    }
    updateMutation.mutate({
      name: edit.name.trim(),
      association: edit.association.trim() || null,
      opens_at: new Date(edit.opensAt).toISOString(),
      closes_at: new Date(edit.closesAt).toISOString(),
      grace_period_hours: Number(edit.gracePeriodHours) || 0,
    });
  }

  if (editing && edit) {
    return (
      <div className="rounded-xl bg-slate-900 px-5 py-4 ring-1 ring-emerald-500/30">
        <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-emerald-400">
          Admin override — editing "{w.name}"
        </p>
        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <label className="mb-1 block text-xs text-slate-400">Window name</label>
            <input
              value={edit.name}
              onChange={(e) => setEdit({ ...edit, name: e.target.value })}
              className="w-full rounded-lg bg-slate-800 px-3 py-2 text-sm text-white ring-1 ring-white/10 focus:outline-none focus:ring-emerald-500"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-slate-400">
              Association <span className="text-slate-600">(blank = global, applies to all clubs)</span>
            </label>
            <input
              value={edit.association}
              onChange={(e) => setEdit({ ...edit, association: e.target.value })}
              placeholder="e.g. England"
              className="w-full rounded-lg bg-slate-800 px-3 py-2 text-sm text-white placeholder-slate-600 ring-1 ring-white/10 focus:outline-none focus:ring-emerald-500"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-slate-400">Opens at</label>
            <input
              type="datetime-local"
              value={edit.opensAt}
              onChange={(e) => setEdit({ ...edit, opensAt: e.target.value })}
              className="w-full rounded-lg bg-slate-800 px-3 py-2 text-sm text-white ring-1 ring-white/10 focus:outline-none focus:ring-emerald-500"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-slate-400">Closes at</label>
            <input
              type="datetime-local"
              value={edit.closesAt}
              onChange={(e) => setEdit({ ...edit, closesAt: e.target.value })}
              className="w-full rounded-lg bg-slate-800 px-3 py-2 text-sm text-white ring-1 ring-white/10 focus:outline-none focus:ring-emerald-500"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-slate-400">
              Grace period (hours) <span className="text-slate-600">— deadline-day completion window</span>
            </label>
            <input
              type="number"
              min={0}
              value={edit.gracePeriodHours}
              onChange={(e) => setEdit({ ...edit, gracePeriodHours: e.target.value })}
              className="w-full rounded-lg bg-slate-800 px-3 py-2 text-sm text-white ring-1 ring-white/10 focus:outline-none focus:ring-emerald-500"
            />
          </div>
        </div>
        {rowError && <p className="mt-3 text-xs text-red-400">{rowError}</p>}
        <div className="mt-4 flex gap-2">
          <Button size="sm" variant="primary" loading={updateMutation.isPending} onClick={saveEdit}>
            Save override
          </Button>
          <Button size="sm" variant="ghost" onClick={() => setEditing(false)} disabled={updateMutation.isPending}>
            Cancel
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-center justify-between rounded-xl bg-slate-900 px-5 py-3 ring-1 ring-white/[0.08]">
      <div>
        <div className="flex items-center gap-2">
          <p className="text-sm font-semibold text-white">{w.name}</p>
          <Badge variant={w.is_open ? "success" : "neutral"}>
            {w.is_open ? "Open" : "Closed"}
          </Badge>
          {w.association ? (
            <Badge variant="neutral">{w.association}</Badge>
          ) : (
            <span className="text-[10px] uppercase tracking-wider text-slate-600">Global</span>
          )}
        </div>
        <p className="mt-0.5 text-xs text-slate-500">
          {formatDate(w.opens_at)} → {formatDate(w.closes_at)}
          <span className="ml-2 text-slate-600">· {w.grace_period_hours}h grace</span>
        </p>
      </div>
      <div className="flex items-center gap-1">
        <button
          onClick={startEdit}
          className="rounded px-2 py-1 text-xs text-slate-400 hover:bg-white/10 hover:text-white transition-colors"
        >
          Edit
        </button>
        <button
          onClick={handleDelete}
          disabled={deleteMutation.isPending}
          className="rounded px-2 py-1 text-xs text-red-400 hover:bg-red-500/10 transition-colors disabled:opacity-40"
        >
          Delete
        </button>
      </div>
    </div>
  );
}

export default function AdminTransferWindowPage() {
  const qc = useQueryClient();
  const [name, setName]       = useState("");
  const [association, setAssociation] = useState("");
  const [opensAt, setOpensAt] = useState("");
  const [closesAt, setClosesAt] = useState("");
  const [gracePeriodHours, setGracePeriodHours] = useState("24");
  const [formError, setFormError] = useState<string | null>(null);

  const { data: statusData, isLoading: statusLoading } = useQuery<TransferWindowStatus>({
    queryKey: ["transfer-window", "status", null],
    queryFn: () => api.get<TransferWindowStatus>("/transfers/window/status").then((r) => r.data),
    staleTime: 30_000,
  });

  const { data: windows, isLoading: listLoading } = useQuery<TransferWindowResponse[]>({
    queryKey: ["admin", "transfer-windows"],
    queryFn: () => api.get<TransferWindowResponse[]>("/transfers/window").then((r) => r.data),
    staleTime: 30_000,
  });

  function invalidateAll() {
    qc.invalidateQueries({ queryKey: ["admin", "transfer-windows"] });
    qc.invalidateQueries({ queryKey: ["transfer-window", "status"] });
  }

  const createMutation = useMutation({
    mutationFn: (body: { name: string; association: string | null; opens_at: string; closes_at: string; grace_period_hours: number }) =>
      api.post<TransferWindowResponse>("/transfers/window", body).then((r) => r.data),
    onSuccess: () => {
      invalidateAll();
      setName(""); setAssociation(""); setOpensAt(""); setClosesAt(""); setGracePeriodHours("24"); setFormError(null);
    },
    onError: (err) => setFormError(getApiError(err, "Failed to create window.")),
  });

  function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setFormError(null);
    if (!name.trim() || !opensAt || !closesAt) {
      setFormError("Name, opens at, and closes at are required.");
      return;
    }
    createMutation.mutate({
      name: name.trim(),
      association: association.trim() || null,
      opens_at: new Date(opensAt).toISOString(),
      closes_at: new Date(closesAt).toISOString(),
      grace_period_hours: Number(gracePeriodHours) || 0,
    });
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-white">Transfer Windows</h1>
        <p className="mt-1 text-sm text-slate-400">
          When windows are configured, sales, offers, and deal completion are blocked outside of open windows
          for the association they cover. Leave association blank for a global window that applies to every club.
          Edit an existing window at any time to override its dates — no need to delete and recreate.
        </p>
      </div>

      {statusLoading ? (
        <div className="flex justify-center py-6"><Spinner /></div>
      ) : statusData ? (
        <WindowStatusBanner status={statusData} />
      ) : null}

      {/* Create form */}
      <div className="mb-8 rounded-xl bg-slate-900 ring-1 ring-white/[0.08] px-6 py-5">
        <p className="mb-4 text-sm font-semibold text-white">Create Transfer Window</p>
        <form onSubmit={handleCreate} className="grid gap-4 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <label className="mb-1 block text-xs text-slate-400">Window name</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Summer 2026"
              className="w-full rounded-lg bg-slate-800 px-3 py-2 text-sm text-white placeholder-slate-600 ring-1 ring-white/10 focus:outline-none focus:ring-emerald-500"
            />
          </div>
          <div className="sm:col-span-2">
            <label className="mb-1 block text-xs text-slate-400">
              Association <span className="text-slate-600">(blank = global, applies to every club)</span>
            </label>
            <input
              value={association}
              onChange={(e) => setAssociation(e.target.value)}
              placeholder="e.g. England — matches each club's country"
              className="w-full rounded-lg bg-slate-800 px-3 py-2 text-sm text-white placeholder-slate-600 ring-1 ring-white/10 focus:outline-none focus:ring-emerald-500"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-slate-400">Opens at</label>
            <input
              type="datetime-local"
              value={opensAt}
              onChange={(e) => setOpensAt(e.target.value)}
              className="w-full rounded-lg bg-slate-800 px-3 py-2 text-sm text-white ring-1 ring-white/10 focus:outline-none focus:ring-emerald-500"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-slate-400">Closes at</label>
            <input
              type="datetime-local"
              value={closesAt}
              onChange={(e) => setClosesAt(e.target.value)}
              className="w-full rounded-lg bg-slate-800 px-3 py-2 text-sm text-white ring-1 ring-white/10 focus:outline-none focus:ring-emerald-500"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-slate-400">
              Grace period (hours) <span className="text-slate-600">— deadline-day completion window</span>
            </label>
            <input
              type="number"
              min={0}
              value={gracePeriodHours}
              onChange={(e) => setGracePeriodHours(e.target.value)}
              className="w-full rounded-lg bg-slate-800 px-3 py-2 text-sm text-white ring-1 ring-white/10 focus:outline-none focus:ring-emerald-500"
            />
          </div>
          <div className="flex items-end">
            <Button type="submit" variant="primary" loading={createMutation.isPending} className="w-full">
              Create Window
            </Button>
          </div>
          {formError && (
            <p className="sm:col-span-2 text-xs text-red-400">{formError}</p>
          )}
        </form>
      </div>

      {/* Window list */}
      <div>
        <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-400">All Windows</p>
        {listLoading && <div className="flex justify-center py-6"><Spinner /></div>}
        {windows && windows.length === 0 && (
          <p className="text-sm text-slate-500">No windows created yet.</p>
        )}
        {windows && windows.length > 0 && (
          <div className="space-y-2">
            {windows.map((w) => (
              <WindowRow key={w.id} w={w} onChanged={invalidateAll} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
