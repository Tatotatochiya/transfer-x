import LiteLayout from "./components/lite/LiteLayout";
import { lazy, Suspense, useEffect } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { useAuthStore } from "./store/auth";
import { useAuthBootstrap } from "./hooks/useAuth";
import { useWebSocket } from "./hooks/useWebSocket";
import AppShell from "./components/layout/AppShell";
import Spinner from "./components/ui/Spinner";
import { ToastProvider } from "./context/ToastContext";
import { ConfirmProvider } from "./context/ConfirmContext";
import { ThemeProvider } from "./context/ThemeContext";
import ErrorBoundary from "./components/ErrorBoundary";
import { CompareProvider } from "./context/CompareContext";
import CompareBar from "./components/players/CompareBar";
import { usePageTracking } from "./hooks/usePageTracking";
import { usePreferencesStore } from "./store/preferences";
import { useFxStore } from "./store/fx";

// ── Eager (hot-path) ──────────────────────────────────────────────────────────
import LoginPage from "./pages/auth/LoginPage";
import RegisterPage from "./pages/auth/RegisterPage";
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
const CreateSalePage            = lazy(() => import("./pages/sales/CreateSalePage"));
const OfferDetailPage           = lazy(() => import("./pages/offers/OfferDetailPage"));
const CreateOfferPage           = lazy(() => import("./pages/offers/CreateOfferPage"));
const DealDetailPage            = lazy(() => import("./pages/deals/DealDetailPage"));
const EnquiryDetailPage         = lazy(() => import("./pages/enquiries/EnquiryDetailPage"));
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
const AdminVerificationPage     = lazy(() => import("./pages/admin/AdminVerificationPage"));
const AdminHealthPage           = lazy(() => import("./pages/admin/AdminHealthPage"));
const AdminAIPage               = lazy(() => import("./pages/admin/AdminAIPage"));
const AdminAuditLogPage = lazy(() => import("./pages/admin/AdminAuditLogPage"));
const TeamPage                  = lazy(() => import("./pages/club/TeamPage"));
const SquadCheckPage            = lazy(() => import("./pages/club/SquadCheckPage"));
const BoardPage                 = lazy(() => import("./pages/board/BoardPage"));
const BoardHistoryPage          = lazy(() => import("./pages/board/BoardHistoryPage"));
const AskPage                   = lazy(() => import("./pages/ask/AskPage"));
const ApprovalsPage             = lazy(() => import("./pages/club/ApprovalsPage"));
const AcceptInvitePage          = lazy(() => import("./pages/auth/AcceptInvitePage"));
const ResetPasswordPage         = lazy(() => import("./pages/auth/ResetPasswordPage"));
const LiteConfirmPage           = lazy(() => import("./pages/lite/LiteConfirmPage"));
const JoinClubPage              = lazy(() => import("./pages/auth/JoinClubPage"));
const JoinPlayerPage            = lazy(() => import("./pages/auth/JoinPlayerPage"));
const LiteHomePage              = lazy(() => import("./pages/lite/LiteHomePage"));
const LiteOffersPage            = lazy(() => import("./pages/lite/LiteOffersPage"));
const LiteAskPage               = lazy(() => import("./pages/lite/LiteAskPage"));
const LiteBuyPositionPage       = lazy(() => import("./pages/lite/LiteBuyPage").then((m) => ({ default: m.LiteBuyPositionPage })));
const LiteBuyBudgetPage         = lazy(() => import("./pages/lite/LiteBuyPage").then((m) => ({ default: m.LiteBuyBudgetPage })));
const LiteBuyResultsPage        = lazy(() => import("./pages/lite/LiteBuyPage").then((m) => ({ default: m.LiteBuyResultsPage })));
const LiteBidPage               = lazy(() => import("./pages/lite/LiteBidPage"));
const LiteSentPage = lazy(() => import("./pages/lite/LiteSentPage"));
const LiteOfferCardPage         = lazy(() => import("./pages/lite/LiteOfferCardPage"));
const LiteApprovalPage          = lazy(() => import("./pages/lite/LiteApprovalPage"));
const AgentDashboardPage        = lazy(() => import("./pages/agent/AgentDashboardPage"));
const AgentPipelinePage         = lazy(() => import("./pages/agent/AgentPipelinePage"));
const AgentProfilePage          = lazy(() => import("./pages/agent/AgentProfilePage"));
const AgentClientPage           = lazy(() => import("./pages/agent/AgentClientPage"));
const AgentRosterImportPage     = lazy(() => import("./pages/agent/AgentRosterImportPage"));
const PlayerProfilePage         = lazy(() => import("./pages/player/PlayerProfilePage"));

