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
import { formatDate, formatDateTime, getApiError } from "../../lib/utils";
import Modal from "../../components/ui/Modal";
import { useAuthStore } from "../../store/auth";
import { useAskReason, useConfirm } from "../../context/ConfirmContext";
import { Link } from "react-router-dom";

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

/**
 * A one-time link (24 hours) for the person to choose a new password. Staff
 * never set or see it. Emailed when email is set up; shown here to copy and
 * share by hand either way. Using it signs them out everywhere.
 */
function ResetLinkButton({ user }: { user: AdminUser }) {
  const confirm = useConfirm();
  const [link, setLink] = useState<{ url: string; expires_at: string; emailed: boolean } | null>(null);
  const [copied, setCopied] = useState(false);
  const mutation = useMutation({
    mutationFn: () =>
      api.post<{ url: string; expires_at: string; emailed: boolean }>(`/admin/users/${user.id}/reset-link`, {})
        .then((r) => r.data),
    onSuccess: (data) => setLink(data),
  });

  async function start() {
    const ok = await confirm({
      title: "Send a password reset link",
      message: `Create a one-time link for ${user.email} to choose a new password? It lasts 24 hours, and using it signs them out on every device.`,
      confirmLabel: "Create link",
    });
    if (ok) mutation.mutate();
  }

  function close() {
    setLink(null);
    setCopied(false);
  }

  return (
    <>
      <button onClick={start} disabled={mutation.isPending}
        className="text-xs text-text-muted hover:text-warning-text transition-colors disabled:opacity-40">
        Reset link
      </button>
      {mutation.isError && <span className="ml-2 text-xs text-danger-text">{getApiError(mutation.error, "Failed")}</span>}
      <Modal open={link !== null} onClose={close} size="sm">
        {link && (
          <div className="p-6">
            <h3 className="mb-2 text-base font-bold text-text">Reset link for {user.email}</h3>
            <p className="text-sm text-text-secondary">
              {link.emailed
                ? "We've emailed it to them. You can also copy it and send it another way."
                : "Email isn't set up, so send them this link yourself."}{" "}
              It works once, until {formatDateTime(link.expires_at)}.
            </p>
            <div className="mt-3 break-all rounded-lg bg-surface-inset px-3 py-2 font-mono text-xs text-text">{link.url}</div>
            <div className="mt-4 flex justify-end gap-2">
              <Button variant="secondary" size="sm" onClick={() => { navigator.clipboard?.writeText(link.url); setCopied(true); }}>
                {copied ? "Copied" : "Copy link"}
              </Button>
              <Button variant="primary" size="sm" onClick={close}>Done</Button>
            </div>
          </div>
        )}
      </Modal>
    </>
  );
}

const TYPE_LABEL: Record<string, string> = { CLUB: "Club", AGENT: "Agent", PLAYER: "Player" };

/** Who someone is on TransferX: their club and role, agency, or player. */
function WhoCell({ user: u }: { user: AdminUser }) {
  const role = u.role ? u.role.replace(/_/g, " ").toLowerCase().replace(/^\w/, (c) => c.toUpperCase()) : null;
  const detail = u.club_name ? `${u.club_name}${role ? ` · ${role}` : ""}` : u.profile_label;
  return (
    <span className="flex min-w-0 flex-wrap items-center gap-1.5 text-xs">
      {u.is_superuser && !u.club_name ? (
        <Badge variant="warning">TransferX staff</Badge>
      ) : (
        u.user_type && <Badge variant="neutral">{TYPE_LABEL[u.user_type] ?? u.user_type}</Badge>
      )}
      {detail ? (
        u.club_id ? <Link to={`/admin/clubs/${u.club_id}`} className="truncate text-text hover:underline">{detail}</Link>
          : <span className="truncate text-text">{detail}</span>
      ) : (
        !u.is_superuser && <span className="text-text-muted">No club or profile</span>
      )}
    </span>
  );
}

