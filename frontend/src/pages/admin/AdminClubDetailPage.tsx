import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "../../lib/api";
import type { AdminClubDetail, AdminClubFinance, ClubStaff } from "../../types/api";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import Metric from "../../components/ui/Metric";
import Spinner from "../../components/ui/Spinner";
import { formatCurrency, formatDate, getApiError } from "../../lib/utils";
import { useAskReason, useConfirm } from "../../context/ConfirmContext";

const ROLES = ["BUYER", "SELLER", "BOTH", "ADMIN"];

export default function AdminClubDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const { data: club, isLoading } = useQuery<AdminClubDetail>({
    queryKey: ["admin", "clubs", id],
    queryFn: () => api.get<AdminClubDetail>(`/admin/clubs/${id}`).then((r) => r.data),
    enabled: !!id,
  });

  // Profile edit state
  const [editProfile, setEditProfile] = useState(false);
  const [pName,   setPName]   = useState("");
  const [pRole,   setPRole]   = useState("");
  const [pCountry, setPCountry] = useState("");

  function openProfileEdit() {
    if (!club) return;
    setPName(club.name);
    setPRole(club.role);
    setPCountry(club.country ?? "");
    setEditProfile(true);
  }

  const profileMutation = useMutation({
    mutationFn: (body: object) =>
      api.patch<AdminClubDetail>(`/admin/clubs/${id}`, body).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "clubs", id] });
      queryClient.invalidateQueries({ queryKey: ["admin", "clubs"] });
      setEditProfile(false);
    },
  });

  // Finance edit state
  const [editFinance, setEditFinance] = useState(false);
  const [fTransfer, setFTransfer] = useState("");
  const [fWage,     setFWage]     = useState("");

  function openFinanceEdit() {
    if (!club?.finance) return;
    setFTransfer(String(club.finance.transfer_budget_total));
    setFWage(String(club.finance.wage_budget_total_weekly));
    setEditFinance(true);
  }

  const financeMutation = useMutation({
    mutationFn: (body: object) =>
      api.put<AdminClubFinance>(`/admin/clubs/${id}/finances`, body).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "clubs", id] });
      setEditFinance(false);
    },
  });

  const askReason = useAskReason();
  const deleteMutation = useMutation({
    mutationFn: (reason: string) => api.delete(`/admin/clubs/${id}`, { data: { reason } }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "clubs"] });
      navigate("/admin/clubs");
    },
  });

  // "View as this club": the app as the club's owner sees it, read-only, for
  // 30 minutes, in a new tab. Needs a reason; recorded in the audit log.
  const [viewAsLink, setViewAsLink] = useState<string | null>(null);
  const viewAsMutation = useMutation({
    mutationFn: (reason: string) =>
      api.post<{ access_token: string }>(`/admin/clubs/${id}/view-as`, { reason }).then((r) => r.data),
    onSuccess: ({ access_token }) => {
      // In the fragment, so the token never reaches a server log.
      const url = `/view-as#view_as=${access_token}`;
      // Not "noopener": with it, window.open returns null even when the tab
      // opens, so a blocked tab couldn't be told apart. The opener is cut here.
      const tab = window.open(url, "_blank");
      if (tab) tab.opener = null;
      setViewAsLink(tab ? null : url);
    },
  });
  async function viewAs() {
    const reason = await askReason({
      title: `View TransferX as ${club?.name ?? "this club"}`,
      message: "Opens a new tab showing exactly what the club's owner sees, for 30 minutes. Nothing can be changed there.",
      reasonLabel: "Why do you need to see it?",
      placeholder: "e.g. Club reports it can't see an offer",
      confirmLabel: "Open their view",
    });
    if (reason) viewAsMutation.mutate(reason);
  }

  async function handleDelete() {
    const reason = await askReason({
      title: "Delete club",
      message: `Permanently delete "${club?.name}"? This cannot be undone. The club must have no active sales, deals, or contracted players.`,
      reasonLabel: "Why are you deleting this club?",
      confirmLabel: "Delete",
      danger: true,
    });
    if (reason) deleteMutation.mutate(reason);
  }

  if (isLoading) {
    return <div className="flex justify-center py-12"><Spinner size="lg" /></div>;
  }

  if (!club) {
    return (
      <div className="rounded-xl bg-danger-bg px-5 py-4 text-sm text-danger-text ring-1 ring-danger-border">
        Club not found.{" "}
        <button onClick={() => navigate("/admin/clubs")} className="underline">Back</button>
      </div>
    );
  }

  return (
    <div>
      <button
        onClick={() => navigate("/admin/clubs")}
        className="mb-6 flex items-center gap-1.5 text-sm text-text-muted hover:text-text transition-colors"
      >
        ← Back to clubs
      </button>

      <div className="mb-6 flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-surface-inset text-xl font-bold text-text-muted overflow-hidden">
            {club.crest_url ? (
              <img src={club.crest_url} alt={club.name} className="h-full w-full object-contain p-1" />
            ) : (
              club.name[0]?.toUpperCase()
            )}
          </div>
          <div>
            <h1 className="text-2xl font-bold text-text">{club.name}</h1>
            <p className="text-xs text-text-muted">ID: {club.id}</p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
        <Button variant="secondary" size="sm" onClick={viewAs} loading={viewAsMutation.isPending}>
          View as this club
        </Button>
        <button
          onClick={handleDelete}
          disabled={deleteMutation.isPending}
          className="rounded-lg bg-danger/10 px-3 py-1.5 text-xs font-medium text-danger-text ring-1 ring-danger/20 hover:bg-danger/20 transition-colors disabled:opacity-40"
        >
          Delete club
        </button>
        </div>
      </div>
      {viewAsMutation.isError && (
        <div className="mb-4 rounded-lg bg-danger/10 px-4 py-2 text-xs text-danger-text ring-1 ring-danger/20">
          {getApiError(viewAsMutation.error, "Couldn't open the club's view.")}
        </div>
      )}
      {viewAsLink && (
        <div className="mb-4 rounded-lg bg-surface-inset px-4 py-2 text-sm text-text-secondary ring-1 ring-border">
          Your browser blocked the new tab. <a href={viewAsLink} target="_blank" rel="noopener" className="font-semibold text-accent">Open the club's view</a>
        </div>
      )}
      {deleteMutation.isError && (
        <div className="mb-4 rounded-lg bg-danger/10 px-4 py-2 text-xs text-danger-text ring-1 ring-danger/20">
          {getApiError(deleteMutation.error, "Delete failed.")}
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2 mb-6">
        {/* ── Profile ── */}
        <Card>
          <div className="mb-4 flex items-center justify-between">
            <p className="text-xs font-semibold uppercase tracking-wider text-text-muted">Club Profile</p>
            {!editProfile && (
              <Button variant="secondary" size="sm" onClick={openProfileEdit}>Edit</Button>
            )}
          </div>

          {!editProfile ? (
            <div className="space-y-2">
              <Metric label="Name"    value={club.name} />
              <Metric label="Role"    value={<Badge variant="neutral">{club.role}</Badge>} />
              <Metric label="Country" value={club.country ?? "—"} />
              <Metric label="City"    value={club.city ?? "—"} />
              <Metric label="League"  value={club.league_name ?? "—"} />
              <Metric label="User ID" value={<span className="text-xs text-text-muted">{club.user_id}</span>} />
              <Metric label="Created" value={formatDate(club.created_at)} />
            </div>
          ) : (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                profileMutation.mutate({ name: pName || undefined, role: pRole || undefined, country: pCountry || undefined });
              }}
              className="space-y-3"
            >
              <div>
                <label className="mb-1 block text-xs text-text-muted">Name</label>
                <input
                  value={pName}
                  onChange={(e) => setPName(e.target.value)}
                  className="w-full rounded-lg bg-surface px-3 py-2 text-sm text-text ring-1 ring-input-border focus:outline-none focus:ring-warning-fill"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs text-text-muted">Role</label>
                <select
                  value={pRole}
                  onChange={(e) => setPRole(e.target.value)}
                  className="w-full rounded-lg bg-surface px-3 py-2 text-sm text-text ring-1 ring-input-border focus:outline-none focus:ring-warning-fill"
                >
                  {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
                </select>
              </div>
              <div>
                <label className="mb-1 block text-xs text-text-muted">Country</label>
                <input
                  value={pCountry}
                  onChange={(e) => setPCountry(e.target.value)}
                  className="w-full rounded-lg bg-surface px-3 py-2 text-sm text-text ring-1 ring-input-border focus:outline-none focus:ring-warning-fill"
                />
              </div>
              {profileMutation.isError && (
                <p className="text-xs text-danger-text">{getApiError(profileMutation.error, "Save failed.")}</p>
              )}
              <div className="flex gap-2">
                <Button type="submit" variant="primary" size="sm" loading={profileMutation.isPending}>Save</Button>
                <Button type="button" variant="ghost" size="sm" onClick={() => setEditProfile(false)}>Cancel</Button>
              </div>
            </form>
          )}
        </Card>

        {/* ── Finance ── */}
        <Card>
          <div className="mb-4 flex items-center justify-between">
            <p className="text-xs font-semibold uppercase tracking-wider text-text-muted">Finances</p>
            {!editFinance && club.finance && (
              <Button variant="secondary" size="sm" onClick={openFinanceEdit}>Edit budgets</Button>
            )}
          </div>

          {!club.finance ? (
            <p className="text-sm text-text-muted">No finance record.</p>
          ) : !editFinance ? (
            <div className="space-y-2">
              <Metric label="Transfer budget"   value={formatCurrency(club.finance.transfer_budget_total)} />
              <Metric label="Transfer reserved" value={formatCurrency(club.finance.transfer_reserved)} />
              <Metric label="Transfer committed" value={formatCurrency(club.finance.transfer_committed)} />
              <Metric label="Transfer remaining" value={<span className="text-success-text">{formatCurrency(club.finance.transfer_remaining)}</span>} />
              <div className="border-t border-rule pt-2">
                <Metric label="Wage budget / wk"   value={formatCurrency(club.finance.wage_budget_total_weekly)} />
                <Metric label="Wage reserved / wk" value={formatCurrency(club.finance.wage_reserved_weekly)} />
                <Metric label="Wage remaining / wk" value={<span className="text-success-text">{formatCurrency(club.finance.wage_remaining_weekly)}</span>} />
              </div>
            </div>
          ) : (
            <form
              onSubmit={async (e) => {
                e.preventDefault();
                // Budgets change what a club can bid; the reason goes in the audit log.
                const reason = await askReason({
                  title: `Change ${club?.name ?? "the club"}'s budgets`,
                  message: "A budget can't go below what is already held, committed or spent against it.",
                  reasonLabel: "Why are the budgets changing?",
                  placeholder: "e.g. Owner approved the January budget",
                  confirmLabel: "Save budgets",
                });
                if (!reason) return;
                financeMutation.mutate({
                  transfer_budget_total: parseFloat(fTransfer),
                  wage_budget_total_weekly: parseFloat(fWage),
                  reason,
                });
              }}
              className="space-y-3"
            >
              <div>
                <label className="mb-1 block text-xs text-text-muted">Transfer budget total (£)</label>
                <input
                  type="number"
                  value={fTransfer}
                  onChange={(e) => setFTransfer(e.target.value)}
                  className="w-full rounded-lg bg-surface px-3 py-2 text-sm text-text ring-1 ring-input-border focus:outline-none focus:ring-warning-fill"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs text-text-muted">Weekly wage budget total (£)</label>
                <input
                  type="number"
                  value={fWage}
                  onChange={(e) => setFWage(e.target.value)}
                  className="w-full rounded-lg bg-surface px-3 py-2 text-sm text-text ring-1 ring-input-border focus:outline-none focus:ring-warning-fill"
                />
              </div>
              {financeMutation.isError && (
                <p className="text-xs text-danger-text">{getApiError(financeMutation.error, "Save failed.")}</p>
              )}
              <div className="flex gap-2">
                <Button type="submit" variant="primary" size="sm" loading={financeMutation.isPending}>Save</Button>
                <Button type="button" variant="ghost" size="sm" onClick={() => setEditFinance(false)}>Cancel</Button>
              </div>
            </form>
          )}
        </Card>
      </div>

      {/* ── Staff Management ── */}
      <StaffPanel clubId={club.id} />
    </div>
  );
}

