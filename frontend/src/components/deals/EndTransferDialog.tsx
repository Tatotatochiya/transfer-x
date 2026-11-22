import { useEffect, useState } from "react";

import Button from "../ui/Button";
import Modal from "../ui/Modal";

const REASON_MAX = 500;

/**
 * The one confirmation in front of any answer that ends a transfer (declining
 * the agent's commission, the personal terms, or recording that the player
 * declined): it says the deal collapses, takes an optional reason the other
 * side sees, and offers a counter instead where one is possible. Every such
 * answer goes through here (design-system README, "Ending a transfer").
 */
export default function EndTransferDialog({ open, title, confirmLabel, who, onConfirm, onCounter, onClose, loading }: {
  open: boolean;
  /** "Decline the agent's commission?" */
  title: string;
  /** "Decline and end the transfer" */
  confirmLabel: string;
  /** Who else is told: "Sofia Reyes and Chelsea". */
  who: string;
  onConfirm: (reason: string | null) => void;
  /** When a counter is possible, the way out of ending it. */
  onCounter?: () => void;
  onClose: () => void;
  loading?: boolean;
}) {
  const [reason, setReason] = useState("");
  useEffect(() => { if (!open) setReason(""); }, [open]);
  return (
    <Modal open={open} onClose={onClose} title={title}>
      <div className="space-y-4 px-6 py-5">
        <p className="text-body text-text">
          This ends the transfer: the deal collapses and the committed budget is released. {who} {who.includes(" and ") ? "are" : "is"} told.
        </p>
        <div>
          <label htmlFor="end-reason" className="block text-small font-semibold text-text-secondary">Reason (optional, shown to them)</label>
          <textarea
            id="end-reason"
            value={reason}
            maxLength={REASON_MAX}
            rows={2}
            onChange={(e) => setReason(e.target.value)}
            className="mt-1.5 w-full resize-none rounded-lg bg-surface px-3 py-2 text-input text-text ring-1 ring-input-border focus:outline-none focus:ring-2 focus:ring-accent lg:text-body"
          />
        </div>
        <div className="flex flex-wrap justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          {onCounter && <Button variant="secondary" onClick={() => { onClose(); onCounter(); }}>Counter instead</Button>}
          <Button variant="danger" loading={loading} onClick={() => onConfirm(reason.trim() || null)}>{confirmLabel}</Button>
        </div>
      </div>
    </Modal>
  );
}
