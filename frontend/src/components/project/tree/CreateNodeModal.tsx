import { useEffect, useState, type FormEvent } from "react";
import {
  createCase,
  createScenario,
  createSection,
  createSuite,
} from "../../../api/testing";
import type {
  BusinessPriority,
  Priority,
  ScenarioPolarity,
  ScenarioType,
} from "../../../types/testing";
import type { EditableCaseDraft } from "../../../types/case-editor";
import { Button, Modal } from "../../ui";
import CaseDetailsForm from "../case-editor/CaseDetailsForm";
import CaseStepsEditor, { createInitialStepRows } from "../case-editor/CaseStepsEditor";
import type { CreateTarget, TreeMutationRequest } from "../../../types/tree";

interface CreateNodeModalProps {
  target: CreateTarget;
  projectId: string;
  onClose: () => void;
  onCreated: (request?: TreeMutationRequest) => Promise<void> | void;
}

type CaseTab = "details" | "steps";

const emptyCaseDraft: EditableCaseDraft = {
  title: "",
  preconditions: "",
  expected_result: "",
  design_status: "draft",
  automation_status: "manual",
  on_failure: "fail_but_continue",
  timeout_ms: "120000",
  test_data_input: "",
  steps: createInitialStepRows(),
  linked_specifications: [],
};

