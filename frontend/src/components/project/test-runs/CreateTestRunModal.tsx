import { useEffect, useMemo, useState } from "react";
import { createTestRun, expandTestRun } from "../../../api/runs";
import type { RunScopeOption, TestRun } from "../../../types/runs";
import { Button, Modal } from "../../ui";

type ScopeType = "suite" | "section";

interface CreateTestRunModalProps {
  open: boolean;
  projectId: string;
  planId: string;
  planName: string;
  suiteOptions: RunScopeOption[];
  sectionOptions: RunScopeOption[];
  onClose: () => void;
  onCreated: (run: TestRun) => void;
}

export default function CreateTestRunModal({
  open,
  projectId,
  planId,
  planName,
  suiteOptions,
  sectionOptions,
  onClose,
  onCreated,
}: CreateTestRunModalProps) {
  const [name, setName] = useState("");
  const [scopeType, setScopeType] = useState<ScopeType>("suite");
  const [suiteId, setSuiteId] = useState("");
  const [sectionId, setSectionId] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setName("");
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
    !!name.trim() &&
    ((scopeType === "suite" && !!suiteId) || (scopeType === "section" && !!sectionId));

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!canSubmit) return;

    setSaving(true);
    setError(null);

    try {
      const run = await createTestRun({
        project: projectId,
        plan: planId,
        name: name.trim(),
      });

      await expandTestRun(
        run.id,
        scopeType === "suite" ? { suite_id: suiteId } : { section_id: sectionId }
      );

      onCreated(run);
    } catch {
      setError("Could not create this run.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Add run to plan"
      size="lg"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button
            form="create-test-run-form"
            type="submit"
            isLoading={saving}
            disabled={!canSubmit}
          >
            Create run
          </Button>
        </>
      }
    >
      <form id="create-test-run-form" onSubmit={handleSubmit} className="space-y-5">
        <div className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3">
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Plan</p>
          <p className="mt-1 text-sm font-semibold text-slate-900">{planName}</p>
        </div>

        <div className="space-y-1.5">
          <label className="text-sm font-medium text-slate-700">Run name</label>
          <input
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="Web regression - Authentication"
            className="w-full rounded-lg border border-slate-200 px-3.5 py-2.5 text-sm text-slate-900 focus:border-transparent focus:outline-none focus:ring-2 focus:ring-slate-900"
          />
        </div>

        <div className="space-y-3">
          <div>
            <p className="text-sm font-medium text-slate-700">Scope</p>
            <p className="mt-1 text-xs text-slate-500">
              Approved cases are added to the run from one suite or section.
            </p>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <label className="flex cursor-pointer items-start gap-3 rounded-lg border border-slate-200 px-4 py-3">
              <input
                type="radio"
                name="run-scope-type"
                value="suite"
                checked={scopeType === "suite"}
                onChange={() => setScopeType("suite")}
                className="mt-1"
              />
              <div>
                <p className="text-sm font-medium text-slate-900">Whole suite</p>
                <p className="text-xs text-slate-500">Useful for broad regression coverage.</p>
              </div>
            </label>
            <label className="flex cursor-pointer items-start gap-3 rounded-lg border border-slate-200 px-4 py-3">
              <input
                type="radio"
                name="run-scope-type"
                value="section"
                checked={scopeType === "section"}
                onChange={() => setScopeType("section")}
                className="mt-1"
              />
              <div>
                <p className="text-sm font-medium text-slate-900">Single section</p>
                <p className="text-xs text-slate-500">Good for a focused validation slice.</p>
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
        </div>

        {selectedScope && (
          <div className="rounded-lg border border-blue-100 bg-blue-50 px-4 py-3 text-sm text-blue-900">
            This run will start with <span className="font-semibold">{selectedScope.caseCount}</span>{" "}
            approved case{selectedScope.caseCount === 1 ? "" : "s"} from{" "}
            <span className="font-semibold">{selectedScope.label}</span>.
          </div>
        )}

        {error && <p className="text-sm text-red-600">{error}</p>}
      </form>
    </Modal>
  );
}
