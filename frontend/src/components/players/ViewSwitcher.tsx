import { useRef, useState } from "react";
import type { PlayerSearchView } from "../../types/api";

interface Props {
  views: PlayerSearchView[];
  activeViewId: string | null;
  isModified: boolean;
  onCreate: (name: string) => Promise<void>;
  onUpdate: (id: string, patch: { name?: string; filters?: Record<string, unknown>; is_default?: boolean }) => Promise<void>;
  onDelete: (id: string) => Promise<void>;
  onSelect: (id: string | null) => void;
  onSaveCurrentToView: (id: string) => Promise<void>;
  onSaveCurrentAsNew: (name: string) => Promise<void>;
}

export default function ViewSwitcher({
  views,
  activeViewId,
  isModified,
  onCreate,
  onUpdate,
  onDelete,
  onSelect,
  onSaveCurrentToView,
  onSaveCurrentAsNew,
}: Props) {
  const [showNewForm, setShowNewForm] = useState(false);
  const [newName, setNewName] = useState("");
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveAsNewName, setSaveAsNewName] = useState("");
  const [showSaveAsNew, setShowSaveAsNew] = useState(false);
  const newInputRef = useRef<HTMLInputElement>(null);
  const renameInputRef = useRef<HTMLInputElement>(null);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!newName.trim()) return;
    setSaving(true);
    try {
      await onCreate(newName.trim());
      setNewName("");
      setShowNewForm(false);
    } finally {
      setSaving(false);
    }
  }

  async function handleRename(e: React.FormEvent, id: string) {
    e.preventDefault();
    if (!renameValue.trim()) return;
    setSaving(true);
    try {
      await onUpdate(id, { name: renameValue.trim() });
      setRenamingId(null);
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(id: string) {
    setSaving(true);
    try {
      await onDelete(id);
      setConfirmDeleteId(null);
      if (activeViewId === id) onSelect(null);
    } finally {
      setSaving(false);
    }
  }

  async function handleSetDefault(view: PlayerSearchView) {
    await onUpdate(view.id, { is_default: !view.is_default });
  }

  async function handleSaveToView() {
    if (!activeViewId) return;
    setSaving(true);
    try { await onSaveCurrentToView(activeViewId); } finally { setSaving(false); }
  }

  async function handleSaveAsNew(e: React.FormEvent) {
    e.preventDefault();
    if (!saveAsNewName.trim()) return;
    setSaving(true);
    try {
      await onSaveCurrentAsNew(saveAsNewName.trim());
      setSaveAsNewName("");
      setShowSaveAsNew(false);
    } finally {
      setSaving(false);
    }
  }

  const activeView = views.find((v) => v.id === activeViewId) ?? null;

  return (
    <div className="mb-4 space-y-2">
      {/* ── Pill row ── */}
      <div className="flex flex-wrap items-center gap-1.5">
        {/* All */}
        <button
          onClick={() => { onSelect(null); setRenamingId(null); setConfirmDeleteId(null); }}
          className={`rounded-md px-3 py-1 text-xs font-semibold ring-1 transition-all ${
            activeViewId === null
              ? "bg-slate-700 text-white ring-white/20"
              : "bg-slate-800/60 text-slate-500 ring-white/10 hover:text-white"
          }`}
        >
          All players
        </button>

        {views.map((view) => {
          const isActive = activeViewId === view.id;
          const isRenaming = renamingId === view.id;
          const isConfirmDelete = confirmDeleteId === view.id;

          if (isRenaming) {
            return (
              <form key={view.id} onSubmit={(e) => handleRename(e, view.id)} className="flex items-center gap-1">
                <input
                  ref={renameInputRef}
                  autoFocus
                  value={renameValue}
                  onChange={(e) => setRenameValue(e.target.value)}
                  className="rounded-md bg-slate-800 px-2 py-1 text-xs text-white ring-1 ring-emerald-500/60 focus:outline-none w-32"
                />
                <button type="submit" disabled={saving} className="text-xs text-emerald-400 hover:text-emerald-300 px-1">✓</button>
                <button type="button" onClick={() => setRenamingId(null)} className="text-xs text-slate-500 hover:text-white px-1">✕</button>
              </form>
            );
          }

          if (isConfirmDelete) {
            return (
              <div key={view.id} className="flex items-center gap-1 rounded-md bg-red-500/10 ring-1 ring-red-500/30 px-2 py-1">
                <span className="text-xs text-red-400">Delete "{view.name}"?</span>
                <button onClick={() => handleDelete(view.id)} disabled={saving} className="text-xs text-red-400 hover:text-red-300 font-semibold px-1">Yes</button>
                <button onClick={() => setConfirmDeleteId(null)} className="text-xs text-slate-500 hover:text-white px-1">No</button>
              </div>
            );
          }

          return (
            <div key={view.id} className="group relative flex items-center">
              <button
                onClick={() => { onSelect(view.id); setConfirmDeleteId(null); setRenamingId(null); }}
                className={`flex items-center gap-1.5 rounded-md px-3 py-1 text-xs font-semibold ring-1 transition-all ${
                  isActive
                    ? "bg-emerald-500/15 text-emerald-400 ring-emerald-500/30"
                    : "bg-slate-800/60 text-slate-500 ring-white/10 hover:text-white"
                }`}
              >
                {view.is_default && (
                  <span className="text-amber-400" title="Default view">★</span>
                )}
                {view.name}
                {isActive && isModified && (
                  <span className="h-1.5 w-1.5 rounded-full bg-amber-400 animate-pulse" title="Unsaved changes" />
                )}
              </button>

              {/* Hover actions — positioned above, pb-2 bridges gap to keep hover active */}
              <div className="absolute bottom-full left-1/2 -translate-x-1/2 pb-2 hidden group-hover:flex flex-col items-center z-10">
              <div className="flex items-center gap-0.5 bg-slate-900 rounded-md ring-1 ring-white/10 px-1 py-0.5">
                <button
                  title={view.is_default ? "Remove default" : "Set as default"}
                  onClick={() => handleSetDefault(view)}
                  className={`p-0.5 text-xs transition-colors ${view.is_default ? "text-amber-400" : "text-slate-500 hover:text-amber-400"}`}
                >
                  ★
                </button>
                <button
                  title="Rename"
                  onClick={() => { setRenamingId(view.id); setRenameValue(view.name); }}
                  className="p-0.5 text-slate-500 hover:text-white transition-colors text-xs"
                >
                  ✏
                </button>
                <button
                  title="Delete"
                  onClick={() => setConfirmDeleteId(view.id)}
                  className="p-0.5 text-slate-500 hover:text-red-400 transition-colors text-xs"
                >
                  ✕
                </button>
              </div>
              </div>
            </div>
          );
        })}

        {/* New view button / inline form */}
        {showNewForm ? (
          <form onSubmit={handleCreate} className="flex items-center gap-1.5">
            <input
              ref={newInputRef}
              autoFocus
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="View name…"
              className="rounded-md bg-slate-800 px-2.5 py-1 text-xs text-white placeholder-slate-500 ring-1 ring-emerald-500/60 focus:outline-none w-36"
            />
            <button
              type="submit"
              disabled={saving || !newName.trim()}
              className="rounded-md bg-emerald-500/15 px-2.5 py-1 text-xs font-semibold text-emerald-400 ring-1 ring-emerald-500/30 hover:bg-emerald-500/25 disabled:opacity-50 transition-colors"
            >
              Save
            </button>
            <button
              type="button"
              onClick={() => { setShowNewForm(false); setNewName(""); }}
              className="text-xs text-slate-500 hover:text-white transition-colors"
            >
              Cancel
            </button>
          </form>
        ) : (
          <button
            onClick={() => setShowNewForm(true)}
            className="flex items-center gap-1 rounded-md px-2.5 py-1 text-xs text-slate-500 ring-1 ring-white/10 hover:text-white hover:ring-white/20 transition-all bg-slate-800/60"
          >
            <svg className="h-3 w-3" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
            </svg>
            New view
          </button>
        )}
      </div>

      {/* ── Unsaved changes strip ── */}
      {isModified && activeView && !showSaveAsNew && (
        <div className="flex items-center gap-2 rounded-lg bg-amber-500/10 ring-1 ring-amber-500/20 px-3 py-2">
          <span className="h-1.5 w-1.5 rounded-full bg-amber-400 shrink-0" />
          <p className="text-xs text-amber-300 flex-1">
            Unsaved changes to <span className="font-semibold">"{activeView.name}"</span>
          </p>
          <button
            onClick={handleSaveToView}
            disabled={saving}
            className="text-xs font-semibold text-amber-400 hover:text-amber-300 transition-colors disabled:opacity-50"
          >
            Update view
          </button>
          <span className="text-slate-600 text-xs">·</span>
          <button
            onClick={() => setShowSaveAsNew(true)}
            className="text-xs text-slate-400 hover:text-white transition-colors"
          >
            Save as new
          </button>
          <span className="text-slate-600 text-xs">·</span>
          <button
            onClick={() => { onSelect(activeViewId); }}
            className="text-xs text-slate-500 hover:text-white transition-colors"
          >
            Discard
          </button>
        </div>
      )}

      {/* Save as new inline form (from unsaved changes strip) */}
      {isModified && showSaveAsNew && (
        <form onSubmit={handleSaveAsNew} className="flex items-center gap-2 rounded-lg bg-slate-800/60 ring-1 ring-white/10 px-3 py-2">
          <input
            autoFocus
            value={saveAsNewName}
            onChange={(e) => setSaveAsNewName(e.target.value)}
            placeholder="New view name…"
            className="flex-1 bg-transparent text-xs text-white placeholder-slate-500 focus:outline-none"
          />
          <button
            type="submit"
            disabled={saving || !saveAsNewName.trim()}
            className="text-xs font-semibold text-emerald-400 hover:text-emerald-300 disabled:opacity-50 transition-colors"
          >
            Save
          </button>
          <button
            type="button"
            onClick={() => { setShowSaveAsNew(false); setSaveAsNewName(""); }}
            className="text-xs text-slate-500 hover:text-white transition-colors"
          >
            Cancel
          </button>
        </form>
      )}
    </div>
  );
}
