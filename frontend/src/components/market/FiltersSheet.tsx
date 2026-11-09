import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Sheet from "../ui/Sheet";
import PlayerFilters, { ClubSearchField, type PlayerFilterState } from "../players/PlayerFilters";
import ViewSwitcher from "../players/ViewSwitcher";
import { useConfirm } from "../../context/ConfirmContext";
import { fetchMarket } from "../../lib/marketQuery";
import type { PlayerSearchView } from "../../types/api";
import { clearFilters } from "./ActiveFilterChips";

const same = (a: PlayerFilterState, b: PlayerFilterState) => JSON.stringify(a) === JSON.stringify(b);

export interface SavedViewsProps {
  views: PlayerSearchView[];
  activeViewId: string | null;
  isModified: (f: PlayerFilterState) => boolean;
  /** Applies the view straight away and returns the filters it set. */
  onSelect: (id: string | null) => PlayerFilterState;
  onCreate: (name: string, f: PlayerFilterState) => Promise<void>;
  onUpdate: (id: string, patch: { name?: string; filters?: Record<string, unknown>; is_default?: boolean }) => Promise<void>;
  onDelete: (id: string) => Promise<void>;
  onSaveToView: (id: string, f: PlayerFilterState) => Promise<void>;
}

/**
 * The filters below 1024px (browse-players-focus §5.8). The sheet edits a
 * draft: "Show {n} players" applies it, and closing with changes asks first.
 * The count is a live page_size=1 call on the draft. Saved views apply at
 * once, as in the rail, and reset the draft to the view.
 */
export default function FiltersSheet({ open, onClose, filters, onApply, saved }: {
  open: boolean;
  onClose: () => void;
  filters: PlayerFilterState;
  onApply: (f: PlayerFilterState) => void;
  /** Absent when signed out (no saved views). */
  saved?: SavedViewsProps;
}) {
  const confirm = useConfirm();
  const [draft, setDraft] = useState(filters);
  const [counted, setCounted] = useState(filters);

  useEffect(() => { if (open) { setDraft(filters); setCounted(filters); } }, [open]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const t = setTimeout(() => setCounted(draft), 300);
    return () => clearTimeout(t);
  }, [draft]);

  const { data: count, isFetching } = useQuery({
    queryKey: ["players", "market", "count", counted],
    queryFn: () => fetchMarket(counted, 1, 1).then((r) => r.total),
    enabled: open,
    staleTime: 30_000,
  });
  const settled = same(counted, draft) && !isFetching && count != null;

  async function close() {
    if (!same(draft, filters) && !(await confirm({
      title: "Discard filter changes?",
      message: "The filters you've changed here won't be applied.",
      confirmLabel: "Discard",
      variant: "danger",
    }))) return;
    onClose();
  }

  return (
    <Sheet
      open={open}
      onClose={close}
      title="Filters"
      closeLabel="Close without applying"
      headerAction={
        <button type="button" onClick={() => setDraft(clearFilters(draft))} className="min-h-11 shrink-0 px-2 text-[15px] font-semibold text-accent hover:text-accent-hover">
          Clear all
        </button>
      }
      footer={
        <button
          type="button"
          onClick={() => { onApply(draft); onClose(); }}
          className="min-h-12 w-full rounded-xl bg-accent text-base font-semibold text-white hover:bg-accent-hover"
        >
          <span aria-live="polite">{settled ? `Show ${count.toLocaleString("en-GB")} player${count === 1 ? "" : "s"}` : "Show players"}</span>
        </button>
      }
    >
      <div className="space-y-5">
        {saved && (
          <ViewSwitcher
            layout="sheet"
            views={saved.views}
            activeViewId={saved.activeViewId}
            isModified={saved.isModified(draft)}
            onSelect={(id) => setDraft(saved.onSelect(id))}
            onCreate={(name) => saved.onCreate(name, draft)}
            onUpdate={saved.onUpdate}
            onDelete={saved.onDelete}
            onSaveCurrentToView={(id) => saved.onSaveToView(id, draft)}
            onSaveCurrentAsNew={(name) => saved.onCreate(name, draft)}
          />
        )}
        <PlayerFilters layout="sheet" filters={draft} onChange={setDraft} />
        <div>
          <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-text-muted">Club</p>
          <ClubSearchField layout="sheet" filters={draft} onChange={setDraft} />
        </div>
      </div>
    </Sheet>
  );
}
