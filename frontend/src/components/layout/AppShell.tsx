import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { useAuth } from "../../hooks/useAuth";
import { useIdentity } from "../../hooks/useIdentity";
import Sidebar from "./Sidebar";
import Icon from "./Icon";
import GlobalSearch from "./GlobalSearch";
import Avatar from "../ui/Avatar";

interface AppShellProps {
  children: React.ReactNode;
}

export default function AppShell({ children }: AppShellProps) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const { pathname } = useLocation();
  const { isAuthenticated } = useAuth();
  const identity = useIdentity();

  // Close mobile menu on route change
  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);

  // TODO(Phase 4): wire to the real whose-move aggregate (backend item B2)
  // once it exists. Zero renders no badge at all, matching the "no
  // background when absent" rule the per-item nav badges already follow.
  const yourMoveCount = 0;

  return (
    <div className="min-h-screen bg-page">
      {/* Sticky top app bar — tablet and mobile only (<1024px), per
          docs/design_handoff_transferx/RESPONSIVE.md */}
      <header className="fixed top-0 left-0 right-0 z-40 flex h-14 items-center gap-2 border-b border-border bg-surface px-3 lg:hidden">
        <button
          type="button"
          onClick={() => setMobileOpen((o) => !o)}
          aria-label="Toggle menu"
          aria-expanded={mobileOpen}
          className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg text-text-secondary hover:bg-surface-inset transition-colors"
        >
          <Icon name={mobileOpen ? "x" : "menu"} />
        </button>
        <span className="text-base font-bold text-text shrink-0">TransferX</span>
        {isAuthenticated && yourMoveCount > 0 && (
          <span className="flex h-5 min-w-[1.25rem] items-center justify-center rounded-full bg-danger-bg-badge px-1.5 text-[11px] font-bold text-danger-heading">
            {yourMoveCount > 99 ? "99+" : yourMoveCount}
          </span>
        )}
        <div className="flex-1" />
        <div className="shrink-0">
          <GlobalSearch />
        </div>
        {isAuthenticated && (
          <Avatar
            name={identity.name}
            crestUrl={identity.crestUrl}
            role={identity.role}
            isSuperuser={identity.isSuperuser}
            size="sm"
            className="shrink-0"
          />
        )}
      </header>

      {/* Desktop search bar — top-right, >=1024px only */}
      <div className="hidden lg:flex fixed top-3 right-6 z-40">
        <GlobalSearch />
      </div>

      <Sidebar mobileOpen={mobileOpen} onMobileClose={() => setMobileOpen(false)} />

      {/* Main content */}
      <main className="pt-14 lg:pt-0 lg:ml-[232px]">
        <div className="mx-auto max-w-[1280px] px-4 py-6 md:px-6 lg:px-8">
          {children}
        </div>
      </main>
    </div>
  );
}
