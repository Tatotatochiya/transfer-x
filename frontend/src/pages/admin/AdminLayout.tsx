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
  { to: "/admin/health",     label: "Health",      icon: "🩺" },
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
        <div className="rounded-xl bg-red-500/10 px-8 py-6 text-center ring-1 ring-red-500/30">
          <p className="text-lg font-semibold text-red-400">Staff access required</p>
          <p className="mt-1 text-sm text-slate-400">This area is restricted to superusers.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex gap-6 min-h-[calc(100vh-4rem)]">
      {/* Admin sub-sidebar */}
      <aside className="w-44 shrink-0">
        <div className="sticky top-6">
          <p className="mb-3 px-2 text-[10px] font-semibold uppercase tracking-widest text-slate-500">
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
                      ? "bg-amber-500/10 text-amber-400 ring-1 ring-amber-500/20"
                      : "text-slate-400 hover:bg-slate-800/60 hover:text-white"
                  }`
                }
              >
                <span className="text-xs">{icon}</span>
                {label}
              </NavLink>
            ))}
          </nav>

          <div className="mt-6 rounded-lg bg-amber-500/10 px-3 py-2 ring-1 ring-amber-500/20">
            <p className="text-[10px] font-semibold text-amber-400">SUPERUSER MODE</p>
            <p className="mt-0.5 text-[10px] text-slate-500">{user.email}</p>
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
