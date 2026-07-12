import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import Sidebar from "./Sidebar";
import Icon from "./Icon";
import GlobalSearch from "./GlobalSearch";
import TransferWindowCountdown from "../transfers/TransferWindowCountdown";

const STORAGE_KEY = "transferx-sidebar-expanded";

interface AppShellProps {
  children: React.ReactNode;
}

export default function AppShell({ children }: AppShellProps) {
  const [expanded, setExpanded] = useState(() => {
    return localStorage.getItem(STORAGE_KEY) === "true";
  });
  const [mobileOpen, setMobileOpen] = useState(false);

  function toggleSidebar() {
    const next = !expanded;
    setExpanded(next);
    localStorage.setItem(STORAGE_KEY, String(next));
  }

  const { pathname } = useLocation();

  // Close mobile menu on route change
  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);

  return (
    <div className="min-h-screen bg-slate-950">
      {/* Mobile top bar */}
      <header className="fixed top-0 left-0 right-0 z-40 flex items-center gap-3 border-b border-white/[0.08] bg-slate-900/95 backdrop-blur px-4 py-3 md:hidden">
        <button
          type="button"
          onClick={() => setMobileOpen((o) => !o)}
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-slate-400 hover:text-white transition-colors"
          aria-label="Toggle menu"
        >
          <Icon name={mobileOpen ? "x" : "menu"} />
        </button>
        <span className="text-lg font-semibold text-white shrink-0">TransferX</span>
        <div className="flex-1">
          <GlobalSearch />
        </div>
        <TransferWindowCountdown />
      </header>

      {/* Desktop search bar + window countdown — top-right */}
      <div className="hidden md:flex items-center gap-3 fixed top-3 right-6 z-40 transition-all duration-200">
        <TransferWindowCountdown />
        <GlobalSearch />
      </div>

      <Sidebar
        mobileOpen={mobileOpen}
        onMobileClose={() => setMobileOpen(false)}
        expanded={expanded}
        onToggle={toggleSidebar}
      />

      {/* Main content */}
      <main
        className={`transition-all duration-200 pt-14 md:pt-0 ${expanded ? "md:ml-56" : "md:ml-[3.75rem]"}`}
      >
        <div className="mx-auto max-w-7xl px-4 py-6 md:px-6 lg:px-8">
          {children}
        </div>
      </main>
    </div>
  );
}
