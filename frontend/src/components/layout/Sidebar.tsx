import { useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useAuthStore } from "../../store/auth";
import { useAuth } from "../../hooks/useAuth";
import api from "../../lib/api";
import Icon from "./Icon";
import type { IconName } from "./Icon";
import type { UnreadCount, UserType } from "../../types/api";

interface NavItem {
  label: string;
  to: string;
  icon: IconName;
  iconColor: string;  // e.g. "text-sky-400"
  iconBg: string;     // e.g. "bg-sky-500/15"
  end?: boolean;      // exact match for active state (React Router NavLink `end`)
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
    { label: "Admin Panel", to: "/admin", icon: "settings", iconColor: "text-amber-400", iconBg: "bg-amber-500/15" },
  ],
};

function getNavGroups(userType: UserType | null): NavGroup[] {
  if (userType === "AGENT") {
    return [
      {
        title: "Market",
        items: [
          { label: "Browse Players", to: "/players/market", icon: "users",            iconColor: "text-sky-400",    iconBg: "bg-sky-500/15" },
          { label: "Transfers",      to: "/transfers",      icon: "arrow-right-left", iconColor: "text-purple-400", iconBg: "bg-purple-500/15" },
        ],
      },
      {
        title: "My Clients",
        authRequired: true,
        items: [
          { label: "Clients",       to: "/agent/dashboard", icon: "users", iconColor: "text-sky-400",    iconBg: "bg-sky-500/15",    end: true },
        ],
      },
      {
        title: "My Profile",
        authRequired: true,
        items: [
          { label: "Agent Profile", to: "/agent/profile",   icon: "user",  iconColor: "text-indigo-400", iconBg: "bg-indigo-500/15" },
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
          { label: "Browse Players", to: "/players/market", icon: "users",            iconColor: "text-sky-400",    iconBg: "bg-sky-500/15" },
          { label: "Transfers",      to: "/transfers",      icon: "arrow-right-left", iconColor: "text-purple-400", iconBg: "bg-purple-500/15" },
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
        { label: "Browse Players", to: "/players/market", icon: "users",            iconColor: "text-sky-400",    iconBg: "bg-sky-500/15" },
        { label: "Listings",       to: "/sales",          icon: "tag",              iconColor: "text-amber-400",  iconBg: "bg-amber-500/15", end: true },
        { label: "Transfers",      to: "/transfers",      icon: "arrow-right-left", iconColor: "text-purple-400", iconBg: "bg-purple-500/15" },
      ],
    },
    {
      title: "My Deals",
      authRequired: true,
      items: [
        { label: "Auctions",    to: "/sales/mine",      icon: "gavel", iconColor: "text-orange-400",  iconBg: "bg-orange-500/15" },
        { label: "Inbox",       to: "/offers/received", icon: "inbox", iconColor: "text-emerald-400", iconBg: "bg-emerald-500/15" },
        { label: "Sent Offers", to: "/offers/sent",     icon: "send",  iconColor: "text-teal-400",    iconBg: "bg-teal-500/15" },
        { label: "Deals",       to: "/deals",           icon: "tag",   iconColor: "text-violet-400",  iconBg: "bg-violet-500/15" },
      ],
    },
    {
      title: "Club",
      authRequired: true,
      items: [
        { label: "War Room", to: "/dashboard",    icon: "layout-dashboard", iconColor: "text-blue-400",   iconBg: "bg-blue-500/15" },
        { label: "My Club",  to: "/club",         icon: "shield",           iconColor: "text-indigo-400", iconBg: "bg-indigo-500/15", end: true },
        { label: "Finance",  to: "/club/finance", icon: "wallet",           iconColor: "text-green-400",  iconBg: "bg-green-500/15" },
      ],
    },
    {
      title: "Scouting",
      authRequired: true,
      items: [
        { label: "Shortlists", to: "/scouting/shortlists", icon: "list", iconColor: "text-cyan-400", iconBg: "bg-cyan-500/15" },
      ],
    },
    ADMIN_GROUP,
  ];
}

interface SidebarProps {
  mobileOpen: boolean;
  onMobileClose: () => void;
  expanded: boolean;
  onToggle: () => void;
}

function NotificationNavItem({ expanded }: { expanded: boolean }) {
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
        `group relative flex items-center gap-3 rounded-lg px-2 py-1.5 text-sm font-medium transition-colors no-underline ${
          isActive ? "bg-white/[0.06]" : "hover:bg-white/[0.04]"
        }`
      }
    >
      {({ isActive }) => (
        <>
          <div
            className={`relative flex h-7 w-7 shrink-0 items-center justify-center rounded-lg transition-colors ${
              isActive ? "bg-rose-500/15 text-rose-400" : "bg-slate-800 group-hover:bg-slate-700/80 text-slate-400 group-hover:text-white"
            }`}
          >
            <Icon name="bell" className="h-4 w-4" />
            {count > 0 && (
              <span className="absolute -right-1 -top-1 flex h-4 min-w-[1rem] items-center justify-center rounded-full bg-red-500 px-1 text-[9px] font-bold text-white leading-none">
                {count > 99 ? "99+" : count}
              </span>
            )}
          </div>
          {expanded && (
            <span className={isActive ? "text-white" : "text-slate-400 group-hover:text-white"}>
              Notifications
            </span>
          )}
          {isActive && (
            <span className="absolute left-0 top-1/2 -translate-y-1/2 h-5 w-0.5 rounded-full bg-current opacity-60" />
          )}
          {!expanded && (
            <div className="pointer-events-none absolute left-full top-1/2 z-50 ml-3 -translate-y-1/2 whitespace-nowrap rounded-md bg-slate-800 px-2.5 py-1.5 text-xs font-medium text-white opacity-0 shadow-xl ring-1 ring-white/10 transition-opacity duration-150 group-hover:opacity-100">
              Notifications{count > 0 ? ` (${count})` : ""}
              <span className="absolute right-full top-1/2 -translate-y-1/2 border-4 border-transparent border-r-slate-800" />
            </div>
          )}
        </>
      )}
    </NavLink>
  );
}

