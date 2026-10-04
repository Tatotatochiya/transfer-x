import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import api from "../../lib/api";
import Button from "../../components/ui/Button";
import Badge from "../../components/ui/Badge";
import Card from "../../components/ui/Card";
import PageHeader from "../../components/ui/PageHeader";
import { getApiError } from "../../lib/utils";
import { useAuthStore } from "../../store/auth";
import { useTheme, type Theme } from "../../context/ThemeContext";
import {
  usePreferencesStore,
  type Currency,
  type MarketView,
  type DateFormat,
} from "../../store/preferences";
import NotificationTypesTable from "../../components/notifications/NotificationTypesTable";
import PushSettingsCard from "../../components/notifications/PushSettingsCard";

// ── Segmented control ─────────────────────────────────────────────────────────

function SegmentedControl<T extends string>({
  value,
  options,
  onChange,
}: {
  value: T;
  options: { value: T; label: string }[];
  onChange: (v: T) => void;
}) {
  return (
    <div className="inline-flex rounded-lg bg-surface-inset p-0.5 ring-1 ring-border">
      {options.map((opt) => (
        <button
          key={opt.value}
          onClick={() => onChange(opt.value)}
          className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
            value === opt.value
              ? "bg-surface text-text shadow-sm"
              : "text-text-muted hover:text-text-secondary"
          }`}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}

// ── Section wrapper ───────────────────────────────────────────────────────────

function Section({ id, title, subtitle, children }: { id?: string; title: string; subtitle?: string; children: React.ReactNode }) {
  return (
    <div id={id} className="scroll-mt-20">
      <div className="mb-3">
        <h2 className="text-sm font-semibold text-text">{title}</h2>
        {subtitle && <p className="mt-0.5 text-xs text-text-muted">{subtitle}</p>}
      </div>
      {children}
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function AccountSettingsPage() {
  const { user } = useAuthStore();
  const { hash } = useLocation();

  // "Notification settings" in the account menu links to #notifications;
  // the router doesn't scroll to an anchor by itself. The cards above it
  // load their data after the first paint and push it down, so scroll again
  // as they settle, unless the person has started scrolling themselves.
  useEffect(() => {
    if (!hash) return;
    const target = () => document.getElementById(hash.slice(1));
    let userScrolled = false;
    const stop = () => { userScrolled = true; };
    window.addEventListener("wheel", stop, { passive: true });
    window.addEventListener("touchmove", stop, { passive: true });
    const timers = [0, 300, 800].map((ms) =>
      window.setTimeout(() => { if (!userScrolled) target()?.scrollIntoView({ block: "start" }); }, ms),
    );
    return () => {
      timers.forEach(clearTimeout);
      window.removeEventListener("wheel", stop);
      window.removeEventListener("touchmove", stop);
    };
  }, [hash]);
  const { theme, setTheme } = useTheme();
  const { currency, defaultMarketView, dateFormat, setCurrency, setDefaultMarketView, setDateFormat } =
    usePreferencesStore();

  // ── Password change ───────────────────────────────────────────────────────
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");

  const passwordMutation = useMutation({
    mutationFn: () =>
      api.patch("/auth/me/password", {
        current_password: current,
        new_password: next,
      }),
    onSuccess: () => {
      setCurrent(""); setNext(""); setConfirm("");
    },
  });

  const mismatch = next.length > 0 && confirm.length > 0 && next !== confirm;

  function handlePasswordSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (mismatch || !next) return;
    passwordMutation.mutate();
  }

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="mx-auto max-w-2xl">
      <PageHeader title="Account Settings" />
      <div className="space-y-10">

        {/* Profile */}
        <Card className="flex items-center gap-4">
          <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-surface-inset text-lg font-bold text-text-secondary ring-1 ring-border">
            {user?.email?.[0]?.toUpperCase() ?? "?"}
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-semibold text-text">{user?.email}</p>
            <p className="mt-0.5 text-xs text-text-muted">
              Member since{" "}
              {user?.created_at
                ? new Date(user.created_at).toLocaleDateString("en-GB", {
                    month: "long",
                    year: "numeric",
                  })
                : "—"}
            </p>
          </div>
          {user?.is_superuser && <Badge variant="warning">Admin</Badge>}
        </Card>

        {/* Display preferences */}
        <Section
          title="Display preferences"
          subtitle="Stored locally in your browser."
        >
          <Card noPadding className="divide-y divide-rule-faint">

            <div className="flex items-center justify-between px-5 py-4">
              <div>
                <p className="text-sm text-text">Appearance</p>
                <p className="mt-0.5 text-xs text-text-muted">Colour scheme used across the app</p>
              </div>
              <SegmentedControl<Theme>
                value={theme}
                onChange={setTheme}
                options={[
                  { value: "light", label: "Light" },
                  { value: "dark", label: "Dark" },
                ]}
              />
            </div>

            <div className="flex items-center justify-between px-5 py-4">
              <div>
                <p className="text-sm text-text">Estimates in another currency</p>
                <p className="mt-0.5 text-xs text-text-muted">
                  Amounts are agreed in pounds. Pick a currency to see an estimate next to fees, valuations and budgets.
                </p>
              </div>
              <SegmentedControl<Currency>
                value={currency}
                onChange={setCurrency}
                options={[
                  { value: "GBP", label: "None" },
                  { value: "EUR", label: "€ EUR" },
                  { value: "USD", label: "$ USD" },
                ]}
              />
            </div>

            <div className="flex items-center justify-between px-5 py-4">
              <div>
                <p className="text-sm text-text">Default market view</p>
                <p className="mt-0.5 text-xs text-text-muted">Starting layout on the player market</p>
              </div>
              <SegmentedControl<MarketView>
                value={defaultMarketView}
                onChange={setDefaultMarketView}
                options={[
                  { value: "grid", label: "Grid" },
                  { value: "list", label: "List" },
                ]}
              />
            </div>

            <div className="flex items-center justify-between px-5 py-4">
              <div>
                <p className="text-sm text-text">Date format</p>
                <p className="mt-0.5 text-xs text-text-muted">How timestamps appear in activity feeds</p>
              </div>
              <SegmentedControl<DateFormat>
                value={dateFormat}
                onChange={setDateFormat}
                options={[
                  { value: "absolute", label: "12 Apr" },
                  { value: "relative", label: "3h ago" },
                ]}
              />
            </div>

          </Card>
        </Section>

        {/* Phone notifications (docs/feature_spec/mobile-notifications §7.3) */}
        <Section
          title="On this phone"
          subtitle="Notifications on this device's lock screen, and how each kind arrives."
        >
          <PushSettingsCard />
        </Section>

        {/* Notification preferences — the account menu's "Notification settings" links here */}
        <Section
          id="notifications"
          title="Notification preferences"
          subtitle="Choose which events reach you, and how: in the app, by email, or as a push."
        >
          <NotificationTypesTable />
        </Section>

        {/* Change password */}
        <Section title="Change password">
          <Card>
            <form onSubmit={handlePasswordSubmit} className="space-y-4">
              <div>
                <label className="mb-1 block text-xs text-text-muted">Current password</label>
                <input
                  type="password"
                  required
                  value={current}
                  onChange={(e) => setCurrent(e.target.value)}
                  className="w-full rounded-lg bg-surface px-3 py-2 text-sm text-text ring-1 ring-input-border focus:outline-none focus:ring-accent"
                />
              </div>

              <div>
                <label className="mb-1 block text-xs text-text-muted">New password</label>
                <input
                  type="password"
                  required
                  value={next}
                  onChange={(e) => setNext(e.target.value)}
                  className="w-full rounded-lg bg-surface px-3 py-2 text-sm text-text ring-1 ring-input-border focus:outline-none focus:ring-accent"
                />
              </div>

              <div>
                <label className="mb-1 block text-xs text-text-muted">Confirm new password</label>
                <input
                  type="password"
                  required
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  className={`w-full rounded-lg bg-surface px-3 py-2 text-sm text-text ring-1 focus:outline-none focus:ring-accent ${
                    mismatch ? "ring-danger" : "ring-input-border"
                  }`}
                />
                {mismatch && <p className="mt-1 text-xs text-danger-text">Passwords do not match</p>}
              </div>

              <div className="flex items-center gap-3 pt-1">
                <Button
                  type="submit"
                  variant="primary"
                  size="sm"
                  loading={passwordMutation.isPending}
                  disabled={mismatch || !current || !next || !confirm}
                >
                  Update password
                </Button>
                {passwordMutation.isError && (
                  <p className="text-xs text-danger-text">
                    {getApiError(passwordMutation.error, "Update failed.")}
                  </p>
                )}
                {passwordMutation.isSuccess && (
                  <p className="text-xs text-success-text">Password updated.</p>
                )}
              </div>
            </form>
          </Card>
        </Section>

      </div>
    </div>
  );
}
