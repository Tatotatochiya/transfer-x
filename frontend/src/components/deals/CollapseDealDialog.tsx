import { useEffect, useId, useState } from "react";
import Button from "../ui/Button";
import Modal from "../ui/Modal";
import type { DealActions } from "../../hooks/useDealActions";

/**
 * Collapsing a deal, from the More menu (D6), with an optional reason. The
 * reason is stored with the deal and both clubs see it on the status card
 * and the timeline, so the dialog says so.
 */
export default function CollapseDealDialog({ open, onClose, actions }: { open: boolean; onClose: () => void; actions: DealActions }) {
  const [reason, setReason] = useState("");
  const id = useId();
  useEffect(() => { if (open) setReason(""); }, [open]);

  return (
    <Modal open={open} onClose={onClose} title="Collapse this deal?" size="md">
      <div className="px-6 py-5">
        <p className="text-body text-text-secondary">
          This cannot be undone. The transfer will fall through and reserved budget will be released.
        </p>
        <label htmlFor={id} className="mt-4 block text-small font-semibold text-text">Reason (optional)</label>
        <textarea
          id={id}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          maxLength={500}
          rows={3}
          placeholder="e.g. Failed the medical"
          className="mt-1.5 w-full rounded-lg bg-surface px-3 py-2 text-input lg:text-body text-text placeholder-text-muted ring-1 ring-input-border focus:outline-none focus:ring-2 focus:ring-accent"
        />
        <p className="mt-1 text-small text-text-muted">Both clubs will see this.</p>
        <div className="mt-5 flex flex-wrap justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button
            variant="danger"
            loading={actions.collapse.isPending}
            onClick={() => actions.collapse.mutate(reason, { onSuccess: onClose })}
          >
            Confirm collapse
          </Button>
        </div>
      </div>
    </Modal>
  );
}
