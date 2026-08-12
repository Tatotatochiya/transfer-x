import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import api from "../../lib/api";
import type { Player } from "../../types/api";
import { useCompare } from "../../context/CompareContext";

function PlayerSlot({ id, onRemove }: { id: string; onRemove: () => void }) {
  const { data: player } = useQuery<Player>({
    queryKey: ["players", "market", id],
    queryFn: () => api.get<Player>(`/players/market/${id}`).then((r) => r.data),
    staleTime: 60_000,
  });

  return (
    <div className="flex items-center gap-2 rounded-lg bg-white/10 px-2.5 py-1.5 ring-1 ring-white/15">
      {player?.photo_url ? (
        <img src={player.photo_url} alt={player.name} className="h-6 w-6 shrink-0 rounded-full object-cover" />
      ) : (
        <div className="h-6 w-6 shrink-0 rounded-full bg-white/15 flex items-center justify-center text-[10px] font-bold text-white/80">
          {player?.name[0]?.toUpperCase() ?? "?"}
        </div>
      )}
      <span className="max-w-[100px] truncate text-xs font-medium text-white">
        {player?.name ?? "…"}
      </span>
      <button
        onClick={onRemove}
        className="ml-0.5 text-white/50 hover:text-white transition-colors"
        title="Remove"
      >
        <svg className="h-3 w-3" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>
  );
}

export default function CompareBar() {
  const { compareIds, toggle, clear } = useCompare();
  const navigate = useNavigate();

  if (compareIds.length === 0) return null;

  return (
    <div className="fixed bottom-0 left-0 right-0 z-50 flex items-center justify-center px-4 pb-4 pointer-events-none">
      <div className="pointer-events-auto flex items-center gap-3 rounded-2xl bg-ink px-9 py-3.5 shadow-2xl">
        <span className="text-xs font-semibold text-white/60 shrink-0">Comparing</span>

        <div className="flex items-center gap-2">
          {compareIds.map((id) => (
            <PlayerSlot key={id} id={id} onRemove={() => toggle(id)} />
          ))}
          {compareIds.length === 1 && (
            <div className="flex h-9 w-28 items-center justify-center rounded-lg border-2 border-dashed border-white/20 text-xs text-white/40">
              + add player
            </div>
          )}
        </div>

        {compareIds.length === 2 && (
          <button
            onClick={() => navigate(`/compare?a=${compareIds[0]}&b=${compareIds[1]}`)}
            className="shrink-0 rounded-lg bg-white px-3.5 py-1.5 text-xs font-bold text-ink hover:bg-white/90 transition-colors"
          >
            Compare 2 players →
          </button>
        )}

        <button
          onClick={clear}
          className="text-white/50 hover:text-white transition-colors"
          title="Clear"
        >
          <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
    </div>
  );
}
