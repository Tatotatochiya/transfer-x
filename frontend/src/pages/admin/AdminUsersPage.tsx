import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "../../lib/api";
import type { AdminUser, Paginated } from "../../types/api";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Pagination from "../../components/ui/Pagination";
import Spinner from "../../components/ui/Spinner";
import { formatDate, getApiError } from "../../lib/utils";
import { useAuthStore } from "../../store/auth";
import { useConfirm } from "../../context/ConfirmContext";

function ToggleSwitch({
  value, disabled, onChange,
}: { value: boolean; disabled?: boolean; onChange: (next: boolean) => void }) {
  return (
    <button
      disabled={disabled}
      onClick={() => onChange(!value)}
      className={`relative inline-flex h-5 w-9 shrink-0 rounded-full border-2 border-transparent transition-colors focus:outline-none disabled:opacity-40 ${
        value ? "bg-emerald-500" : "bg-slate-600"
      }`}
    >
      <span className={`pointer-events-none inline-block h-4 w-4 rounded-full bg-white shadow transition-transform ${value ? "translate-x-4" : "translate-x-0"}`} />
    </button>
  );
}

// ── Copy UUID button ──────────────────────────────────────────────────────────

function CopyUuid({ id }: { id: string }) {
  const [copied, setCopied] = useState(false);
  function copy() {
    navigator.clipboard.writeText(id).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  }
  return (
    <button
      onClick={copy}
      title={id}
      className="font-mono text-xs transition-colors"
      style={{ color: copied ? "#34d399" : "#4b5563" }}
    >
      {copied ? "Copied!" : `${id.slice(0, 8)}…`}
    </button>
  );
}

// ── Inline password reset ─────────────────────────────────────────────────────

function ResetPasswordRow({ userId }: { userId: string }) {
  const [open, setOpen] = useState(false);
  const [pw, setPw]     = useState("");

  const mutation = useMutation({
    mutationFn: () =>
      api.post(`/admin/users/${userId}/reset-password`, { new_password: pw }).then((r) => r.data),
    onSuccess: () => { setOpen(false); setPw(""); },
  });

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="text-xs text-slate-500 hover:text-amber-400 transition-colors"
      >
        Reset pw
      </button>
    );
  }

  return (
    <form
      onSubmit={(e) => { e.preventDefault(); mutation.mutate(); }}
      className="flex items-center gap-1.5"
      onClick={(e) => e.stopPropagation()}
    >
      <input
        type="password"
        value={pw}
        onChange={(e) => setPw(e.target.value)}
        placeholder="new password"
        required
        autoFocus
        className="w-28 rounded bg-slate-800 px-2 py-1 text-xs text-white ring-1 ring-white/10 focus:outline-none focus:ring-amber-500"
      />
      <button
        type="submit"
        disabled={mutation.isPending || !pw}
        className="text-xs text-emerald-400 hover:text-emerald-300 disabled:opacity-40"
      >
        Set
      </button>
      <button
        type="button"
        onClick={() => { setOpen(false); setPw(""); }}
        className="text-xs text-slate-500 hover:text-white"
      >
        ✕
      </button>
      {mutation.isError && (
        <span className="text-xs text-red-400">{getApiError(mutation.error, "Failed")}</span>
      )}
    </form>
  );
}

// ── Create user form ──────────────────────────────────────────────────────────