export default function CreateNodeModal({
  target,
  projectId,
  onClose,
  onCreated,
}: CreateNodeModalProps) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [folderPath, setFolderPath] = useState("");
  const [scenarioType, setScenarioType] = useState<ScenarioType>("happy_path");
  const [priority, setPriority] = useState<Priority>("medium");
  const [businessPriority, setBusinessPriority] = useState<BusinessPriority | "">("");
  const [polarity, setPolarity] = useState<ScenarioPolarity>("positive");
  const [caseDraft, setCaseDraft] = useState<EditableCaseDraft>(emptyCaseDraft);
  const [caseTab, setCaseTab] = useState<CaseTab>("details");
  const [testDataError, setTestDataError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!target) return;
    setName("");
    setDescription("");
    setFolderPath("");
    setScenarioType("happy_path");
    setPriority("medium");
    setBusinessPriority("");
    setPolarity("positive");
    setCaseDraft(emptyCaseDraft);
    setCaseTab("details");
    setTestDataError(null);
    setError(null);
  }, [target]);

  if (!target) return null;

  function handleCaseField<K extends keyof EditableCaseDraft>(
    field: K,
    value: EditableCaseDraft[K]
  ) {
    setCaseDraft((current) => ({ ...current, [field]: value }));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!target) return;

    setSaving(true);
    setError(null);

    try {
      if (target.type === "suite") {
        if (!name.trim()) return;
        const created = await createSuite({
          project: projectId,
          name: name.trim(),
          description: description.trim() || undefined,
          folder_path: folderPath.trim() || undefined,
        });
        await onCreated({
          nextSelection: { type: "suite", id: created.id },
          resetCaseCache: true,
        });
      } else if (target.type === "section") {
        if (!name.trim()) return;
        const created = await createSection(target.suiteId, {
          name: name.trim(),
          parent: target.parentId ?? undefined,
        });
        await onCreated({
          nextSelection: { type: "section", id: created.id, parentId: target.suiteId },
          resetCaseCache: true,
        });
      } else if (target.type === "scenario") {
        if (!name.trim()) return;
        const created = await createScenario(target.sectionId, {
          title: name.trim(),
          description: description.trim(),
          scenario_type: scenarioType,
          priority,
          business_priority: businessPriority || null,
          polarity,
        });
        await onCreated({
          nextSelection: { type: "scenario", id: created.id, parentId: target.sectionId },
          resetCaseCache: true,
        });
      } else {
        if (!caseDraft.title.trim() || !caseDraft.expected_result.trim()) {
          setError("Title and expected result are required.");
          setSaving(false);
          return;
        }

        let parsedTestData: Record<string, unknown> = {};
        if (caseDraft.test_data_input.trim()) {
          try {
            parsedTestData = JSON.parse(caseDraft.test_data_input);
          } catch {
            setTestDataError("Test data must be valid JSON.");
            setCaseTab("details");
            setSaving(false);
            return;
          }
        }

        const created = await createCase(target.scenarioId, {
          title: caseDraft.title.trim(),
          preconditions: caseDraft.preconditions,
          expected_result: caseDraft.expected_result.trim(),
          design_status: caseDraft.design_status,
          automation_status: caseDraft.automation_status,
          on_failure: caseDraft.on_failure,
          timeout_ms: Number(caseDraft.timeout_ms) || 120000,
          test_data: parsedTestData,
          steps: caseDraft.steps
            .filter((row) => row.step.trim() || row.outcome.trim())
            .map((row) => ({ step: row.step, outcome: row.outcome })),
        });
        await onCreated({
          nextSelection: { type: "case", id: created.id, parentId: target.scenarioId },
          invalidateScenarioIds: [target.scenarioId],
        });
      }
    } catch {
      setError("Failed to create this item.");
      setSaving(false);
      return;
    }

    setSaving(false);
    onClose();
  }

  const modalTitle =
    target.type === "suite"
      ? "New test suite"
      : target.type === "section"
        ? target.parentId
          ? "New child section"
          : "New section"
        : target.type === "scenario"
          ? "New scenario"
          : "New test case";

  const modalSize =
    target.type === "case" ? "2xl" : target.type === "scenario" ? "lg" : "md";

  const contextLabel =
    target.type === "section"
      ? target.parentName
        ? `Inside section "${target.parentName}" in suite "${target.suiteName}"`
        : `Inside suite "${target.suiteName}"`
      : target.type === "scenario"
        ? `Inside section "${target.sectionName}"`
        : target.type === "case"
          ? `Inside scenario "${target.scenarioTitle}"`
          : "";

  return (
    <Modal
      open
      onClose={onClose}
      size={modalSize}
      title={modalTitle}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button form="create-node-form" type="submit" isLoading={saving}>
            Create
          </Button>
        </>
      }
    >
      <form id="create-node-form" onSubmit={handleSubmit} className="space-y-4">
        {contextLabel && <p className="text-xs text-slate-500">{contextLabel}</p>}

        {(target.type === "suite" ||
          target.type === "section" ||
          target.type === "scenario") && (
          <Field label={target.type === "scenario" ? "Title" : "Name"} required>
            <input
              autoFocus
              required
              value={name}
              onChange={(event) => setName(event.target.value)}
              className={inputClass}
            />
          </Field>
        )}

        {target.type === "suite" && (
          <>
            <Field label="Description">
              <textarea
                rows={3}
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                className={inputClass}
              />
            </Field>
            <Field label="Folder path">
              <input
                value={folderPath}
                onChange={(event) => setFolderPath(event.target.value)}
                className={inputClass}
              />
            </Field>
          </>
        )}

        {target.type === "scenario" && (
          <>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              <Field label="Type">
                <select
                  value={scenarioType}
                  onChange={(event) => setScenarioType(event.target.value as ScenarioType)}
                  className={inputClass}
                >
                  <option value="happy_path">Happy path</option>
                  <option value="alternative_flow">Alternative flow</option>
                  <option value="edge_case">Edge case</option>
                  <option value="security">Security</option>
                  <option value="performance">Performance</option>
                  <option value="accessibility">Accessibility</option>
                </select>
              </Field>
              <Field label="Priority">
                <select
                  value={priority}
                  onChange={(event) => setPriority(event.target.value as Priority)}
                  className={inputClass}
                >
                  <option value="low">Low</option>
                  <option value="medium">Medium</option>
                  <option value="high">High</option>
                  <option value="critical">Critical</option>
                </select>
              </Field>
              <Field label="Business priority">
                <select
                  value={businessPriority}
                  onChange={(event) =>
                    setBusinessPriority(event.target.value as BusinessPriority | "")
                  }
                  className={inputClass}
                >
                  <option value="">Not set</option>
                  <option value="must_have">Must have</option>
                  <option value="should_have">Should have</option>
                  <option value="could_have">Could have</option>
                  <option value="wont_have">Won't have</option>
                </select>
              </Field>
              <Field label="Polarity">
                <select
                  value={polarity}
                  onChange={(event) => setPolarity(event.target.value as ScenarioPolarity)}
                  className={inputClass}
                >
                  <option value="positive">Positive</option>
                  <option value="negative">Negative</option>
                </select>
              </Field>
            </div>
            <Field label="Description" required>
              <textarea
                required
                rows={3}
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                className={inputClass}
              />
            </Field>
          </>
        )}

        {target.type === "case" && (
          <>
            <div className="flex gap-2 border-b border-slate-100 pb-3">
              {(["details", "steps"] as CaseTab[]).map((value) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => setCaseTab(value)}
                  className={`rounded-md px-3 py-1.5 text-sm transition ${
                    caseTab === value
                      ? "bg-slate-900 text-white"
                      : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                  }`}
                >
                  {value === "details" ? "Test details" : "Test steps"}
                </button>
              ))}
            </div>

            {caseTab === "details" ? (
              <CaseDetailsForm
                draft={caseDraft}
                testDataError={testDataError}
                onFieldChange={handleCaseField}
              />
            ) : (
              <CaseStepsEditor
                rows={caseDraft.steps}
                onChange={(rows) => handleCaseField("steps", rows)}
              />
            )}
          </>
        )}

        {error && <p className="text-sm text-red-600">{error}</p>}
      </form>
    </Modal>
  );
}

const inputClass =
  "w-full rounded-md border border-slate-200 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100";

function Field({
  label,
  required,
  children,
}: {
  label: string;
  required?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label className="mb-1 block text-sm font-medium text-slate-700">
        {label} {required && <span className="text-red-500">*</span>}
      </label>
      {children}
    </div>
  );
}
