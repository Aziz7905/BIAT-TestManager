import { useEffect, useMemo, useState } from "react";
import { getCaseWorkspace, updateCase } from "../../../api/testing";
import type { CaseWorkspace, TestCaseStep } from "../../../types/testing";
import { Badge, Button, EmptyState, Modal, Spinner } from "../../ui";
import CaseDetailsForm from "./CaseDetailsForm";
import CaseStepsEditor, { createInitialStepRows } from "./CaseStepsEditor";
import type { EditableCaseDraft, EditableStepRow } from "../../../types/case-editor";

type EditorTab = "details" | "steps";

interface CaseEditorModalProps {
  caseId: string | null;
  open: boolean;
  onClose: () => void;
  onSaved: (payload: { caseId: string; scenarioId: string }) => Promise<void> | void;
}

function formatLabel(value: string) {
  return value.replaceAll("_", " ");
}

function createStepRows(steps: TestCaseStep[]): EditableStepRow[] {
  if (steps.length === 0) {
    return createInitialStepRows();
  }

  return steps.map((step, index) => ({
    id: `${index + 1}-${crypto.randomUUID()}`,
    step: step.step ?? "",
    outcome: step.outcome ?? "",
  }));
}

function createDraftFromWorkspace(workspace: CaseWorkspace): EditableCaseDraft {
  return {
    title: workspace.title,
    preconditions: workspace.design.preconditions,
    expected_result: workspace.design.expected_result,
    design_status: workspace.design.design_status,
    automation_status: workspace.design.automation_status,
    on_failure: workspace.design.on_failure,
    timeout_ms: String(workspace.design.timeout_ms ?? 120000),
    test_data_input:
      workspace.design.test_data && Object.keys(workspace.design.test_data).length > 0
        ? JSON.stringify(workspace.design.test_data, null, 2)
        : "",
    steps: createStepRows(workspace.design.steps),
    linked_specifications: workspace.design.linked_specifications,
  };
}

export default function CaseEditorModal({
  caseId,
  open,
  onClose,
  onSaved,
}: CaseEditorModalProps) {
  const [workspace, setWorkspace] = useState<CaseWorkspace | null>(null);
  const [draft, setDraft] = useState<EditableCaseDraft | null>(null);
  const [tab, setTab] = useState<EditorTab>("details");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [testDataError, setTestDataError] = useState<string | null>(null);

  useEffect(() => {
    if (!open || !caseId) {
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);
    setTestDataError(null);

    getCaseWorkspace(caseId)
      .then((payload) => {
        if (cancelled) {
          return;
        }
        setWorkspace(payload);
        setDraft(createDraftFromWorkspace(payload));
        setTab("details");
      })
      .catch(() => {
        if (!cancelled) {
          setWorkspace(null);
          setDraft(null);
          setError("Failed to load this test case.");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [caseId, open]);

  const headerBadges = useMemo(() => {
    if (!workspace) {
      return null;
    }

    return (
      <div className="flex flex-wrap items-center gap-2">
        <Badge label={formatLabel(workspace.design.design_status)} color="blue" />
        <Badge label={formatLabel(workspace.design.automation_status)} color="green" />
        <Badge label={`v${workspace.design.version}`} color="slate" />
      </div>
    );
  }, [workspace]);

  function handleFieldChange<K extends keyof EditableCaseDraft>(
    field: K,
    value: EditableCaseDraft[K]
  ) {
    setDraft((current) => (current ? { ...current, [field]: value } : current));
  }

  async function handleSave() {
    if (!workspace || !draft) {
      return;
    }

    if (!draft.title.trim() || !draft.expected_result.trim()) {
      setError("Title and expected result are required.");
      return;
    }

    let parsedTestData: Record<string, unknown> = {};
    if (draft.test_data_input.trim()) {
      try {
        parsedTestData = JSON.parse(draft.test_data_input);
      } catch {
        setTestDataError("Test data must be valid JSON.");
        return;
      }
    }

    setTestDataError(null);
    setSaving(true);
    setError(null);

    try {
      await updateCase(workspace.context.scenario_id ?? "", workspace.id, {
        title: draft.title.trim(),
        preconditions: draft.preconditions,
        expected_result: draft.expected_result.trim(),
        design_status: draft.design_status,
        automation_status: draft.automation_status,
        on_failure: draft.on_failure,
        timeout_ms: Number(draft.timeout_ms) || 120000,
        test_data: parsedTestData,
        linked_specification_ids: draft.linked_specifications.map((specification) => specification.id),
        steps: draft.steps
          .filter((row) => row.step.trim() || row.outcome.trim())
          .map((row) => ({
            step: row.step,
            outcome: row.outcome,
          })),
      });

      await onSaved({
        caseId: workspace.id,
        scenarioId: workspace.context.scenario_id ?? "",
      });
      onClose();
    } catch {
      setError("Failed to save this test case.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      size="2xl"
      title={workspace ? `Edit ${workspace.title}` : "Edit test case"}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={() => void handleSave()} isLoading={saving}>
            Save changes
          </Button>
        </>
      }
    >
      {loading && (
        <div className="flex min-h-80 items-center justify-center">
          <Spinner size="lg" />
        </div>
      )}

      {!loading && error && !draft && (
        <EmptyState title="Could not load this editor" description={error} />
      )}

      {!loading && workspace && draft && (
        <div className="space-y-5">
          <div className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-100 pb-4">
            <div className="min-w-0">
              <div className="text-xs font-medium uppercase tracking-wide text-slate-500">
                {workspace.context.project_name} / {workspace.context.suite_name} / {workspace.context.section_name}
              </div>
              <div className="mt-1 text-sm text-slate-600">{workspace.context.scenario_title}</div>
            </div>
            {headerBadges}
          </div>

          <div className="flex gap-2 border-b border-slate-100 pb-3">
            {(["details", "steps"] as EditorTab[]).map((value) => (
              <button
                key={value}
                type="button"
                onClick={() => setTab(value)}
                className={`rounded-md px-3 py-1.5 text-sm transition ${
                  tab === value
                    ? "bg-slate-900 text-white"
                    : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                }`}
              >
                {value === "details" ? "Test details" : "Test steps"}
              </button>
            ))}
          </div>

          {tab === "details" ? (
            <CaseDetailsForm
              projectId={workspace.context.project_id}
              draft={draft}
              testDataError={testDataError}
              onFieldChange={handleFieldChange}
            />
          ) : (
            <CaseStepsEditor
              rows={draft.steps}
              onChange={(rows) => handleFieldChange("steps", rows)}
            />
          )}

          {error && draft && <p className="text-sm text-red-600">{error}</p>}
        </div>
      )}
    </Modal>
  );
}