export default function AdminUsersPage() {
  const queryClient = useQueryClient();
  const { user: me } = useAuthStore();
  const askReason = useAskReason();
  const [search, setSearch] = useState("");
  const [dateRange, setDateRange] = useState<DateRange>(EMPTY_DATE_RANGE);
  const [page,   setPage]   = useState(1);

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
    mutationFn: ({ userId, reason }: { userId: string; reason: string }) =>
      api.delete(`/admin/users/${userId}`, { data: { reason } }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin", "users"] }),
  });

  async function handleDeleteUser(userId: string, email: string) {
    const reason = await askReason({
      title: "Delete user",
      message: `Permanently delete "${email}"? This can't be undone. Someone with deals, offers or a club can't be deleted; deactivate them instead.`,
      reasonLabel: "Why are you deleting this account?",
      confirmLabel: "Delete",
      danger: true,
    });
    if (reason) deleteMutation.mutate({ userId, reason });
  }

  // Granting or removing staff rights, and deactivating someone, need a
  // reason (recorded in the audit log). Reactivating doesn't.
  async function setFlag(u: AdminUser, field: "is_active" | "is_superuser", next: boolean) {
    if (field === "is_active" && next) {
      toggleMutation.mutate({ userId: u.id, patch: { is_active: true } });
      return;
    }
    const reason = await askReason(field === "is_superuser"
      ? {
          title: next ? "Grant TransferX staff rights" : "Remove TransferX staff rights",
          message: next
            ? `${u.email} will be able to see and change everything in the admin panel.`
            : `${u.email} will lose access to the admin panel.`,
          reasonLabel: "Why?",
          confirmLabel: next ? "Grant rights" : "Remove rights",
          danger: true,
        }
      : {
          title: "Deactivate account",
          message: `${u.email} won't be able to sign in until reactivated.`,
          reasonLabel: "Why are you deactivating them?",
          confirmLabel: "Deactivate",
          danger: true,
        });
    if (reason) toggleMutation.mutate({ userId: u.id, patch: { [field]: next, reason } });
  }

  const toggleMutation = useMutation({
    mutationFn: ({ userId, patch }: { userId: string; patch: object }) =>
      api.patch<AdminUser>(`/admin/users/${userId}`, patch).then((r) => r.data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin", "users"] }),
  });

  const columns: ResponsiveColumn<AdminUser>[] = [
    {
      key: "email", header: "Name / email", priority: 1,
      render: (u) => (
        <span className="font-medium text-text">
          {u.full_name ?? u.email}
          {u.id === me?.id && <Badge variant="warning" className="ml-2">You</Badge>}
          {u.full_name && <span className="block text-xs font-normal text-text-muted">{u.email}</span>}
        </span>
      ),
    },
    {
      key: "active", header: "Active", priority: 2, className: "text-center",
      render: (u) => (
        <ToggleSwitch
          value={u.is_active}
          disabled={u.id === me?.id || toggleMutation.isPending}
          onChange={(next) => setFlag(u, "is_active", next)}
        />
      ),
    },
    {
      key: "superuser", header: "Superuser", priority: 3, className: "text-center",
      render: (u) => (
        <ToggleSwitch
          value={u.is_superuser}
          disabled={u.id === me?.id || toggleMutation.isPending}
          onChange={(next) => setFlag(u, "is_superuser", next)}
        />
      ),
    },
    {
      key: "who", header: "Who", priority: 2,
      render: (u) => <WhoCell user={u} />,
    },
    {
      key: "active_at", header: "Last active", priority: 4,
      render: (u) => (
        <span className="text-xs text-text-muted" title={`Joined ${formatDate(u.created_at)}`}>
          {u.last_active_at ? formatDateTime(u.last_active_at) : "Never"}
        </span>
      ),
    },
    {
      key: "password", header: "Password",
      render: (u) => (u.id === me?.id ? null : <ResetLinkButton user={u} />),
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
          {/* Accounts are created by invitation, so each arrives with its
              club, role or player record: clubs from Clubs, staff by their
              club, players by their club or agent. */}
          <Link to="/admin/clubs" className="whitespace-nowrap text-sm font-semibold text-accent hover:underline">
            Invite a club →
          </Link>

        </div>
      </div>

      <div className="mb-6">
        <DateRangeFilter value={dateRange} onChange={handleDateRangeChange} accent="amber" />
      </div>


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
                    {u.full_name ?? u.email}
                    {u.id === me?.id && <Badge variant="warning" className="ml-2">You</Badge>}
                  </span>
                  <span className="text-xs text-text-muted">
                    {u.last_active_at ? `Active ${formatDateTime(u.last_active_at)}` : "Never signed in"}
                  </span>
                </div>
                <WhoCell user={u} />
                <div className="flex items-center gap-4 text-xs text-text-muted">
                  <label className="flex items-center gap-1.5">
                    Active
                    <ToggleSwitch
                      value={u.is_active}
                      disabled={u.id === me?.id || toggleMutation.isPending}
                      onChange={(next) => setFlag(u, "is_active", next)}
                    />
                  </label>
                  <label className="flex items-center gap-1.5">
                    Superuser
                    <ToggleSwitch
                      value={u.is_superuser}
                      disabled={u.id === me?.id || toggleMutation.isPending}
                      onChange={(next) => setFlag(u, "is_superuser", next)}
                    />
                  </label>
                </div>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    {u.id !== me?.id && <ResetLinkButton user={u} />}
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
