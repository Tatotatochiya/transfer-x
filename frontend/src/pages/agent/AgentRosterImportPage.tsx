import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../../lib/api";
import type {
  ImportRow,
  MatchCandidate,
  RosterImportRequest,
  RosterImportResult,
  RosterPreviewRow,
} from "../../types/api";
import Card from "../../components/ui/Card";
import PageHeader from "../../components/ui/PageHeader";
import Button from "../../components/ui/Button";
import Spinner from "../../components/ui/Spinner";

// ── Step 1: upload ────────────────────────────────────────────────────────────

function UploadStep({ onPreview }: { onPreview: (rows: RosterPreviewRow[]) => void }) {
  const [dragging, setDragging] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  async function handleFile(file: File) {
    setError(null);
    setLoading(true);
    try {
      const form = new FormData();
      form.append("file", file);
      const { data } = await api.post<{ rows: RosterPreviewRow[] }>("/agents/me/roster/preview", form, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      if (data.rows.length === 0) {
        setError("No valid rows found in the file. Make sure the CSV has a 'Name' column.");
        return;
      }
      onPreview(data.rows);
    } catch {
      setError("Failed to parse the file. Please check the format and try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card>
      <p className="mb-1 text-base font-semibold text-white">Upload your client roster</p>
      <p className="mb-6 text-sm text-slate-400">
        Upload a CSV or Excel file. Required column: <code className="rounded bg-slate-800 px-1 text-xs">Name</code>.
        Optional: DOB, Nationality, Position, Current Club, Contract Expiry.
      </p>

      {error && (
        <div className="mb-4 rounded-lg bg-red-500/10 px-4 py-3 text-sm text-red-400 ring-1 ring-red-500/30">
          {error}
        </div>
      )}

      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          const file = e.dataTransfer.files[0];
          if (file) handleFile(file);
        }}
        onClick={() => fileRef.current?.click()}
        className={`flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed py-14 transition-colors ${
          dragging
            ? "border-emerald-500 bg-emerald-500/5"
            : "border-white/10 bg-slate-800/50 hover:border-white/20 hover:bg-slate-800"
        }`}
      >
        {loading ? (
          <Spinner size="lg" />
        ) : (
          <>
            <svg className="mb-3 h-10 w-10 text-slate-500" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
            </svg>
            <p className="text-sm font-medium text-white">Drop your file here</p>
            <p className="mt-1 text-xs text-slate-500">or click to browse (CSV)</p>
          </>
        )}
      </div>
      <input
        ref={fileRef}
        type="file"
        accept=".csv,.tsv,.txt"
        className="hidden"
        onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFile(f); }}
      />
    </Card>
  );
}

// ── Step 2: review rows ───────────────────────────────────────────────────────

type RowAction = "create" | "link" | "skip";

interface RowState {
  action: RowAction;
  linkedPlayerId: string;
}

