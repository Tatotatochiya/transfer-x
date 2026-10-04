import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import api from "../../lib/api";
import { formatCurrency, formatDate, formatWage, getApiError } from "../../lib/utils";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import CurrencyInput from "../../components/ui/CurrencyInput";
import EmptyState from "../../components/ui/EmptyState";
import PageHeader from "../../components/ui/PageHeader";
import Spinner from "../../components/ui/Spinner";
import { useClubCapabilities } from "../../hooks/useClubCapabilities";
import { useToast } from "../../context/ToastContext";

/**
 * Check your squad (Phase 1): confirm each player's contract, wage and
 * valuation, and see what's missing. Backend: clubs/squad_check.py.
 */

type Issue = "NO_CONTRACT" | "ENDED" | "NO_END_DATE" | "NO_WAGE" | "NO_VALUATION";

export interface SquadCheckPlayer {
  player_id: string;
  name: string;
  position: string | null;
  contract: {
    start_date: string | null;
    end_date: string | null;
    wage_weekly: string | number | null;
    club_valuation: string | number | null;
    confirmed_at: string | null;
    confirmed_by: string | null;
  } | null;
  issues: Issue[];
  confirmed: boolean;
}

interface SquadCheck {
  players: SquadCheckPlayer[];
  total: number;
  confirmed: number;
  without_contract: number;
  needs_attention: number;
}

const ISSUE_LABEL: Record<Issue, string> = {
  NO_CONTRACT: "No contract",
  ENDED: "Contract ended",
  NO_END_DATE: "No end date",
  NO_WAGE: "No wage",
  NO_VALUATION: "No valuation",
};

const num = (v: string | number | null | undefined) => (v == null || v === "" ? null : Number(v));
const raw = (v: string | number | null | undefined) => (v == null ? "" : String(Math.round(Number(v))));

function ConfirmForm({ p, onDone, onCancel }: { p: SquadCheckPlayer; onDone: (row: SquadCheckPlayer) => void; onCancel: () => void }) {
  const c = p.contract;
  const [start, setStart] = useState(c?.start_date ?? "");
  const [end, setEnd] = useState(c?.end_date ?? "");
  const [wage, setWage] = useState(raw(c?.wage_weekly));
  const [valuation, setValuation] = useState(raw(c?.club_valuation));
  const save = useMutation({
    mutationFn: () =>
      api.post<SquadCheckPlayer>(`/clubs/me/squad-check/${p.player_id}/confirm`, {
        start_date: start || null,
        end_date: end,
        wage_weekly: Number(wage),
        club_valuation: valuation ? Number(valuation) : null,
      }).then((r) => r.data),
    onSuccess: onDone,
  });
  const input = "w-full rounded-lg bg-surface px-3 py-2 text-sm text-text ring-1 ring-input-border focus:outline-none focus:ring-accent";
  const ready = end && Number(wage) > 0;

  return (
    <form
      className="mt-3 grid gap-3 sm:grid-cols-4"
      onSubmit={(e) => { e.preventDefault(); if (ready) save.mutate(); }}
    >
      <label className="text-xs text-text-secondary">
        Contract starts <span className="text-text-muted">(optional)</span>
        <input type="date" value={start} onChange={(e) => setStart(e.target.value)} className={`${input} mt-1`} />
      </label>
      <label className="text-xs text-text-secondary">
        Contract ends
        <input type="date" required value={end} onChange={(e) => setEnd(e.target.value)} className={`${input} mt-1`} />
      </label>
      <label className="text-xs text-text-secondary">
        Wage a week (£)
        <CurrencyInput required value={wage} onChange={setWage} className={`${input} mt-1`} />
      </label>
      <label className="text-xs text-text-secondary">
        Your valuation (£) <span className="text-text-muted">(optional)</span>
        <CurrencyInput value={valuation} onChange={setValuation} className={`${input} mt-1`} />
      </label>
      {save.isError && <p className="text-sm text-danger-text sm:col-span-4">{getApiError(save.error)}</p>}
      <div className="flex gap-2 sm:col-span-4">
        <Button type="submit" disabled={!ready || save.isPending}>
          {save.isPending ? "Saving…" : c ? "Confirm" : "Create contract and confirm"}
        </Button>
        <Button type="button" variant="ghost" onClick={onCancel}>Cancel</Button>
      </div>
    </form>
  );
}

