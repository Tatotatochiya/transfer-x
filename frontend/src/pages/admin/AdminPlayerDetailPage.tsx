import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "../../lib/api";
import type { Player } from "../../types/api";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import Metric from "../../components/ui/Metric";
import Spinner from "../../components/ui/Spinner";
import PlayerAccountCard from "../../components/players/PlayerAccountCard";
import { formatDate, getApiError } from "../../lib/utils";
import { positionVariant } from "../../lib/badges";
import type { PlayerPosition } from "../../types/enums";
import FallbackImage from "../../components/ui/FallbackImage";
import { useConfirm } from "../../context/ConfirmContext";

/** GET /admin/players/{id}: the player plus every contract, past and present. */
type AdminPlayer = Player & {
  contracts: { id: string; club_id: string; start_date?: string; end_date?: string; wage_weekly?: number; is_active: boolean }[];
};

/** One row of GET /admin/players/{id}/transfer-fees (vendor and staff rows alike). */
type TransferFee = {
  id: string;
  transfer_date: string | null;
  transfer_type: string | null;
  from_club: string | null;
  to_club: string | null;
  fee_display: string | null;
  fee_gbp: number | null;
  vendor: string;
  fee_basis: string | null;
  source_note: string | null;
  source_url: string | null;
  entered_by_user_id: string | null;
};

const EMPTY_FEE = {
  amount: "", currency: "GBP", transfer_date: "", from_club: "", to_club: "",
  basis: "PERMANENT", source_note: "", source_url: "",
};

const POSITIONS  = ["GK", "DEF", "MID", "FWD"];
const VISIBILITIES = ["PUBLIC", "CLUBS_ONLY", "PRIVATE"];
const STATUSES   = ["CONTRACTED", "EXTERNAL", "FREE_AGENT"];

const VIS_STYLE: Record<string, string> = {
  PUBLIC:     "text-success-text",
  CLUBS_ONLY: "text-accent",
  PRIVATE:    "text-text-muted",
};

