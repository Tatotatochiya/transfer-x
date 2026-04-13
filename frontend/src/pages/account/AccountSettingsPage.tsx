import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "../../lib/api";
import Button from "../../components/ui/Button";
import Badge from "../../components/ui/Badge";
import Spinner from "../../components/ui/Spinner";
import { getApiError } from "../../lib/utils";
import { useAuthStore } from "../../store/auth";
import {
  usePreferencesStore,
  type Currency,
  type MarketView,
  type DateFormat,
} from "../../store/preferences";
import type { NotificationPreferencesResponse } from "../../types/api";

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
    <div className="inline-flex rounded-lg bg-slate-800 p-0.5 ring-1 ring-white/[0.06]">
      {options.map((opt) => (
        <button
          key={opt.value}
          onClick={() => onChange(opt.value)}
          className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
            value === opt.value
              ? "bg-slate-700 text-white shadow-sm"
              : "text-slate-400 hover:text-slate-200"
          }`}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}

// ── Notification type labels / groups ─────────────────────────────────────────

const TYPE_LABELS: Record<string, string> = {
  OUTBID:               "Outbid on an auction",
  OFFER_RECEIVED:       "Offer received",
  OFFER_ACCEPTED:       "Offer accepted",
  OFFER_REJECTED:       "Offer rejected",
  OFFER_COUNTERED:      "Counter-offer received",
  OFFER_WITHDRAWN:      "Offer withdrawn by other party",
  OFFER_EXPIRING:       "Offer expiring soon",
  OFFER_MESSAGE:        "New message in a negotiation",
  AUCTION_BID_RECEIVED: "Bid received on your auction",
  AUCTION_ENDING:       "Auction ending soon",
  AUCTION_BID_ACCEPTED: "Your auction bid accepted",
  DEAL_COMPLETED:       "Deal completed",
  DEAL_COLLAPSED:       "Deal collapsed",
  PLAYER_AVAILABLE:     "Shortlisted player becomes available",
};

const TYPE_GROUPS: { label: string; types: string[] }[] = [
  {
    label: "Auctions",
    types: ["AUCTION_BID_RECEIVED", "AUCTION_ENDING", "AUCTION_BID_ACCEPTED", "OUTBID"],
  },
  {
    label: "Offers",
    types: ["OFFER_RECEIVED", "OFFER_ACCEPTED", "OFFER_REJECTED", "OFFER_COUNTERED", "OFFER_WITHDRAWN", "OFFER_EXPIRING", "OFFER_MESSAGE"],
  },
  {
    label: "Deals",
    types: ["DEAL_COMPLETED", "DEAL_COLLAPSED"],
  },
  {
    label: "Scouting",
    types: ["PLAYER_AVAILABLE"],
  },
];

// ── Toggle ─────────────────────────────────────────────────────────────────────

function Toggle({ enabled, disabled, onToggle, label }: { enabled: boolean; disabled: boolean; onToggle: () => void; label: string }) {
  return (
    <button
      disabled={disabled}
      onClick={onToggle}
      className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors focus:outline-none disabled:opacity-50 ${
        enabled ? "bg-emerald-500" : "bg-slate-600"
      }`}
      aria-label={label}
    >
      <span
        className={`pointer-events-none inline-block h-4 w-4 rounded-full bg-white shadow ring-0 transition-transform ${
          enabled ? "translate-x-4" : "translate-x-0"
        }`}
      />
    </button>
  );
}

// ── Section wrapper ───────────────────────────────────────────────────────────