function ReviewStep({
  rows,
  rowStates,
  onChange,
}: {
  rows: RosterPreviewRow[];
  rowStates: RowState[];
  onChange: (index: number, patch: Partial<RowState>) => void;
}) {
  const actionBadge: Record<RowAction, string> = {
    create: "bg-sky-500/15 text-sky-400 ring-sky-500/30",
    link:   "bg-emerald-500/15 text-emerald-400 ring-emerald-500/30",
    skip:   "bg-slate-700 text-slate-500 ring-white/10",
  };

  return (
    <div className="overflow-x-auto rounded-xl ring-1 ring-white/[0.08]">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-white/[0.06] bg-slate-900">
            <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">Name</th>
            <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">Details</th>
            <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">Match</th>
            <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">Action</th>
          </tr>
        </thead>
        <tbody className="bg-slate-900/50">
          {rows.map((row, i) => {
            const state = rowStates[i];
            return (
              <tr key={row.row_index} className="border-b border-white/[0.04] last:border-0">
                <td className="px-4 py-3">
                  <p className="font-medium text-white">{row.name}</p>
                  {row.current_club && <p className="text-xs text-slate-500">{row.current_club}</p>}
                </td>
                <td className="px-4 py-3 text-xs text-slate-400">
                  {[row.position, row.nationality, row.dob].filter(Boolean).join(" · ") || "—"}
                </td>
                <td className="px-4 py-3">
                  {row.match_status === "no_match" ? (
                    <span className="text-xs text-slate-500">No match — will create</span>
                  ) : row.match_candidates.length === 1 ? (
                    <span className="text-xs text-emerald-400">
                      Matched: {row.match_candidates[0].player_name}
                    </span>
                  ) : (
                    <select
                      value={state.linkedPlayerId}
                      onChange={(e) => onChange(i, { linkedPlayerId: e.target.value, action: "link" })}
                      className="rounded bg-slate-800 px-2 py-1 text-xs text-white ring-1 ring-white/10 focus:outline-none focus:ring-emerald-500"
                    >
                      {row.match_candidates.map((c: MatchCandidate) => (
                        <option key={c.player_id} value={c.player_id}>
                          {c.player_name}{c.player_club ? ` · ${c.player_club}` : ""}
                        </option>
                      ))}
                    </select>
                  )}
                </td>
                <td className="px-4 py-3">
                  <div className="flex gap-1">
                    {(["create", "link", "skip"] as RowAction[]).map((a) => {
                      if (a === "link" && row.match_status === "no_match") return null;
                      if (a === "create" && row.match_status !== "no_match") return null;
                      return (
                        <button
                          key={a}
                          onClick={() => onChange(i, { action: a })}
                          className={`rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 transition-all capitalize ${
                            state.action === a
                              ? actionBadge[a]
                              : "bg-transparent ring-white/10 text-slate-500 hover:text-slate-300"
                          }`}
                        >
                          {a}
                        </button>
                      );
                    })}
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ── Step 3: mandate settings ──────────────────────────────────────────────────

interface MandateSettings {
  exclusive: boolean;
  start_date: string;
  end_date: string;
  territory: string;
}

function SettingsStep({
  settings,
  onChange,
}: {
  settings: MandateSettings;
  onChange: (patch: Partial<MandateSettings>) => void;
}) {
  const INPUT = "w-full rounded-lg bg-slate-800 px-3 py-2 text-sm text-white ring-1 ring-white/10 focus:outline-none focus:ring-emerald-500";

  return (
    <Card>
      <p className="mb-4 text-base font-semibold text-white">Mandate settings</p>
      <p className="mb-6 text-sm text-slate-400">
        These settings apply to all mandates created from the import. You can edit them individually afterwards.
      </p>
      <div className="space-y-4">
        <label className="flex items-center gap-3 cursor-pointer select-none">
          <input
            type="checkbox"
            checked={settings.exclusive}
            onChange={(e) => onChange({ exclusive: e.target.checked })}
            className="accent-emerald-500 h-4 w-4"
          />
          <div>
            <p className="text-sm font-medium text-white">Exclusive mandate</p>
            <p className="text-xs text-slate-500">You are the sole agent for these clients</p>
          </div>
        </label>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <p className="mb-1.5 text-xs font-medium text-slate-400">Start date</p>
            <input
              type="date"
              value={settings.start_date}
              onChange={(e) => onChange({ start_date: e.target.value })}
              className={INPUT}
            />
          </div>
          <div>
            <p className="mb-1.5 text-xs font-medium text-slate-400">End date</p>
            <input
              type="date"
              value={settings.end_date}
              onChange={(e) => onChange({ end_date: e.target.value })}
              className={INPUT}
            />
          </div>
        </div>
        <div>
          <p className="mb-1.5 text-xs font-medium text-slate-400">Territory (optional)</p>
          <input
            type="text"
            value={settings.territory}
            onChange={(e) => onChange({ territory: e.target.value })}
            placeholder="e.g. Europe"
            className={INPUT}
          />
        </div>
      </div>
    </Card>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

type WizardStep = "upload" | "review" | "settings" | "done";

export default function AgentRosterImportPage() {
  const navigate = useNavigate();

  const [step, setStep] = useState<WizardStep>("upload");
  const [previewRows, setPreviewRows] = useState<RosterPreviewRow[]>([]);
  const [rowStates, setRowStates] = useState<RowState[]>([]);
  const [mandateSettings, setMandateSettings] = useState<MandateSettings>({
    exclusive: false,
    start_date: "",
    end_date: "",
    territory: "",
  });
  const [importing, setImporting] = useState(false);
  const [result, setResult] = useState<RosterImportResult | null>(null);

  function handlePreview(rows: RosterPreviewRow[]) {
    setPreviewRows(rows);
    setRowStates(
      rows.map((r) => ({
        action: r.match_status === "no_match" ? "create" : "link",
        linkedPlayerId: r.match_candidates[0]?.player_id ?? "",
      }))
    );
    setStep("review");
  }

  function updateRowState(index: number, patch: Partial<RowState>) {
    setRowStates((prev) => prev.map((s, i) => (i === index ? { ...s, ...patch } : s)));
  }

  async function handleImport() {
    setImporting(true);
    try {
      const rows: ImportRow[] = previewRows.map((row, i) => {
        const state = rowStates[i];
        if (state.action === "skip") return { action: "skip" as const };
        if (state.action === "link") {
          return {
            action: "link" as const,
            player_id: state.linkedPlayerId || row.match_candidates[0]?.player_id,
          };
        }
        return {
          action: "create" as const,
          name: row.name,
          dob: row.dob ?? undefined,
          nationality: row.nationality ?? undefined,
          position: row.position ?? undefined,
          current_club: row.current_club ?? undefined,
        };
      });

      const body: RosterImportRequest = {
        rows,
        exclusive: mandateSettings.exclusive,
        start_date: mandateSettings.start_date || null,
        end_date: mandateSettings.end_date || null,
        territory: mandateSettings.territory.trim() || null,
      };

      const { data } = await api.post<RosterImportResult>("/agents/me/roster/import", body);
      setResult(data);
      setStep("done");
    } catch {
      // errors shown via result
    } finally {
      setImporting(false);
    }
  }

  const STEPS: WizardStep[] = ["upload", "review", "settings", "done"];
  const STEP_LABELS = ["Upload", "Review", "Settings", "Done"];
  const stepIndex = STEPS.indexOf(step);

  return (
    <div className="max-w-4xl">
      <PageHeader title="Import client roster" subtitle="Bulk-add your existing clients from a spreadsheet" />

      {/* Step indicator */}
      <div className="mb-8 flex items-center gap-3">
        {STEPS.filter((s) => s !== "done").map((s, i) => (
          <div key={s} className="flex items-center gap-3">
            <div className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-semibold ${
              i < stepIndex
                ? "bg-emerald-500 text-white"
                : i === stepIndex
                ? "bg-emerald-500/20 text-emerald-400 ring-1 ring-emerald-500"
                : "bg-slate-800 text-slate-500 ring-1 ring-white/10"
            }`}>
              {i < stepIndex ? (
                <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                </svg>
              ) : (
                i + 1
              )}
            </div>
            <span className={`text-sm font-medium ${i === stepIndex ? "text-white" : "text-slate-500"}`}>
              {STEP_LABELS[i]}
            </span>
            {i < 2 && <div className="h-px w-8 bg-white/10" />}
          </div>
        ))}
      </div>

      {/* Step content */}
      {step === "upload" && <UploadStep onPreview={handlePreview} />}

      {step === "review" && (
        <div className="space-y-4">
          <p className="text-sm text-slate-400">
            {previewRows.length} player{previewRows.length !== 1 ? "s" : ""} found.
            Review the suggested actions and adjust as needed.
          </p>
          <ReviewStep rows={previewRows} rowStates={rowStates} onChange={updateRowState} />
          <div className="flex justify-end gap-3">
            <button onClick={() => setStep("upload")} className="text-sm text-slate-400 hover:text-white">
              ← Back
            </button>
            <Button variant="primary" onClick={() => setStep("settings")}>
              Next: mandate settings →
            </Button>
          </div>
        </div>
      )}

      {step === "settings" && (
        <div className="space-y-4">
          <SettingsStep
            settings={mandateSettings}
            onChange={(patch) => setMandateSettings((s) => ({ ...s, ...patch }))}
          />
          <div className="flex justify-end gap-3">
            <button onClick={() => setStep("review")} className="text-sm text-slate-400 hover:text-white">
              ← Back
            </button>
            <Button variant="primary" loading={importing} onClick={handleImport}>
              Import {rowStates.filter((s) => s.action !== "skip").length} clients
            </Button>
          </div>
        </div>
      )}

      {step === "done" && result && (
        <Card>
          <div className="text-center py-6">
            <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-emerald-500/15">
              <svg className="h-7 w-7 text-emerald-400" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
              </svg>
            </div>
            <p className="text-lg font-semibold text-white">Import complete</p>
            <div className="mt-4 flex justify-center gap-6 text-sm">
              <div className="text-center">
                <p className="text-2xl font-bold text-sky-400">{result.created}</p>
                <p className="text-slate-500">Created</p>
              </div>
              <div className="text-center">
                <p className="text-2xl font-bold text-emerald-400">{result.linked}</p>
                <p className="text-slate-500">Linked</p>
              </div>
              <div className="text-center">
                <p className="text-2xl font-bold text-slate-500">{result.skipped}</p>
                <p className="text-slate-500">Skipped</p>
              </div>
            </div>
            {result.errors.length > 0 && (
              <div className="mt-4 text-left rounded-lg bg-red-500/10 px-4 py-3 ring-1 ring-red-500/25">
                <p className="mb-2 text-xs font-semibold text-red-400">Errors ({result.errors.length})</p>
                {result.errors.map((e, i) => (
                  <p key={i} className="text-xs text-red-400">{e}</p>
                ))}
              </div>
            )}
            <div className="mt-6 flex justify-center gap-3">
              <Button variant="primary" onClick={() => navigate("/agent/dashboard")}>
                View my clients
              </Button>
              <button
                onClick={() => { setStep("upload"); setPreviewRows([]); setResult(null); }}
                className="text-sm text-slate-400 hover:text-white"
              >
                Import another file
              </button>
            </div>
          </div>
        </Card>
      )}
    </div>
  );
}