function CreateUserPanel({ onCreated }: { onCreated: () => void }) {
  const [email, setEmail] = useState("");
  const [pw,    setPw]    = useState("");

  const mutation = useMutation({
    mutationFn: () =>
      api.post("/admin/users", { email, password: pw }).then((r) => r.data),
    onSuccess: () => { setEmail(""); setPw(""); onCreated(); },
  });

  return (
    <form
      onSubmit={(e) => { e.preventDefault(); mutation.mutate(); }}
      className="flex flex-wrap items-end gap-3"
    >
      <div>
        <label className="mb-1 block text-xs text-slate-400">Email</label>
        <input
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="user@example.com"
          className="rounded-lg bg-slate-800 px-3 py-2 text-sm text-white ring-1 ring-white/10 focus:outline-none focus:ring-amber-500 w-56"
        />
      </div>
      <div>
        <label className="mb-1 block text-xs text-slate-400">Password</label>
        <input
          type="password"
          required
          value={pw}
          onChange={(e) => setPw(e.target.value)}
          className="rounded-lg bg-slate-800 px-3 py-2 text-sm text-white ring-1 ring-white/10 focus:outline-none focus:ring-amber-500 w-40"
        />
      </div>
      <Button type="submit" variant="primary" size="sm" loading={mutation.isPending}>
        Create user
      </Button>
      {mutation.isError && (
        <p className="w-full text-xs text-red-400">{getApiError(mutation.error, "Create failed.")}</p>
      )}
      {mutation.isSuccess && (
        <p className="w-full text-xs text-emerald-400">User created.</p>
      )}
    </form>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function AdminUsersPage() {
  const queryClient = useQueryClient();
  const { user: me } = useAuthStore();
  const confirm = useConfirm();
  const [search, setSearch] = useState("");
  const [page,   setPage]   = useState(1);
  const [showCreate, setShowCreate] = useState(false);

  const { data, isLoading } = useQuery<Paginated<AdminUser>>({
    queryKey: ["admin", "users", { search, page }],
    queryFn: () =>
      api
        .get<Paginated<AdminUser>>("/admin/users", {
          params: { page, page_size: 20, ...(search && { search }) },
        })
        .then((r) => r.data),
  });

  const deleteMutation = useMutation({
    mutationFn: (userId: string) => api.delete(`/admin/users/${userId}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin", "users"] }),
  });

  async function handleDeleteUser(userId: string, email: string) {
    const ok = await confirm({
      title: "Delete user",
      message: `Permanently delete "${email}"? Their club and all associated data will also be removed.`,
      confirmLabel: "Delete",
      danger: true,
    });
    if (ok) deleteMutation.mutate(userId);
  }

  const toggleMutation = useMutation({
    mutationFn: ({ userId, patch }: { userId: string; patch: object }) =>
      api.patch<AdminUser>(`/admin/users/${userId}`, patch).then((r) => r.data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin", "users"] }),
  });

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Users</h1>
          <p className="mt-1 text-sm text-slate-400">{data ? `${data.total} total` : ""}</p>
        </div>
        <div className="flex items-center gap-3">
          <input
            type="text"
            placeholder="Search email…"
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            className="rounded-lg bg-slate-800 px-3 py-2 text-sm text-white placeholder-slate-500 ring-1 ring-white/10 focus:outline-none focus:ring-amber-500 transition-colors w-56"
          />
          <Button variant="primary" size="sm" onClick={() => setShowCreate((v) => !v)}>
            {showCreate ? "Hide" : "Create user"}
          </Button>
        </div>
      </div>

      {showCreate && (
        <div className="mb-6 rounded-xl bg-slate-900 ring-1 ring-white/[0.08] px-5 py-4">
          <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-400">New user account</p>
          <CreateUserPanel onCreated={() => {
            queryClient.invalidateQueries({ queryKey: ["admin", "users"] });
          }} />
        </div>
      )}

      {isLoading && <div className="flex justify-center py-12"><Spinner size="lg" /></div>}

      {data && (
        <>
          <div className="overflow-x-auto rounded-xl ring-1 ring-white/[0.08]">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="border-b border-white/[0.08] text-left text-xs font-semibold uppercase tracking-wider text-slate-500">
                  <th className="px-4 py-3">Email</th>
                  <th className="px-4 py-3 text-center">Active</th>
                  <th className="px-4 py-3 text-center">Superuser</th>
                  <th className="px-4 py-3">Joined</th>
                  <th className="px-4 py-3">Password</th>
                  <th className="px-4 py-3 w-8" />
                  <th className="px-4 py-3 w-8" />
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.04]">
                {data.items.map((u) => {
                  const isMe = u.id === me?.id;
                  return (
                    <tr key={u.id} className="bg-slate-900 hover:bg-slate-800/40 transition-colors">
                      <td className="px-4 py-3 font-medium text-white">
                        {u.email}
                        {isMe && (
                          <span className="ml-2 rounded-full bg-amber-500/20 px-2 py-0.5 text-[10px] font-semibold text-amber-400">You</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-center">
                        <ToggleSwitch
                          value={u.is_active}
                          disabled={isMe || toggleMutation.isPending}
                          onChange={(next) => toggleMutation.mutate({ userId: u.id, patch: { is_active: next } })}
                        />
                      </td>
                      <td className="px-4 py-3 text-center">
                        <ToggleSwitch
                          value={u.is_superuser}
                          disabled={isMe || toggleMutation.isPending}
                          onChange={(next) => toggleMutation.mutate({ userId: u.id, patch: { is_superuser: next } })}
                        />
                      </td>
                      <td className="px-4 py-3 text-slate-400 text-xs">{formatDate(u.created_at)}</td>
                      <td className="px-4 py-3">
                        {!isMe && <ResetPasswordRow userId={u.id} />}
                      </td>
                      <td className="px-4 py-3">
                        <CopyUuid id={u.id} />
                      </td>
                      <td className="px-4 py-3">
                        {!isMe && (
                          <button
                            onClick={() => handleDeleteUser(u.id, u.email)}
                            disabled={deleteMutation.isPending}
                            className="rounded bg-red-500/10 px-2 py-1 text-xs text-red-400 hover:bg-red-500/20 transition-colors disabled:opacity-40"
                          >
                            Delete
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {toggleMutation.isError && (
            <p className="mt-3 text-xs text-red-400">{getApiError(toggleMutation.error, "Update failed.")}</p>
          )}
          {deleteMutation.isError && (
            <p className="mt-3 text-xs text-red-400">{getApiError(deleteMutation.error, "Delete failed.")}</p>
          )}

          <Pagination page={data.page} total={data.total} pageSize={data.page_size} onChange={setPage} />
        </>
      )}
    </div>
  );
}