function Section({ title, subtitle, children }: { title: string; subtitle?: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="mb-3">
        <h2 className="text-sm font-semibold text-white">{title}</h2>
        {subtitle && <p className="mt-0.5 text-xs text-slate-500">{subtitle}</p>}
      </div>
      {children}
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function AccountSettingsPage() {
  const { user } = useAuthStore();
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

  // ── Notification preferences ──────────────────────────────────────────────
  const queryClient = useQueryClient();

  const { data: notifData, isLoading: notifLoading } = useQuery<NotificationPreferencesResponse>({
    queryKey: ["notifications", "preferences"],
    queryFn: () =>
      api.get<NotificationPreferencesResponse>("/notifications/preferences").then((r) => r.data),
  });

  const notifMutation = useMutation({
    mutationFn: ({ type, enabled }: { type: string; enabled: boolean }) =>
      api
        .patch<NotificationPreferencesResponse>(`/notifications/preferences/${type}`, { enabled })
        .then((r) => r.data),
    onSuccess: (newData) => {
      queryClient.setQueryData(["notifications", "preferences"], newData);
    },
  });

  const prefMap = Object.fromEntries(
    (notifData?.preferences ?? []).map((p) => [p.type, p.enabled])
  );

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="mx-auto max-w-2xl space-y-10">

      {/* Profile */}
      <div className="rounded-xl bg-slate-900 ring-1 ring-white/[0.08] px-6 py-5 flex items-center gap-4">
        <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-slate-800 text-lg font-bold text-slate-300 ring-1 ring-white/10">
          {user?.email?.[0]?.toUpperCase() ?? "?"}
        </div>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-semibold text-white">{user?.email}</p>
          <p className="mt-0.5 text-xs text-slate-500">
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
      </div>

      {/* Display preferences */}
      <Section
        title="Display preferences"
        subtitle="Stored locally in your browser."
      >
        <div className="rounded-xl bg-slate-900 ring-1 ring-white/[0.08] divide-y divide-white/[0.04]">

          <div className="flex items-center justify-between px-5 py-4">
            <div>
              <p className="text-sm text-slate-200">Currency</p>
              <p className="mt-0.5 text-xs text-slate-500">Applied to all transfer fees and wages</p>
            </div>
            <SegmentedControl<Currency>
              value={currency}
              onChange={setCurrency}
              options={[
                { value: "GBP", label: "£ GBP" },
                { value: "EUR", label: "€ EUR" },
                { value: "USD", label: "$ USD" },
              ]}
            />
          </div>

          <div className="flex items-center justify-between px-5 py-4">
            <div>
              <p className="text-sm text-slate-200">Default market view</p>
              <p className="mt-0.5 text-xs text-slate-500">Starting layout on the player market</p>
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
              <p className="text-sm text-slate-200">Date format</p>
              <p className="mt-0.5 text-xs text-slate-500">How timestamps appear in activity feeds</p>
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

        </div>
      </Section>

      {/* Notification preferences */}
      <Section
        title="Notification preferences"
        subtitle="Choose which events trigger a notification."
      >
        {notifLoading ? (
          <div className="flex items-center justify-center py-8">
            <Spinner size="sm" />
          </div>
        ) : (
          <div className="space-y-3">
            {TYPE_GROUPS.map((group) => (
              <div
                key={group.label}
                className="rounded-xl bg-slate-900 ring-1 ring-white/[0.08] overflow-hidden"
              >
                <div className="border-b border-white/[0.06] px-5 py-2.5">
                  <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                    {group.label}
                  </p>
                </div>
                <div className="divide-y divide-white/[0.04]">
                  {group.types.map((type) => {
                    const enabled = prefMap[type] ?? true;
                    const isPending =
                      notifMutation.isPending &&
                      (notifMutation.variables as { type: string } | undefined)?.type === type;
                    return (
                      <div key={type} className="flex items-center justify-between px-5 py-3">
                        <span className="text-sm text-slate-200">
                          {TYPE_LABELS[type] ?? type}
                        </span>
                        <Toggle
                          enabled={enabled}
                          disabled={isPending}
                          onToggle={() => notifMutation.mutate({ type, enabled: !enabled })}
                          label={enabled ? `Disable ${type}` : `Enable ${type}`}
                        />
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
            {notifMutation.isError && (
              <p className="text-sm text-red-400">
                {getApiError(notifMutation.error, "Failed to save preference.")}
              </p>
            )}
          </div>
        )}
      </Section>

      {/* Change password */}
      <Section title="Change password">
        <div className="rounded-xl bg-slate-900 ring-1 ring-white/[0.08] px-6 py-5">
          <form onSubmit={handlePasswordSubmit} className="space-y-4">
            <div>
              <label className="mb-1 block text-xs text-slate-400">Current password</label>
              <input
                type="password"
                required
                value={current}
                onChange={(e) => setCurrent(e.target.value)}
                className="w-full rounded-lg bg-slate-800 px-3 py-2 text-sm text-white ring-1 ring-white/10 focus:outline-none focus:ring-amber-500"
              />
            </div>

            <div>
              <label className="mb-1 block text-xs text-slate-400">New password</label>
              <input
                type="password"
                required
                value={next}
                onChange={(e) => setNext(e.target.value)}
                className="w-full rounded-lg bg-slate-800 px-3 py-2 text-sm text-white ring-1 ring-white/10 focus:outline-none focus:ring-amber-500"
              />
            </div>

            <div>
              <label className="mb-1 block text-xs text-slate-400">Confirm new password</label>
              <input
                type="password"
                required
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                className={`w-full rounded-lg bg-slate-800 px-3 py-2 text-sm text-white ring-1 focus:outline-none focus:ring-amber-500 ${
                  mismatch ? "ring-red-500" : "ring-white/10"
                }`}
              />
              {mismatch && <p className="mt-1 text-xs text-red-400">Passwords do not match</p>}
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
                <p className="text-xs text-red-400">
                  {getApiError(passwordMutation.error, "Update failed.")}
                </p>
              )}
              {passwordMutation.isSuccess && (
                <p className="text-xs text-emerald-400">Password updated.</p>
              )}
            </div>
          </form>
        </div>
      </Section>

    </div>
  );
}
