import { NavLink, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "../../hooks/useAuth";
import { useClubCapabilities } from "../../hooks/useClubCapabilities";
import { useIdentity, type IdentityRole } from "../../hooks/useIdentity";
import api from "../../lib/api";
import Avatar from "../ui/Avatar";
import { useFocusTrap } from "../../hooks/useFocusTrap";
import Icon from "./Icon";
import type { IconName } from "./Icon";
import { countByKind, useClubDashboard } from "../../hooks/useClubDashboard";
import type { DashboardItem, UnreadCount, UserType } from "../../types/api";

const ROLE_LABEL: Record<IdentityRole, string> = { CLUB: "Club", AGENT: "Agent", PLAYER: "Player" };

/**
 * Which nav destination each B2 `kind` belongs to.
 *
 * Keyed by route rather than label so a renamed nav item can't silently drop
 * its badge. Sales map to "My Auctions" (`/sales/mine`) rather than the public
 * listings browse — a sale needing your attention is always one you're selling.
 */
const WAITING_ROUTE: Record<DashboardItem["kind"], string> = {
  offer:    "/offers/received",
  deal:     "/deals",
  sale:     "/sales/mine",
  approval: "/club/approvals",
};

interface NavItem {
  label: string;
  to: string;
  icon: IconName;
  end?: boolean;      // exact match for active state (React Router NavLink `end`)
  // TRA-151: capability-gated items (server matrix via useClubCapabilities)
  gate?: "TEAM_MANAGE" | "APPROVALS";
}

interface NavGroup {
  title: string;
  items: NavItem[];
  authRequired?: boolean;
  superuserOnly?: boolean;
}

const ADMIN_GROUP: NavGroup = {
  title: "Admin",
  authRequired: true,
  superuserOnly: true,
  items: [
    { label: "Admin Panel", to: "/admin", icon: "settings" },
  ],
};

function getNavGroups(userType: UserType | null): NavGroup[] {
  if (userType === "AGENT") {
    return [
      {
        title: "Agency",
        authRequired: true,
        items: [
          { label: "Pipeline",     to: "/agent/pipeline",  icon: "layout-dashboard", end: true },
          { label: "My Roster",   to: "/agent/dashboard", icon: "briefcase",        end: true },
          { label: "Agent Profile", to: "/agent/profile", icon: "user" },
        ],
      },
      {
        title: "Market",
        items: [
          { label: "Browse Players", to: "/players/market", icon: "crosshair" },
          { label: "Transfers",      to: "/transfers",      icon: "arrow-right-left" },
        ],
      },
      ADMIN_GROUP,
    ];
  }

  if (userType === "PLAYER") {
    return [
      {
        title: "Market",
        items: [
          { label: "Browse Players", to: "/players/market", icon: "users" },
          { label: "Transfers",      to: "/transfers",      icon: "arrow-right-left" },
        ],
      },
      {
        title: "My Profile",
        authRequired: true,
        items: [
          { label: "My Profile", to: "/player/profile", icon: "user", end: true },
        ],
      },
      ADMIN_GROUP,
    ];
  }

  // CLUB / unauthenticated / STAFF / ADMIN
  return [
    {
      title: "Market",
      items: [
        { label: "Browse Players", to: "/players/market", icon: "users" },
        { label: "Listings",       to: "/sales",          icon: "tag", end: true },
        { label: "Transfers",      to: "/transfers",      icon: "arrow-right-left" },
      ],
    },
    {
      title: "My Deals",
      authRequired: true,
      items: [
        { label: "Auctions",    to: "/sales/mine",      icon: "gavel" },
        { label: "Inbox",       to: "/offers/received", icon: "inbox" },
        { label: "Sent Offers", to: "/offers/sent",     icon: "send" },
        { label: "Deals",       to: "/deals",           icon: "tag" },
      ],
    },
    {
      title: "Club",
      authRequired: true,
      items: [
        { label: "War Room",  to: "/dashboard",      icon: "layout-dashboard" },
        { label: "My Club",   to: "/club",           icon: "shield", end: true },
        { label: "Finance",   to: "/club/finance",   icon: "wallet" },
        { label: "Team",      to: "/club/team",      icon: "users", gate: "TEAM_MANAGE" },
        { label: "Approvals", to: "/club/approvals", icon: "check", gate: "APPROVALS" },
      ],
    },
    {
      title: "Scouting",
      authRequired: true,
      items: [
        { label: "Shortlists", to: "/scouting/shortlists", icon: "list" },
      ],
    },
    ADMIN_GROUP,
  ];
}

interface SidebarProps {
  mobileOpen: boolean;
  onMobileClose: () => void;
}

function NotificationNavItem() {
  const { data } = useQuery<UnreadCount>({
    queryKey: ["notifications", "unread-count"],
    queryFn: () => api.get<UnreadCount>("/notifications/unread-count").then((r) => r.data),
    refetchInterval: 300_000,
    staleTime: 60_000,
  });
  const count = data?.count ?? 0;

  return (
    <NavLink
      to="/notifications"
      className={({ isActive }) =>
        `min-h-12 lg:min-h-0 flex items-center gap-3 rounded-lg px-2 py-1.5 text-sm font-medium transition-colors no-underline ${
          isActive ? "bg-accent-bg" : "hover:bg-surface-inset"
        }`
      }
    >
      {({ isActive }) => (
        <>
          <div
            className={`relative flex h-7 w-7 shrink-0 items-center justify-center rounded-lg transition-colors ${
              isActive ? "bg-danger/15 text-danger-text" : "bg-surface-inset text-text-muted"
            }`}
          >
            <Icon name="bell" className="h-4 w-4" />
            {count > 0 && (
              <span className="absolute -right-1 -top-1 flex h-4 min-w-[1rem] items-center justify-center rounded-full bg-danger px-1 text-[9px] font-bold text-white leading-none">
                {count > 99 ? "99+" : count}
              </span>
            )}
          </div>
          <span className={isActive ? "text-accent font-semibold" : "text-text-secondary"}>
            Notifications
          </span>
        </>
      )}
    </NavLink>
  );
}

function SidebarLink({ item, waiting = 0 }: { item: NavItem; waiting?: number }) {
  return (
    <NavLink
      to={item.to}
      end={item.end}
      className={({ isActive }) =>
        `min-h-12 lg:min-h-0 flex items-center gap-3 rounded-lg px-2 py-1.5 text-sm font-medium transition-colors no-underline ${
          isActive ? "bg-accent-bg" : "hover:bg-surface-inset"
        }`
      }
    >
      {({ isActive }) => (
        <>
          <div
            className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-lg transition-colors ${
              isActive ? "bg-accent-bg text-accent" : "bg-surface-inset text-text-muted"
            }`}
          >
            <Icon name={item.icon} className="h-4 w-4" />
          </div>
          <span className={isActive ? "text-accent font-semibold" : "text-text-secondary"}>
            {item.label}
          </span>
          {/* A count, not a bare dot: TOKENS/CLAUDE.md rule 10 says colour is
              never the only carrier of meaning, and the number is its own
              label. Same danger red the Notifications badge already uses, so
              "red in the nav" keeps meaning exactly one thing. */}
          {waiting > 0 && (
            <span
              className="ml-auto flex h-4 min-w-[1rem] items-center justify-center rounded-full bg-danger px-1 text-[9px] font-bold text-white leading-none"
              aria-label={`${waiting} waiting on you`}
            >
              {waiting > 99 ? "99+" : waiting}
            </span>
          )}
        </>
      )}
    </NavLink>
  );
}

export default function Sidebar({ mobileOpen, onMobileClose }: SidebarProps) {
  const { user, isAuthenticated, logout, userType } = useAuth();
  const identity = useIdentity();
  const { can, role } = useClubCapabilities();
  const navigate = useNavigate();

  // TRA-151: capability-gated items are hidden, not disabled (D3).
  // Approvals shows for deciders (owner/SD) and for MANAGERs, whose own
  // requests land there; scouts and read-only members never see it.
  const itemVisible = (item: NavItem) => {
    if (!item.gate) return true;
    if (item.gate === "TEAM_MANAGE") return can("TEAM_MANAGE");
    return can("APPROVE_ACTIONS") || role === "MANAGER";
  };
  const navGroups = getNavGroups(userType)
    .map((g) => ({ ...g, items: g.items.filter(itemVisible) }))
    .filter((g) => g.items.length > 0);

  // B2: one aggregate call, counted per section. Club accounts only — agents
  // and player accounts have no club dashboard, and asking for one 403s.
  const { data: dashboard } = useClubDashboard(isAuthenticated && userType === "CLUB");
  const waitingByRoute = (() => {
    const byKind = countByKind(dashboard?.waiting_on_you);
    const byRoute: Record<string, number> = {};
    for (const [kind, route] of Object.entries(WAITING_ROUTE)) {
      byRoute[route] = byKind[kind as DashboardItem["kind"]];
    }
    return byRoute;
  })();

  // Only meaningfully "traps" below 1024px, where the aside is the
  // off-canvas drawer — on desktop the aside is always open/persistent, so
  // Escape/Tab-cycling would be unwelcome there. mobileOpen is naturally
  // false on desktop under normal use (see AppShell's route-change effect).
  const drawerRef = useFocusTrap(mobileOpen, onMobileClose);

  async function handleLogout() {
    await logout();
    navigate("/login");
  }

  return (
    <>
      {/* Drawer backdrop — below 1024px only */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-ink/40 lg:hidden"
          onClick={onMobileClose}
        />
      )}

      {/* Persistent 232px sidebar at >=1024px; 280px off-canvas drawer below it.
          No icon-only collapsed state at any width — RESPONSIVE.md bans it. */}
      <aside
        ref={drawerRef as React.RefObject<HTMLElement>}
        className={`fixed top-0 left-0 z-50 flex h-full w-[280px] flex-col border-r border-border bg-surface transition-transform duration-200
          ${mobileOpen ? "translate-x-0" : "-translate-x-full"} lg:translate-x-0 lg:w-[232px]`}
      >
        {/* Logo */}
        <div className="flex h-[60px] items-center gap-3 border-b border-border px-5">
          <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-accent">
            <Icon name="bolt" className="h-4 w-4 text-white" />
          </div>
          <span className="text-[15px] font-bold text-text whitespace-nowrap">TransferX</span>
        </div>

        {/* Nav — no overflow-y-auto so focus outlines aren't clipped */}
        <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-5">
          {isAuthenticated && (
            <div className="space-y-0.5">
              <NotificationNavItem />
            </div>
          )}
          {navGroups.map((group) => {
            if (group.authRequired && !isAuthenticated) return null;
            if (group.superuserOnly && !user?.is_superuser) return null;
            return (
              <div key={group.title}>
                <p className="mb-1.5 px-2 text-[11px] font-semibold uppercase tracking-[0.04em] text-text-muted">
                  {group.title}
                </p>
                <div className="space-y-0.5">
                  {group.items.map((item) => (
                    <SidebarLink key={item.to} item={item} waiting={waitingByRoute[item.to] ?? 0} />
                  ))}
                </div>
              </div>
            );
          })}
        </nav>

        {/* Footer */}
        <div className="border-t border-border px-3 py-3 space-y-0.5">
          {isAuthenticated && (
            <NavLink
              to="/account"
              className={({ isActive }) =>
                `min-h-12 lg:min-h-0 flex items-center gap-3 rounded-lg px-2 py-1.5 text-sm font-medium transition-colors no-underline ${
                  isActive ? "bg-accent-bg" : "hover:bg-surface-inset"
                }`
              }
            >
              <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-surface-inset text-text-muted">
                <Icon name="settings" className="h-4 w-4" />
              </div>
              <span className="text-text-secondary">Settings</span>
            </NavLink>
          )}

          {isAuthenticated ? (
            <div className="flex items-center gap-3 rounded-lg px-2 py-1.5">
              <Avatar
                name={identity.name ?? user?.email}
                crestUrl={identity.crestUrl}
                role={identity.role}
                isSuperuser={identity.isSuperuser}
                size="sm"
              />
              <div className="min-w-0 flex-1">
                <p className="truncate text-xs font-semibold text-text">{identity.name ?? user?.email}</p>
                <div className="mt-0.5 flex flex-wrap items-center gap-1.5">
                  {identity.role && (
                    <span className="text-[11px] font-medium text-text-muted">
                      {ROLE_LABEL[identity.role]}
                    </span>
                  )}
                  {identity.isSuperuser && (
                    <span className="rounded px-1.5 py-px text-[9px] font-bold uppercase tracking-wider bg-danger/15 text-danger-text">
                      Staff
                    </span>
                  )}
                  {identity.subLabel && (
                    <span className="truncate text-[11px] text-text-muted">{identity.subLabel}</span>
                  )}
                </div>
                <button
                  onClick={handleLogout}
                  className="mt-0.5 text-[11px] text-text-muted hover:text-text-secondary transition-colors"
                >
                  Logout
                </button>
              </div>
            </div>
          ) : (
            <NavLink
              to="/login"
              className="min-h-12 lg:min-h-0 flex items-center gap-3 rounded-lg px-2 py-1.5 text-sm text-text-secondary hover:bg-surface-inset no-underline"
            >
              <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-surface-inset">
                <Icon name="log-out" className="h-4 w-4" />
              </div>
              <span>Login</span>
            </NavLink>
          )}
        </div>
      </aside>
    </>
  );
}
