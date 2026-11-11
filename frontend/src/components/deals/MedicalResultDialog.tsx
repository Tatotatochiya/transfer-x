import { useEffect, useState } from "react";
import type { Deal } from "../../types/api";
import Button from "../ui/Button";
import Modal from "../ui/Modal";
import type { DealActions, MedicalStatus } from "../../hooks/useDealActions";

/** How each result reads as a choice, and what it does. */
export const MEDICAL: Record<MedicalStatus, { choice: string; effect: string; icon: string; box: string; dot: string }> = {
  PASSED: {
    choice: "Passed",
    effect: "Completes the medical step on the Paperwork checklist. If it is the last step, the deal is confirmed.",
    icon: "✓",
    box: "bg-success-bg ring-success-ring text-success-text",
    dot: "bg-success-text text-white",
  },
  FAILED: {
    choice: "Failed",
    effect: "Stops the deal moving on. Record a new result if it is retaken, or collapse the deal.",
    icon: "✕",
    box: "bg-danger-bg ring-danger-border text-danger-text",
    dot: "bg-danger-text text-white",
  },
  PENDING: {
    choice: "Still in progress",
    effect: "Booked or under way, with no result yet. The medical step stays open.",
    icon: "…",
    box: "bg-warning-bg ring-warning-ring text-warning-text",
    dot: "bg-warning-fill text-white",
  },
};

/**
 * Recording the medical result (TRA-61): the buying club at Paperwork, or
 * staff. Opened from the status card or the terms card's Medical row.
 */
export default function MedicalResultDialog({ open, onClose, medicalCheck, actions }: {
  open: boolean;
  onClose: () => void;
  medicalCheck: Deal["medical_check"];
  actions: DealActions;
}) {
  const [status, setStatus] = useState<MedicalStatus | null>(null);
  const [notes, setNotes] = useState("");

  useEffect(() => {
    if (!open) return;
    setStatus(medicalCheck?.status === "PENDING" ? null : medicalCheck?.status ?? null);
    setNotes(medicalCheck?.notes ?? "");
  }, [open, medicalCheck]);

  return (
    <Modal open={open} onClose={onClose} title="Medical result" size="lg">
      <div className="space-y-4 px-6 py-5">
        <fieldset>
          <legend className="mb-2 text-body font-semibold text-text">What was the result?</legend>
          <div className="grid gap-2 sm:grid-cols-3" role="radiogroup">
            {(["PASSED", "FAILED", "PENDING"] as MedicalStatus[]).map((s) => {
              const selected = status === s;
              return (
                <button
                  key={s}
                  type="button"
                  role="radio"
                  aria-checked={selected}
                  onClick={() => setStatus(s)}
                  className={`flex min-h-11 flex-col items-start gap-1 rounded-lg px-3 py-3 text-left ring-1 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-accent ${
                    selected ? `${MEDICAL[s].box} ring-2` : "bg-surface ring-border hover:ring-accent"
                  }`}
                >
                  <span className="flex items-center gap-2 text-body font-bold">
                    <span className={`flex h-5 w-5 items-center justify-center rounded-full text-caption ${selected ? MEDICAL[s].dot : "ring-1 ring-border text-text-muted"}`} aria-hidden>
                      {selected ? MEDICAL[s].icon : ""}
                    </span>
                    <span className={selected ? "" : "text-text"}>{MEDICAL[s].choice}</span>
                  </span>
                  <span className={`text-caption leading-snug ${selected ? "" : "text-text-muted"}`}>{MEDICAL[s].effect}</span>
                </button>
              );
            })}
          </div>
        </fieldset>
        <div>
          <label htmlFor="medical-notes" className="mb-1 block text-body font-semibold text-text">Notes <span className="font-normal text-text-muted">(optional)</span></label>
          <textarea
            id="medical-notes"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={3}
            placeholder="e.g. Carried out at the training ground by the club doctor; no concerns."
            className="w-full rounded-lg bg-surface px-3 py-2 text-input lg:text-body text-text placeholder-text-muted ring-1 ring-input-border focus:outline-none focus:ring-accent"
          />
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <Button
            variant="primary"
            loading={actions.recordMedical.isPending}
            disabled={!status}
            onClick={() => status && actions.recordMedical.mutate(
              { status, notes: notes.trim() || null },
              { onSuccess: onClose },
            )}
          >
            {status ? `Record: ${MEDICAL[status].choice.toLowerCase()}` : "Choose a result"}
          </Button>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
        </div>
      </div>
    </Modal>
  );
}
