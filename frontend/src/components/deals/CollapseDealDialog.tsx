import Button from "../ui/Button";
import Modal from "../ui/Modal";
import type { DealActions } from "../../hooks/useDealActions";

/**
 * Collapsing a deal, from the More menu (D6). No reason field: the endpoint
 * takes none, so one typed here was thrown away (Q2).
 */
export default function CollapseDealDialog({ open, onClose, actions }: { open: boolean; onClose: () => void; actions: DealActions }) {
  return (
    <Modal open={open} onClose={onClose} title="Collapse this deal?" size="md">
      <div className="px-6 py-5">
      <p className="text-[15px] text-text-secondary">
        This cannot be undone. The transfer will fall through and reserved budget will be released.
      </p>
      <div className="mt-5 flex flex-wrap justify-end gap-2">
        <Button variant="ghost" onClick={onClose}>Cancel</Button>
        <Button
          variant="danger"
          loading={actions.collapse.isPending}
          onClick={() => actions.collapse.mutate(undefined, { onSuccess: onClose })}
        >
          Confirm collapse
        </Button>
      </div>
      </div>
    </Modal>
  );
}
