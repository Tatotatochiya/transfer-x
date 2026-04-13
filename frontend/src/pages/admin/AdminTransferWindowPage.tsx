import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "../../lib/api";
import type { TransferWindowResponse, TransferWindowStatus } from "../../types/api";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Spinner from "../../components/ui/Spinner";
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

export default function AdminTransferWindowPage() {
  const qc = useQueryClient();
  const [name, setName]       = useState("");
  const [opensAt, setOpensAt] = useState("");
  const [closesAt, setClosesAt] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  const { data: statusData, isLoading: statusLoading } = useQuery<TransferWindowStatus>({
    queryKey: ["transfer-window", "status"],
    queryFn: () => api.get<TransferWindowStatus>("/transfers/window/status").then((r) => r.data),
    staleTime: 30_000,
  });

  const { data: windows, isLoading: listLoading } = useQuery<TransferWindowResponse[]>({
    queryKey: ["admin", "transfer-windows"],
    queryFn: () => api.get<TransferWindowResponse[]>("/transfers/window").then((r) => r.data),
    staleTime: 30_000,
  });

  const createMutation = useMutation({
    mutationFn: (body: { name: string; opens_at: string; closes_at: string }) =>
      api.post<TransferWindowResponse>("/transfers/window", body).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin", "transfer-windows"] });
      qc.invalidateQueries({ queryKey: ["transfer-window", "status"] });
      setName(""); setOpensAt(""); setClosesAt(""); setFormError(null);
    },
    onError: (err) => setFormError(getApiError(err, "Failed to create window.")),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/transfers/window/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin", "transfer-windows"] });
      qc.invalidateQueries({ queryKey: ["transfer-window", "status"] });
    },
  });

  function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setFormError(null);
    if (!name.trim() || !opensAt || !closesAt) {
      setFormError("All fields are required.");
      return;
    }
    createMutation.mutate({ name: name.trim(), opens_at: opensAt, closes_at: closesAt });
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-white">Transfer Windows</h1>
        <p className="mt-1 text-sm text-slate-400">
          When windows are configured, sales and offers are blocked outside of open windows.
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
        <form onSubmit={handleCreate} className="grid gap-4 sm:grid-cols-3">
          <div className="sm:col-span-3">
            <label className="mb-1 block text-xs text-slate-400">Window name</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Summer 2026"
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
          <div className="flex items-end">
            <Button type="submit" variant="primary" loading={createMutation.isPending} className="w-full">
              Create Window
            </Button>
          </div>
          {formError && (
            <p className="sm:col-span-3 text-xs text-red-400">{formError}</p>
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
              <div key={w.id} className="flex items-center justify-between rounded-xl bg-slate-900 px-5 py-3 ring-1 ring-white/[0.08]">
                <div>
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-semibold text-white">{w.name}</p>
                    <Badge variant={w.is_open ? "success" : "neutral"}>
                      {w.is_open ? "Open" : "Closed"}
                    </Badge>
                  </div>
                  <p className="mt-0.5 text-xs text-slate-500">
                    {formatDate(w.opens_at)} → {formatDate(w.closes_at)}
                  </p>
                </div>
                <button
                  onClick={() => deleteMutation.mutate(w.id)}
                  disabled={deleteMutation.isPending}
                  className="rounded px-2 py-1 text-xs text-red-400 hover:bg-red-500/10 transition-colors disabled:opacity-40"
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
