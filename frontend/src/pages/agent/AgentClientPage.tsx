import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "../../lib/api";
import type { ClientAlert, ClientStatus, MandateDetailResponse, UpdateMandateRequest } from "../../types/api";
import Card from "../../components/ui/Card";
import PageHeader from "../../components/ui/PageHeader";
import Spinner from "../../components/ui/Spinner";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import { ALERT_SEVERITY_DOT, ALERT_TYPE_LABELS } from "../../lib/badges";
import { formatDateTime } from "../../lib/utils";

const CLIENT_STATUS_LABELS: Record<ClientStatus, string> = {
  ACTIVE:             "Active",
  SEEKING_MOVE:       "Seeking move",
  LOAN_AVAILABLE:     "Available for loan",
  CONTRACT_EXTENSION: "Contract extension",
  UNAVAILABLE:        "Unavailable",
};

const CLIENT_STATUS_COLORS: Record<ClientStatus, string> = {
  ACTIVE:             "bg-success/15 text-success-text ring-success/30",
  SEEKING_MOVE:       "bg-accent/15 text-accent ring-accent/30",
  LOAN_AVAILABLE:     "bg-role-agent-bg text-role-agent-text ring-role-agent-text/30",
  CONTRACT_EXTENSION: "bg-warning-fill/15 text-warning-text ring-warning-fill/30",
  UNAVAILABLE:        "bg-text-muted/15 text-text-muted ring-text-muted/30",
};

const INPUT = "w-full rounded-lg bg-surface px-3 py-2 text-sm text-text ring-1 ring-input-border focus:outline-none focus:ring-accent placeholder-text-muted";
const LABEL = "mb-1.5 block text-xs font-medium text-text-secondary";

