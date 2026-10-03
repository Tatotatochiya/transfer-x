import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import api from "../../lib/api";
import { getApiError } from "../../lib/utils";
import {
  subscribe,
  unsubscribe,
  usePushState,
  useRefreshPush,
  useThisDeviceEndpoint,
  type PushState,
} from "../../lib/push";
import { usePreferences, useUpdatePreferences, type PushMode, type PushSettings } from "../../hooks/usePreferences";
import { useToast } from "../../context/ToastContext";
import type { PushDevice } from "../../types/api";
import Button from "../ui/Button";
import Card from "../ui/Card";
import Spinner from "../ui/Spinner";
import InstallGuide from "./InstallGuide";
import { MiniToggle } from "./NotificationTypesTable";

/**
 * "On this phone": turn notifications on for this device, choose how each
 * tier arrives, quiet hours, hiding amounts on the lock screen, and the
 * other devices that get pushes (docs/feature_spec/mobile-notifications §7.3, 5c).
 */

const MODES: { value: PushMode; label: string }[] = [
  { value: "SOUND", label: "Sound" },
  { value: "SILENT", label: "Silent" },
  { value: "OFF", label: "Off" },
];

function ModeControl({ value, onChange, label }: { value: PushMode; onChange: (m: PushMode) => void; label: string }) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex shrink-0 rounded-lg bg-surface-inset p-0.5 ring-1 ring-border">
      {MODES.map((m) => (
        <button
          key={m.value}
          type="button"
          role="radio"
          aria-checked={value === m.value}
          onClick={() => onChange(m.value)}
          className={`rounded-md px-2.5 py-1 text-xs font-medium transition-colors ${
            value === m.value ? "bg-surface text-text shadow-sm" : "text-text-muted hover:text-text-secondary"
          }`}
        >
          {m.label}
        </button>
      ))}
    </div>
  );
}

const hhmm = (t: string) => t.slice(0, 5);

function TimeInput({ value, onCommit, label }: { value: string; onCommit: (v: string) => void; label: string }) {
  const [draft, setDraft] = useState(hhmm(value));
  return (
    <input
      type="time"
      aria-label={label}
      value={draft}
      onChange={(e) => setDraft(e.target.value)}
      onBlur={() => { if (/^\d\d:\d\d$/.test(draft) && draft !== hhmm(value)) onCommit(draft); }}
      className="w-[6.5rem] rounded-md bg-surface px-2 py-1 text-sm tabular-nums text-text ring-1 ring-inset ring-input-border focus:outline-none focus:ring-accent"
    />
  );
}

const MODE_SUMMARY: Record<PushMode, string> = {
  SOUND: "Straight away, with sound",
  SILENT: "Straight away, silent",
  OFF: "Not pushed",
};

