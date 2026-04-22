import { useState } from "react";
import Button from "../../ui/Button";
import Modal from "../../ui/Modal";
import type { ExecutionCheckpoint } from "../../../types/automation";

interface CheckpointModalProps {
  checkpoint: ExecutionCheckpoint | null;
  open: boolean;
  onClose: () => void;
  onResume: (payload: Record<string, unknown>) => Promise<void>;
}

export default function CheckpointModal({
  checkpoint,
  open,
  onClose,
  onResume,
}: CheckpointModalProps) {
  const [note, setNote] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  async function handleResume() {
    setIsSaving(true);
    try {
      await onResume(note.trim() ? { note: note.trim() } : {});
      setNote("");
      onClose();
    } finally {
      setIsSaving(false);
    }
  }

  if (!checkpoint) return null;

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={checkpoint.title}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={isSaving}>
            Cancel
          </Button>
          <Button onClick={handleResume} isLoading={isSaving} loadingText="Resuming">
            Resume execution
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <p className="text-sm text-slate-700">{checkpoint.instructions}</p>
        <label className="block">
          <span className="mb-1 block text-xs font-semibold uppercase text-slate-500">
            Note
          </span>
          <textarea
            value={note}
            onChange={(event) => setNote(event.target.value)}
            rows={4}
            className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm outline-none focus:border-slate-900 focus:ring-1 focus:ring-slate-900"
          />
        </label>
      </div>
    </Modal>
  );
}
