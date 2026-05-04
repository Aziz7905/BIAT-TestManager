import { useEffect, useState } from "react";
import { updateTestRun } from "../../../api/runs";
import type { TestRun } from "../../../types/runs";
import { Button, Modal } from "../../ui";

interface EditTestRunModalProps {
  open: boolean;
  run: TestRun | null;
  onClose: () => void;
  onSaved: (run: TestRun) => void;
}

export default function EditTestRunModal({
  open,
  run,
  onClose,
  onSaved,
}: EditTestRunModalProps) {
  const [name, setName] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setName(run?.name ?? "");
    setError(null);
  }, [open, run]);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!run || !name.trim()) return;

    setSaving(true);
    setError(null);
    try {
      const saved = await updateTestRun(run.id, { name: name.trim() });
      onSaved(saved);
    } catch {
      setError("Could not update this run.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Edit run"
      size="md"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button
            form="edit-test-run-form"
            type="submit"
            isLoading={saving}
            disabled={!name.trim() || !run}
          >
            Save changes
          </Button>
        </>
      }
    >
      <form id="edit-test-run-form" onSubmit={handleSubmit} className="space-y-4">
        <div className="space-y-1.5">
          <label className="text-sm font-medium text-slate-700">Run name</label>
          <input
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="Authentication - Chrome desktop"
            className="w-full rounded-lg border border-slate-200 px-3.5 py-2.5 text-sm text-slate-900 focus:border-transparent focus:outline-none focus:ring-2 focus:ring-slate-900"
          />
        </div>

        {error && <p className="text-sm text-red-600">{error}</p>}
      </form>
    </Modal>
  );
}
