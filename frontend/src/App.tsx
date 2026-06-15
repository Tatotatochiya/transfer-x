import { lazy, Suspense } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { useAuthStore } from "./store/auth";
import { useAuth } from "./hooks/useAuth";
import { useWebSocket } from "./hooks/useWebSocket";
import AppShell from "./components/layout/AppShell";
import Spinner from "./components/ui/Spinner";
import { ToastProvider } from "./context/ToastContext";
import { ConfirmProvider } from "./context/ConfirmContext";
import ErrorBoundary from "./components/ErrorBoundary";
import { CompareProvider } from "./context/CompareContext";
import CompareBar from "./components/players/CompareBar";
import { usePageTracking } from "./hooks/usePageTracking";

// ── Eager (hot-path) ──────────────────────────────────────────────────────────
import LoginPage from "./pages/auth/LoginPage";
import DashboardPage from "./pages/dashboard/DashboardPage";
import PlayerMarketPage from "./pages/market/PlayerMarketPage";
import PlayerMarketDetailPage from "./pages/market/PlayerMarketDetailPage";
import SaleListPage from "./pages/market/SaleListPage";
import SaleDetailPage from "./pages/market/SaleDetailPage";
import ClubListPage from "./pages/market/ClubListPage";
import ClubDetailPage from "./pages/market/ClubDetailPage";
import MyClubPage from "./pages/club/MyClubPage";

// ── Lazy (non-hot-path) ───────────────────────────────────────────────────────
const AccountSettingsPage       = lazy(() => import("./pages/account/AccountSettingsPage"));
const WorldTeamDetailPage       = lazy(() => import("./pages/world/WorldTeamDetailPage"));
const TransferActivityPage      = lazy(() => import("./pages/transfers/TransferActivityPage"));
const PlayerComparePage         = lazy(() => import("./pages/players/PlayerComparePage"));
const MySalesPage               = lazy(() => import("./pages/sales/MySalesPage"));
const CreateSalePage            = lazy(() => import("./pages/sales/CreateSalePage"));
const OfferInboxPage            = lazy(() => import("./pages/offers/OfferInboxPage"));
const SentOffersPage            = lazy(() => import("./pages/offers/SentOffersPage"));
const OfferDetailPage           = lazy(() => import("./pages/offers/OfferDetailPage"));
const CreateOfferPage           = lazy(() => import("./pages/offers/CreateOfferPage"));
const DealListPage              = lazy(() => import("./pages/deals/DealListPage"));
const DealDetailPage            = lazy(() => import("./pages/deals/DealDetailPage"));
const FinancePage               = lazy(() => import("./pages/club/FinancePage"));
const ShortlistListPage         = lazy(() => import("./pages/scouting/ShortlistListPage"));
const ShortlistDetailPage       = lazy(() => import("./pages/scouting/ShortlistDetailPage"));
const NotificationsPage         = lazy(() => import("./pages/notifications/NotificationsPage"));
const AdminLayout               = lazy(() => import("./pages/admin/AdminLayout"));
const AdminDashboardPage        = lazy(() => import("./pages/admin/AdminDashboardPage"));
const AdminUsersPage            = lazy(() => import("./pages/admin/AdminUsersPage"));
const AdminClubsPage            = lazy(() => import("./pages/admin/AdminClubsPage"));
const AdminClubDetailPage       = lazy(() => import("./pages/admin/AdminClubDetailPage"));
const AdminPlayersPage          = lazy(() => import("./pages/admin/AdminPlayersPage"));
const AdminPlayerDetailPage     = lazy(() => import("./pages/admin/AdminPlayerDetailPage"));
const AdminSalesPage            = lazy(() => import("./pages/admin/AdminSalesPage"));
const AdminDealsPage            = lazy(() => import("./pages/admin/AdminDealsPage"));
const AdminOffersPage           = lazy(() => import("./pages/admin/AdminOffersPage"));
const AdminWorldImportPage      = lazy(() => import("./pages/admin/AdminWorldImportPage"));
const AdminVendorPage           = lazy(() => import("./pages/admin/AdminVendorPage"));
const AdminAnalyticsPage        = lazy(() => import("./pages/admin/AdminAnalyticsPage"));
const AdminTransferWindowPage   = lazy(() => import("./pages/admin/AdminTransferWindowPage"));
const AdminHealthPage           = lazy(() => import("./pages/admin/AdminHealthPage"));
const AdminAIPage               = lazy(() => import("./pages/admin/AdminAIPage"));

const NotFoundPage = () => (
  <div className="flex min-h-screen items-center justify-center bg-slate-950">
    <div className="text-center">
      <p className="text-5xl font-bold text-slate-700">404</p>
      <p className="mt-3 text-slate-400">Page not found.</p>
      <a href="/" className="mt-4 inline-block text-emerald-400 hover:underline text-sm">
        Go home
      </a>
    </div>
  </div>
);

// ── Single bootstrap + WebSocket connection for the whole app ─────────────────

function GlobalSetup() {
  useAuth();      // Called once here — not inside route wrappers, so it never gets cancelled by navigation
  useWebSocket();
  usePageTracking();
  return null;
}

// ── Route wrappers ────────────────────────────────────────────────────────────

function PublicRoute({ children }: { children: React.ReactNode }) {
  return <AppShell>{children}</AppShell>;
}

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { accessToken, refreshToken, isBootstrapping } = useAuthStore();
  if (isBootstrapping) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-950">
        <Spinner size="lg" />
      </div>
    );
  }
  if (!accessToken && !refreshToken) {
    return <Navigate to="/login" replace />;
  }
  return <AppShell>{children}</AppShell>;
}

