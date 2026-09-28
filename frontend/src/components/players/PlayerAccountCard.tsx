import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import api from "../../lib/api";
import { formatDate, getApiError } from "../../lib/utils";
import { useClubCapabilities } from "../../hooks/useClubCapabilities";
import Button from "../ui/Button";
import Card from "../ui/Card";

interface PlayerInvitation {
  id: string;
  player_id: string;
  email: string;
  created_at: string;
  expires_at: string;
  accepted_at: string | null;
  revoked_at: string | null;
  accept_url: string | null;
}

interface PlayerAccountStatus {
  has_account: boolean;
  invitation: PlayerInvitation | null;
}

/**
 * Whether one of the club's players has a TransferX account, and the way to
 * invite him (product decision, 2026-09-28: players join only by invitation
 * from their club). With an account he accepts his own personal terms; his
 * mandated agent can still answer for him.
 */
export default function PlayerAccountCard({ playerId, playerName }: { playerId: string; playerName: string }) {
  const queryClient = useQueryClient();
  const { can } = useClubCapabilities();
  const canInvite = can("TEAM_MANAGE");
  const [email, setEmail] = useState("");
  const [link, setLink] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const key = ["clubs", "me", "players", playerId, "account"];
  const { data } = useQuery<PlayerAccountStatus>({
    queryKey: key,
    queryFn: () => api.get<PlayerAccountStatus>(`/clubs/me/players/${playerId}/account`).then((r) => r.data),
  });

  const invite = useMutation({
    mutationFn: () =>
      api.post<PlayerInvitation>("/clubs/me/player-invitations", { player_id: playerId, email }).then((r) => r.data),
    onSuccess: (inv) => {
      setLink(inv.accept_url);
      setEmail("");
      queryClient.invalidateQueries({ queryKey: key });
    },
  });

  const revoke = useMutation({
    mutationFn: (id: string) => api.post(`/clubs/me/player-invitations/${id}/revoke`).then((r) => r.data),
    onSuccess: () => {
      setLink(null);
      queryClient.invalidateQueries({ queryKey: key });
    },
  });

  if (!data) return null;
  const inv = data.invitation;
  const pending = inv && !inv.accepted_at && !inv.revoked_at && new Date(inv.expires_at) > new Date();

  return (
    <Card>
      <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-text-muted">Player account</p>
      {data.has_account ? (
        <p className="text-sm text-text">
          {playerName} has a TransferX account and accepts his own personal terms.
        </p>
      ) : pending ? (
        <div className="space-y-2 text-sm">
          <p className="text-text">
            Invited <span className="font-medium">{inv!.email}</span> — expires {formatDate(inv!.expires_at)}.
          </p>
          {link && (
            <div className="rounded-lg bg-accent-bg px-3 py-2 ring-1 ring-accent/20">
              <p className="text-xs text-text-secondary">
                Shown once — also emailed to him. Share it only with the player.
              </p>
              <div className="mt-1.5 flex items-center gap-2">
                <input readOnly value={link} className="min-w-0 flex-1 rounded bg-surface px-2 py-1 text-xs text-text ring-1 ring-border" />
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => {
                    void navigator.clipboard?.writeText(link);
                    setCopied(true);
                  }}
                >
                  {copied ? "Copied" : "Copy"}
                </Button>
              </div>
            </div>
          )}
          {canInvite && (
            <Button size="sm" variant="ghost" loading={revoke.isPending} onClick={() => revoke.mutate(inv!.id)}>
              Revoke invitation
            </Button>
          )}
        </div>
      ) : (
        <div className="space-y-2">
          <p className="text-sm text-text-muted">
            {playerName} has no account yet, so your club records his answer to personal terms (with the signed
            copy), or his agent answers for him. Invite him to answer himself.
          </p>
          {canInvite && (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                invite.mutate();
              }}
              className="flex gap-2"
            >
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="player@email.com"
                className="min-w-0 flex-1 rounded-lg bg-surface px-3 py-1.5 text-sm text-text ring-1 ring-input-border focus:outline-none focus:ring-accent"
              />
              <Button type="submit" size="sm" variant="secondary" loading={invite.isPending}>
                Invite
              </Button>
            </form>
          )}
          {invite.isError && <p className="text-xs text-danger-text">{getApiError(invite.error, "Could not send the invitation.")}</p>}
        </div>
      )}
    </Card>
  );
}
