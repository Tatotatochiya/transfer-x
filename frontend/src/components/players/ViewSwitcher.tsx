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
  /** "sheet" (below 1024px): the list sits behind one full-width button, and
   *  every control is a 44px touch target with its actions always shown. */
  layout?: "rail" | "sheet";
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
  layout = "rail",
}: Props) {
  const sheet = layout === "sheet";
  const [listOpen, setListOpen] = useState(!sheet);
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
  const rowText = sheet ? "min-h-11 text-body" : "py-1.5 text-caption";
  const iconBtn = sheet ? "flex h-11 w-11 items-center justify-center text-small" : "p-0.5 text-caption";

  return (
    <div>
      <p className="mb-1.5 text-caption font-semibold text-text-secondary">Saved views</p>

      {sheet && (
        <button
          type="button"
          aria-expanded={listOpen}
          onClick={() => setListOpen((o) => !o)}
          className="flex min-h-12 w-full items-center justify-between gap-2 rounded-lg bg-surface px-3 text-left text-body text-text ring-1 ring-input-border"
        >
          <span className="truncate">
            {activeView ? activeView.name : "All players"}
            {isModified && <span className="ml-1.5 text-small text-warning-text">(changed)</span>}
          </span>
          <span aria-hidden className={`text-text-muted transition-transform ${listOpen ? "rotate-180" : ""}`}>⌄</span>
        </button>
      )}

      {listOpen && (
      <div className={`space-y-0.5 ${sheet ? "mt-1.5" : ""}`}>
        <button
          type="button"
          onClick={() => { onSelect(null); setRenamingId(null); setConfirmDeleteId(null); }}
          className={`flex w-full items-center rounded-md px-2 text-left transition-colors ${rowText} ${
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
                  className="min-w-0 flex-1 rounded-md bg-surface-inset px-2 py-1 text-caption text-text ring-1 ring-accent focus:outline-none"
                />
                <button type="submit" disabled={saving} className="shrink-0 text-caption text-success-text hover:text-success px-1">✓</button>
                <button type="button" onClick={() => setRenamingId(null)} className="shrink-0 text-caption text-text-muted hover:text-text px-1">✕</button>
              </form>
            );
          }

          if (isConfirmDelete) {
            return (
              <div key={view.id} className="flex items-center gap-1.5 rounded-md bg-danger-bg px-2 py-1.5">
                <span className="flex-1 text-caption text-danger-text truncate">Delete "{view.name}"?</span>
                <button onClick={() => handleDelete(view.id)} disabled={saving} className="shrink-0 text-caption font-semibold text-danger-text hover:text-danger px-1">Yes</button>
                <button onClick={() => setConfirmDeleteId(null)} className="shrink-0 text-caption text-text-muted hover:text-text px-1">No</button>
              </div>
            );
          }

          return (
            <div key={view.id} className="group flex items-center rounded-md hover:bg-surface-inset">
              <button
                type="button"
                onClick={() => { onSelect(view.id); setConfirmDeleteId(null); setRenamingId(null); }}
                className={`flex min-w-0 flex-1 items-center gap-1.5 px-2 text-left transition-colors ${rowText} ${
                  isActive ? "font-semibold text-ink" : "text-text-secondary group-hover:text-text"
                }`}
              >
                {view.is_default && <span className="shrink-0 text-warning-fill" title="Default view">★</span>}
                <span className="truncate">{view.name}</span>
                {isActive && isModified && (
                  <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-warning-fill" title="Unsaved changes" />
                )}
              </button>

              <div className={`shrink-0 items-center gap-0.5 pr-1 ${sheet ? "flex" : "hidden group-hover:flex"}`}>
                <button
                  type="button"
                  title={view.is_default ? "Remove default" : "Set as default"}
                  onClick={() => handleSetDefault(view)}
                  className={`${iconBtn} transition-colors ${view.is_default ? "text-warning-fill" : "text-text-muted hover:text-warning-fill"}`}
                >
                  ★
                </button>
                <button
                  type="button"
                  title="Rename"
                  onClick={() => { setRenamingId(view.id); setRenameValue(view.name); }}
                  className={`${iconBtn} text-text-muted hover:text-text transition-colors`}
                >
                  ✏
                </button>
                <button
                  type="button"
                  title="Delete"
                  onClick={() => setConfirmDeleteId(view.id)}
                  className={`${iconBtn} text-text-muted hover:text-danger-text transition-colors`}
                >
                  ✕
                </button>
              </div>
            </div>
          );
        })}
      </div>
      )}

      {/* New view */}
      {showNewForm ? (
        <form onSubmit={handleCreate} className="mt-1.5 flex items-center gap-1.5">
          <input
            autoFocus
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="View name…"
            className="min-w-0 flex-1 rounded-md bg-surface-inset px-2 py-1 text-caption text-text placeholder-text-muted ring-1 ring-accent focus:outline-none"
          />
          <button
            type="submit"
            disabled={saving || !newName.trim()}
            className="shrink-0 rounded-md bg-accent-bg px-2 py-1 text-caption font-semibold text-accent-active hover:bg-accent-bg/70 disabled:opacity-50 transition-colors"
          >
            Save
          </button>
          <button type="button" onClick={() => { setShowNewForm(false); setNewName(""); }} className="shrink-0 text-caption text-text-muted hover:text-text transition-colors">
            Cancel
          </button>
        </form>
      ) : (
        <button
          type="button"
          onClick={() => setShowNewForm(true)}
          className={`mt-1.5 flex items-center gap-1 text-text-muted hover:text-text transition-colors ${sheet ? "min-h-11 text-body font-semibold" : "text-caption"}`}
        >
          <svg className="h-3 w-3" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
          </svg>
          {sheet ? "Save as view" : "New view"}
        </button>
      )}

      {/* Unsaved changes */}
      {isModified && activeView && !showSaveAsNew && (
        <div className="mt-2 rounded-lg bg-warning-bg px-2.5 py-2">
          <p className="text-caption text-warning-text">Unsaved changes to <span className="font-semibold">"{activeView.name}"</span></p>
          <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5">
            <button onClick={handleSaveToView} disabled={saving} className="text-caption font-semibold text-warning-text hover:opacity-80 disabled:opacity-50">Update</button>
            <span className="text-text-muted text-caption">·</span>
            <button onClick={() => setShowSaveAsNew(true)} className="text-caption text-text-muted hover:text-text">Save as new</button>
            <span className="text-text-muted text-caption">·</span>
            <button onClick={() => onSelect(activeViewId)} className="text-caption text-text-muted hover:text-text">Discard</button>
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
            className="min-w-0 flex-1 bg-transparent text-caption text-text placeholder-text-muted focus:outline-none"
          />
          <button type="submit" disabled={saving || !saveAsNewName.trim()} className="shrink-0 text-caption font-semibold text-accent hover:text-accent-hover disabled:opacity-50">Save</button>
          <button type="button" onClick={() => { setShowSaveAsNew(false); setSaveAsNewName(""); }} className="shrink-0 text-caption text-text-muted hover:text-text">Cancel</button>
        </form>
      )}
    </div>
  );
}
