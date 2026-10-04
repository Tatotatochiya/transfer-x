import { useEffect, useRef, useState } from "react";
import { Link, NavLink, useLocation, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "../../hooks/useAuth";
import { useClubCapabilities } from "../../hooks/useClubCapabilities";
import { useIdentity, type IdentityRole } from "../../hooks/useIdentity";
import { useUpdatePreferences } from "../../hooks/usePreferences";
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
  // Everything a transfer is waiting on shows on the Transfers board
  // (product ADR 0008); approvals keep their own page.
  offer:    "/board",
  deal:     "/board",
  sale:     "/board",
  approval: "/club/approvals",
  enquiry:  "/board",
};

interface NavItem {
  label: string;
  to: string;
  icon: IconName;
  end?: boolean;      // exact match for active state (React Router NavLink `end`)
  // TRA-151: capability-gated items (server matrix via useClubCapabilities)
  gate?: "TEAM_MANAGE" | "APPROVALS";
  /** Hidden when signed out, in a group that also has public items. */
  authRequired?: boolean;
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

/** A TransferX staff account (superuser, no club): the admin panel's pages,
 *  instead of a club's nav that would only fail for them. */
const STAFF_GROUPS: NavGroup[] = [
  {
    title: "Admin",
    authRequired: true,
    items: [
      { label: "Overview",   to: "/admin",         icon: "layout-dashboard", end: true },
      { label: "Users",      to: "/admin/users",   icon: "user" },
      { label: "Clubs",      to: "/admin/clubs",   icon: "shield" },
      { label: "Players",    to: "/admin/players", icon: "users" },
      { label: "Sales",      to: "/admin/sales",   icon: "tag" },
      { label: "Deals",      to: "/admin/deals",   icon: "arrow-right-left" },
      { label: "Offers",     to: "/admin/offers",  icon: "send" },
      { label: "Audit log",  to: "/admin/audit",   icon: "list" },
    ],
  },
  {
    title: "Operations",
    authRequired: true,
    items: [
      { label: "Verification",     to: "/admin/verification", icon: "check" },
      { label: "Transfer windows", to: "/admin/windows",      icon: "gavel" },
      { label: "Health",           to: "/admin/health",       icon: "bolt" },
      { label: "Analytics",        to: "/admin/analytics",    icon: "crosshair" },
      { label: "AI",               to: "/admin/ai",           icon: "message" },
      { label: "Vendor sync",      to: "/admin/vendor",       icon: "inbox" },
      { label: "Import",           to: "/admin/import",       icon: "user-plus" },
    ],
  },
  {
    title: "Market",
    items: [
      { label: "Browse Players",   to: "/players/market", icon: "users" },
      { label: "Recent Transfers", to: "/transfers",      icon: "crosshair" },
    ],
  },
];

function getNavGroups(userType: UserType | null, staffAccount = false): NavGroup[] {
  if (staffAccount) return STAFF_GROUPS;
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
  //
  // Grouped by what the club is doing — buying or selling — rather than by
  // the platform's object types (offers, sales, deals). A signed-out visitor
  // sees only Buying's public items: the market and the listings.
  return [
    {
      title: "Home",
      authRequired: true,
      items: [
        { label: "Dashboard", to: "/dashboard", icon: "layout-dashboard" },
        // Every player the club is buying or selling, once (product ADR 0008).
        { label: "Transfers", to: "/board", icon: "columns" },
      ],
    },
    {
      title: "Find players",
      items: [
        { label: "Browse Players", to: "/players/market",      icon: "users" },
        { label: "Listings",       to: "/sales",               icon: "tag", end: true },
        { label: "Shortlists",     to: "/scouting/shortlists", icon: "list", authRequired: true },
        { label: "Recent Transfers", to: "/transfers",         icon: "crosshair" },
      ],
    },
    {
      title: "Club",
      authRequired: true,
      items: [
        { label: "My Club",   to: "/club",           icon: "shield", end: true },
        { label: "Finance",   to: "/club/finance",   icon: "wallet" },
        { label: "Team",      to: "/club/team",      icon: "user-plus", gate: "TEAM_MANAGE" },
        { label: "Approvals", to: "/club/approvals", icon: "check", gate: "APPROVALS" },
      ],
    },
    ADMIN_GROUP,
  ];
}

interface SidebarProps {
  mobileOpen: boolean;
  onMobileClose: () => void;
}

/**
 * The notifications bell: in the sidebar's logo row, and in the phone and
 * tablet top bar (AppShell). One query, shared by both through its key.
 */
export function NotificationBell({ size = "sm" }: { size?: "sm" | "touch" }) {
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
      title="Notifications"
      aria-label={count > 0 ? `Notifications, ${count} unread` : "Notifications"}
      className={({ isActive }) =>
        `relative flex shrink-0 items-center justify-center rounded-lg ring-1 ring-inset transition-colors no-underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent ${
          size === "touch" ? "h-11 w-11" : "h-8 w-8"
        } ${isActive ? "bg-accent-bg text-accent ring-accent/30" : "text-text-secondary ring-border hover:bg-surface-inset"}`
      }
    >
      <Icon name="bell" className={size === "touch" ? "h-5 w-5" : "h-4 w-4"} />
      {count > 0 && (
        <span
          aria-hidden
          className="absolute -right-1.5 -top-1.5 flex h-4 min-w-[1rem] items-center justify-center rounded-full bg-danger px-1 text-[11px] font-bold leading-none text-white"
        >
          {count > 99 ? "99+" : count}
        </span>
      )}
    </NavLink>
  );
}

