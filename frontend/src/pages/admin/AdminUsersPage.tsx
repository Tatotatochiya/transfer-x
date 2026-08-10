import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "../../lib/api";
import type { AdminUser, Paginated } from "../../types/api";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import DateRangeFilter, { EMPTY_DATE_RANGE, type DateRange } from "../../components/ui/DateRangeFilter";
import Input from "../../components/ui/Input";
import Pagination from "../../components/ui/Pagination";
import ResponsiveTable, { type ResponsiveColumn } from "../../components/ui/ResponsiveTable";
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
        value ? "bg-accent" : "bg-input-border"
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
      className={`font-mono text-xs transition-colors ${copied ? "text-success-text" : "text-text-muted"}`}
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
        className="text-xs text-text-muted hover:text-warning-text transition-colors"
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
        className="w-28 rounded bg-surface px-2 py-1 text-xs text-text ring-1 ring-input-border focus:outline-none focus:ring-warning-fill"
      />
      <button
        type="submit"
        disabled={mutation.isPending || !pw}
        className="text-xs text-accent hover:text-accent-hover disabled:opacity-40"
      >
        Set
      </button>
      <button
        type="button"
        onClick={() => { setOpen(false); setPw(""); }}
        className="text-xs text-text-muted hover:text-text"
      >
        ✕
      </button>
      {mutation.isError && (
        <span className="text-xs text-danger-text">{getApiError(mutation.error, "Failed")}</span>
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
      <Input
        label="Email"
        type="email"
        required
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        placeholder="user@example.com"
        wrapperClassName="w-56"
      />
      <Input
        label="Password"
        type="password"
        required
        value={pw}
        onChange={(e) => setPw(e.target.value)}
        wrapperClassName="w-40"
      />
      <Button type="submit" variant="primary" size="sm" loading={mutation.isPending}>
        Create user
      </Button>
      {mutation.isError && (
        <p className="w-full text-xs text-danger-text">{getApiError(mutation.error, "Create failed.")}</p>
      )}
      {mutation.isSuccess && (
        <p className="w-full text-xs text-success-text">User created.</p>
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
  const [dateRange, setDateRange] = useState<DateRange>(EMPTY_DATE_RANGE);
  const [page,   setPage]   = useState(1);
  const [showCreate, setShowCreate] = useState(false);

  const { data, isLoading } = useQuery<Paginated<AdminUser>>({
    queryKey: ["admin", "users", { search, ...dateRange, page }],
    queryFn: () =>
      api
        .get<Paginated<AdminUser>>("/admin/users", {
          params: {
            page, page_size: 30,
            ...(search && { search }),
            ...(dateRange.dateFrom && { date_from: dateRange.dateFrom }),
            ...(dateRange.dateTo && { date_to: dateRange.dateTo }),
          },
        })
        .then((r) => r.data),
  });

  function handleDateRangeChange(range: DateRange) {
    setDateRange(range);
    setPage(1);
  }

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

  const columns: ResponsiveColumn<AdminUser>[] = [
    {
      key: "email", header: "Email", priority: 1,
      render: (u) => (
        <span className="font-medium text-text">
          {u.email}
          {u.id === me?.id && <Badge variant="warning" className="ml-2">You</Badge>}
        </span>
      ),
    },
    {
      key: "active", header: "Active", priority: 2, className: "text-center",
      render: (u) => (
        <ToggleSwitch
          value={u.is_active}
          disabled={u.id === me?.id || toggleMutation.isPending}
          onChange={(next) => toggleMutation.mutate({ userId: u.id, patch: { is_active: next } })}
        />
      ),
    },
    {
      key: "superuser", header: "Superuser", priority: 3, className: "text-center",
      render: (u) => (
        <ToggleSwitch
          value={u.is_superuser}
          disabled={u.id === me?.id || toggleMutation.isPending}
          onChange={(next) => toggleMutation.mutate({ userId: u.id, patch: { is_superuser: next } })}
        />
      ),
    },
    {
      key: "joined", header: "Joined", priority: 4,
      render: (u) => <span className="text-text-muted text-xs">{formatDate(u.created_at)}</span>,
    },
    {
      key: "password", header: "Password",
      render: (u) => (u.id === me?.id ? null : <ResetPasswordRow userId={u.id} />),
    },
    {
      key: "uuid", header: "",
      render: (u) => <CopyUuid id={u.id} />,
    },
    {
      key: "delete", header: "",
      render: (u) =>
        u.id === me?.id ? null : (
          <button
            onClick={() => handleDeleteUser(u.id, u.email)}
            disabled={deleteMutation.isPending}
            className="rounded bg-danger-bg px-2 py-1 text-xs text-danger-text hover:bg-danger-bg-badge transition-colors disabled:opacity-40"
          >
            Delete
          </button>
        ),
    },
  ];

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-text">Users</h1>
          <p className="mt-1 text-sm text-text-muted">{data ? `${data.total} total` : ""}</p>
        </div>
        <div className="flex items-center gap-3">
          <Input
            type="text"
            placeholder="Search email…"
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            wrapperClassName="w-56"
          />
          <Button variant="primary" size="sm" onClick={() => setShowCreate((v) => !v)}>
            {showCreate ? "Hide" : "Create user"}
          </Button>
        </div>
      </div>

      <div className="mb-6">
        <DateRangeFilter value={dateRange} onChange={handleDateRangeChange} accent="amber" />
      </div>

      {showCreate && (
        <div className="mb-6 rounded-xl bg-surface ring-1 ring-border px-5 py-4">
          <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-text-muted">New user account</p>
          <CreateUserPanel onCreated={() => {
            queryClient.invalidateQueries({ queryKey: ["admin", "users"] });
          }} />
        </div>
      )}

      {isLoading && <div className="flex justify-center py-12"><Spinner size="lg" /></div>}

      {data && (
        <>
          <ResponsiveTable
            columns={columns}
            rows={data.items}
            rowKey={(u) => u.id}
            emptyTitle="No users found"
            renderCard={(u) => (
              <div className="px-4 py-3 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-semibold text-text">
                    {u.email}
                    {u.id === me?.id && <Badge variant="warning" className="ml-2">You</Badge>}
                  </span>
                  <span className="text-xs text-text-muted">{formatDate(u.created_at)}</span>
                </div>
                <div className="flex items-center gap-4 text-xs text-text-muted">
                  <label className="flex items-center gap-1.5">
                    Active
                    <ToggleSwitch
                      value={u.is_active}
                      disabled={u.id === me?.id || toggleMutation.isPending}
                      onChange={(next) => toggleMutation.mutate({ userId: u.id, patch: { is_active: next } })}
                    />
                  </label>
                  <label className="flex items-center gap-1.5">
                    Superuser
                    <ToggleSwitch
                      value={u.is_superuser}
                      disabled={u.id === me?.id || toggleMutation.isPending}
                      onChange={(next) => toggleMutation.mutate({ userId: u.id, patch: { is_superuser: next } })}
                    />
                  </label>
                </div>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    {u.id !== me?.id && <ResetPasswordRow userId={u.id} />}
                    <CopyUuid id={u.id} />
                  </div>
                  {u.id !== me?.id && (
                    <button
                      onClick={() => handleDeleteUser(u.id, u.email)}
                      disabled={deleteMutation.isPending}
                      className="rounded bg-danger-bg px-2 py-1 text-xs text-danger-text disabled:opacity-40"
                    >
                      Delete
                    </button>
                  )}
                </div>
              </div>
            )}
          />

          {toggleMutation.isError && (
            <p className="mt-3 text-xs text-danger-text">{getApiError(toggleMutation.error, "Update failed.")}</p>
          )}
          {deleteMutation.isError && (
            <p className="mt-3 text-xs text-danger-text">{getApiError(deleteMutation.error, "Delete failed.")}</p>
          )}

          <Pagination page={data.page} total={data.total} pageSize={data.page_size} onChange={setPage} />
        </>
      )}
    </div>
  );
}