export default function AdminPlayerDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const confirm = useConfirm();

  const { data: player, isLoading } = useQuery<AdminPlayer>({
    queryKey: ["admin", "players", id],
    queryFn: () => api.get<AdminPlayer>(`/admin/players/${id}`).then((r) => r.data),
    enabled: !!id,
  });

  // The fee history the market-v3 anchor reads: vendor rows plus staff entries.
  const { data: fees = [], isLoading: feesLoading } = useQuery<TransferFee[]>({
    queryKey: ["admin", "players", id, "transfer-fees"],
    queryFn: () => api.get<TransferFee[]>(`/admin/players/${id}/transfer-fees`).then((r) => r.data),
    enabled: !!id,
  });
  const [feeForm, setFeeForm] = useState(EMPTY_FEE);

  /** The fee is an input to his valuation and the ledger's Last transfer cell. */
  function invalidateFeeDependents() {
    queryClient.invalidateQueries({ queryKey: ["admin", "players", id, "transfer-fees"] });
    queryClient.invalidateQueries({ queryKey: ["valuation"] });
    queryClient.invalidateQueries({ queryKey: ["players", id, "ledger"] });
  }

  const addFee = useMutation({
    mutationFn: (body: object) =>
      api.post(`/admin/players/${id}/transfer-fees`, body).then((r) => r.data),
    onSuccess: () => {
      invalidateFeeDependents();
      setFeeForm(EMPTY_FEE);
    },
  });

  const removeFee = useMutation({
    mutationFn: (feeId: string) => api.delete(`/admin/players/${id}/transfer-fees/${feeId}`),
    onSuccess: invalidateFeeDependents,
  });

  const [editing, setEditing] = useState(false);

  // form state
  const [fName,          setFName]         = useState("");
  const [fAge,           setFAge]          = useState("");
  const [fNationality,   setFNationality]  = useState("");
  const [fPosition,      setFPosition]     = useState("");
  const [fVisibility,    setFVisibility]   = useState("");
  const [fStatus,        setFStatus]       = useState("");
  const [fOpenToOffers,  setFOpenToOffers] = useState(false);
  const [fPhotoUrl,      setFPhotoUrl]     = useState("");
  const [fClubId,        setFClubId]       = useState("");
  const [fClearClub,     setFClearClub]    = useState(false);

  useEffect(() => {
    if (player && editing) {
      setFName(player.name);
      setFAge(player.age != null ? String(player.age) : "");
      setFNationality(player.nationality ?? "");
      setFPosition(player.position ?? "");
      setFVisibility(player.visibility ?? "");
      setFStatus(player.status ?? "");
      setFOpenToOffers(player.open_to_offers ?? false);
      setFPhotoUrl(player.photo_url ?? "");
      setFClubId(player.current_club?.id ?? "");
      setFClearClub(false);
    }
  }, [player, editing]);

  const mutation = useMutation({
    mutationFn: (body: object) =>
      api.patch<Player>(`/admin/players/${id}`, body).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "players", id] });
      queryClient.invalidateQueries({ queryKey: ["admin", "players"] });
      setEditing(false);
    },
  });

  function handleSave(e: React.FormEvent) {
    e.preventDefault();
    mutation.mutate({
      name:           fName || undefined,
      age:            fAge ? parseInt(fAge) : undefined,
      nationality:    fNationality || undefined,
      position:       fPosition || undefined,
      visibility:     fVisibility || undefined,
      status:         fStatus || undefined,
      open_to_offers: fOpenToOffers,
      photo_url:      fPhotoUrl || undefined,
      current_club_id: (!fClearClub && fClubId) ? fClubId : undefined,
      clear_club:     fClearClub,
    });
  }

  async function handleRemoveFee(fee: TransferFee) {
    const ok = await confirm({
      title: "Remove this fee?",
      message: "His model value is recalculated straight away.",
      confirmLabel: "Remove",
    });
    if (ok) removeFee.mutate(fee.id);
  }

  function handleAddFee(e: React.FormEvent) {
    e.preventDefault();
    addFee.mutate({
      amount: Number(feeForm.amount),
      currency: feeForm.currency,
      transfer_date: feeForm.transfer_date,
      from_club: feeForm.from_club,
      to_club: feeForm.to_club,
      basis: feeForm.basis,
      source_note: feeForm.source_note,
      source_url: feeForm.source_url || undefined,
    });
  }

  const feeInput = "w-full rounded-lg bg-surface px-3 py-2 text-input lg:text-body text-text ring-1 ring-input-border focus:outline-none focus:ring-warning-fill";
  const feeLabel = "mb-1 block text-caption text-text-muted";

  if (isLoading) return <div className="flex justify-center py-12"><Spinner size="lg" /></div>;
  if (!player) return (
    <div className="rounded-xl bg-danger-bg px-5 py-4 text-small text-danger-text ring-1 ring-danger-border">
      Player not found.{" "}
      <button onClick={() => navigate("/admin/players")} className="underline">Back</button>
    </div>
  );

  return (
    <div>
      <button
        onClick={() => navigate("/admin/players")}
        className="mb-6 flex items-center gap-1.5 text-body text-text-muted hover:text-text transition-colors"
      >
        ← Back to players
      </button>

      <div className="mb-6 flex items-center gap-3">
        <FallbackImage src={player.photo_url} name={player.name} sizeClass="h-12 w-12 text-section" colorClass="bg-surface-inset text-text-muted" className={player.photo_url ? "ring-1 ring-border" : ""} />
        <div>
          <h1 className="text-title-sm sm:text-title font-bold text-text">{player.name}</h1>
          <p className="text-small text-text-muted">ID: {player.id}</p>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* ── Profile card ── */}
        <Card>
          <div className="mb-4 flex items-center justify-between">
            <p className="text-caption font-semibold text-text-secondary">Player profile</p>
            {!editing && <Button variant="secondary" size="sm" onClick={() => setEditing(true)}>Edit</Button>}
          </div>

          {!editing ? (
            <div className="space-y-2">
              <Metric label="Name"        value={player.name} />
              <Metric label="Position"    value={
                player.position
                  ? <Badge variant={positionVariant(player.position as PlayerPosition)}>{player.position}</Badge>
                  : "—"
              } />
              <Metric label="Age"         value={player.age ?? "—"} />
              <Metric label="Nationality" value={player.nationality ?? "—"} />
              <Metric label="Status"      value={
                <Badge variant={player.status === "FREE_AGENT" ? "warning" : "info"}>
                  {player.status === "FREE_AGENT" ? "Free Agent"
                    : player.status === "EXTERNAL" ? "External"
                    : "Contracted"}
                </Badge>
              } />
              <Metric label="Visibility"  value={
                <span className={`text-caption font-medium ${VIS_STYLE[player.visibility] ?? ""}`}>
                  {player.visibility}
                </span>
              } />
              <Metric label="Open to offers" value={
                <Badge variant={player.open_to_offers ? "success" : "neutral"}>
                  {player.open_to_offers ? "Yes" : "No"}
                </Badge>
              } />
              <Metric label="Current club" value={player.current_club?.name ?? player.team_name ?? "—"} />
              <Metric label="Added"        value={formatDate(player.created_at)} />
            </div>
          ) : (
            <form onSubmit={handleSave} className="space-y-3">
              {[
                { label: "Name",        val: fName,        set: setFName        },
                { label: "Nationality", val: fNationality, set: setFNationality },
                { label: "Photo URL",   val: fPhotoUrl,    set: setFPhotoUrl    },
              ].map(({ label, val, set }) => (
                <div key={label}>
                  <label className="mb-1 block text-caption text-text-muted">{label}</label>
                  <input
                    value={val}
                    onChange={(e) => set(e.target.value)}
                    className="w-full rounded-lg bg-surface px-3 py-2 text-input lg:text-body text-text ring-1 ring-input-border focus:outline-none focus:ring-warning-fill"
                  />
                </div>
              ))}
              <div>
                <label className="mb-1 block text-caption text-text-muted">Age</label>
                <input
                  type="number"
                  value={fAge}
                  onChange={(e) => setFAge(e.target.value)}
                  className="w-full rounded-lg bg-surface px-3 py-2 text-input lg:text-body text-text ring-1 ring-input-border focus:outline-none focus:ring-warning-fill"
                />
              </div>
              {[
                { label: "Position",   val: fPosition,   set: setFPosition,   options: ["", ...POSITIONS]   },
                { label: "Visibility", val: fVisibility, set: setFVisibility, options: ["", ...VISIBILITIES] },
                { label: "Status",     val: fStatus,     set: setFStatus,     options: ["", ...STATUSES]     },
              ].map(({ label, val, set, options }) => (
                <div key={label}>
                  <label className="mb-1 block text-caption text-text-muted">{label}</label>
                  <select
                    value={val}
                    onChange={(e) => set(e.target.value)}
                    className="w-full rounded-lg bg-surface px-3 py-2 text-input lg:text-body text-text ring-1 ring-input-border focus:outline-none focus:ring-warning-fill"
                  >
                    {options.map((o) => <option key={o} value={o}>{o || `— keep current —`}</option>)}
                  </select>
                </div>
              ))}

              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="oto"
                  checked={fOpenToOffers}
                  onChange={(e) => setFOpenToOffers(e.target.checked)}
                  className="rounded accent-warning-fill"
                />
                <label htmlFor="oto" className="text-small text-text-secondary">Open to offers</label>
              </div>

              <div className="border-t border-rule pt-3">
                <label className="mb-1 block text-caption text-text-muted">Reassign to club (ID)</label>
                <input
                  value={fClubId}
                  onChange={(e) => { setFClubId(e.target.value); setFClearClub(false); }}
                  placeholder="paste club UUID…"
                  disabled={fClearClub}
                  className="w-full rounded-lg bg-surface px-3 py-2 text-input lg:text-body text-text ring-1 ring-input-border focus:outline-none focus:ring-warning-fill disabled:opacity-40"
                />
                <label className="mt-2 flex items-center gap-2 text-caption text-text-muted">
                  <input
                    type="checkbox"
                    checked={fClearClub}
                    onChange={(e) => { setFClearClub(e.target.checked); if (e.target.checked) setFClubId(""); }}
                    className="rounded accent-warning-fill"
                  />
                  Make free agent (clear club)
                </label>
              </div>

              {mutation.isError && (
                <p className="text-small text-danger-text">{getApiError(mutation.error, "Save failed.")}</p>
              )}
              <div className="flex gap-2">
                <Button type="submit" variant="primary" size="sm" loading={mutation.isPending}>Save</Button>
                <Button type="button" variant="ghost" size="sm" onClick={() => setEditing(false)}>Cancel</Button>
              </div>
            </form>
          )}
        </Card>

        {/* ── Player account: TransferX invites a free agent ── */}
        <PlayerAccountCard
          playerId={player.id}
          playerName={player.name}
          inviter="staff"
          canInvite={player.status === "FREE_AGENT"}
        />

        {/* ── Contract info ── */}
        <Card>
          <p className="mb-4 text-caption font-semibold text-text-secondary">Contracts</p>
          {(!player.contracts || player.contracts.length === 0) ? (
            <p className="text-small text-text-muted">No contracts on record.</p>
          ) : (
            <div className="space-y-2">
              {player.contracts.map((c: { id: string; club_id: string; start_date?: string; end_date?: string; wage_weekly?: number; is_active: boolean }) => (
                <div key={c.id} className="rounded-lg bg-surface-inset px-3 py-2 text-caption">
                  <div className="flex items-center justify-between">
                    <span className="text-text-secondary">Club: {c.club_id.slice(0, 8)}…</span>
                    <Badge variant={c.is_active ? "success" : "neutral"}>{c.is_active ? "Active" : "Inactive"}</Badge>
                  </div>
                  {c.end_date && <p className="mt-1 text-text-muted">Ends: {formatDate(c.end_date)}</p>}
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>

      {/* ── Transfer fees: staff entries plus the vendor's, the anchor's input ── */}
      <Card className="mt-6">
        <div className="mb-4 flex items-center justify-between">
          <p className="text-caption font-semibold text-text-secondary">Transfer fees</p>
          <span className="text-small text-text-muted">The newest fee is his last transfer</span>
        </div>

        {feesLoading ? (
          <div className="flex justify-center py-6"><Spinner /></div>
        ) : fees.length === 0 ? (
          <p className="mb-5 text-small text-text-muted">No fees on record.</p>
        ) : (
          <div className="mb-5 overflow-x-auto">
            <table className="w-full text-left text-small">
              <thead>
                <tr className="text-text-muted">
                  <th className="pb-2 pr-3 font-medium">Date</th>
                  <th className="pb-2 pr-3 font-medium">Move</th>
                  <th className="pb-2 pr-3 font-medium">Fee</th>
                  <th className="pb-2 pr-3 font-medium">Source</th>
                  <th className="pb-2 pr-3 font-medium">Note</th>
                  <th className="pb-2 font-medium" />
                </tr>
              </thead>
              <tbody>
                {fees.map((fee) => (
                  <tr key={fee.id} className="border-t border-rule">
                    <td className="py-2 pr-3 tabular-nums text-text-secondary">
                      {fee.transfer_date ? formatDate(fee.transfer_date) : "—"}
                    </td>
                    <td className="py-2 pr-3 text-text-secondary">
                      {[fee.from_club, fee.to_club].filter(Boolean).join(" → ") || "—"}
                    </td>
                    <td className="py-2 pr-3 tabular-nums text-text">{fee.fee_display ?? "—"}</td>
                    <td className="py-2 pr-3 text-text-secondary">
                      {fee.vendor === "manual" ? "Manual" : "API-Football"}
                    </td>
                    <td className="py-2 pr-3 text-text-muted">
                      {fee.source_url ? (
                        <a href={fee.source_url} target="_blank" rel="noreferrer" className="underline hover:text-text">
                          {fee.source_note ?? fee.source_url}
                        </a>
                      ) : fee.source_note ?? "—"}
                    </td>
                    <td className="py-2 text-right">
                      {fee.vendor === "manual" && (
                        <button
                          type="button"
                          onClick={() => void handleRemoveFee(fee)}
                          disabled={removeFee.isPending}
                          aria-label={`Remove the fee from ${fee.transfer_date ?? "record"}`}
                          className="text-small text-danger-text hover:underline disabled:opacity-40"
                        >
                          Remove
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <form onSubmit={handleAddFee} className="grid gap-3 border-t border-rule pt-4 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <label htmlFor="fee-amount" className={feeLabel}>Amount</label>
            <input id="fee-amount" type="number" min="1" step="any" required value={feeForm.amount}
              onChange={(e) => setFeeForm({ ...feeForm, amount: e.target.value })} className={feeInput} />
          </div>
          <div>
            <label htmlFor="fee-currency" className={feeLabel}>Currency</label>
            <select id="fee-currency" value={feeForm.currency}
              onChange={(e) => setFeeForm({ ...feeForm, currency: e.target.value })} className={feeInput}>
              {["GBP", "EUR", "USD"].map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          <div>
            <label htmlFor="fee-date" className={feeLabel}>Transfer date</label>
            <input id="fee-date" type="date" required value={feeForm.transfer_date}
              max={new Date().toISOString().slice(0, 10)}
              onChange={(e) => setFeeForm({ ...feeForm, transfer_date: e.target.value })} className={feeInput} />
          </div>
          <div>
            <label htmlFor="fee-basis" className={feeLabel}>Basis</label>
            <select id="fee-basis" value={feeForm.basis}
              onChange={(e) => setFeeForm({ ...feeForm, basis: e.target.value })} className={feeInput}>
              <option value="PERMANENT">Permanent transfer</option>
              <option value="RELEASE_CLAUSE">Release clause</option>
            </select>
          </div>
          <div>
            <label htmlFor="fee-from" className={feeLabel}>From club</label>
            <input id="fee-from" required maxLength={200} value={feeForm.from_club}
              onChange={(e) => setFeeForm({ ...feeForm, from_club: e.target.value })} className={feeInput} />
          </div>
          <div>
            <label htmlFor="fee-to" className={feeLabel}>To club</label>
            <input id="fee-to" required maxLength={200} value={feeForm.to_club}
              onChange={(e) => setFeeForm({ ...feeForm, to_club: e.target.value })} className={feeInput} />
          </div>
          <div>
            <label htmlFor="fee-note" className={feeLabel}>Source note (shown to clubs)</label>
            <input id="fee-note" required minLength={5} maxLength={500} placeholder="e.g. BBC Sport, 15 Jul 2023"
              value={feeForm.source_note}
              onChange={(e) => setFeeForm({ ...feeForm, source_note: e.target.value })} className={feeInput} />
          </div>
          <div>
            <label htmlFor="fee-url" className={feeLabel}>Source URL</label>
            <input id="fee-url" type="url" maxLength={512} placeholder="https://…"
              value={feeForm.source_url}
              onChange={(e) => setFeeForm({ ...feeForm, source_url: e.target.value })} className={feeInput} />
            <p className="mt-1 text-small text-text-muted">Admins only — this link is not shown to clubs.</p>
          </div>

          <div className="flex items-center gap-2 sm:col-span-2 lg:col-span-4">
            <Button type="submit" variant="primary" size="sm" loading={addFee.isPending}>Record fee</Button>
            {addFee.isError && (
              <p className="text-small text-danger-text">{getApiError(addFee.error, "Could not record the fee.")}</p>
            )}
            {removeFee.isError && (
              <p className="text-small text-danger-text">{getApiError(removeFee.error, "Could not remove the fee.")}</p>
            )}
          </div>
        </form>
      </Card>
    </div>
  );
}