// ── Query client ──────────────────────────────────────────────────────────────

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 30_000, retry: 1 },
  },
});

// ── App ───────────────────────────────────────────────────────────────────────

export default function App() {
  return (
    <ErrorBoundary>
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
      <ConfirmProvider>
      <CompareProvider>
      <BrowserRouter>
        <GlobalSetup />
        <CompareBar />
        <Suspense fallback={<div className="flex min-h-screen items-center justify-center bg-slate-950"><Spinner size="lg" /></div>}>
        <Routes>
          {/* ── Auth (no shell) ── */}
          <Route path="/login" element={<LoginPage />} />

          {/* ── Public market ── */}
          <Route path="/players/market"     element={<PublicRoute><PlayerMarketPage /></PublicRoute>} />
          <Route path="/players/market/:id" element={<PublicRoute><PlayerMarketDetailPage /></PublicRoute>} />
          {/* /sales/mine must come before /sales/:id to avoid swallowing "mine" as an id */}
          <Route path="/sales/mine"         element={<ProtectedRoute><MySalesPage /></ProtectedRoute>} />
          <Route path="/sales/new"          element={<ProtectedRoute><CreateSalePage /></ProtectedRoute>} />
          <Route path="/sales"              element={<PublicRoute><SaleListPage /></PublicRoute>} />
          <Route path="/sales/:id"          element={<PublicRoute><SaleDetailPage /></PublicRoute>} />
          <Route path="/clubs"              element={<PublicRoute><ClubListPage /></PublicRoute>} />
          <Route path="/clubs/:id"          element={<PublicRoute><ClubDetailPage /></PublicRoute>} />
          <Route path="/world/teams/:id"    element={<PublicRoute><WorldTeamDetailPage /></PublicRoute>} />
          <Route path="/transfers"          element={<PublicRoute><TransferActivityPage /></PublicRoute>} />
          <Route path="/compare"            element={<PublicRoute><PlayerComparePage /></PublicRoute>} />

          {/* ── Offers (protected) ── */}
          {/* /offers/received and /offers/sent must come before /offers/:id */}
          <Route path="/offers/received" element={<ProtectedRoute><OfferInboxPage /></ProtectedRoute>} />
          <Route path="/offers/sent"     element={<ProtectedRoute><SentOffersPage /></ProtectedRoute>} />
          <Route path="/offers/new"      element={<ProtectedRoute><CreateOfferPage /></ProtectedRoute>} />
          <Route path="/offers/:id"      element={<ProtectedRoute><OfferDetailPage /></ProtectedRoute>} />

          {/* ── Deals (protected) ── */}
          <Route path="/deals"     element={<ProtectedRoute><DealListPage /></ProtectedRoute>} />
          <Route path="/deals/:id" element={<ProtectedRoute><DealDetailPage /></ProtectedRoute>} />

          {/* ── Protected ── */}
          <Route path="/dashboard" element={<ProtectedRoute><DashboardPage /></ProtectedRoute>} />

          {/* ── Club (protected) ── */}
          <Route path="/club"         element={<ProtectedRoute><MyClubPage /></ProtectedRoute>} />
          <Route path="/club/finance" element={<ProtectedRoute><FinancePage /></ProtectedRoute>} />

          {/* ── Scouting (protected) ── */}
          {/* /scouting/shortlists/:id must come before catch-alls */}
          <Route path="/scouting/shortlists/:id" element={<ProtectedRoute><ShortlistDetailPage /></ProtectedRoute>} />
          <Route path="/scouting/shortlists"     element={<ProtectedRoute><ShortlistListPage /></ProtectedRoute>} />

          {/* ── Notifications (protected) ── */}
          <Route path="/notifications" element={<ProtectedRoute><NotificationsPage /></ProtectedRoute>} />
          <Route path="/notifications/preferences" element={<Navigate to="/account" replace />} />

          {/* ── Account (protected) ── */}
          <Route path="/account" element={<ProtectedRoute><AccountSettingsPage /></ProtectedRoute>} />


          {/* ── Admin (superuser only, nested under AdminLayout) ── */}
          <Route path="/admin" element={<ProtectedRoute><AdminLayout /></ProtectedRoute>}>
            <Route index element={<AdminDashboardPage />} />
            <Route path="users"          element={<AdminUsersPage />} />
            <Route path="clubs"          element={<AdminClubsPage />} />
            <Route path="clubs/:id"      element={<AdminClubDetailPage />} />
            <Route path="players"        element={<AdminPlayersPage />} />
            <Route path="players/:id"    element={<AdminPlayerDetailPage />} />
            <Route path="sales"          element={<AdminSalesPage />} />
            <Route path="deals"          element={<AdminDealsPage />} />
            <Route path="offers"         element={<AdminOffersPage />} />
            <Route path="import"         element={<AdminWorldImportPage />} />
            <Route path="vendor"         element={<AdminVendorPage />} />
            <Route path="analytics"      element={<AdminAnalyticsPage />} />
            <Route path="windows"        element={<AdminTransferWindowPage />} />
            <Route path="health"         element={<AdminHealthPage />} />
            <Route path="ai"             element={<AdminAIPage />} />
          </Route>

          {/* ── Defaults ── */}
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
        </Suspense>
      </BrowserRouter>
      </CompareProvider>
      </ConfirmProvider>
      </ToastProvider>
    </QueryClientProvider>
    </ErrorBoundary>
  );
}