const NotFoundPage = () => (
  <div className="flex min-h-screen items-center justify-center bg-page">
    <div className="text-center">
      <p className="text-5xl font-bold text-text-muted">404</p>
      <p className="mt-3 text-text-muted">Page not found.</p>
      <a href="/" className="mt-4 inline-block text-accent hover:underline text-sm">
        Go home
      </a>
    </div>
  </div>
);

// ── Single bootstrap + WebSocket connection for the whole app ─────────────────

function GlobalSetup() {
  useAuthBootstrap(); // Once, here only — not inside route wrappers, so it never gets cancelled by navigation
  useWebSocket();
  usePageTracking();
  // Rates for the "≈ €" estimates, only once someone asks for them.
  const currency = usePreferencesStore((s) => s.currency);
  useEffect(() => {
    if (currency !== "GBP") void useFxStore.getState().load();
  }, [currency]);
  return null;
}

// ── Route wrappers ────────────────────────────────────────────────────────────

function PublicRoute({ children }: { children: React.ReactNode }) {
  return <AppShell>{children}</AppShell>;
}

const LoadingScreen = () => (
  <div className="flex min-h-screen items-center justify-center bg-page">
    <Spinner size="lg" />
  </div>
);

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { accessToken, refreshToken, isBootstrapping } = useAuthStore();
  if (isBootstrapping) return <LoadingScreen />;
  if (!accessToken && !refreshToken) return <Navigate to="/login" replace />;
  return <AppShell>{children}</AppShell>;
}

function ClubRoute({ children }: { children: React.ReactNode }) {
  const { user, accessToken, refreshToken, isBootstrapping } = useAuthStore();
  if (isBootstrapping) return <LoadingScreen />;
  if (!accessToken && !refreshToken) return <Navigate to="/login" replace />;
  if (user && user.user_type !== "CLUB" && !user.is_superuser) return <Navigate to="/" replace />;
  return <AppShell>{children}</AppShell>;
}

/** Lite mode (docs/feature_spec/lite-mode): club members only, in the Lite
 *  shell rather than the full app's. */
function LiteRoute({ children }: { children: React.ReactNode }) {
  const { user, accessToken, refreshToken, isBootstrapping } = useAuthStore();
  if (isBootstrapping) return <LoadingScreen />;
  if (!accessToken && !refreshToken) return <Navigate to="/login" replace />;
  if (user && user.user_type !== "CLUB") return <Navigate to="/" replace />;
  return <LiteLayout>{children}</LiteLayout>;
}

function AgentRoute({ children }: { children: React.ReactNode }) {
  const { user, accessToken, refreshToken, isBootstrapping } = useAuthStore();
  if (isBootstrapping) return <LoadingScreen />;
  if (!accessToken && !refreshToken) return <Navigate to="/login" replace />;
  if (user && user.user_type !== "AGENT") return <Navigate to="/" replace />;
  return <AppShell>{children}</AppShell>;
}