function Dot({ className }: { className: string }) {
  return <span aria-hidden className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${className}`} />;
}

function Row({ children }: { children: React.ReactNode }) {
  return <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 px-5 py-3.5">{children}</div>;
}

// ── This device ───────────────────────────────────────────────────────────────

function ThisDevice({ state, onTurnOn, busy, device, onTest, onTurnOff, onShowGuide }: {
  state: PushState;
  onShowGuide: () => void;
  onTurnOn: () => void;
  busy: boolean;
  device: PushDevice | undefined;
  onTest: () => void;
  onTurnOff: () => void;
}) {
  if (state === "unsupported") {
    return <p className="text-sm text-text-secondary">This browser can't show notifications. You'll still get email.</p>;
  }
  if (state === "not-configured") {
    return <p className="text-sm text-text-secondary">Phone notifications aren't switched on for TransferX yet. You'll still get email.</p>;
  }
  if (state === "needs-install") {
    return (
      <div className="space-y-2 text-sm text-text-secondary">
        <p className="font-semibold text-text">Add TransferX to your Home Screen first</p>
        <p>On iPhone and iPad, notifications only work in the TransferX app opened from the Home Screen.</p>
        <Button variant="primary" size="sm" onClick={onShowGuide}>Show me how</Button>
      </div>
    );
  }
  if (state === "denied") {
    return (
      <p className="text-sm text-text-secondary">
        <span className="font-semibold text-danger-text">Blocked.</span> Notifications are blocked for TransferX.
        Turn them on in your browser's or phone's settings, then come back.
      </p>
    );
  }
  if (state === "granted-subscribed") {
    return (
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-text">{device?.label ?? "This device"}</p>
          <p className="text-xs font-semibold text-success-text">On</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="secondary" size="sm" onClick={onTest}>Send a test notification</Button>
          <Button variant="ghost" size="sm" onClick={onTurnOff} loading={busy}>Turn off</Button>
        </div>
      </div>
    );
  }
  // default, granted-unsubscribed
  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div className="min-w-0">
        <p className="text-sm text-text">Get offers and approvals on this device as they happen.</p>
        <p className="text-xs text-text-muted">Off</p>
      </div>
      <Button variant="primary" size="sm" onClick={onTurnOn} loading={busy}>Turn on notifications</Button>
    </div>
  );
}

// ── Card ──────────────────────────────────────────────────────────────────────

export default function PushSettingsCard() {
  const { addToast } = useToast();
  const refresh = useRefreshPush();
  const { data: state, isLoading: stateLoading } = usePushState();
  const { data: thisEndpoint } = useThisDeviceEndpoint();
  const { data: prefs } = usePreferences();
  const update = useUpdatePreferences();
  const [busy, setBusy] = useState(false);
  const [guide, setGuide] = useState(false);

  const { data: devices, refetch: refetchDevices } = useQuery<PushDevice[]>({
    queryKey: ["notifications", "push", "devices"],
    queryFn: () => api.get<PushDevice[]>("/notifications/push/subscriptions").then((r) => r.data),
  });

  const save = (body: Partial<PushSettings>) =>
    update.mutate(body, { onError: (e) => addToast(getApiError(e, "Couldn't save that setting."), "error") });

  // Called straight from the click: iOS asks for permission only from a tap.
  async function turnOn() {
    setBusy(true);
    try {
      const result = await subscribe();
      if (result === "granted-subscribed") addToast("Notifications are on for this device", "success");
      else if (result === "denied") addToast("Notifications are blocked for TransferX in this browser's settings.", "error");
    } catch (e) {
      addToast(getApiError(e, "Couldn't turn notifications on."), "error");
    } finally {
      setBusy(false);
      refresh();
    }
  }

  async function turnOff() {
    setBusy(true);
    try {
      await unsubscribe();
    } finally {
      setBusy(false);
      refresh();
    }
  }

  const test = useMutation({
    mutationFn: () =>
      api.post<{ sent: boolean; reason: string }>("/notifications/push/test", { endpoint: thisEndpoint }).then((r) => r.data),
    onSuccess: (r) =>
      addToast(r.sent ? "Test sent. It should arrive in a few seconds." : "The test couldn't be delivered to this device.", r.sent ? "success" : "error"),
    onError: (e) => addToast(getApiError(e, "Couldn't send the test."), "error"),
  });

  const remove = useMutation({
    mutationFn: (endpoint: string) => api.delete("/notifications/push/subscriptions", { data: { endpoint } }),
    onSuccess: () => refetchDevices(),
  });

  const thisDevice = devices?.find((d) => d.endpoint === thisEndpoint);
  const others = (devices ?? []).filter((d) => d.endpoint !== thisEndpoint);
  // Settings apply to every device, so show them whenever push can work here
  // or another device already gets pushes.
  const showSettings = !!prefs && (others.length > 0 || state === "granted-subscribed" || state === "granted-unsubscribed" || state === "default");

  return (
    <Card noPadding className="divide-y divide-rule-faint">
      <div className="px-5 py-4">
        {stateLoading || !state ? (
          <div className="flex justify-center py-2"><Spinner size="sm" /></div>
        ) : (
          <ThisDevice
            state={state}
            onTurnOn={turnOn}
            busy={busy}
            device={thisDevice}
            onTest={() => test.mutate()}
            onTurnOff={turnOff}
            onShowGuide={() => setGuide(true)}
          />
        )}
      </div>

      {showSettings && prefs && (
        <>
          <Row>
            <div className="flex min-w-0 flex-[1_1_16rem] gap-2.5">
              <Dot className="bg-danger" />
              <div>
                <p className="text-sm font-semibold text-text">Your move</p>
                <p className="text-xs text-text-muted">Offers, counters and approvals that need you. {MODE_SUMMARY[prefs.push_your_move]}.</p>
              </div>
            </div>
            <ModeControl label="Your move" value={prefs.push_your_move} onChange={(m) => save({ push_your_move: m })} />
          </Row>
          <Row>
            <div className="flex min-w-0 flex-[1_1_16rem] gap-2.5">
              <Dot className="bg-warning-fill" />
              <div>
                <p className="text-sm font-semibold text-text">Heads-up</p>
                <p className="text-xs text-text-muted">Outbid, messages, auctions ending. {MODE_SUMMARY[prefs.push_heads_up]}.</p>
              </div>
            </div>
            <ModeControl label="Heads-up" value={prefs.push_heads_up} onChange={(m) => save({ push_heads_up: m })} />
          </Row>
          <Row>
            <div className="flex min-w-0 flex-[1_1_16rem] gap-2.5">
              <Dot className="bg-text-muted" />
              <div>
                <p className="text-sm font-semibold text-text">FYI, and a morning summary</p>
                <p className="text-xs text-text-muted">
                  Completed deals, loans and the like stay in the app. One push each morning says what's waiting on you, only when something is.
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              {prefs.push_summary && (
                <TimeInput key={`m${prefs.summary_local_time}`} label="Morning summary time" value={prefs.summary_local_time}
                  onCommit={(v) => save({ summary_local_time: v })} />
              )}
              <MiniToggle
                value={prefs.push_summary}
                disabled={update.isPending}
                onChange={() => save({ push_summary: !prefs.push_summary })}
                label="Morning summary"
              />
            </div>
          </Row>
          <Row>
            <div className="min-w-0 flex-[1_1_16rem]">
              <p className="text-sm font-semibold text-text">Quiet hours</p>
              <p className="text-xs text-text-muted">
                Held until morning. Something of yours with a deadline before then still comes through.
              </p>
            </div>
            <div className="flex items-center gap-2">
              {prefs.quiet_hours_enabled && (
                <>
                  <TimeInput key={`s${prefs.quiet_start}`} label="Quiet hours start" value={prefs.quiet_start} onCommit={(v) => save({ quiet_start: v })} />
                  <span className="text-sm text-text-muted">to</span>
                  <TimeInput key={`e${prefs.quiet_end}`} label="Quiet hours end" value={prefs.quiet_end} onCommit={(v) => save({ quiet_end: v })} />
                </>
              )}
              <MiniToggle
                value={prefs.quiet_hours_enabled}
                disabled={update.isPending}
                onChange={() => save({ quiet_hours_enabled: !prefs.quiet_hours_enabled })}
                label="Quiet hours"
              />
            </div>
          </Row>
          <Row>
            <div className="min-w-0 flex-[1_1_16rem]">
              <p className="text-sm font-semibold text-text">Hide amounts on the lock screen</p>
              <p className="text-xs text-text-muted">
                Pushes say only what happened, such as "New offer received". No figures, clubs or players until you open TransferX.
              </p>
            </div>
            <MiniToggle
              value={prefs.push_hide_amounts}
              disabled={update.isPending}
              onChange={() => save({ push_hide_amounts: !prefs.push_hide_amounts })}
              label="Hide amounts on the lock screen"
            />
          </Row>
          <p className="px-5 py-2.5 text-xs text-text-muted">Times are in {prefs.timezone.replace(/_/g, " ")}.</p>
        </>
      )}

      {others.length > 0 && (
        <div className="px-5 py-3.5">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-text-muted">Other devices</p>
          <ul className="space-y-2">
            {others.map((d) => (
              <li key={d.id} className="flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <p className="truncate text-sm text-text">{d.label}</p>
                  <p className="text-xs text-text-muted">
                    Added {new Date(d.created_at).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" })}
                  </p>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  loading={remove.isPending && remove.variables === d.endpoint}
                  onClick={() => remove.mutate(d.endpoint)}
                >
                  Remove
                </Button>
              </li>
            ))}
          </ul>
        </div>
      )}
      <InstallGuide open={guide} onClose={() => setGuide(false)} />
    </Card>
  );
}
