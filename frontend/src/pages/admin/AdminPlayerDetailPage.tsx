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
import { formatDate, getApiError } from "../../lib/utils";
import { positionVariant } from "../../lib/badges";
import type { PlayerPosition } from "../../types/enums";

const POSITIONS  = ["GK", "DEF", "MID", "FWD"];
const VISIBILITIES = ["PUBLIC", "CLUBS_ONLY", "PRIVATE"];
const STATUSES   = ["CONTRACTED", "FREE_AGENT"];

const VIS_STYLE: Record<string, string> = {
  PUBLIC:     "text-emerald-400",
  CLUBS_ONLY: "text-sky-400",
  PRIVATE:    "text-slate-500",
};

export default function AdminPlayerDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const { data: player, isLoading } = useQuery<Player>({
    queryKey: ["admin", "players", id],
    queryFn: () => api.get<Player>(`/admin/players/${id}`).then((r) => r.data),
    enabled: !!id,
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

  if (isLoading) return <div className="flex justify-center py-12"><Spinner size="lg" /></div>;
  if (!player) return (
    <div className="rounded-xl bg-red-500/10 px-5 py-4 text-sm text-red-400 ring-1 ring-red-500/30">
      Player not found.{" "}
      <button onClick={() => navigate("/admin/players")} className="underline">Back</button>
    </div>
  );

  return (
    <div>
      <button
        onClick={() => navigate("/admin/players")}
        className="mb-6 flex items-center gap-1.5 text-sm text-slate-400 hover:text-white transition-colors"
      >
        ← Back to players
      </button>

      <div className="mb-6 flex items-center gap-3">
        {player.photo_url ? (
          <img src={player.photo_url} alt={player.name} className="h-12 w-12 rounded-full object-cover ring-1 ring-white/10" />
        ) : (
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-slate-800 text-lg font-bold text-slate-400">
            {player.name[0]?.toUpperCase()}
          </div>
        )}
        <div>
          <h1 className="text-2xl font-bold text-white">{player.name}</h1>
          <p className="text-xs text-slate-500">ID: {player.id}</p>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* ── Profile card ── */}
        <Card>
          <div className="mb-4 flex items-center justify-between">
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">Player Profile</p>
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
                  {player.status === "FREE_AGENT" ? "Free Agent" : "Contracted"}
                </Badge>
              } />
              <Metric label="Visibility"  value={
                <span className={`text-xs font-medium ${VIS_STYLE[player.visibility] ?? ""}`}>
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
                  <label className="mb-1 block text-xs text-slate-400">{label}</label>
                  <input
                    value={val}
                    onChange={(e) => set(e.target.value)}
                    className="w-full rounded-lg bg-slate-800 px-3 py-2 text-sm text-white ring-1 ring-white/10 focus:outline-none focus:ring-amber-500"
                  />
                </div>
              ))}
              <div>
                <label className="mb-1 block text-xs text-slate-400">Age</label>
                <input
                  type="number"
                  value={fAge}
                  onChange={(e) => setFAge(e.target.value)}
                  className="w-full rounded-lg bg-slate-800 px-3 py-2 text-sm text-white ring-1 ring-white/10 focus:outline-none focus:ring-amber-500"
                />
              </div>
              {[
                { label: "Position",   val: fPosition,   set: setFPosition,   options: ["", ...POSITIONS]   },
                { label: "Visibility", val: fVisibility, set: setFVisibility, options: ["", ...VISIBILITIES] },
                { label: "Status",     val: fStatus,     set: setFStatus,     options: ["", ...STATUSES]     },
              ].map(({ label, val, set, options }) => (
                <div key={label}>
                  <label className="mb-1 block text-xs text-slate-400">{label}</label>
                  <select
                    value={val}
                    onChange={(e) => set(e.target.value)}
                    className="w-full rounded-lg bg-slate-800 px-3 py-2 text-sm text-white ring-1 ring-white/10 focus:outline-none focus:ring-amber-500"
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
                  className="rounded accent-amber-500"
                />
                <label htmlFor="oto" className="text-sm text-slate-300">Open to offers</label>
              </div>

              <div className="border-t border-white/[0.06] pt-3">
                <label className="mb-1 block text-xs text-slate-400">Reassign to club (ID)</label>
                <input
                  value={fClubId}
                  onChange={(e) => { setFClubId(e.target.value); setFClearClub(false); }}
                  placeholder="paste club UUID…"
                  disabled={fClearClub}
                  className="w-full rounded-lg bg-slate-800 px-3 py-2 text-sm text-white ring-1 ring-white/10 focus:outline-none focus:ring-amber-500 disabled:opacity-40"
                />
                <label className="mt-2 flex items-center gap-2 text-xs text-slate-400">
                  <input
                    type="checkbox"
                    checked={fClearClub}
                    onChange={(e) => { setFClearClub(e.target.checked); if (e.target.checked) setFClubId(""); }}
                    className="rounded accent-amber-500"
                  />
                  Make free agent (clear club)
                </label>
              </div>

              {mutation.isError && (
                <p className="text-xs text-red-400">{getApiError(mutation.error, "Save failed.")}</p>
              )}
              <div className="flex gap-2">
                <Button type="submit" variant="primary" size="sm" loading={mutation.isPending}>Save</Button>
                <Button type="button" variant="ghost" size="sm" onClick={() => setEditing(false)}>Cancel</Button>
              </div>
            </form>
          )}
        </Card>

        {/* ── Contract info ── */}
        <Card>
          <p className="mb-4 text-xs font-semibold uppercase tracking-wider text-slate-400">Contracts</p>
          {(!player.contracts || player.contracts.length === 0) ? (
            <p className="text-sm text-slate-500">No contracts on record.</p>
          ) : (
            <div className="space-y-2">
              {player.contracts.map((c: { id: string; club_id: string; start_date?: string; end_date?: string; wage_weekly?: number; is_active: boolean }) => (
                <div key={c.id} className="rounded-lg bg-slate-800/50 px-3 py-2 text-xs">
                  <div className="flex items-center justify-between">
                    <span className="text-slate-300">Club: {c.club_id.slice(0, 8)}…</span>
                    <Badge variant={c.is_active ? "success" : "neutral"}>{c.is_active ? "Active" : "Inactive"}</Badge>
                  </div>
                  {c.end_date && <p className="mt-1 text-slate-500">Ends: {formatDate(c.end_date)}</p>}
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
