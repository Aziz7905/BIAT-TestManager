import { Button, Modal } from "../../ui";
import type { DeleteTarget } from "../../../types/tree";

interface DeleteConfirmModalProps {
  target: DeleteTarget;
  loading?: boolean;
  onClose: () => void;
  onConfirm: () => void;
}

function ImpactLine({ label, value }: { label: string; value?: number }) {
  if (!value) {
    return null;
  }

  return (
    <div className="flex items-center justify-between rounded-md border border-slate-200 px-3 py-2 text-sm">
      <span className="text-slate-600">{label}</span>
      <span className="font-semibold text-slate-900">{value}</span>
    </div>
  );
}

function buildDescription(target: Exclude<DeleteTarget, null>) {
  if (target.type === "suite") {
    return `Delete suite "${target.name}" and everything under it.`;
  }
  if (target.type === "section") {
    return `Delete section "${target.name}" and all nested repository content.`;
  }
  if (target.type === "scenario") {
    return `Delete scenario "${target.name}" and its test cases.`;
  }
  return `Delete case "${target.name}".`;
}

export default function DeleteConfirmModal({
  target,
  loading = false,
  onClose,
  onConfirm,
}: DeleteConfirmModalProps) {
  if (!target) {
    return null;
  }

  return (
    <Modal
      open
      onClose={onClose}
      size="sm"
      title="Delete repository item"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="danger" onClick={onConfirm} isLoading={loading}>
            Delete
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <p className="text-sm text-slate-600">{buildDescription(target)}</p>

        {(target.impact.sectionCount ||
          target.impact.childSectionCount ||
          target.impact.scenarioCount ||
          target.impact.caseCount) && (
          <div className="space-y-2">
            <ImpactLine label="Sections" value={target.impact.sectionCount} />
            <ImpactLine label="Child sections" value={target.impact.childSectionCount} />
            <ImpactLine label="Scenarios" value={target.impact.scenarioCount} />
            <ImpactLine label="Cases" value={target.impact.caseCount} />
          </div>
        )}

        <p className="text-xs text-slate-500">This action cannot be undone.</p>
      </div>
    </Modal>
  );
}
