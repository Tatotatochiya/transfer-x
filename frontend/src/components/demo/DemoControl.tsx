import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import api from "../../lib/api";
import { useAuth } from "../../hooks/useAuth";
import { useAuthStore } from "../../store/auth";
import { useConfirm } from "../../context/ConfirmContext";
import { useToast } from "../../context/ToastContext";
import { formatDate, getApiError } from "../../lib/utils";
import type { DemoRun } from "../../types/api";

interface HouseClub {
  id: string;
  name: string;
  crest_url: string | null;
  personality: string | null;
}

/**
 * Demo mode (backend app/demo), for testers: start a demo, play a house
 * club in its own tab, and put everything back with Reset. Bottom-right on
 * every page, full app and Lite. Hidden from everyone else, and inside a
 * view-as or play-as tab.
 */
export default function DemoControl() {
  const { canDemo, demoPlayedBy, viewedBy } = useAuth();
  const inTab = useAuthStore((s) => s.viewAs);
  if (!canDemo || demoPlayedBy || viewedBy || inTab) return null;
  return <DemoPill />;
}

function DemoPill() {
  const queryClient = useQueryClient();
  const confirm = useConfirm();
  const { addToast } = useToast();
  const [open, setOpen] = useState(false);

  const { data } = useQuery<{ can_demo: boolean; run: DemoRun | null }>({
    queryKey: ["demo", "run"],
    queryFn: () => api.get("/demo/run").then((r) => r.data),
    refetchInterval: 15_000,
  });
  const run = data?.run ?? null;
  const houses = useQuery<HouseClub[]>({
    queryKey: ["demo", "house-clubs"],
    queryFn: () => api.get("/demo/house-clubs").then((r) => r.data),
    enabled: open && !!run,
  });

  const done = () => {
    setOpen(false);
    queryClient.invalidateQueries();  // a reset can change anything on screen
  };
  const start = useMutation({
    mutationFn: () => api.post("/demo/run").then((r) => r.data),
    onSuccess: () => { done(); addToast("Demo started. Everything you do from now on can be reset.", "success"); },
    onError: (err) => addToast(getApiError(err, "Couldn't start a demo."), "error"),
  });
  const reset = useMutation({
    mutationFn: () => api.post<{ undone: number; skipped: unknown[] }>("/demo/run/reset").then((r) => r.data),
    onSuccess: (r) => {
      done();
      addToast(r.skipped.length
        ? `Demo reset. ${r.skipped.length} change${r.skipped.length === 1 ? " was" : "s were"} left because something real changed since; staff can see which in Admin → Demo.`
        : "Demo reset. Everything is back as it was.", r.skipped.length ? "warning" : "success");
    },
    onError: (err) => addToast(getApiError(err, "Couldn't reset the demo."), "error"),
  });
  const keep = useMutation({
    mutationFn: () => api.post("/demo/run/keep"),
    onSuccess: () => { done(); addToast("Demo ended. Its changes stay.", "success"); },
    onError: (err) => addToast(getApiError(err, "Couldn't end the demo."), "error"),
  });
  const playAs = useMutation({
    mutationFn: (clubId: string) =>
      api.post<{ access_token: string }>(`/demo/house-clubs/${clubId}/play-as`).then((r) => r.data),
    onSuccess: ({ access_token }) => {
      setOpen(false);
      window.open(`/view-as#view_as=${access_token}`, "_blank", "noopener");
    },
    onError: (err) => addToast(getApiError(err, "Couldn't open that club."), "error"),
  });

  async function askReset() {
    if (!run) return;
    const ok = await confirm({
      title: "Reset your demo?",
      message: `This puts back all ${run.changes} change${run.changes === 1 ? "" : "s"} your demo made: offers, deals, money and squads. Anything real that changed since is left as it is.`,
      confirmLabel: "Reset demo",
      variant: "danger",
    });
    if (ok) reset.mutate();
  }

  if (!run) {
    return (
      <button
        type="button"
        onClick={() => start.mutate()}
        disabled={start.isPending}
        className="fixed bottom-4 right-4 z-[60] rounded-full bg-surface px-4 py-2 text-sm font-semibold text-text shadow-lg ring-1 ring-border hover:ring-accent disabled:opacity-60"
      >
        Start demo
      </button>
    );
  }

  return (
    <div className="fixed bottom-4 right-4 z-[60] flex max-w-[calc(100vw-2rem)] flex-col items-end gap-2">
      {open && (
        <div role="dialog" aria-label="Demo" className="w-80 max-w-full rounded-2xl bg-surface p-4 text-sm shadow-xl ring-1 ring-border">
          <p className="font-semibold text-text">Your demo</p>
          <p className="mt-1 text-text-secondary">
            {run.changes} change{run.changes === 1 ? "" : "s"} so far. Resets by itself on {run.resets_on ? formatDate(run.resets_on) : "—"}.
          </p>
          <p className="mt-3 text-xs font-semibold uppercase tracking-wider text-text-muted">Play the other side</p>
          {houses.isLoading ? (
            <p className="mt-1 text-text-muted">Loading…</p>
          ) : !houses.data?.length ? (
            <p className="mt-1 text-text-muted">No house clubs yet. Staff choose them in Admin → Demo.</p>
          ) : (
            <ul className="mt-1 max-h-40 space-y-1 overflow-y-auto">
              {houses.data.map((c) => (
                <li key={c.id}>
                  <button
                    type="button"
                    onClick={() => playAs.mutate(c.id)}
                    disabled={playAs.isPending}
                    className="w-full rounded-lg px-2 py-1.5 text-left text-text hover:bg-surface-inset"
                  >
                    Play as {c.name} <span className="text-text-muted">· opens a tab</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
          <div className="mt-4 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={askReset}
              disabled={reset.isPending}
              className="rounded-lg bg-danger px-3 py-1.5 font-semibold text-white disabled:opacity-60"
            >
              Reset demo
            </button>
            <button
              type="button"
              onClick={() => keep.mutate()}
              disabled={keep.isPending}
              className="rounded-lg px-3 py-1.5 font-semibold text-text ring-1 ring-border hover:ring-accent disabled:opacity-60"
            >
              End, keep changes
            </button>
          </div>
        </div>
      )}
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="flex items-center gap-2 rounded-full bg-warning-fill px-4 py-2 text-sm font-bold text-ink shadow-lg"
      >
        <span aria-hidden>●</span> Demo · {run.changes} change{run.changes === 1 ? "" : "s"}
      </button>
    </div>
  );
}

/** Across a "play as this house club" tab: whose demo it is, and that it resets with it. */
export function DemoPlayAsBanner() {
  const { demoPlayedBy } = useAuth();
  if (!demoPlayedBy) return null;
  return (
    <div role="status" className="sticky top-0 z-[70] bg-warning-fill px-4 py-2 text-center text-sm font-semibold text-ink">
      Demo: you&rsquo;re playing this house club in {demoPlayedBy}&rsquo;s demo. Everything here is undone when the demo is reset.
    </div>
  );
}