function Row({ p, canConfirm }: { p: SquadCheckPlayer; canConfirm: boolean }) {
  const [open, setOpen] = useState(false);
  const qc = useQueryClient();
  const { addToast } = useToast();
  const c = p.contract;
  const blocking = p.issues.filter((i) => i !== "NO_VALUATION");

  return (
    <div className="px-5 py-3.5">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-semibold text-text">
            {p.name}
            {p.position && <span className="ml-2 text-xs font-normal text-text-muted">{p.position}</span>}
          </p>
          <p className="mt-0.5 text-xs text-text-muted">
            {c
              ? <>Until {c.end_date ? formatDate(c.end_date) : "—"} · {formatWage(num(c.wage_weekly))} · valued {c.club_valuation != null ? formatCurrency(num(c.club_valuation)) : "—"}</>
              : "No contract on TransferX"}
          </p>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {p.confirmed && <Badge variant="success">Confirmed</Badge>}
          {p.issues.map((i) => (
            <Badge key={i} variant={i === "NO_VALUATION" ? "neutral" : "danger"}>{ISSUE_LABEL[i]}</Badge>
          ))}
          {!p.confirmed && blocking.length === 0 && <Badge variant="warning">Not confirmed</Badge>}
        </div>
        {canConfirm && !open && (
          <Button size="sm" variant={p.confirmed ? "ghost" : "primary"} onClick={() => setOpen(true)}>
            {p.confirmed ? "Edit" : "Check"}
          </Button>
        )}
      </div>
      {c?.confirmed_at && (
        <p className="mt-1 text-xs text-text-muted">
          Confirmed {formatDate(c.confirmed_at)}{c.confirmed_by ? ` by ${c.confirmed_by}` : ""}
        </p>
      )}
      {open && (
        <ConfirmForm
          p={p}
          onCancel={() => setOpen(false)}
          onDone={(row) => {
            setOpen(false);
            addToast(`${row.name} confirmed`, "success");
            void qc.invalidateQueries({ queryKey: ["clubs", "me", "squad-check"] });
          }}
        />
      )}
    </div>
  );
}

export default function SquadCheckPage() {
  const { can } = useClubCapabilities();
  const canConfirm = can("CLUB_ADMIN");
  const { data, isLoading, isError } = useQuery<SquadCheck>({
    queryKey: ["clubs", "me", "squad-check"],
    queryFn: () => api.get<SquadCheck>("/clubs/me/squad-check").then((r) => r.data),
  });

  return (
    <div className="mx-auto max-w-4xl">
      <PageHeader
        title="Check your squad"
        subtitle="Confirm each player's contract, wage and valuation. Buyers, budgets and approvals rely on them."
      />
      {isLoading ? (
        <div className="flex justify-center py-16"><Spinner size="lg" /></div>
      ) : isError || !data ? (
        <EmptyState title="Couldn't load your squad" body="Try again in a moment." />
      ) : data.total === 0 ? (
        <EmptyState title="No players yet" body="Players you add, or that TransferX imports for your club, appear here." />
      ) : (
        <>
          <Card className="mb-4">
            <div className="flex flex-wrap items-baseline gap-x-6 gap-y-1">
              <p className="text-2xl font-bold text-text">{data.confirmed} of {data.total} confirmed</p>
              {data.without_contract > 0 && (
                <p className="text-sm font-semibold text-danger-text">
                  {data.without_contract} without a contract
                </p>
              )}
              {data.needs_attention > 0 && (
                <p className="text-sm text-text-muted">{data.needs_attention} need a date or wage</p>
              )}
            </div>
            <div className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-border-quiet">
              <div className="h-full bg-success" style={{ width: `${(data.confirmed / data.total) * 100}%` }} />
            </div>
            {!canConfirm && (
              <p className="mt-3 text-xs text-text-muted">The owner or sporting director confirms contracts.</p>
            )}
          </Card>
          <Card noPadding className="divide-y divide-rule-faint">
            {data.players.map((p) => <Row key={p.player_id} p={p} canConfirm={canConfirm} />)}
          </Card>
        </>
      )}
    </div>
  );
}