function SidebarLink({ item, expanded }: { item: NavItem; expanded: boolean }) {
  return (
    <NavLink
      to={item.to}
      end={item.end}
      className={({ isActive }) =>
        `group relative flex items-center gap-3 rounded-lg px-2 py-1.5 text-sm font-medium transition-colors no-underline ${
          isActive ? "bg-white/[0.06]" : "hover:bg-white/[0.04]"
        }`
      }
    >
      {({ isActive }) => (
        <>
          {/* Coloured icon badge */}
          <div
            className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-lg transition-colors ${
              isActive ? item.iconBg : "bg-slate-800 group-hover:bg-slate-700/80"
            } ${item.iconColor}`}
          >
            <Icon name={item.icon} className="h-4 w-4" />
          </div>

          {/* Label (expanded only) */}
          {expanded && (
            <span className={isActive ? "text-white" : "text-slate-400 group-hover:text-white"}>
              {item.label}
            </span>
          )}

          {/* Active indicator */}
          {isActive && (
            <span className="absolute left-0 top-1/2 -translate-y-1/2 h-5 w-0.5 rounded-full bg-current opacity-60" />
          )}

          {/* Tooltip (collapsed mode only) */}
          {!expanded && (
            <div
              className="pointer-events-none absolute left-full top-1/2 z-50 ml-3 -translate-y-1/2 whitespace-nowrap rounded-md bg-slate-800 px-2.5 py-1.5 text-xs font-medium text-white opacity-0 shadow-xl ring-1 ring-white/10 transition-opacity duration-150 group-hover:opacity-100"
            >
              {item.label}
              {/* Arrow */}
              <span className="absolute right-full top-1/2 -translate-y-1/2 border-4 border-transparent border-r-slate-800" />
            </div>
          )}
        </>
      )}
    </NavLink>
  );
}

export default function Sidebar({ mobileOpen, onMobileClose, expanded, onToggle }: SidebarProps) {
  const { user, isAuthenticated, logout, userType } = useAuth();
  const navigate = useNavigate();
  const navGroups = getNavGroups(userType);
  // Show text labels when desktop sidebar is expanded OR mobile drawer is open
  const showText = expanded || mobileOpen;

  async function handleLogout() {
    await logout();
    navigate("/login");
  }

  const initial = user?.email?.[0]?.toUpperCase() ?? "?";

  return (
    <>
      {/* Mobile overlay */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/60 md:hidden"
          onClick={onMobileClose}
        />
      )}

      <aside
        className={`fixed top-0 left-0 z-50 flex h-full flex-col border-r border-white/[0.08] bg-slate-900 transition-all duration-200
          ${mobileOpen ? "translate-x-0 w-56" : "-translate-x-full w-56"} md:translate-x-0
          ${expanded ? "md:w-56" : "md:w-[3.75rem]"}`}
      >
        {/* Logo */}
        <div className="flex h-14 items-center gap-3 border-b border-white/[0.08] px-3">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-emerald-500/20">
            <Icon name="bolt" className="h-5 w-5 text-emerald-400" />
          </div>
          {showText && (
            <span className="text-lg font-semibold text-white whitespace-nowrap">TransferX</span>
          )}
        </div>

        {/* Nav — no overflow-y-auto so tooltips can escape the x boundary */}
        <nav className="flex-1 px-2 py-4 space-y-5">
          {isAuthenticated && (
            <div className="space-y-0.5">
              <NotificationNavItem expanded={showText} />
            </div>
          )}
          {navGroups.map((group) => {
            if (group.authRequired && !isAuthenticated) return null;
            if (group.superuserOnly && !user?.is_superuser) return null;
            return (
              <div key={group.title}>
                {showText && (
                  <p className="mb-1.5 px-2 text-[10px] font-semibold uppercase tracking-wider text-slate-600">
                    {group.title}
                  </p>
                )}
                {!showText && <div className="mb-1 mx-auto h-px w-6 bg-white/[0.06]" />}
                <div className="space-y-0.5">
                  {group.items.map((item) => (
                    <SidebarLink key={item.to} item={item} expanded={showText} />
                  ))}
                </div>
              </div>
            );
          })}
        </nav>

        {/* Footer */}
        <div className="border-t border-white/[0.08] px-2 py-3 space-y-0.5">
          {/* Account settings */}
          {isAuthenticated && (
            <NavLink
              to="/account"
              className={({ isActive }) =>
                `group relative flex items-center gap-3 rounded-lg px-2 py-1.5 text-sm font-medium transition-colors no-underline ${
                  isActive ? "bg-white/[0.06]" : "hover:bg-white/[0.04]"
                }`
              }
            >
              <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-slate-800 text-slate-400 group-hover:bg-slate-700/80 group-hover:text-white transition-colors">
                <Icon name="settings" className="h-4 w-4" />
              </div>
              {showText && <span className="text-slate-400 group-hover:text-white">Settings</span>}
              {!showText && (
                <div className="pointer-events-none absolute left-full top-1/2 z-50 ml-3 -translate-y-1/2 whitespace-nowrap rounded-md bg-slate-800 px-2.5 py-1.5 text-xs font-medium text-white opacity-0 shadow-xl ring-1 ring-white/10 transition-opacity duration-150 group-hover:opacity-100">
                  Settings
                  <span className="absolute right-full top-1/2 -translate-y-1/2 border-4 border-transparent border-r-slate-800" />
                </div>
              )}
            </NavLink>
          )}

          {/* User info + logout */}
          {isAuthenticated ? (
            <div className="group relative flex items-center gap-3 rounded-lg px-2 py-1.5">
              <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-emerald-500/20 text-xs font-semibold text-emerald-400">
                {initial}
              </div>
              {showText && (
                <div className="min-w-0 flex-1">
                  <p className="truncate text-xs font-medium text-white">{user?.email}</p>
                  <button
                    onClick={handleLogout}
                    className="text-[11px] text-slate-500 hover:text-slate-300 transition-colors"
                  >
                    Logout
                  </button>
                </div>
              )}
              {!showText && (
                <div className="pointer-events-none absolute left-full top-1/2 z-50 ml-3 -translate-y-1/2 whitespace-nowrap rounded-md bg-slate-800 px-2.5 py-1.5 text-xs font-medium text-white opacity-0 shadow-xl ring-1 ring-white/10 transition-opacity duration-150 group-hover:opacity-100">
                  {user?.email}
                  <span className="absolute right-full top-1/2 -translate-y-1/2 border-4 border-transparent border-r-slate-800" />
                </div>
              )}
            </div>
          ) : (
            <NavLink
              to="/login"
              className="flex items-center gap-3 rounded-lg px-2 py-1.5 text-sm text-slate-400 hover:text-white hover:bg-white/[0.04] no-underline"
            >
              <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-slate-800">
                <Icon name="log-out" className="h-4 w-4" />
              </div>
              {expanded && <span>Login</span>}
            </NavLink>
          )}

          {/* Collapse toggle (desktop only) */}
          <button
            onClick={onToggle}
            className="group relative hidden md:flex w-full items-center gap-3 rounded-lg px-2 py-1.5 text-slate-500 hover:text-white hover:bg-white/[0.04] transition-colors"
          >
            <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg">
              <Icon
                name={expanded ? "chevrons-left" : "chevrons-right"}
                className="h-4 w-4"
              />
            </div>
            {expanded && <span className="text-sm">Collapse</span>}
            {!expanded && (
              <div className="pointer-events-none absolute left-full top-1/2 z-50 ml-3 -translate-y-1/2 whitespace-nowrap rounded-md bg-slate-800 px-2.5 py-1.5 text-xs font-medium text-white opacity-0 shadow-xl ring-1 ring-white/10 transition-opacity duration-150 group-hover:opacity-100">
                Expand sidebar
                <span className="absolute right-full top-1/2 -translate-y-1/2 border-4 border-transparent border-r-slate-800" />
              </div>
            )}
          </button>
        </div>
      </aside>
    </>
  );
}
