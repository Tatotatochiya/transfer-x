import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import api from "../../lib/api";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import DateRangeFilter, { EMPTY_DATE_RANGE, type DateRange } from "../../components/ui/DateRangeFilter";
import Input from "../../components/ui/Input";
import Pagination from "../../components/ui/Pagination";
import ResponsiveTable, { type ResponsiveColumn } from "../../components/ui/ResponsiveTable";
import { formatDateTime, getApiError } from "../../lib/utils";
import { useDebounce } from "../../hooks/useDebounce";

/**
 * Every audit event, newest first: what TransferX staff changed in the admin
 * panel (with their reason) beside the deal, offer and loan history. Filter,
 * search, open the thing it's about, and export the current view to Excel.
 */

interface AuditRow {
  id: string;
  created_at: string;
  actor_user_id: string | null;
  actor_email: string | null;
  action: string;
  entity_type: string;
  entity_id: string;
  description: string | null;
  reason: string | null;
  payload: Record<string, unknown>;
  link: string | null;
  by_staff: boolean;
}

interface AuditPage {
  items: AuditRow[];
  total: number;
  page: number;
  page_size: number;
}

const PAGE_SIZE = 50;

/** "admin.user.updated" → "User updated". */
export function actionLabel(action: string): string {
  const words = action.replace(/^admin\./, "").replace(/[._]/g, " ").trim().toLowerCase();
  return words.charAt(0).toUpperCase() + words.slice(1);
}

function Details({ row }: { row: AuditRow }) {
  const { admin_action: _a, reason: _r, ...rest } = row.payload ?? {};
  const changes = rest.changes as Record<string, [unknown, unknown]> | undefined;
  return (
    <div className="space-y-1 text-xs text-text-secondary">
      {changes && Object.entries(changes).map(([field, [from, to]]) => (
        <div key={field}>
          <span className="font-semibold text-text">{field.replace(/_/g, " ")}</span>: {String(from ?? "—")} → {String(to ?? "—")}
        </div>
      ))}
      {Object.keys(rest).filter((k) => k !== "changes").length > 0 && (
        <pre className="max-w-xl overflow-x-auto whitespace-pre-wrap rounded bg-surface-inset p-2 font-mono text-[11px]">
          {JSON.stringify(Object.fromEntries(Object.entries(rest).filter(([k]) => k !== "changes")), null, 2)}
        </pre>
      )}
    </div>
  );
}

