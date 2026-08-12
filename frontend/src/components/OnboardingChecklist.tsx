import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import api from "../lib/api";
import { useAuth } from "../hooks/useAuth";
import { useClubCapabilities } from "../hooks/useClubCapabilities";
import Icon from "./layout/Icon";
import type {
  AgentProfileResponse,
  Club,
  Paginated,
  PlayerDetail,
  Sale,
  TeamResponse,
  Offer,
  VerificationRequest,
} from "../types/api";

/**
 * Per-persona first-run checklist (Phase 6, D8): entirely stateless — every
 * done-state derives from data the app already fetches, or a localStorage
 * visited-flag for "go look at X" steps. Dismissal is localStorage, keyed by
 * user id. Zero new backend endpoints.
 */

interface Step {
  id: string;
  label: string;
  done: boolean;
  to: string;
  /** Steps whose completion is "you went and looked" — marked done on click. */
  visitFlag?: boolean;
}

function flagKey(userId: string, stepId: string) {
  return `onboarding-${userId}-${stepId}`;
}

function readFlag(userId: string, stepId: string): boolean {
  try {
    return localStorage.getItem(flagKey(userId, stepId)) === "1";
  } catch {
    return false;
  }
}

function ChecklistShell({
  userId,
  title,
  steps,
}: {
  userId: string;
  title: string;
  steps: Step[];
}) {
  const navigate = useNavigate();
  const dismissKey = `onboarding-dismissed-${userId}`;
  const [dismissed, setDismissed] = useState(() => {
    try {
      return localStorage.getItem(dismissKey) === "1";
    } catch {
      return false;
    }
  });
  const [, forceRender] = useState(0);

  const doneCount = steps.filter((s) => s.done).length;
  if (dismissed || steps.length === 0 || doneCount === steps.length) return null;

  function dismiss() {
    try {
      localStorage.setItem(dismissKey, "1");
    } catch {
      /* ignore */
    }
    setDismissed(true);
  }

  function open(step: Step) {
    if (step.visitFlag) {
      try {
        localStorage.setItem(flagKey(userId, step.id), "1");
      } catch {
        /* ignore */
      }
      forceRender((n) => n + 1);
    }
    navigate(step.to);
  }

  return (
    <div className="mb-6 rounded-xl bg-surface ring-1 ring-success/20 overflow-hidden">
      <div className="flex items-center justify-between border-b border-rule px-5 py-3">
        <div className="flex items-center gap-2">
          <span className="flex h-6 w-6 items-center justify-center rounded-lg bg-success/15">
            <Icon name="bolt" className="h-3.5 w-3.5 text-success-text" />
          </span>
          <p className="text-sm font-semibold text-text">{title}</p>
          <span className="text-xs text-text-muted">
            {doneCount}/{steps.length}
          </span>
        </div>
        <button
          onClick={dismiss}
          className="text-xs text-text-muted hover:text-text-secondary transition-colors"
        >
          Dismiss
        </button>
      </div>
      <div className="divide-y divide-rule-faint">
        {steps.map((step) => (
          <button
            key={step.id}
            onClick={() => open(step)}
            className="flex w-full items-center gap-3 px-5 py-2.5 text-left transition-colors hover:bg-surface-inset"
          >
            <span
              className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full ring-1 ${
                step.done
                  ? "bg-success/20 ring-success/40 text-success-text"
                  : "bg-surface-inset ring-input-border text-transparent"
              }`}
            >
              <Icon name="check" className="h-3 w-3" />
            </span>
            <span className={`text-sm ${step.done ? "text-text-muted line-through" : "text-text-secondary"}`}>
              {step.label}
            </span>
            {!step.done && <span className="ml-auto text-xs text-text-muted">→</span>}
          </button>
        ))}
      </div>
    </div>
  );
}

// ── Club (owner + staff, on the dashboard) ────────────────────────────────────

function ClubChecklist({ userId }: { userId: string }) {
  const { role } = useClubCapabilities();

  const { data: club } = useQuery<Club>({
    queryKey: ["clubs", "me"],
    queryFn: () => api.get<Club>("/clubs/me").then((r) => r.data),
    staleTime: 60_000,
  });

  const isOwner = role === "OWNER";

  const { data: team } = useQuery<TeamResponse>({
    queryKey: ["clubs", "me", "staff"],
    queryFn: () => api.get<TeamResponse>("/clubs/me/staff").then((r) => r.data),
    enabled: isOwner,
    staleTime: 60_000,
  });

  const { data: verifications } = useQuery<VerificationRequest[]>({
    queryKey: ["verification", "mine"],
    queryFn: () => api.get<VerificationRequest[]>("/verification/requests/mine").then((r) => r.data),
    enabled: isOwner,
    staleTime: 60_000,
  });

  const { data: mySales } = useQuery<Paginated<Sale>>({
    queryKey: ["sales", { sellerClubId: club?.id, forOnboarding: true }],
    queryFn: () =>
      api
        .get<Paginated<Sale>>("/sales", { params: { seller_club_id: club!.id, page_size: 1 } })
        .then((r) => r.data),
    enabled: isOwner && !!club?.id,
    staleTime: 60_000,
  });

  const { data: sentOffers } = useQuery<Paginated<Offer>>({
    queryKey: ["offers", "sent", { forOnboarding: true }],
    queryFn: () =>
      api.get<Paginated<Offer>>("/offers/sent", { params: { page_size: 1 } }).then((r) => r.data),
    enabled: isOwner,
    staleTime: 60_000,
  });

  if (!club || !role) return null;

  if (isOwner) {
    if (!team || !verifications) return null;
    const steps: Step[] = [
      {
        id: "club-profile",
        label: "Complete your club profile (crest and country)",
        done: !!club.crest_url && !!club.country,
        to: "/club",
      },
      {
        id: "club-budgets",
        label: "Review your budgets",
        done:
          Number(club.finance?.transfer_budget_total ?? 0) > 0 ||
          Number(club.finance?.wage_budget_total_weekly ?? 0) > 0,
        to: "/club/finance",
      },
      {
        id: "club-team",
        label: "Invite your team — scouts, managers, your sporting director",
        done: (team.staff.length + team.invitations.length) > 0,
        to: "/club/team",
      },
      {
        id: "club-verify",
        label: "Request verification",
        done: club.verified || verifications.length > 0,
        to: "/club",
      },
      {
        id: "club-market",
        label: "Make your first market move — a listing, bid, or offer",
        done: (mySales?.total ?? 0) > 0 || (sentOffers?.total ?? 0) > 0,
        to: "/players/market",
      },
    ];
    return <ChecklistShell userId={userId} title="Get your club set up" steps={steps} />;
  }

  // Staff personas — role-appropriate; READONLY gets no checklist at all
  // (no empty checklist for a role with nothing to do).
  if (role === "SCOUT") {
    return <ScoutChecklist userId={userId} />;
  }
  if (role === "MANAGER" || role === "SPORTING_DIRECTOR") {
    const steps: Step[] = [
      {
        id: "staff-market",
        label: "Tour the player market",
        done: readFlag(userId, "staff-market"),
        to: "/players/market",
        visitFlag: true,
      },
      {
        id: "staff-deals",
        label: "See where your club's deals stand",
        done: readFlag(userId, "staff-deals"),
        to: "/deals",
        visitFlag: true,
      },
    ];
    return <ChecklistShell userId={userId} title="Find your way around" steps={steps} />;
  }
  return null;
}

function ScoutChecklist({ userId }: { userId: string }) {
  const { data: shortlists } = useQuery<{ id: string }[]>({
    queryKey: ["scouting", "shortlists"],
    queryFn: () => api.get<{ id: string }[]>("/scouting/shortlists").then((r) => r.data),
    staleTime: 60_000,
  });
  if (!shortlists) return null;
  const steps: Step[] = [
    {
      id: "scout-shortlist",
      label: "Create your first shortlist",
      done: shortlists.length > 0,
      to: "/scouting/shortlists",
    },
    {
      id: "scout-market",
      label: "Browse the player market",
      done: readFlag(userId, "scout-market"),
      to: "/players/market",
      visitFlag: true,
    },
  ];
  return <ChecklistShell userId={userId} title="Start scouting" steps={steps} />;
}

// ── Agent ─────────────────────────────────────────────────────────────────────

function AgentChecklist({ userId }: { userId: string }) {
  const { data: profile } = useQuery<AgentProfileResponse>({
    queryKey: ["agents", "me"],
    queryFn: () => api.get<AgentProfileResponse>("/agents/me").then((r) => r.data),
    staleTime: 60_000,
  });
  const { data: roster } = useQuery<unknown[]>({
    queryKey: ["agents", "me", "players"],
    queryFn: () => api.get<unknown[]>("/agents/me/players").then((r) => r.data),
    staleTime: 60_000,
  });
  const { data: verifications } = useQuery<VerificationRequest[]>({
    queryKey: ["verification", "mine"],
    queryFn: () => api.get<VerificationRequest[]>("/verification/requests/mine").then((r) => r.data),
    staleTime: 60_000,
  });

  if (!profile || !roster || !verifications) return null;
  const steps: Step[] = [
    {
      id: "agent-profile",
      label: "Complete your agency profile (licence number)",
      done: !!profile.licence_no,
      to: "/agent/profile",
    },
    {
      id: "agent-verify",
      label: "Request verification",
      done: profile.verified || verifications.length > 0,
      to: "/agent/profile",
    },
    {
      id: "agent-client",
      label: "Add your first client",
      done: roster.length > 0,
      to: "/agent/dashboard",
    },
    {
      id: "agent-alerts",
      label: "Review your client alert preferences",
      done: readFlag(userId, "agent-alerts"),
      to: "/agent/dashboard",
      visitFlag: true,
    },
  ];
  return <ChecklistShell userId={userId} title="Set up your agency" steps={steps} />;
}

// ── Player ────────────────────────────────────────────────────────────────────

function PlayerChecklist({ userId }: { userId: string }) {
  const { data: me } = useQuery<PlayerDetail>({
    queryKey: ["players", "me"],
    queryFn: () => api.get<PlayerDetail>("/players/me").then((r) => r.data),
    staleTime: 60_000,
  });
  if (!me) return null;
  const steps: Step[] = [
    {
      id: "player-visibility",
      label: "Choose who can see your profile",
      done: readFlag(userId, "player-visibility"),
      to: "/player/profile",
      visitFlag: true,
    },
    {
      id: "player-openness",
      label: "Set whether you're open to offers",
      done: readFlag(userId, "player-openness") || !!me.open_to_offers,
      to: "/player/profile",
      visitFlag: true,
    },
    {
      id: "player-representation",
      label: "Review your representation",
      done: readFlag(userId, "player-representation"),
      to: "/player/profile",
      visitFlag: true,
    },
  ];
  return <ChecklistShell userId={userId} title="Set up your profile" steps={steps} />;
}

// ── Entry point ───────────────────────────────────────────────────────────────

export default function OnboardingChecklist() {
  const { user, isClub, isAgent, isPlayer, isSuperuser } = useAuth();
  if (!user || isSuperuser) return null;
  if (isClub) return <ClubChecklist userId={user.id} />;
  if (isAgent) return <AgentChecklist userId={user.id} />;
  if (isPlayer) return <PlayerChecklist userId={user.id} />;
  return null;
}