// ── Staff panel ───────────────────────────────────────────────────────────────

type StaffRoleOption = "SPORTING_DIRECTOR" | "MANAGER" | "SCOUT" | "READONLY";

function StaffPanel({ clubId }: { clubId: string }) {
  const queryClient = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [email,    setEmail]    = useState("");
  const [role,     setRole]     = useState<StaffRoleOption>("READONLY");
  const [invite,   setInvite]   = useState<{ email: string; accept_url: string; emailed: boolean } | null>(null);

  const { data: staff, isLoading } = useQuery<ClubStaff[]>({
    queryKey: ["admin", "clubs", clubId, "staff"],
    queryFn: () => api.get<ClubStaff[]>(`/admin/clubs/${clubId}/staff`).then((r) => r.data),
  });

  // An invitation, as the club's own Team page sends: they choose their own
  // password from the link. Staff never set one.
  const createMutation = useMutation({
    mutationFn: (body: object) =>
      api.post<{ email: string; accept_url: string; emailed: boolean }>(`/admin/clubs/${clubId}/staff`, body).then((r) => r.data),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["admin", "clubs", clubId, "staff"] });
      setInvite(data);
      setShowForm(false);
      setEmail("");
      setRole("READONLY");
    },
  });

  const roleMutation = useMutation({
    mutationFn: ({ staffId, newRole }: { staffId: string; newRole: string }) =>
      api.patch<ClubStaff>(`/admin/clubs/${clubId}/staff/${staffId}`, { role: newRole }).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "clubs", clubId, "staff"] });
    },
  });

  const confirmRemove = useConfirm();
  const deleteMutation = useMutation({
    mutationFn: (staffId: string) =>
      api.delete(`/admin/clubs/${clubId}/staff/${staffId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "clubs", clubId, "staff"] });
    },
  });

  return (
    <Card>
      <div className="mb-4 flex items-center justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-text-muted">Staff Accounts</p>
          <p className="mt-0.5 text-xs text-text-muted">
            Invite someone by email. They choose their own password from the link; it lasts 7 days.
          </p>
        </div>
        {!showForm && (
          <Button variant="primary" size="sm" onClick={() => setShowForm(true)}>
            Invite staff
          </Button>
        )}
      </div>

      {invite && (
        <div className="mb-5 rounded-lg bg-success-bg px-4 py-3 text-sm ring-1 ring-border">
          <p className="font-semibold text-text">Invitation for {invite.email} created</p>
          <p className="mt-0.5 text-text-secondary">
            {invite.emailed ? "We've emailed it. You can also send this link yourself:" : "Email isn't set up, so send them this link:"}
          </p>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <code className="min-w-0 flex-1 break-all rounded bg-surface px-2 py-1 text-xs text-text">{invite.accept_url}</code>
            <Button variant="secondary" size="sm" onClick={() => navigator.clipboard?.writeText(invite.accept_url)}>Copy</Button>
            <Button variant="ghost" size="sm" onClick={() => setInvite(null)}>Done</Button>
          </div>
        </div>
      )}

      {/* Create form */}
      {showForm && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            createMutation.mutate({ email, role });
          }}
          className="mb-5 rounded-lg bg-surface-inset p-4 space-y-3 ring-1 ring-border"
        >
          <p className="text-xs font-semibold text-text-secondary">Invite to the staff</p>
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <label className="mb-1 block text-xs text-text-muted">Email</label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full rounded-lg bg-surface px-3 py-2 text-sm text-text ring-1 ring-input-border focus:outline-none focus:ring-warning-fill"
              />
            </div>
          </div>
          <div>
            <label className="mb-1 block text-xs text-text-muted">Role</label>
            <select
              value={role}
              onChange={(e) => setRole(e.target.value as StaffRoleOption)}
              className="rounded-lg bg-surface px-3 py-2 text-sm text-text ring-1 ring-input-border focus:outline-none focus:ring-warning-fill"
            >
              <option value="SPORTING_DIRECTOR">Sporting director — decides deals and approvals</option>
              <option value="MANAGER">Manager — can bid, offer &amp; cancel</option>
              <option value="SCOUT">Scout — shortlists and scouting</option>
              <option value="READONLY">Read-only — view only</option>
            </select>
          </div>
          {createMutation.isError && (
            <p className="text-xs text-danger-text">{getApiError(createMutation.error, "Couldn't create the invitation.")}</p>
          )}
          <div className="flex gap-2">
            <Button type="submit" variant="primary" size="sm" loading={createMutation.isPending}>
              Send invitation
            </Button>
            <Button type="button" variant="ghost" size="sm" onClick={() => setShowForm(false)}>
              Cancel
            </Button>
          </div>
        </form>
      )}

      {/* Staff list */}
      {isLoading && <div className="flex justify-center py-4"><Spinner size="sm" /></div>}

      {staff && staff.length === 0 && !showForm && (
        <p className="text-sm text-text-muted">No staff accounts yet.</p>
      )}

      {staff && staff.length > 0 && (
        <div className="overflow-x-auto rounded-lg ring-1 ring-border">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="border-b border-rule text-left text-xs font-semibold uppercase tracking-wider text-text-muted">
                <th className="px-3 py-2">Email</th>
                <th className="px-3 py-2">Role</th>
                <th className="px-3 py-2">Status</th>
                <th className="px-3 py-2" />
              </tr>
            </thead>
            <tbody className="divide-y divide-rule-faint">
              {staff.map((s) => (
                <tr key={s.id} className="bg-surface-inset">
                  <td className="px-3 py-2 text-text text-xs">{s.user?.email ?? s.user_id}</td>
                  <td className="px-3 py-2">
                    <select
                      value={s.role}
                      disabled={roleMutation.isPending}
                      onChange={(e) =>
                        roleMutation.mutate({ staffId: s.id, newRole: e.target.value })
                      }
                      className="rounded bg-surface px-2 py-1 text-xs text-text ring-1 ring-input-border focus:outline-none focus:ring-warning-fill disabled:opacity-50"
                    >
                      <option value="MANAGER">Manager</option>
                      <option value="READONLY">Read-only</option>
                    </select>
                  </td>
                  <td className="px-3 py-2">
                    <Badge variant={s.user?.is_active ? "success" : "neutral"}>
                      {s.user?.is_active ? "Active" : "Inactive"}
                    </Badge>
                  </td>
                  <td className="px-3 py-2 text-right">
                    <button
                      onClick={async () => {
                        if (await confirmRemove({
                          title: "Remove staff member",
                          message: `Remove ${s.user?.email ?? "this person"} from the club's staff? They lose access to the club straight away.`,
                          confirmLabel: "Remove", danger: true,
                        })) deleteMutation.mutate(s.id);
                      }}
                      disabled={deleteMutation.isPending}
                      className="text-xs text-danger-text hover:text-danger-text-alt transition-colors disabled:opacity-40"
                    >
                      Remove
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {deleteMutation.isError && (
            <p className="mt-2 px-3 text-xs text-danger-text">{getApiError(deleteMutation.error, "Delete failed.")}</p>
          )}
        </div>
      )}
    </Card>
  );
}
