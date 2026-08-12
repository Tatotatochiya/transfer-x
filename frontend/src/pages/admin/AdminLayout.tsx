import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuthStore } from "../../store/auth";
import { useEffect } from "react";

const NAV_LINKS = [
  { to: "/admin",            label: "Dashboard",   icon: "⬛" },
  { to: "/admin/users",      label: "Users",       icon: "👤" },
  { to: "/admin/clubs",      label: "Clubs",       icon: "🏟" },
  { to: "/admin/players",    label: "Players",     icon: "⚽" },
  { to: "/admin/sales",      label: "Sales",       icon: "🏷" },
  { to: "/admin/deals",      label: "Deals",       icon: "🤝" },
  { to: "/admin/offers",     label: "Offers",      icon: "💬" },
  { to: "/admin/import",     label: "Import",      icon: "📥" },
  { to: "/admin/vendor",     label: "Vendor Sync", icon: "🔄" },
  { to: "/admin/analytics",  label: "Analytics",   icon: "📊" },
  { to: "/admin/windows",    label: "TW Windows",  icon: "🗓" },
  { to: "/admin/verification", label: "Verification", icon: "✅" },
  { to: "/admin/health",     label: "Health",      icon: "🩺" },
  { to: "/admin/ai",         label: "AI",          icon: "✦"  },
];

export default function AdminLayout() {
  const { user } = useAuthStore();
  const navigate = useNavigate();

  useEffect(() => {
    if (user && !user.is_superuser) {
      navigate("/dashboard", { replace: true });
    }
  }, [user, navigate]);

  if (!user?.is_superuser) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="rounded-xl bg-danger-bg px-8 py-6 text-center ring-1 ring-danger-border">
          <p className="text-lg font-semibold text-danger-text">Staff access required</p>
          <p className="mt-1 text-sm text-text-muted">This area is restricted to superusers.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col lg:flex-row gap-6 min-h-[calc(100vh-4rem)]">
      {/* Admin sub-nav — horizontal scroller below 1024px, persistent sidebar at and above */}
      <nav className="flex lg:hidden gap-1.5 overflow-x-auto pb-1 -mx-4 px-4 sm:mx-0 sm:px-0">
        {NAV_LINKS.map(({ to, label, icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/admin"}
            className={({ isActive }) =>
              `flex shrink-0 items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium whitespace-nowrap transition-colors ${
                isActive
                  ? "bg-warning-fill/10 text-warning-text ring-1 ring-warning-fill/20"
                  : "text-text-muted hover:bg-surface-inset hover:text-text"
              }`
            }
          >
            <span className="text-xs">{icon}</span>
            {label}
          </NavLink>
        ))}
      </nav>

      <aside className="hidden lg:block w-44 shrink-0">
        <div className="sticky top-6">
          <p className="mb-3 px-2 text-[10px] font-semibold uppercase tracking-widest text-text-muted">
            Admin Panel
          </p>
          <nav className="space-y-0.5">
            {NAV_LINKS.map(({ to, label, icon }) => (
              <NavLink
                key={to}
                to={to}
                end={to === "/admin"}
                className={({ isActive }) =>
                  `flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                    isActive
                      ? "bg-warning-fill/10 text-warning-text ring-1 ring-warning-fill/20"
                      : "text-text-muted hover:bg-surface-inset hover:text-text"
                  }`
                }
              >
                <span className="text-xs">{icon}</span>
                {label}
              </NavLink>
            ))}
          </nav>

          <div className="mt-6 rounded-lg bg-warning-fill/10 px-3 py-2 ring-1 ring-warning-fill/20">
            <p className="text-[10px] font-semibold text-warning-text">SUPERUSER MODE</p>
            <p className="mt-0.5 text-[10px] text-text-muted">{user.email}</p>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <div className="flex-1 min-w-0">
        <Outlet />
      </div>
    </div>
  );
}
