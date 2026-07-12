import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "../../lib/api";
import type { StaffInviteResponse, TeamResponse } from "../../types/api";
import type { StaffRole } from "../../types/enums";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import EmptyState from "../../components/ui/EmptyState";
import PageHeader from "../../components/ui/PageHeader";
import Spinner from "../../components/ui/Spinner";
import { useConfirm } from "../../context/ConfirmContext";
import { useToast } from "../../context/ToastContext";
import { useClubCapabilities } from "../../hooks/useClubCapabilities";
import { STAFF_ROLE_INFO as ROLE_INFO, STAFF_ROLE_ORDER as ROLE_ORDER } from "../../lib/badges";
import { getApiError, formatDateTime } from "../../lib/utils";

export default function TeamPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const confirm = useConfirm();
  const { addToast } = useToast();
  const { can, isLoading: capsLoading } = useClubCapabilities();

  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState<StaffRole>("SCOUT");
  const [inviteError, setInviteError] = useState<string | null>(null);
  // The accept URL exists client-side only, right after creation — the raw
  // token is never stored server-side, so it can't be shown again later (D6).
  const [lastInvite, setLastInvite] = useState<{ email: string; url: string } | null>(null);

  const { data: team, isLoading } = useQuery<TeamResponse>({
    queryKey: ["clubs", "me", "staff"],
    queryFn: () => api.get<TeamResponse>("/clubs/me/staff").then((r) => r.data),
    enabled: can("TEAM_MANAGE"),
  });

  const inviteMutation = useMutation({
    mutationFn: (body: { email: string; role: StaffRole }) =>
      api.post<StaffInviteResponse>("/clubs/me/staff/invitations", body).then((r) => r.data),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["clubs", "me", "staff"] });
      setLastInvite({ email: data.invitation.email, url: data.accept_url });
      setInviteEmail("");
      setInviteError(null);
    },
    onError: (err: unknown) => setInviteError(getApiError(err, "Failed to send invitation.")),
  });

  const revokeMutation = useMutation({
    mutationFn: (invitationId: string) => api.delete(`/clubs/me/staff/invitations/${invitationId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["clubs", "me", "staff"] });
      addToast("Invitation revoked", "info");
    },
    onError: (err: unknown) => addToast(getApiError(err, "Failed to revoke invitation."), "error"),
  });

  const roleMutation = useMutation({
    mutationFn: ({ staffId, role }: { staffId: string; role: StaffRole }) =>
      api.patch(`/clubs/me/staff/${staffId}`, { role }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["clubs", "me", "staff"] });
      addToast("Role updated", "success");
    },
    onError: (err: unknown) => addToast(getApiError(err, "Failed to change role."), "error"),
  });

  const removeMutation = useMutation({
    mutationFn: (staffId: string) => api.delete(`/clubs/me/staff/${staffId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["clubs", "me", "staff"] });
      addToast("Team member removed — their account is deactivated", "info");
    },
    onError: (err: unknown) => addToast(getApiError(err, "Failed to remove member."), "error"),
  });

  async function handleRemove(staffId: string, email: string) {
    const ok = await confirm({
      title: "Remove team member?",
      message: `${email} will lose access immediately and their account will be deactivated. This cannot be undone from here.`,
      confirmLabel: "Remove",
      variant: "danger",
    });
    if (ok) removeMutation.mutate(staffId);
  }

  function handleInvite(e: React.FormEvent) {
    e.preventDefault();
    if (!inviteEmail.trim()) return;
    inviteMutation.mutate({ email: inviteEmail.trim(), role: inviteRole });
  }

  async function copyAcceptUrl(url: string) {
    try {
      await navigator.clipboard.writeText(url);
      addToast("Invitation link copied", "success");
    } catch {
      addToast("Could not copy — select and copy the link manually", "warning");
    }
  }

  if (capsLoading || isLoading) {
    return <div className="flex items-center justify-center py-20"><Spinner size="lg" /></div>;
  }

  if (!can("TEAM_MANAGE")) {
    return (
      <EmptyState
        title="Owner only"
        body="Only the club owner can manage the team."
        action={<Button variant="secondary" onClick={() => navigate("/club")}>Back to My Club</Button>}
      />
    );
  }

  const staff = team?.staff ?? [];
  const invitations = team?.invitations ?? [];

  return (
    <div>
      <button
        onClick={() => navigate("/club")}
        className="mb-6 flex items-center gap-1.5 text-sm text-slate-400 hover:text-white transition-colors"
      >
        ← Back to My Club
      </button>

      <PageHeader
        title="Team"
        subtitle="Invite staff, set their roles, and manage who can act for your club"
      />

      <div className="grid gap-6 lg:grid-cols-[1fr_340px]">
        <div className="space-y-6">
          {/* ── Active staff ── */}
          <div className="rounded-xl bg-slate-900 ring-1 ring-white/[0.08] overflow-hidden">
            <div className="border-b border-white/[0.06] px-5 py-3">
              <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                Staff ({staff.length})
              </p>
            </div>
            {staff.length === 0 ? (
              <p className="px-5 py-6 text-sm text-slate-500">
                No staff yet — invite your sporting director, managers, scouts, or read-only
                board members from the panel on the right.
              </p>
            ) : (
              <div className="divide-y divide-white/[0.04]">
                {staff.map((member) => (
                  <div key={member.id} className="flex flex-wrap items-center gap-3 px-5 py-3.5">
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-white">{member.email}</p>
                      <p className="mt-0.5 text-xs text-slate-500">
                        Joined {formatDateTime(member.created_at)}
                      </p>
                    </div>
                    <Badge variant={ROLE_INFO[member.role].badge}>
                      {ROLE_INFO[member.role].label}
                    </Badge>
                    <select
                      value={member.role}
                      onChange={(e) =>
                        roleMutation.mutate({ staffId: member.id, role: e.target.value as StaffRole })
                      }
                      disabled={roleMutation.isPending}
                      className="rounded-lg bg-slate-800 px-2 py-1.5 text-xs text-white ring-1 ring-white/10 focus:outline-none focus:ring-emerald-500"
                    >
                      {ROLE_ORDER.map((r) => (
                        <option key={r} value={r}>{ROLE_INFO[r].label}</option>
                      ))}
                    </select>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleRemove(member.id, member.email)}
                      loading={removeMutation.isPending}
                    >
                      <span className="text-red-400">Remove</span>
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* ── Pending invitations ── */}
          <div className="rounded-xl bg-slate-900 ring-1 ring-white/[0.08] overflow-hidden">
            <div className="border-b border-white/[0.06] px-5 py-3">
              <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                Pending invitations ({invitations.length})
              </p>
            </div>
            {invitations.length === 0 ? (
              <p className="px-5 py-6 text-sm text-slate-500">No pending invitations.</p>
            ) : (
              <div className="divide-y divide-white/[0.04]">
                {invitations.map((inv) => (
                  <div key={inv.id} className="flex flex-wrap items-center gap-3 px-5 py-3.5">
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-white">{inv.email}</p>
                      <p className="mt-0.5 text-xs text-slate-500">
                        Expires {formatDateTime(inv.expires_at)}
                      </p>
                    </div>
                    <Badge variant={ROLE_INFO[inv.role].badge}>{ROLE_INFO[inv.role].label}</Badge>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => revokeMutation.mutate(inv.id)}
                      loading={revokeMutation.isPending}
                    >
                      <span className="text-red-400">Revoke</span>
                    </Button>
                  </div>
                ))}
              </div>
            )}
            {invitations.length > 0 && (
              <p className="border-t border-white/[0.06] px-5 py-2.5 text-[11px] text-slate-600">
                For security, an invitation link is shown only once, when it's created. If a
                link is lost, revoke the invitation and send a new one.
              </p>
            )}
          </div>
        </div>

        {/* ── Invite panel ── */}
        <div className="space-y-4 h-fit lg:sticky lg:top-6">
          <div className="rounded-xl bg-slate-900 ring-1 ring-white/[0.08] px-5 py-5">
            <p className="mb-4 text-sm font-semibold text-white">Invite a team member</p>
            <form onSubmit={handleInvite} className="space-y-4">
              <div>
                <label className="mb-1.5 block text-xs font-medium text-slate-400">Email</label>
                <input
                  type="email"
                  required
                  value={inviteEmail}
                  onChange={(e) => setInviteEmail(e.target.value)}
                  placeholder="scout@yourclub.com"
                  className="w-full rounded-lg bg-slate-950 px-3 py-2 text-sm text-white placeholder-slate-600 ring-1 ring-white/10 focus:outline-none focus:ring-emerald-500 transition-colors"
                />
              </div>
              <div>
                <label className="mb-1.5 block text-xs font-medium text-slate-400">Role</label>
                <select
                  value={inviteRole}
                  onChange={(e) => setInviteRole(e.target.value as StaffRole)}
                  className="w-full rounded-lg bg-slate-950 px-3 py-2 text-sm text-white ring-1 ring-white/10 focus:outline-none focus:ring-emerald-500"
                >
                  {ROLE_ORDER.map((r) => (
                    <option key={r} value={r}>{ROLE_INFO[r].label}</option>
                  ))}
                </select>
                <p className="mt-2 text-xs leading-relaxed text-slate-500">
                  {ROLE_INFO[inviteRole].description}
                </p>
              </div>
              {inviteError && <p className="text-sm text-red-400">{inviteError}</p>}
              <Button type="submit" variant="primary" size="sm" loading={inviteMutation.isPending}>
                Send invitation
              </Button>
            </form>
          </div>

          {lastInvite && (
            <div className="rounded-xl bg-emerald-500/10 ring-1 ring-emerald-500/30 px-5 py-4">
              <p className="text-sm font-semibold text-emerald-300">
                Invitation created for {lastInvite.email}
              </p>
              <p className="mt-1 text-xs text-emerald-200/70">
                An email has been sent if email delivery is configured. This link is shown
                once — copy it now if you want to share it yourself.
              </p>
              <div className="mt-3 flex items-center gap-2">
                <code className="min-w-0 flex-1 truncate rounded bg-slate-950/60 px-2 py-1.5 text-[11px] text-slate-300">
                  {lastInvite.url}
                </code>
                <Button variant="secondary" size="sm" onClick={() => copyAcceptUrl(lastInvite.url)}>
                  Copy
                </Button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
