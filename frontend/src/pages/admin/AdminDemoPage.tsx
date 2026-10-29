import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import api from "../../lib/api";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import PageHeader from "../../components/ui/PageHeader";
import Spinner from "../../components/ui/Spinner";
import { useAskReason, useConfirm } from "../../context/ConfirmContext";
import { useToast } from "../../context/ToastContext";
import { formatDateTime, getApiError } from "../../lib/utils";
import type { DemoRun } from "../../types/api";

interface Overview {
  enabled: boolean;
  runs: (DemoRun & { user: string | null })[];
  testers: { id: string; name: string }[];
  clubs: { id: string; name: string; house_club: boolean; personality: string | null; in_use: boolean }[];
}

const PERSONALITY: Record<string, string> = { hard: "Hard-nosed", fair: "Fair", eager: "Eager to sell" };

/**
 * Demo mode (backend app/demo): every demo run and what its reset did, the
 * clubs TransferX plays in demos (only clubs nobody uses), and who may start
 * a demo. Every change asks for a reason and is audited.
 */
export default function AdminDemoPage() {
  const queryClient = useQueryClient();
  const askReason = useAskReason();
  const confirm = useConfirm();
  const { addToast } = useToast();
  const [email, setEmail] = useState("");

  const { data, isLoading, isError } = useQuery<Overview>({
    queryKey: ["admin", "demo"],
    queryFn: () => api.get<Overview>("/admin/demo").then((r) => r.data),
  });
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["admin", "demo"] });
  const onError = (fallback: string) => (err: unknown) => addToast(getApiError(err, fallback), "error");

  const setHouse = useMutation({
    mutationFn: (b: { id: string; house_club: boolean; personality?: string; reason: string }) =>
      api.patch(`/admin/demo/clubs/${b.id}`, b),
    onSuccess: refresh,
    onError: onError("Couldn't change that club."),
  });
  const setTester = useMutation({
    mutationFn: (b: { id: string; can_demo: boolean; reason: string }) => api.patch(`/admin/demo/testers/${b.id}`, b),
    onSuccess: () => { refresh(); setEmail(""); },
    onError: onError("Couldn't change that tester."),
  });
  const reset = useMutation({
    mutationFn: (id: string) => api.post<{ skipped: unknown[] }>(`/admin/demo/runs/${id}/reset`).then((r) => r.data),
    onSuccess: (r) => { refresh(); addToast(r.skipped.length ? `Reset, with ${r.skipped.length} change(s) left as they were.` : "Reset.", "success"); },
    onError: onError("Couldn't reset that demo."),
  });

  async function toggleHouse(c: Overview["clubs"][number], personality?: string) {
    const on = personality ? true : !c.house_club;
    const reason = await askReason({
      title: on ? `TransferX plays ${c.name} in demos` : `Stop playing ${c.name}`,
      message: on
        ? "Testers can deal with it in their demos and play it by hand. Its real squad and money are used, and put back when each demo resets."
        : "Testers can't start new deals with it in their demos.",
      reasonLabel: "Why?",
      placeholder: "e.g. For the Friday demo to the board",
      confirmLabel: on ? "Make house club" : "Stop",
    });
    if (reason) setHouse.mutate({ id: c.id, house_club: on, personality: personality ?? c.personality ?? "fair", reason });
  }

  async function addTester() {
    const term = email.trim();
    if (!term) return;
    const found = await api.get<{ items: { id: string; email: string }[] }>("/admin/users", { params: { search: term } })
      .then((r) => r.data.items.find((u) => u.email.toLowerCase() === term.toLowerCase()))
      .catch(() => undefined);
    if (!found) { addToast(`No account with the email ${term}.`, "error"); return; }
    const reason = await askReason({
      title: `Let ${found.email} start demos`,
      message: "They can start a demo, deal with house clubs in it, play a house club by hand, and reset it.",
      reasonLabel: "Why?",
      placeholder: "e.g. Testing the buy flow before launch",
      confirmLabel: "Allow demos",
    });
    if (reason) setTester.mutate({ id: found.id, can_demo: true, reason });
  }

  async function removeTester(t: Overview["testers"][number]) {
    const reason = await askReason({
      title: `Stop ${t.name} starting demos`, message: "A demo they have running stays until it's reset.",
      reasonLabel: "Why?", placeholder: "e.g. Testing finished", confirmLabel: "Remove",
    });
    if (reason) setTester.mutate({ id: t.id, can_demo: false, reason });
  }

  async function resetRun(r: Overview["runs"][number]) {
    const ok = await confirm({
      title: `Reset ${r.user ?? "this tester"}'s demo?`,
      message: `This puts back its ${r.changes} change${r.changes === 1 ? "" : "s"}. Anything real that changed since is left as it is.`,
      confirmLabel: "Reset", variant: "danger",
    });
    if (ok) reset.mutate(r.id);
  }

  if (isLoading) return <div className="flex justify-center py-12"><Spinner size="lg" /></div>;
  if (isError || !data) return <p className="text-sm text-danger-text">Couldn&rsquo;t load demo mode. Try again in a moment.</p>;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Demo"
        subtitle="Testers try TransferX on real data against clubs TransferX plays, then put everything back."
      />
      {!data.enabled && (
        <p className="rounded-xl bg-warning-fill/10 px-4 py-3 text-sm text-text ring-1 ring-warning-fill/30">
          Demo mode is off on this server (<code>DEMO_ENABLED</code>). Nobody can start a demo, and nothing is journaled.
        </p>
      )}

      <Card noPadding>
        <p className="border-b border-rule px-5 py-3 text-xs font-semibold uppercase tracking-wider text-text-muted">Demo runs</p>
        {data.runs.length === 0 ? (
          <p className="px-5 py-6 text-sm text-text-muted">No demos yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="text-left text-xs font-semibold uppercase tracking-wider text-text-muted">
                  <th className="px-5 py-2">Tester</th><th className="px-5 py-2">Started</th>
                  <th className="px-5 py-2">Changes</th><th className="px-5 py-2">Status</th><th className="px-5 py-2" />
                </tr>
              </thead>
              <tbody>
                {data.runs.map((r) => (
                  <tr key={r.id} className="border-t border-rule-faint align-top">
                    <td className="px-5 py-3 text-text">{r.user ?? "—"}</td>
                    <td className="px-5 py-3 text-text-muted">{formatDateTime(r.started_at)}</td>
                    <td className="px-5 py-3 text-text">{r.changes}</td>
                    <td className="px-5 py-3">
                      <Badge variant={r.status === "ACTIVE" ? "warning" : "neutral"}>
                        {r.status === "ACTIVE" ? "Running" : r.status === "RESET" ? "Reset" : "Kept"}
                      </Badge>
                      {r.report?.skipped?.length ? (
                        <details className="mt-1 text-xs text-text-muted">
                          <summary>{r.report.skipped.length} left as they were</summary>
                          <ul className="mt-1 list-disc pl-4">
                            {r.report.skipped.map((s, i) => <li key={i}>{s.table}: {s.why}</li>)}
                          </ul>
                        </details>
                      ) : null}
                    </td>
                    <td className="px-5 py-3 text-right">
                      {r.status === "ACTIVE" && (
                        <Button variant="danger" size="sm" disabled={reset.isPending} onClick={() => resetRun(r)}>Reset</Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Card noPadding>
        <p className="border-b border-rule px-5 py-3 text-xs font-semibold uppercase tracking-wider text-text-muted">
          House clubs · clubs TransferX plays in demos
        </p>
        <div className="divide-y divide-rule-faint">
          {data.clubs.map((c) => (
            <div key={c.id} className="flex flex-wrap items-center gap-3 px-5 py-2.5 text-sm">
              <span className="min-w-0 flex-1 text-text">{c.name}</span>
              {c.house_club && <Badge variant="info">House club</Badge>}
              {c.in_use && !c.house_club && <span className="text-xs text-text-muted">In use: people sign in to it</span>}
              {c.house_club && (
                <select
                  aria-label={`${c.name} personality`}
                  value={c.personality ?? "fair"}
                  onChange={(e) => toggleHouse(c, e.target.value)}
                  className="rounded-lg bg-surface px-2 py-1 text-sm text-text ring-1 ring-input-border"
                >
                  {Object.entries(PERSONALITY).map(([k, label]) => <option key={k} value={k}>{label}</option>)}
                </select>
              )}
              <Button
                variant={c.house_club ? "ghost" : "secondary"}
                size="sm"
                disabled={setHouse.isPending || (!c.house_club && c.in_use)}
                title={!c.house_club && c.in_use ? "People use this club, so TransferX can't play it" : undefined}
                onClick={() => toggleHouse(c)}
              >
                {c.house_club ? "Stop" : "Make house club"}
              </Button>
            </div>
          ))}
        </div>
      </Card>

      <Card>
        <p className="text-xs font-semibold uppercase tracking-wider text-text-muted">Testers</p>
        <p className="mt-1 text-sm text-text-secondary">TransferX staff can always start a demo. Add anyone else here.</p>
        <ul className="mt-3 space-y-1 text-sm">
          {data.testers.length === 0 && <li className="text-text-muted">No testers yet.</li>}
          {data.testers.map((t) => (
            <li key={t.id} className="flex items-center gap-3">
              <span className="flex-1 text-text">{t.name}</span>
              <Button variant="ghost" size="sm" onClick={() => removeTester(t)}>Remove</Button>
            </li>
          ))}
        </ul>
        <div className="mt-3 flex flex-wrap gap-2">
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="Their sign-in email"
            aria-label="Tester's email"
            className="min-w-0 flex-1 rounded-lg bg-surface px-3 py-1.5 text-sm text-text ring-1 ring-input-border placeholder:text-text-muted"
          />
          <Button variant="secondary" size="sm" disabled={!email.trim() || setTester.isPending} onClick={addTester}>Add tester</Button>
        </div>
      </Card>
    </div>
  );
}