function PlayerRoute({ children }: { children: React.ReactNode }) {
  const { user, accessToken, refreshToken, isBootstrapping } = useAuthStore();
  if (isBootstrapping) return <LoadingScreen />;
  if (!accessToken && !refreshToken) return <Navigate to="/login" replace />;
  if (user && user.user_type !== "PLAYER") return <Navigate to="/" replace />;
  return <AppShell>{children}</AppShell>;
}

function SmartRedirect() {
  const { user, accessToken, refreshToken, isBootstrapping } = useAuthStore();
  if (isBootstrapping) return <LoadingScreen />;
  if (!accessToken && !refreshToken) return <Navigate to="/login" replace />;
  // TransferX staff start on the admin panel, whatever their account type.
  if (user?.is_superuser) return <Navigate to="/admin" replace />;
  if (user?.user_type === "AGENT") return <Navigate to="/agent/pipeline" replace />;
  if (user?.user_type === "PLAYER") return <Navigate to="/player/profile" replace />;
  return <Navigate to="/dashboard" replace />;
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
    <ThemeProvider>
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
      <ConfirmProvider>
      <CompareProvider>
      <BrowserRouter>
        <GlobalSetup />
        <CompareBar />
        <Suspense fallback={<div className="flex min-h-screen items-center justify-center bg-page"><Spinner size="lg" /></div>}>
        <Routes>
          {/* ── Auth (no shell) ── */}
          <Route path="/login"    element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          {/* Staff invitation acceptance — public tokenised link, not open signup (D6) */}
          <Route path="/accept-invite" element={<AcceptInvitePage />} />
          <Route path="/reset-password" element={<ResetPasswordPage />} />
          {/* A decision from an email (Lite L8): works signed out, for saying no. */}
          <Route path="/lite/confirm/:token" element={<LiteConfirmPage />} />
          {/* A view-as tab arrives here; the token was taken from the URL by the auth store. */}
          <Route path="/view-as" element={<Navigate to="/dashboard" replace />} />
          <Route path="/join" element={<JoinClubPage />} />
          <Route path="/join/player" element={<JoinPlayerPage />} />
          <Route path="/lite" element={<LiteRoute><LiteHomePage /></LiteRoute>} />
          <Route path="/lite/offers" element={<LiteRoute><LiteOffersPage /></LiteRoute>} />
          <Route path="/lite/offers/:offerId" element={<LiteRoute><LiteOfferCardPage /></LiteRoute>} />
          <Route path="/lite/approvals/:id" element={<LiteRoute><LiteApprovalPage /></LiteRoute>} />
          <Route path="/lite/bid" element={<LiteRoute><LiteBidPage /></LiteRoute>} />
          <Route path="/lite/actions/:actionId" element={<LiteRoute><LiteSentPage /></LiteRoute>} />
          <Route path="/lite/ask" element={<LiteRoute><LiteAskPage /></LiteRoute>} />
          <Route path="/lite/buy" element={<LiteRoute><LiteBuyPositionPage /></LiteRoute>} />
          <Route path="/lite/buy/budget" element={<LiteRoute><LiteBuyBudgetPage /></LiteRoute>} />
          <Route path="/lite/buy/results" element={<LiteRoute><LiteBuyResultsPage /></LiteRoute>} />

          {/* ── Public market ── */}
          <Route path="/players/market"     element={<PublicRoute><PlayerMarketPage /></PublicRoute>} />
          <Route path="/players/market/:id" element={<PublicRoute><PlayerMarketDetailPage /></PublicRoute>} />
          {/* /sales/mine must come before /sales/:id to avoid swallowing "mine" as an id */}
          {/* The Transfers board replaced these list pages (product ADR 0008). */}
          <Route path="/sales/mine"         element={<Navigate to="/board?side=SELLING" replace />} />
          <Route path="/sales/new"          element={<ClubRoute><CreateSalePage /></ClubRoute>} />
          <Route path="/sales"              element={<PublicRoute><SaleListPage /></PublicRoute>} />
          <Route path="/sales/:id"          element={<PublicRoute><SaleDetailPage /></PublicRoute>} />
          <Route path="/clubs"              element={<PublicRoute><ClubListPage /></PublicRoute>} />
          <Route path="/clubs/:id"          element={<PublicRoute><ClubDetailPage /></PublicRoute>} />
          <Route path="/world/teams/:id"    element={<PublicRoute><WorldTeamDetailPage /></PublicRoute>} />
          <Route path="/transfers"          element={<PublicRoute><TransferActivityPage /></PublicRoute>} />
          <Route path="/compare"            element={<PublicRoute><PlayerComparePage /></PublicRoute>} />

          {/* ── Offers (club-only) ── */}
          {/* /offers/received and /offers/sent must come before /offers/:id */}
          <Route path="/offers/received" element={<Navigate to="/board?side=SELLING" replace />} />
          <Route path="/offers/sent"     element={<Navigate to="/board?side=BUYING" replace />} />
          <Route path="/offers/new"      element={<ClubRoute><CreateOfferPage /></ClubRoute>} />
          <Route path="/offers/:id"      element={<ProtectedRoute><OfferDetailPage /></ProtectedRoute>} />

          {/* ── Deals (club-only list; deal room accessible to all parties) ── */}
          <Route path="/deals"     element={<Navigate to="/board" replace />} />
          <Route path="/enquiries"     element={<Navigate to="/board" replace />} />
          <Route path="/enquiries/:id" element={<ClubRoute><EnquiryDetailPage /></ClubRoute>} />
          <Route path="/deals/:id" element={<ProtectedRoute><DealDetailPage /></ProtectedRoute>} />

          {/* ── Club (protected, club-only) ── */}
          <Route path="/dashboard"      element={<ClubRoute><DashboardPage /></ClubRoute>} />
          <Route path="/club"           element={<ClubRoute><MyClubPage /></ClubRoute>} />
          <Route path="/club/finance"   element={<ClubRoute><FinancePage /></ClubRoute>} />
          <Route path="/club/team"      element={<ClubRoute><TeamPage /></ClubRoute>} />
          <Route path="/club/squad-check" element={<ClubRoute><SquadCheckPage /></ClubRoute>} />
          <Route path="/board" element={<ClubRoute><BoardPage /></ClubRoute>} />
          <Route path="/board/history" element={<ClubRoute><BoardHistoryPage /></ClubRoute>} />
          <Route path="/ask" element={<ClubRoute><AskPage /></ClubRoute>} />
          <Route path="/club/approvals" element={<ClubRoute><ApprovalsPage /></ClubRoute>} />

          {/* ── Agent portal ── */}
          <Route path="/agent/pipeline"           element={<AgentRoute><AgentPipelinePage /></AgentRoute>} />
          <Route path="/agent/dashboard"          element={<AgentRoute><AgentDashboardPage /></AgentRoute>} />
          <Route path="/agent/profile"            element={<AgentRoute><AgentProfilePage /></AgentRoute>} />
          <Route path="/agent/clients/:mandateId" element={<AgentRoute><AgentClientPage /></AgentRoute>} />
          <Route path="/agent/roster/import"      element={<AgentRoute><AgentRosterImportPage /></AgentRoute>} />

          {/* ── Player portal ── */}
          <Route path="/player/profile" element={<PlayerRoute><PlayerProfilePage /></PlayerRoute>} />

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
            <Route path="verification"   element={<AdminVerificationPage />} />
            <Route path="health"         element={<AdminHealthPage />} />
            <Route path="ai"             element={<AdminAIPage />} />
            <Route path="audit"          element={<AdminAuditLogPage />} />
          </Route>

          {/* ── Defaults ── */}
          <Route path="/" element={<SmartRedirect />} />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
        </Suspense>
      </BrowserRouter>
      </CompareProvider>
      </ConfirmProvider>
      </ToastProvider>
    </QueryClientProvider>
    </ThemeProvider>
    </ErrorBoundary>
  );
}
