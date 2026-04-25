import { useEffect, useMemo, useState } from "react";
import { expandTestRun } from "../../../api/runs";
import type { RunScopeOption } from "../../../types/runs";
import { Button, Modal } from "../../ui";

type ScopeType = "suite" | "section";

interface ExpandRunScopeModalProps {
  open: boolean;
  runId: string | null;
  runName: string;
  suiteOptions: RunScopeOption[];
  sectionOptions: RunScopeOption[];
  onClose: () => void;
  onExpanded: () => void;
}

export default function ExpandRunScopeModal({
  open,
  runId,
  runName,
  suiteOptions,
  sectionOptions,
  onClose,
  onExpanded,
}: ExpandRunScopeModalProps) {
  const [scopeType, setScopeType] = useState<ScopeType>("section");
  const [suiteId, setSuiteId] = useState("");
  const [sectionId, setSectionId] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setScopeType(sectionOptions.length > 0 ? "section" : "suite");
    setSuiteId(suiteOptions[0]?.id ?? "");
    setSectionId(sectionOptions[0]?.id ?? "");
    setError(null);
  }, [open, sectionOptions, suiteOptions]);

  const selectedScope = useMemo(() => {
    if (scopeType === "suite") {
      return suiteOptions.find((option) => option.id === suiteId) ?? null;
    }
    return sectionOptions.find((option) => option.id === sectionId) ?? null;
  }, [scopeType, sectionId, sectionOptions, suiteId, suiteOptions]);

  const canSubmit =
    !!runId &&
    ((scopeType === "suite" && !!suiteId) || (scopeType === "section" && !!sectionId));

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!runId || !canSubmit) return;

    setSaving(true);
    setError(null);

    try {
      await expandTestRun(
        runId,
        scopeType === "suite" ? { suite_id: suiteId } : { section_id: sectionId }
      );
      onExpanded();
    } catch {
      setError("Could not add cases to this run.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Add approved cases"
      size="lg"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button
            form="expand-run-form"
            type="submit"
            isLoading={saving}
            disabled={!canSubmit}
          >
            Add cases
          </Button>
        </>
      }
    >
      <form id="expand-run-form" onSubmit={handleSubmit} className="space-y-5">
        <div className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3">
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Run</p>
          <p className="mt-1 text-sm font-semibold text-slate-900">{runName}</p>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          <label className="flex cursor-pointer items-start gap-3 rounded-lg border border-slate-200 px-4 py-3">
            <input
              type="radio"
              name="expand-scope-type"
              value="suite"
              checked={scopeType === "suite"}
              onChange={() => setScopeType("suite")}
              className="mt-1"
            />
            <div>
              <p className="text-sm font-medium text-slate-900">Add whole suite</p>
              <p className="text-xs text-slate-500">Append approved cases from a suite.</p>
            </div>
          </label>
          <label className="flex cursor-pointer items-start gap-3 rounded-lg border border-slate-200 px-4 py-3">
            <input
              type="radio"
              name="expand-scope-type"
              value="section"
              checked={scopeType === "section"}
              onChange={() => setScopeType("section")}
              className="mt-1"
            />
            <div>
              <p className="text-sm font-medium text-slate-900">Add section</p>
              <p className="text-xs text-slate-500">Append a focused section of approved cases.</p>
            </div>
          </label>
        </div>

        {scopeType === "suite" ? (
          <div className="space-y-1.5">
            <label className="text-sm font-medium text-slate-700">Suite</label>
            <select
              value={suiteId}
              onChange={(event) => setSuiteId(event.target.value)}
              className="w-full rounded-lg border border-slate-200 bg-white px-3.5 py-2.5 text-sm text-slate-900 focus:border-transparent focus:outline-none focus:ring-2 focus:ring-slate-900"
            >
              {suiteOptions.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.label} ({option.caseCount} approved cases)
                </option>
              ))}
            </select>
          </div>
        ) : (
          <div className="space-y-1.5">
            <label className="text-sm font-medium text-slate-700">Section</label>
            <select
              value={sectionId}
              onChange={(event) => setSectionId(event.target.value)}
              className="w-full rounded-lg border border-slate-200 bg-white px-3.5 py-2.5 text-sm text-slate-900 focus:border-transparent focus:outline-none focus:ring-2 focus:ring-slate-900"
            >
              {sectionOptions.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.label} ({option.caseCount} approved cases)
                </option>
              ))}
            </select>
          </div>
        )}

        {selectedScope && (
          <div className="rounded-lg border border-blue-100 bg-blue-50 px-4 py-3 text-sm text-blue-900">
            This adds <span className="font-semibold">{selectedScope.caseCount}</span> approved
            case{selectedScope.caseCount === 1 ? "" : "s"} from{" "}
            <span className="font-semibold">{selectedScope.label}</span>.
          </div>
        )}

        {error && <p className="text-sm text-red-600">{error}</p>}
      </form>
    </Modal>
  );
}
