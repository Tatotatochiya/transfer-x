import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "../../lib/api";
import type { ClientStatus, MandateDetailResponse, UpdateMandateRequest } from "../../types/api";
import Card from "../../components/ui/Card";
import PageHeader from "../../components/ui/PageHeader";
import Spinner from "../../components/ui/Spinner";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import { formatCurrency } from "../../lib/utils";

const CLIENT_STATUS_LABELS: Record<ClientStatus, string> = {
  ACTIVE:             "Active",
  SEEKING_MOVE:       "Seeking move",
  LOAN_AVAILABLE:     "Available for loan",
  CONTRACT_EXTENSION: "Contract extension",
  UNAVAILABLE:        "Unavailable",
};

const CLIENT_STATUS_COLORS: Record<ClientStatus, string> = {
  ACTIVE:             "bg-emerald-500/15 text-emerald-400 ring-emerald-500/30",
  SEEKING_MOVE:       "bg-sky-500/15 text-sky-400 ring-sky-500/30",
  LOAN_AVAILABLE:     "bg-purple-500/15 text-purple-400 ring-purple-500/30",
  CONTRACT_EXTENSION: "bg-amber-500/15 text-amber-400 ring-amber-500/30",
  UNAVAILABLE:        "bg-slate-700 text-slate-400 ring-white/10",
};

const INPUT = "w-full rounded-lg bg-slate-800 px-3 py-2 text-sm text-white ring-1 ring-white/10 focus:outline-none focus:ring-emerald-500 placeholder-slate-500";
const LABEL = "mb-1.5 block text-xs font-medium text-slate-400";

export default function AgentClientPage() {
  const { mandateId } = useParams<{ mandateId: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const { data: client, isLoading } = useQuery<MandateDetailResponse>({
    queryKey: ["mandates", mandateId],
    queryFn: () => api.get<MandateDetailResponse>(`/mandates/${mandateId}`).then((r) => r.data),
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
        className="mb-4 flex items-center gap-1.5 text-sm text-slate-400 hover:text-white transition-colors"
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
            <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-400">
              Player
            </p>
            <div className="space-y-2 text-sm">
              {client.player_age != null && (
                <div className="flex justify-between">
                  <span className="text-slate-500">Age</span>
                  <span className="text-white">{client.player_age}</span>
                </div>
              )}
              {client.player_nationality && (
                <div className="flex justify-between">
                  <span className="text-slate-500">Nationality</span>
                  <span className="text-white">{client.player_nationality}</span>
                </div>
              )}
              {client.player_club_name && (
                <div className="flex justify-between">
                  <span className="text-slate-500">Club</span>
                  <span className="text-white">{client.player_club_name}</span>
                </div>
              )}
              {client.contract_expiry && (
                <div className="flex justify-between">
                  <span className="text-slate-500">Contract expires</span>
                  <span className={`font-medium ${
                    daysUntilExpiry != null && daysUntilExpiry < 180
                      ? "text-amber-400"
                      : "text-white"
                  }`}>
                    {client.contract_expiry}
                    {daysUntilExpiry != null && daysUntilExpiry > 0 && (
                      <span className="ml-1 text-xs text-slate-500">({daysUntilExpiry}d)</span>
                    )}
                  </span>
                </div>
              )}
            </div>
            <div className="mt-3 border-t border-white/[0.06] pt-3">
              <Link
                to={`/players/market/${client.player_id}`}
                className="text-xs text-emerald-400 hover:underline"
              >
                View market profile →
              </Link>
            </div>
          </Card>

          <Card>
            <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-400">
              Mandate
            </p>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-slate-500">Type</span>
                <span>
                  {client.exclusive
                    ? <Badge variant="success">Exclusive</Badge>
                    : <span className="text-slate-400">Non-exclusive</span>}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Status</span>
                <span className={`rounded-full px-2 py-0.5 text-xs font-medium ring-1 ${CLIENT_STATUS_COLORS[clientStatus]}`}>
                  {CLIENT_STATUS_LABELS[clientStatus]}
                </span>
              </div>
              {client.start_date && (
                <div className="flex justify-between">
                  <span className="text-slate-500">Start</span>
                  <span className="text-white">{client.start_date}</span>
                </div>
              )}
              {client.end_date && (
                <div className="flex justify-between">
                  <span className="text-slate-500">End</span>
                  <span className="text-white">{client.end_date}</span>
                </div>
              )}
              {client.territory && (
                <div className="flex justify-between">
                  <span className="text-slate-500">Territory</span>
                  <span className="text-white">{client.territory}</span>
                </div>
              )}
            </div>
          </Card>
        </div>

        {/* Right: private notes (agent-only) */}
        <div>
          <Card>
            <p className="mb-4 text-xs font-semibold uppercase tracking-wider text-slate-400">
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
                          : "bg-slate-800 ring-white/10 text-slate-400 hover:text-white hover:ring-white/20"
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
              <div className="border-t border-white/[0.06] pt-4">
                <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-500">
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
                <p className="text-xs text-red-400">Failed to save. Please try again.</p>
              )}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
