import { useEffect, useState } from "react";
import { createTestPlan, updateTestPlan } from "../../../api/runs";
import type { TestPlan } from "../../../types/runs";
import { Button, Modal } from "../../ui";

interface CreateTestPlanModalProps {
  open: boolean;
  projectId: string;
  plan?: TestPlan | null;
  onClose: () => void;
  onSaved: (plan: TestPlan) => void;
}

export default function CreateTestPlanModal({
  open,
  projectId,
  plan,
  onClose,
  onSaved,
}: CreateTestPlanModalProps) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const isEditing = Boolean(plan);

  useEffect(() => {
    if (!open) return;
    setName(plan?.name ?? "");
    setDescription(plan?.description ?? "");
    setError(null);
  }, [open, plan]);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError(null);

    try {
      const savedPlan = plan
        ? await updateTestPlan(plan.id, {
            name: name.trim(),
            description: description.trim(),
          })
        : await createTestPlan({
            project: projectId,
            name: name.trim(),
            description: description.trim(),
          });
      onSaved(savedPlan);
    } catch {
      setError(isEditing ? "Could not update this test plan." : "Could not create this test plan.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={isEditing ? "Edit test plan" : "New test plan"}
      size="lg"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button
            form="create-test-plan-form"
            type="submit"
            isLoading={saving}
            disabled={!name.trim()}
          >
            {isEditing ? "Save changes" : "Create plan"}
          </Button>
        </>
      }
    >
      <form id="create-test-plan-form" onSubmit={handleSubmit} className="space-y-4">
        <div className="space-y-1.5">
          <label className="text-sm font-medium text-slate-700">Plan name</label>
          <input
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="Release regression"
            className="w-full rounded-lg border border-slate-200 px-3.5 py-2.5 text-sm text-slate-900 focus:border-transparent focus:outline-none focus:ring-2 focus:ring-slate-900"
          />
        </div>

        <div className="space-y-1.5">
          <label className="text-sm font-medium text-slate-700">Description</label>
          <textarea
            rows={5}
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            placeholder="Group runs for a release, feature area, or validation cycle."
            className="w-full rounded-lg border border-slate-200 px-3.5 py-2.5 text-sm text-slate-900 focus:border-transparent focus:outline-none focus:ring-2 focus:ring-slate-900"
          />
        </div>

        <div className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
          Use a plan to group related runs, keep execution scope clear, and review progress without
          mixing it with ad-hoc automation history.
        </div>

        {error && <p className="text-sm text-red-600">{error}</p>}
      </form>
    </Modal>
  );
}
