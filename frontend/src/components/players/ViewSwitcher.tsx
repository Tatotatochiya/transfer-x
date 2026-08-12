import { useState } from "react";
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
    <div>
      <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-text-muted">Saved views</p>

      <div className="space-y-0.5">
        <button
          onClick={() => { onSelect(null); setRenamingId(null); setConfirmDeleteId(null); }}
          className={`block w-full rounded-md px-2 py-1.5 text-left text-[13px] transition-colors ${
            activeViewId === null ? "font-semibold text-ink" : "text-text-secondary hover:text-text"
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
              <form key={view.id} onSubmit={(e) => handleRename(e, view.id)} className="flex items-center gap-1 px-2 py-0.5">
                <input
                  autoFocus
                  value={renameValue}
                  onChange={(e) => setRenameValue(e.target.value)}
                  className="min-w-0 flex-1 rounded-md bg-surface-inset px-2 py-1 text-xs text-text ring-1 ring-accent focus:outline-none"
                />
                <button type="submit" disabled={saving} className="shrink-0 text-xs text-success-text hover:text-success px-1">✓</button>
                <button type="button" onClick={() => setRenamingId(null)} className="shrink-0 text-xs text-text-muted hover:text-text px-1">✕</button>
              </form>
            );
          }

          if (isConfirmDelete) {
            return (
              <div key={view.id} className="flex items-center gap-1.5 rounded-md bg-danger-bg px-2 py-1.5">
                <span className="flex-1 text-xs text-danger-text truncate">Delete "{view.name}"?</span>
                <button onClick={() => handleDelete(view.id)} disabled={saving} className="shrink-0 text-xs font-semibold text-danger-text hover:text-danger px-1">Yes</button>
                <button onClick={() => setConfirmDeleteId(null)} className="shrink-0 text-xs text-text-muted hover:text-text px-1">No</button>
              </div>
            );
          }

          return (
            <div key={view.id} className="group flex items-center rounded-md hover:bg-surface-inset">
              <button
                onClick={() => { onSelect(view.id); setConfirmDeleteId(null); setRenamingId(null); }}
                className={`flex min-w-0 flex-1 items-center gap-1.5 px-2 py-1.5 text-left text-[13px] transition-colors ${
                  isActive ? "font-semibold text-ink" : "text-text-secondary group-hover:text-text"
                }`}
              >
                {view.is_default && <span className="shrink-0 text-warning-fill" title="Default view">★</span>}
                <span className="truncate">{view.name}</span>
                {isActive && isModified && (
                  <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-warning-fill" title="Unsaved changes" />
                )}
              </button>

              <div className="hidden shrink-0 items-center gap-0.5 pr-1 group-hover:flex">
                <button
                  title={view.is_default ? "Remove default" : "Set as default"}
                  onClick={() => handleSetDefault(view)}
                  className={`p-0.5 text-xs transition-colors ${view.is_default ? "text-warning-fill" : "text-text-muted hover:text-warning-fill"}`}
                >
                  ★
                </button>
                <button
                  title="Rename"
                  onClick={() => { setRenamingId(view.id); setRenameValue(view.name); }}
                  className="p-0.5 text-xs text-text-muted hover:text-text transition-colors"
                >
                  ✏
                </button>
                <button
                  title="Delete"
                  onClick={() => setConfirmDeleteId(view.id)}
                  className="p-0.5 text-xs text-text-muted hover:text-danger-text transition-colors"
                >
                  ✕
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {/* New view */}
      {showNewForm ? (
        <form onSubmit={handleCreate} className="mt-1.5 flex items-center gap-1.5">
          <input
            autoFocus
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="View name…"
            className="min-w-0 flex-1 rounded-md bg-surface-inset px-2 py-1 text-xs text-text placeholder-text-muted ring-1 ring-accent focus:outline-none"
          />
          <button
            type="submit"
            disabled={saving || !newName.trim()}
            className="shrink-0 rounded-md bg-accent-bg px-2 py-1 text-xs font-semibold text-accent-active hover:bg-accent-bg/70 disabled:opacity-50 transition-colors"
          >
            Save
          </button>
          <button type="button" onClick={() => { setShowNewForm(false); setNewName(""); }} className="shrink-0 text-xs text-text-muted hover:text-text transition-colors">
            Cancel
          </button>
        </form>
      ) : (
        <button
          onClick={() => setShowNewForm(true)}
          className="mt-1.5 flex items-center gap-1 text-xs text-text-muted hover:text-text transition-colors"
        >
          <svg className="h-3 w-3" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
          </svg>
          New view
        </button>
      )}

      {/* Unsaved changes */}
      {isModified && activeView && !showSaveAsNew && (
        <div className="mt-2 rounded-lg bg-warning-bg px-2.5 py-2">
          <p className="text-xs text-warning-text">Unsaved changes to <span className="font-semibold">"{activeView.name}"</span></p>
          <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5">
            <button onClick={handleSaveToView} disabled={saving} className="text-xs font-semibold text-warning-text hover:opacity-80 disabled:opacity-50">Update</button>
            <span className="text-text-muted text-xs">·</span>
            <button onClick={() => setShowSaveAsNew(true)} className="text-xs text-text-muted hover:text-text">Save as new</button>
            <span className="text-text-muted text-xs">·</span>
            <button onClick={() => onSelect(activeViewId)} className="text-xs text-text-muted hover:text-text">Discard</button>
          </div>
        </div>
      )}

      {isModified && showSaveAsNew && (
        <form onSubmit={handleSaveAsNew} className="mt-2 flex items-center gap-1.5 rounded-lg bg-surface-inset px-2.5 py-2">
          <input
            autoFocus
            value={saveAsNewName}
            onChange={(e) => setSaveAsNewName(e.target.value)}
            placeholder="New view name…"
            className="min-w-0 flex-1 bg-transparent text-xs text-text placeholder-text-muted focus:outline-none"
          />
          <button type="submit" disabled={saving || !saveAsNewName.trim()} className="shrink-0 text-xs font-semibold text-accent hover:text-accent-hover disabled:opacity-50">Save</button>
          <button type="button" onClick={() => { setShowSaveAsNew(false); setSaveAsNewName(""); }} className="shrink-0 text-xs text-text-muted hover:text-text">Cancel</button>
        </form>
      )}
    </div>
  );
}