export default function AgentClientPage() {
  const { mandateId } = useParams<{ mandateId: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const { data: client, isLoading } = useQuery<MandateDetailResponse>({
    queryKey: ["mandates", mandateId],
    queryFn: () => api.get<MandateDetailResponse>(`/mandates/${mandateId}`).then((r) => r.data),
    enabled: !!mandateId,
  });

  const { data: alerts = [] } = useQuery<ClientAlert[]>({
    queryKey: ["mandates", mandateId, "alerts"],
    queryFn: () => api.get<ClientAlert[]>(`/mandates/${mandateId}/alerts`).then((r) => r.data),
    enabled: !!mandateId,
  });

  const [clientStatus, setClientStatus] = useState<ClientStatus>("ACTIVE");
  const [notes, setNotes] = useState("");
  const [destinations, setDestinations] = useState("");
  const [askingPrice, setAskingPrice] = useState("");
  const [askingWage, setAskingWage] = useState("");
  const [mandateStart, setMandateStart] = useState("");
  const [mandateEnd, setMandateEnd] = useState("");
  const [territory, setTerritory] = useState("");
  const [alertContractExpiryEnabled, setAlertContractExpiryEnabled] = useState(true);
  const [alertContractExpiryMonths, setAlertContractExpiryMonths] = useState("12");
  const [alertValuationChangeEnabled, setAlertValuationChangeEnabled] = useState(true);
  const [alertValuationChangePct, setAlertValuationChangePct] = useState("10");
  const [alertClubInterestEnabled, setAlertClubInterestEnabled] = useState(true);
  const [dirty, setDirty] = useState(false);

  useEffect(() => {
    if (client) {
      setClientStatus(client.client_status);
      setNotes(client.agent_notes ?? "");
      setDestinations(client.preferred_destinations ?? "");
      setAskingPrice(client.asking_price != null ? String(client.asking_price) : "");
      setAskingWage(client.asking_wage != null ? String(client.asking_wage) : "");
      setMandateStart(client.start_date ?? "");
      setMandateEnd(client.end_date ?? "");
      setTerritory(client.territory ?? "");
      setAlertContractExpiryEnabled(client.alert_contract_expiry_enabled);
      setAlertContractExpiryMonths(String(client.alert_contract_expiry_months));
      setAlertValuationChangeEnabled(client.alert_valuation_change_enabled);
      setAlertValuationChangePct(String(Math.round(client.alert_valuation_change_pct * 100)));
      setAlertClubInterestEnabled(client.alert_club_interest_enabled);
      setDirty(false);
    }
  }, [client]);

  const saveMutation = useMutation({
    mutationFn: (body: UpdateMandateRequest) =>
      api.patch<MandateDetailResponse>(`/mandates/${mandateId}`, body).then((r) => r.data),
    onSuccess: (data) => {
      queryClient.setQueryData(["mandates", mandateId], data);
      queryClient.invalidateQueries({ queryKey: ["agents", "me", "players"] });
      setDirty(false);
    },
  });

  function handleSave() {
    const body: UpdateMandateRequest = {
      client_status: clientStatus,
      agent_notes: notes.trim() || null,
      preferred_destinations: destinations.trim() || null,
      asking_price: askingPrice ? parseFloat(askingPrice) : null,
      asking_wage: askingWage ? parseFloat(askingWage) : null,
      start_date: mandateStart || null,
      end_date: mandateEnd || null,
      territory: territory.trim() || null,
      alert_contract_expiry_enabled: alertContractExpiryEnabled,
      alert_contract_expiry_months: parseInt(alertContractExpiryMonths, 10) || 12,
      alert_valuation_change_enabled: alertValuationChangeEnabled,
      alert_valuation_change_pct: (parseFloat(alertValuationChangePct) || 10) / 100,
      alert_club_interest_enabled: alertClubInterestEnabled,
    };
    saveMutation.mutate(body);
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Spinner size="lg" />
      </div>
    );
  }

  if (!client) return null;

  const daysUntilExpiry = client.contract_expiry
    ? Math.ceil((new Date(client.contract_expiry).getTime() - Date.now()) / 86_400_000)
    : null;

  return (
    <div className="max-w-3xl">
      {/* Back link */}
      <button
        onClick={() => navigate("/agent/dashboard")}
        className="mb-4 flex items-center gap-1.5 text-sm text-text-muted hover:text-text transition-colors"
      >
        <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
        </svg>
        My clients
      </button>

      <PageHeader
        title={client.player_name}
        subtitle={[client.player_position, client.player_nationality].filter(Boolean).join(" · ")}
      />

      <div className="grid gap-4 lg:grid-cols-2">

        {/* Left: player info + mandate */}
        <div className="space-y-4">
          <Card>
            <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-text-muted">
              Player
            </p>
            <div className="space-y-2 text-sm">
              {client.player_age != null && (
                <div className="flex justify-between">
                  <span className="text-text-muted">Age</span>
                  <span className="text-text">{client.player_age}</span>
                </div>
              )}
              {client.player_nationality && (
                <div className="flex justify-between">
                  <span className="text-text-muted">Nationality</span>
                  <span className="text-text">{client.player_nationality}</span>
                </div>
              )}
              {client.player_club_name && (
                <div className="flex justify-between">
                  <span className="text-text-muted">Club</span>
                  <span className="text-text">{client.player_club_name}</span>
                </div>
              )}
              {client.contract_expiry && (
                <div className="flex justify-between">
                  <span className="text-text-muted">Contract expires</span>
                  <span className={`font-medium ${
                    daysUntilExpiry != null && daysUntilExpiry < 180
                      ? "text-warning-text"
                      : "text-text"
                  }`}>
                    {client.contract_expiry}
                    {daysUntilExpiry != null && daysUntilExpiry > 0 && (
                      <span className="ml-1 text-xs text-text-muted">({daysUntilExpiry}d)</span>
                    )}
                  </span>
                </div>
              )}
            </div>
            <div className="mt-3 border-t border-rule pt-3">
              <Link
                to={`/players/market/${client.player_id}`}
                className="text-xs text-accent hover:underline"
              >
                View market profile →
              </Link>
            </div>
          </Card>

          <Card>
            <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-text-muted">
              Mandate
            </p>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-text-muted">Type</span>
                <span>
                  {client.exclusive
                    ? <Badge variant="success">Exclusive</Badge>
                    : <span className="text-text-muted">Non-exclusive</span>}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-text-muted">Status</span>
                <span className={`rounded-full px-2 py-0.5 text-xs font-medium ring-1 ${CLIENT_STATUS_COLORS[clientStatus]}`}>
                  {CLIENT_STATUS_LABELS[clientStatus]}
                </span>
              </div>
              {client.start_date && (
                <div className="flex justify-between">
                  <span className="text-text-muted">Start</span>
                  <span className="text-text">{client.start_date}</span>
                </div>
              )}
              {client.end_date && (
                <div className="flex justify-between">
                  <span className="text-text-muted">End</span>
                  <span className="text-text">{client.end_date}</span>
                </div>
              )}
              {client.territory && (
                <div className="flex justify-between">
                  <span className="text-text-muted">Territory</span>
                  <span className="text-text">{client.territory}</span>
                </div>
              )}
            </div>
          </Card>

          {/* Alert history (TRA-135) */}
          <Card>
            <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-text-muted">
              Recent Alerts
            </p>
            {alerts.length === 0 ? (
              <p className="text-sm text-text-muted">No alerts for this client yet.</p>
            ) : (
              <div className="space-y-2">
                {alerts.slice(0, 10).map((alert) => (
                  <div key={alert.id} className="flex items-start gap-2.5 rounded-lg bg-surface-inset px-3 py-2">
                    <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${ALERT_SEVERITY_DOT[alert.severity]}`} />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-[11px] font-semibold uppercase tracking-wider text-text-muted">
                          {ALERT_TYPE_LABELS[alert.alert_type]}
                        </span>
                        <span className="shrink-0 text-[13px] text-text-muted">{formatDateTime(alert.created_at)}</span>
                      </div>
                      <p className="mt-0.5 text-xs text-text-secondary">{alert.message}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>

        {/* Right: private notes (agent-only) */}
        <div>
          <Card>
            <p className="mb-4 text-xs font-semibold uppercase tracking-wider text-text-muted">
              Private notes
            </p>
            <div className="space-y-4">
              {/* Client status */}
              <div>
                <label className={LABEL}>Client status</label>
                <div className="grid grid-cols-1 gap-1.5">
                  {(Object.keys(CLIENT_STATUS_LABELS) as ClientStatus[]).map((s) => (
                    <button
                      key={s}
                      type="button"
                      onClick={() => { setClientStatus(s); setDirty(true); }}
                      className={`flex items-center gap-2 rounded-lg px-3 py-2 text-left text-xs font-medium ring-1 transition-all ${
                        clientStatus === s
                          ? CLIENT_STATUS_COLORS[s] + " ring-1"
                          : "bg-surface-inset ring-input-border text-text-muted hover:text-text hover:ring-accent"
                      }`}
                    >
                      {clientStatus === s && <span className="h-1.5 w-1.5 rounded-full bg-current" />}
                      {CLIENT_STATUS_LABELS[s]}
                    </button>
                  ))}
                </div>
              </div>

              {/* Preferred destinations */}
              <div>
                <label className={LABEL}>Preferred destinations</label>
                <input
                  type="text"
                  value={destinations}
                  onChange={(e) => { setDestinations(e.target.value); setDirty(true); }}
                  placeholder="e.g. Premier League, La Liga"
                  className={INPUT}
                />
              </div>

              {/* Asking price + wage */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className={LABEL}>Asking price</label>
                  <input
                    type="number"
                    min={0}
                    value={askingPrice}
                    onChange={(e) => { setAskingPrice(e.target.value); setDirty(true); }}
                    placeholder="e.g. 15000000"
                    className={INPUT}
                  />
                </div>
                <div>
                  <label className={LABEL}>Asking wage / week</label>
                  <input
                    type="number"
                    min={0}
                    value={askingWage}
                    onChange={(e) => { setAskingWage(e.target.value); setDirty(true); }}
                    placeholder="e.g. 50000"
                    className={INPUT}
                  />
                </div>
              </div>

              {/* Notes */}
              <div>
                <label className={LABEL}>Notes</label>
                <textarea
                  rows={4}
                  value={notes}
                  onChange={(e) => { setNotes(e.target.value); setDirty(true); }}
                  placeholder="Private notes about this client…"
                  className={INPUT + " resize-none"}
                />
              </div>

              {/* Mandate dates/territory */}
              <div className="border-t border-rule pt-4">
                <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-text-muted">
                  Mandate settings
                </p>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className={LABEL}>Start date</label>
                    <input
                      type="date"
                      value={mandateStart}
                      onChange={(e) => { setMandateStart(e.target.value); setDirty(true); }}
                      className={INPUT}
                    />
                  </div>
                  <div>
                    <label className={LABEL}>End date</label>
                    <input
                      type="date"
                      value={mandateEnd}
                      onChange={(e) => { setMandateEnd(e.target.value); setDirty(true); }}
                      className={INPUT}
                    />
                  </div>
                </div>
                <div className="mt-3">
                  <label className={LABEL}>Territory</label>
                  <input
                    type="text"
                    value={territory}
                    onChange={(e) => { setTerritory(e.target.value); setDirty(true); }}
                    placeholder="e.g. Europe"
                    className={INPUT}
                  />
                </div>
              </div>

              {/* Alert preferences (TRA-135) */}
              <div className="border-t border-rule pt-4">
                <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-text-muted">
                  Alert preferences
                </p>
                <div className="space-y-3">
                  <div className="flex items-center justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <p className="text-xs font-medium text-text-secondary">Contract expiry</p>
                      <div className="mt-1 flex items-center gap-1.5">
                        <span className="text-[11px] text-text-muted">Alert within</span>
                        <input
                          type="number"
                          min={1}
                          max={36}
                          value={alertContractExpiryMonths}
                          disabled={!alertContractExpiryEnabled}
                          onChange={(e) => { setAlertContractExpiryMonths(e.target.value); setDirty(true); }}
                          className="w-14 rounded bg-surface px-1.5 py-0.5 text-xs text-text ring-1 ring-input-border focus:outline-none focus:ring-accent disabled:opacity-50"
                        />
                        <span className="text-[11px] text-text-muted">months of expiry</span>
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => { setAlertContractExpiryEnabled((v) => !v); setDirty(true); }}
                      className={`relative inline-flex h-5 w-9 shrink-0 rounded-full border-2 border-transparent transition-colors focus:outline-none ${
                        alertContractExpiryEnabled ? "bg-success" : "bg-border"
                      }`}
                    >
                      <span className={`pointer-events-none inline-block h-4 w-4 rounded-full bg-white shadow transition-transform ${
                        alertContractExpiryEnabled ? "translate-x-4" : "translate-x-0"
                      }`} />
                    </button>
                  </div>

                  <div className="flex items-center justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <p className="text-xs font-medium text-text-secondary">Valuation change</p>
                      <div className="mt-1 flex items-center gap-1.5">
                        <span className="text-[11px] text-text-muted">Alert on moves over</span>
                        <input
                          type="number"
                          min={1}
                          max={100}
                          value={alertValuationChangePct}
                          disabled={!alertValuationChangeEnabled}
                          onChange={(e) => { setAlertValuationChangePct(e.target.value); setDirty(true); }}
                          className="w-14 rounded bg-surface px-1.5 py-0.5 text-xs text-text ring-1 ring-input-border focus:outline-none focus:ring-accent disabled:opacity-50"
                        />
                        <span className="text-[11px] text-text-muted">%</span>
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => { setAlertValuationChangeEnabled((v) => !v); setDirty(true); }}
                      className={`relative inline-flex h-5 w-9 shrink-0 rounded-full border-2 border-transparent transition-colors focus:outline-none ${
                        alertValuationChangeEnabled ? "bg-success" : "bg-border"
                      }`}
                    >
                      <span className={`pointer-events-none inline-block h-4 w-4 rounded-full bg-white shadow transition-transform ${
                        alertValuationChangeEnabled ? "translate-x-4" : "translate-x-0"
                      }`} />
                    </button>
                  </div>

                  <div className="flex items-center justify-between gap-3">
                    <p className="text-xs font-medium text-text-secondary">Club interest</p>
                    <button
                      type="button"
                      onClick={() => { setAlertClubInterestEnabled((v) => !v); setDirty(true); }}
                      className={`relative inline-flex h-5 w-9 shrink-0 rounded-full border-2 border-transparent transition-colors focus:outline-none ${
                        alertClubInterestEnabled ? "bg-success" : "bg-border"
                      }`}
                    >
                      <span className={`pointer-events-none inline-block h-4 w-4 rounded-full bg-white shadow transition-transform ${
                        alertClubInterestEnabled ? "translate-x-4" : "translate-x-0"
                      }`} />
                    </button>
                  </div>
                </div>
              </div>

              {dirty && (
                <Button
                  variant="primary"
                  loading={saveMutation.isPending}
                  onClick={handleSave}
                  className="w-full"
                >
                  Save changes
                </Button>
              )}
              {saveMutation.isError && (
                <p className="text-xs text-danger-text">Failed to save. Please try again.</p>
              )}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
