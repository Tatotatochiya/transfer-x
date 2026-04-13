import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "../../lib/api";
import type { ShortlistSummary } from "../../types/api";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import EmptyState from "../../components/ui/EmptyState";
import PageHeader from "../../components/ui/PageHeader";
import { formatDate, getApiError } from "../../lib/utils";
import { useConfirm } from "../../context/ConfirmContext";
import { ListSkeleton } from "../../components/ui/Skeleton";

function CreateForm({ onDone }: { onDone: () => void }) {
  const queryClient = useQueryClient();
  const [name, setName]         = useState("");
  const [desc, setDesc]         = useState("");
  const [error, setError]       = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: (body: object) =>
      api.post("/scouting/shortlists", body).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["scouting", "shortlists"] });
      onDone();
    },
    onError: (err: unknown) => {
      setError(getApiError(err, "Failed to create."));
    },
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) { setError("Name is required."); return; }
    mutation.mutate({ name: name.trim(), description: desc.trim() || undefined });
  }

  return (
    <Card>
      <p className="mb-4 text-xs font-semibold uppercase tracking-wider text-slate-400">
        New Shortlist
      </p>
      <form onSubmit={handleSubmit} className="space-y-3">
        <div>
          <label className="mb-1.5 block text-sm font-medium text-slate-300">
            Name
          </label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Summer targets"
            autoFocus
            className="w-full rounded-lg bg-slate-800 px-3 py-2.5 text-sm text-white placeholder-slate-500 ring-1 ring-white/10 focus:outline-none focus:ring-emerald-500 transition-colors"
          />
        </div>
        <div>
          <label className="mb-1.5 block text-sm font-medium text-slate-300">
            Description <span className="text-slate-500">(optional)</span>
          </label>
          <input
            type="text"
            value={desc}
            onChange={(e) => setDesc(e.target.value)}
            placeholder="What's this list for?"
            className="w-full rounded-lg bg-slate-800 px-3 py-2.5 text-sm text-white placeholder-slate-500 ring-1 ring-white/10 focus:outline-none focus:ring-emerald-500 transition-colors"
          />
        </div>
        {error && <p className="text-sm text-red-400">{error}</p>}
        <div className="flex gap-2 pt-1">
          <Button type="submit" variant="primary" size="sm" loading={mutation.isPending}>
            Create
          </Button>
          <Button type="button" variant="ghost" size="sm" onClick={onDone}>
            Cancel
          </Button>
        </div>
      </form>
    </Card>
  );
}

export default function ShortlistListPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const confirm = useConfirm();
  const [creating, setCreating] = useState(false);

  const { data: shortlists, isLoading } = useQuery<ShortlistSummary[]>({
    queryKey: ["scouting", "shortlists"],
    queryFn: () =>
      api.get<ShortlistSummary[]>("/scouting/shortlists").then((r) => r.data),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) =>
      api.delete(`/scouting/shortlists/${id}`).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["scouting", "shortlists"] });
    },
  });

  return (
    <div>
      <PageHeader
        title="Shortlists"
        subtitle="Curated lists of scouting targets"
        actions={
          !creating && (
            <Button variant="primary" onClick={() => setCreating(true)}>
              + New shortlist
            </Button>
          )
        }
      />

      {creating && (
        <div className="mb-6 max-w-md">
          <CreateForm onDone={() => setCreating(false)} />
        </div>
      )}

      {isLoading && <ListSkeleton count={4} />}

      {shortlists && shortlists.length === 0 && !creating && (
        <EmptyState
          title="No shortlists"
          body="Create a shortlist to start tracking targets."
          action={{ label: "New shortlist", onClick: () => setCreating(true) }}
        />
      )}

      {shortlists && shortlists.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {shortlists.map((sl) => (
            <button
              key={sl.id}
              onClick={() => navigate(`/scouting/shortlists/${sl.id}`)}
              className="group rounded-2xl bg-slate-900 px-5 py-4 ring-1 ring-white/[0.08] hover:ring-emerald-500/30 transition-all text-left"
            >
              <div className="flex items-start justify-between gap-2">
                <p className="font-semibold text-white group-hover:text-emerald-400 transition-colors">
                  {sl.name}
                </p>
                <button
                  onClick={async (e) => {
                    e.stopPropagation();
                    if (await confirm({ message: `Delete "${sl.name}"?`, confirmLabel: "Delete", variant: "danger" })) {
                      deleteMutation.mutate(sl.id);
                    }
                  }}
                  className="shrink-0 text-xs text-slate-600 hover:text-red-400 transition-colors"
                >
                  Delete
                </button>
              </div>
              {sl.description && (
                <p className="mt-1 text-xs text-slate-500 line-clamp-2">
                  {sl.description}
                </p>
              )}
              <div className="mt-3 flex items-center gap-3 text-xs text-slate-500">
                <span>{sl.item_count} player{sl.item_count !== 1 ? "s" : ""}</span>
                <span>·</span>
                <span>{formatDate(sl.updated_at)}</span>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