export default function AdminAuditLogPage() {
  const [search, setSearch] = useState("");
  const [action, setAction] = useState("");
  const [entityType, setEntityType] = useState("");
  const [staffOnly, setStaffOnly] = useState(true);
  const [dateRange, setDateRange] = useState<DateRange>(EMPTY_DATE_RANGE);
  const [page, setPage] = useState(1);
  const [open, setOpen] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);
  const q = useDebounce(search, 300);

  const params = {
    ...(q.trim() && { q: q.trim() }),
    ...(action && { action }),
    ...(entityType && { entity_type: entityType }),
    ...(staffOnly && { admin_only: true }),
    ...(dateRange.dateFrom && { date_from: dateRange.dateFrom }),
    ...(dateRange.dateTo && { date_to: dateRange.dateTo }),
  };

  const { data: facets } = useQuery<{ actions: string[]; entity_types: string[] }>({
    queryKey: ["admin", "audit-log", "facets"],
    queryFn: () => api.get("/admin/audit-log/facets").then((r) => r.data),
    staleTime: 60_000,
  });
  const { data, isLoading } = useQuery<AuditPage>({
    queryKey: ["admin", "audit-log", params, page],
    queryFn: () => api.get("/admin/audit-log", { params: { ...params, page, page_size: PAGE_SIZE } }).then((r) => r.data),
  });

  const reset = <T,>(set: (v: T) => void) => (v: T) => { set(v); setPage(1); };

  // The file comes from the API with the same filters as the view. The
  // export itself is recorded in the log.
  async function exportExcel() {
    setExporting(true);
    setExportError(null);
    try {
      const resp = await api.get<Blob>("/admin/audit-log/export.xlsx", { params, responseType: "blob" });
      // The API names the file, but a cross-origin page can't read that
      // header, so fall back to the same name built here.
      const name = /filename="([^"]+)"/.exec(String(resp.headers["content-disposition"] ?? ""))?.[1]
        ?? `transferx-audit-log-${new Date().toISOString().slice(0, 10)}.xlsx`;
      const url = URL.createObjectURL(resp.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = name;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (e) {
      setExportError(getApiError(e, "Export failed."));
    } finally {
      setExporting(false);
    }
  }

  const actions = (facets?.actions ?? []).filter((a) => !staffOnly || a.startsWith("admin."));

  const columns: ResponsiveColumn<AuditRow>[] = [
    {
      key: "when", header: "When", priority: 3,
      render: (r) => <span className="whitespace-nowrap text-xs text-text-muted">{formatDateTime(r.created_at)}</span>,
    },
    {
      key: "who", header: "Who", priority: 2,
      render: (r) => (
        <span className="text-xs">
          <span className="font-medium text-text">{r.actor_email ?? (r.actor_user_id ? "Deleted user" : "System")}</span>
          {r.by_staff && <Badge variant="warning" className="ml-1.5">Staff</Badge>}
        </span>
      ),
    },
    {
      key: "what", header: "What", priority: 1,
      render: (r) => (
        <div className="min-w-0">
          <p className="text-sm font-medium text-text">{r.description ?? actionLabel(r.action)}</p>
          <p className="text-xs text-text-muted">
            {actionLabel(r.action)}
            {r.link ? <> · <Link to={r.link} className="text-accent hover:underline" onClick={(e) => e.stopPropagation()}>Open {r.entity_type.toLowerCase()}</Link></> : <> · {r.entity_type.toLowerCase()}</>}
          </p>
          {open === r.id && <div className="mt-2"><Details row={r} /></div>}
        </div>
      ),
    },
    {
      key: "reason", header: "Reason", priority: 4,
      render: (r) => r.reason ? <span className="text-sm text-text-secondary">{r.reason}</span> : <span className="text-text-muted">—</span>,
    },
  ];

  return (
    <div>
      <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-text">Audit log</h1>
          <p className="mt-1 text-sm text-text-muted">
            {data ? `${data.total.toLocaleString("en-GB")} ${data.total === 1 ? "event" : "events"}` : ""}
            {" · "}Who changed what, when, and why. Click a row for the details.
          </p>
        </div>
        <div className="flex flex-col items-end gap-1">
          <Button variant="secondary" size="sm" onClick={exportExcel} loading={exporting} disabled={!data || data.total === 0}>
            Export to Excel
          </Button>
          {exportError && <span className="text-xs text-danger-text">{exportError}</span>}
          {data && data.total > 50_000 && <span className="text-xs text-text-muted">Exports the newest 50,000</span>}
        </div>
      </div>

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <Input
          type="text"
          placeholder="Search description, email, action or ID…"
          value={search}
          onChange={(e) => { setSearch(e.target.value); setPage(1); }}
          wrapperClassName="w-72 max-w-full"
        />
        <select
          aria-label="Action"
          value={action}
          onChange={(e) => reset(setAction)(e.target.value)}
          className="rounded-lg bg-surface px-3 py-2 text-sm text-text ring-1 ring-input-border focus:outline-none focus:ring-accent"
        >
          <option value="">All actions</option>
          {actions.map((a) => <option key={a} value={a}>{actionLabel(a)}{a.startsWith("admin.") ? " (staff)" : ""}</option>)}
        </select>
        <select
          aria-label="Entity type"
          value={entityType}
          onChange={(e) => reset(setEntityType)(e.target.value)}
          className="rounded-lg bg-surface px-3 py-2 text-sm text-text ring-1 ring-input-border focus:outline-none focus:ring-accent"
        >
          <option value="">Everything</option>
          {(facets?.entity_types ?? []).map((t) => <option key={t} value={t}>{t.replace(/_/g, " ").toLowerCase()}</option>)}
        </select>
        <label className="flex items-center gap-2 text-sm text-text-secondary">
          <input type="checkbox" checked={staffOnly} onChange={(e) => { setStaffOnly(e.target.checked); setAction(""); setPage(1); }} />
          Staff actions only
        </label>
      </div>

      <div className="mb-6">
        <DateRangeFilter value={dateRange} onChange={reset(setDateRange)} accent="amber" />
      </div>

      <ResponsiveTable
        columns={columns}
        rows={data?.items ?? []}
        rowKey={(r) => r.id}
        loading={isLoading}
        emptyTitle="Nothing in the log"
        emptyBody={staffOnly ? "No staff actions match. Untick \"Staff actions only\" to see deal and offer history too." : "No events match these filters."}
        onRowClick={(r) => setOpen(open === r.id ? null : r.id)}
      />

      {data && data.total > PAGE_SIZE && (
        <div className="mt-4">
          <Pagination page={page} total={data.total} pageSize={PAGE_SIZE} onChange={setPage} />
        </div>
      )}
    </div>
  );
}