// 32px rows on desktop; 48px touch rows in the drawer below 1024px.
const ROW = "flex min-h-12 items-center gap-2.5 rounded-[7px] px-2 text-[15px] font-medium no-underline transition-colors lg:h-8 lg:min-h-0 lg:text-[13.5px]";
// An inset outline, so the nav's overflow-y-auto never clips it.
const FOCUS = "focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-accent";
const ROW_ICON = "h-[18px] w-[18px] shrink-0 lg:h-4 lg:w-4";

function SidebarLink({ item, waiting = 0 }: { item: NavItem; waiting?: number }) {
  return (
    <NavLink
      to={item.to}
      end={item.end}
      className={({ isActive }) => `${ROW} ${FOCUS} ${isActive ? "bg-accent-bg" : "hover:bg-surface-inset"}`}
    >
      {({ isActive }) => (
        <>
          <Icon name={item.icon} className={`${ROW_ICON} ${isActive ? "text-accent" : "text-text-muted"}`} />
          <span className={`whitespace-nowrap ${isActive ? "text-accent font-semibold" : "text-text-secondary"}`}>
            {item.label}
          </span>
          {/* A count, not a bare dot: TOKENS/CLAUDE.md rule 10 says colour is
              never the only carrier of meaning, and the number is its own
              label. Same danger red the bell's badge uses, so "red in the
              nav" keeps meaning exactly one thing. */}
          {waiting > 0 && (
            <span
              className="ml-auto flex h-4 min-w-[1rem] items-center justify-center rounded-full bg-danger px-1 text-[11px] font-bold text-white leading-none"
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

// ── Account menu (the footer) ────────────────────────────────────────────────

const MENU_ITEM = `flex min-h-12 w-full items-center rounded-lg px-2.5 text-left text-[15px] text-text no-underline hover:bg-surface-inset disabled:opacity-50 lg:min-h-9 lg:text-[13.5px] ${FOCUS}`;

/**
 * One button that opens upwards: Settings, Notification settings, Switch to
 * Lite mode (clubs only) and Log out. Keyboard: arrows, Home and End move
 * between items; Escape closes it and returns focus to the button. Escape
 * is stopped here, so inside the phone drawer it closes only the menu, not
 * the drawer behind it (whose focus trap also listens for Escape).
 */
function AccountMenu({ onLogout }: { onLogout: () => void }) {
  const { user, userType, hasClub } = useAuth();
  const identity = useIdentity();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const switchToLite = useUpdatePreferences();
  const [open, setOpen] = useState(false);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const focusFirst = useRef(false);

  useEffect(() => setOpen(false), [pathname]);

  useEffect(() => {
    if (!open) return;
    function onDown(e: MouseEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  const items = () =>
    Array.from(menuRef.current?.querySelectorAll<HTMLElement>('[role="menuitem"]:not([disabled])') ?? []);

  // Opened from the keyboard: focus the first item.
  useEffect(() => {
    if (open && focusFirst.current) items()[0]?.focus();
    focusFirst.current = false;
  }, [open]);

  function close() {
    setOpen(false);
    buttonRef.current?.focus();
  }

  function onButtonKeyDown(e: React.KeyboardEvent) {
    if (e.key === "ArrowUp" || e.key === "ArrowDown") {
      e.preventDefault();
      focusFirst.current = true;
      setOpen(true);
    } else if (e.key === "Escape" && open) {
      e.stopPropagation();
      close();
    }
  }

  function onMenuKeyDown(e: React.KeyboardEvent) {
    const list = items();
    const i = list.indexOf(document.activeElement as HTMLElement);
    const go = (n: number) => { e.preventDefault(); list[(n + list.length) % list.length]?.focus(); };
    if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); close(); }
    else if (e.key === "ArrowDown") go(i + 1);
    else if (e.key === "ArrowUp") go(i - 1);
    else if (e.key === "Home") go(0);
    else if (e.key === "End") go(list.length - 1);
    else if (e.key === "Tab") setOpen(false);
  }

  const name = identity.name ?? user?.email ?? "";
  const subLine = identity.subLabel ?? (identity.role ? ROLE_LABEL[identity.role] : null);

  return (
    <div ref={wrapperRef} className="relative border-t border-border px-2.5 py-2">
      {open && (
        <div
          ref={menuRef}
          role="menu"
          aria-label="Account"
          onKeyDown={onMenuKeyDown}
          className="absolute bottom-[calc(100%+6px)] left-2.5 right-2.5 z-50 rounded-xl bg-surface p-1.5 shadow-xl ring-1 ring-border"
        >
          <NavLink to="/account" role="menuitem" tabIndex={-1} className={MENU_ITEM}>Settings</NavLink>
          <Link to="/account#notifications" role="menuitem" tabIndex={-1} className={MENU_ITEM}>Notification settings</Link>
          {userType === "CLUB" && hasClub && (
            <button
              type="button"
              role="menuitem"
              tabIndex={-1}
              disabled={switchToLite.isPending}
              onClick={() => switchToLite.mutate({ lite_mode: true }, { onSuccess: () => navigate("/lite") })}
              className={MENU_ITEM}
            >
              Switch to Lite mode
            </button>
          )}
          <div role="separator" className="my-1 h-px bg-rule" />
          <button
            type="button"
            role="menuitem"
            tabIndex={-1}
            onClick={() => { setOpen(false); onLogout(); }}
            className={`${MENU_ITEM} text-danger-text-alt`}
          >
            Log out
          </button>
        </div>
      )}
      <button
        ref={buttonRef}
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={(e) => {
          focusFirst.current = e.detail === 0; // Enter or Space, not a pointer
          setOpen((o) => !o);
        }}
        onKeyDown={onButtonKeyDown}
        className={`flex min-h-12 w-full items-center gap-2.5 rounded-lg bg-surface-inset px-2 text-left transition-colors hover:bg-border/40 lg:h-11 lg:min-h-0 ${FOCUS}`}
      >
        <Avatar
          name={name}
          crestUrl={identity.crestUrl}
          role={identity.role}
          isSuperuser={identity.isSuperuser}
          size="sm"
        />
        <span className="min-w-0 flex-1">
          <span className="block truncate text-[13px] font-semibold text-text">{name}</span>
          <span className="flex min-w-0 items-center gap-1.5">
            {subLine && <span className="truncate text-[11.5px] text-text-muted">{subLine}</span>}
            {identity.isSuperuser && (
              <span className="shrink-0 rounded px-1.5 py-px text-[10px] font-bold uppercase tracking-wider bg-danger/15 text-danger-text">
                Staff
              </span>
            )}
          </span>
        </span>
        {/* Up while closed: the menu opens upwards. */}
        <Icon name="chevron-up" className={`h-3.5 w-3.5 shrink-0 text-text-muted transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
    </div>
  );
}

export default function Sidebar({ mobileOpen, onMobileClose }: SidebarProps) {
  const { user, isAuthenticated, logout, userType, hasClub, isStaffAccount } = useAuth();
  const { can, role } = useClubCapabilities();
  const navigate = useNavigate();

  // TRA-151: capability-gated items are hidden, not disabled (D3).
  // Approvals shows for deciders (owner/SD) and for MANAGERs, whose own
  // requests land there; scouts and read-only members never see it.
  const itemVisible = (item: NavItem) => {
    if (item.authRequired && !isAuthenticated) return false;
    if (!item.gate) return true;
    if (item.gate === "TEAM_MANAGE") return can("TEAM_MANAGE");
    return can("APPROVE_ACTIONS") || role === "MANAGER";
  };
  const navGroups = getNavGroups(userType, isStaffAccount)
    .map((g) => ({ ...g, items: g.items.filter(itemVisible) }))
    .filter((g) => g.items.length > 0);

  // B2: one aggregate call, counted per section. Club accounts only — agents
  // and player accounts have no club dashboard, and asking for one 403s.
  const { data: dashboard } = useClubDashboard(isAuthenticated && userType === "CLUB" && hasClub);
  const waitingByRoute = (() => {
    const byKind = countByKind(dashboard?.waiting_on_you);
    const byRoute: Record<string, number> = {};
    for (const [kind, route] of Object.entries(WAITING_ROUTE)) {
      // Several kinds share the Transfers board, so add, don't overwrite.
      byRoute[route] = (byRoute[route] ?? 0) + (byKind[kind as DashboardItem["kind"]] ?? 0);
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
          No icon-only collapsed state at any width — RESPONSIVE.md bans it.
          Compact rows (docs/feature_spec/compact-sidebar) so a club's whole
          nav fits a 13-inch laptop without scrolling. */}
      <aside
        ref={drawerRef as React.RefObject<HTMLElement>}
        className={`fixed top-0 left-0 z-50 flex h-full w-[280px] flex-col border-r border-border bg-surface transition-transform duration-200
          ${mobileOpen ? "translate-x-0" : "-translate-x-full"} lg:translate-x-0 lg:w-[232px]`}
      >
        {/* Logo, and the notifications bell */}
        <div className="flex h-[52px] shrink-0 items-center gap-2.5 border-b border-border pl-[18px] pr-3">
          <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-[7px] bg-accent">
            <Icon name="bolt" className="h-3.5 w-3.5 text-white" />
          </div>
          <Link to="/dashboard" className={`flex-1 rounded text-[15px] font-bold text-text whitespace-nowrap no-underline ${FOCUS}`}>
            TransferX
          </Link>
          {isAuthenticated && <NotificationBell />}
        </div>

        {/* Nav. It scrolls only when the window is shorter than the nav
            (Admin group, short laptop screens); focus outlines are inset so
            the scroll container never clips them. */}
        <nav className="flex flex-1 flex-col gap-3 overflow-y-auto px-2.5 py-2.5">
          {navGroups.map((group) => {
            if (group.authRequired && !isAuthenticated) return null;
            if (group.superuserOnly && !user?.is_superuser) return null;
            return (
              <div key={group.title}>
                <p className="flex h-[22px] items-center px-2 text-[11px] font-semibold uppercase tracking-[0.04em] text-text-muted">
                  {group.title}
                </p>
                <div className="flex flex-col">
                  {group.items.map((item) => (
                    <SidebarLink key={item.to} item={item} waiting={waitingByRoute[item.to] ?? 0} />
                  ))}
                </div>
              </div>
            );
          })}
        </nav>

        {/* Footer: the account menu, or Login when signed out */}
        {isAuthenticated ? (
          <AccountMenu onLogout={handleLogout} />
        ) : (
          <div className="border-t border-border px-2.5 py-2">
            <NavLink to="/login" className={`${ROW} ${FOCUS} text-text-secondary hover:bg-surface-inset`}>
              <Icon name="log-out" className={`${ROW_ICON} text-text-muted`} />
              <span>Login</span>
            </NavLink>
          </div>
        )}
      </aside>
    </>
  );
}
