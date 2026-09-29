import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import api from "../../lib/api";
import { formatDate, getApiError } from "../../lib/utils";
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

/** Who is inviting, and so which endpoints: the owning club, the player's
 *  agent (free agents only), or TransferX staff (free agents only). */
export type Inviter = "club" | "agent" | "staff";

const ENDPOINTS: Record<Inviter, { status: (id: string) => string; invite: string; revoke: (id: string) => string }> = {
  club: {
    status: (id) => `/clubs/me/players/${id}/account`,
    invite: "/clubs/me/player-invitations",
    revoke: (id) => `/clubs/me/player-invitations/${id}/revoke`,
  },
  agent: {
    status: (id) => `/agents/me/players/${id}/account`,
    invite: "/agents/me/player-invitations",
    revoke: (id) => `/agents/me/player-invitations/${id}/revoke`,
  },
  staff: {
    status: (id) => `/admin/players/${id}/account`,
    invite: "/admin/player-invitations",
    revoke: (id) => `/admin/player-invitations/${id}/revoke`,
  },
};

const NO_ACCOUNT_TEXT: Record<Inviter, (name: string) => string> = {
  club: (name) =>
    `${name} has no account yet, so your club records his answer to personal terms (with the signed copy), or his agent answers for him. Invite him to answer himself.`,
  agent: (name) =>
    `${name} is a free agent with no account yet. Invite him so he can accept terms himself; you can still answer for him.`,
  staff: (name) =>
    `${name} has no account yet. TransferX can invite a free agent (so can his agent); a player at a club is invited by his club.`,
};

/**
 * Whether a player has a TransferX account, and the way to invite him
 * (product ADR 0007: players join only by invitation — from their club, or
 * for a free agent from his agent or TransferX). With an account he accepts
 * his own personal terms; his mandated agent can still answer for him.
 */
export default function PlayerAccountCard({
  playerId,
  playerName,
  inviter = "club",
  canInvite = true,
}: {
  playerId: string;
  playerName: string;
  inviter?: Inviter;
  /** Clubs: members with TEAM_MANAGE. */
  canInvite?: boolean;
}) {
  const queryClient = useQueryClient();
  const urls = ENDPOINTS[inviter];
  const [email, setEmail] = useState("");
  const [link, setLink] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const key = ["player-account", inviter, playerId];
  const { data } = useQuery<PlayerAccountStatus>({
    queryKey: key,
    queryFn: () => api.get<PlayerAccountStatus>(urls.status(playerId)).then((r) => r.data),
  });

  const invite = useMutation({
    mutationFn: () =>
      api.post<PlayerInvitation>(urls.invite, { player_id: playerId, email }).then((r) => r.data),
    onSuccess: (inv) => {
      setLink(inv.accept_url);
      setEmail("");
      queryClient.invalidateQueries({ queryKey: key });
    },
  });

  const revoke = useMutation({
    mutationFn: (id: string) => api.post(urls.revoke(id)).then((r) => r.data),
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
          <p className="text-sm text-text-muted">{NO_ACCOUNT_TEXT[inviter](playerName)}</p>
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
