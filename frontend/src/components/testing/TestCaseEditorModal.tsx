/** Structured test case editor modal for summary and step/outcome authoring. */
import { useEffect, useMemo, useState } from "react";
import type { ChangeEvent } from "react";
import { Button } from "../Button";
import { FormInput } from "../FormInput";
import { FormSelect } from "../FormSelect";
import { Modal } from "../Modal";
import { Badge, StepRow } from "../ui";
import type {
  TestCase,
  TestCaseAutomationStatus,
  TestCaseOnFailure,
  TestCaseStatus,
  TestCaseWritePayload,
  TestStep,
} from "../../types/testing";

type EditorTab = "details" | "steps";

interface EditableStep {
  id: string;
  step: string;
  outcome: string;
}

interface RequirementOption {
  id: string;
  label: string;
  reference: string | null;
}

interface TestCaseEditorModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (payload: TestCaseWritePayload) => Promise<void> | void;
  isSaving?: boolean;
  scenarioTitle?: string;
  initialCase?: TestCase | null;
  specificationOptions?: RequirementOption[];
}

interface TestCaseFormState {
  title: string;
  preconditions: string;
  expectedResult: string;
  status: TestCaseStatus;
  automationStatus: TestCaseAutomationStatus;
  jiraIssueKey: string;
  onFailure: TestCaseOnFailure;
  timeoutMs: string;
  orderIndex: string;
  testDataText: string;
  linkedSpecificationIds: string[];
  steps: EditableStep[];
}

const STATUS_OPTIONS = [
  { value: "draft", label: "draft" },
  { value: "ready", label: "ready" },
  { value: "running", label: "running" },
  { value: "passed", label: "passed" },
  { value: "failed", label: "failed" },
  { value: "skipped", label: "skipped" },
] as const satisfies ReadonlyArray<{ value: TestCaseStatus; label: string }>;

const AUTOMATION_OPTIONS = [
  { value: "manual", label: "manual" },
  { value: "automated", label: "automated" },
  { value: "in_progress", label: "in progress" },
] as const satisfies ReadonlyArray<{
  value: TestCaseAutomationStatus;
  label: string;
}>;

const ON_FAILURE_OPTIONS = [
  { value: "fail_but_continue", label: "fail but continue" },
  { value: "fail_and_stop", label: "fail and stop" },
] as const satisfies ReadonlyArray<{
  value: TestCaseOnFailure;
  label: string;
}>;

function createEmptyEditableStep(index: number): EditableStep {
  return {
    id: `step-${index}-${Date.now()}`,
    step: "",
    outcome: "",
  };
}

function normalizeSteps(steps: TestStep[] | undefined): EditableStep[] {
  if (!steps?.length) {
    return [createEmptyEditableStep(1)];
  }

  return steps.map((step, index) => ({
    id: `step-${index + 1}-${Date.now()}`,
    step:
      typeof step.step === "string"
        ? step.step
        : typeof step.action === "string"
          ? step.action
          : "",
    outcome:
      typeof step.outcome === "string"
        ? step.outcome
        : typeof step.expected === "string"
          ? step.expected
          : "",
  }));
}

function buildInitialState(initialCase: TestCase | null | undefined): TestCaseFormState {
  return {
    title: initialCase?.title ?? "",
    preconditions: initialCase?.preconditions ?? "",
    expectedResult: initialCase?.expected_result ?? "",
    status: initialCase?.status ?? "draft",
    automationStatus: initialCase?.automation_status ?? "manual",
    jiraIssueKey: initialCase?.jira_issue_key ?? "",
    onFailure: initialCase?.on_failure ?? "fail_but_continue",
    timeoutMs: String(initialCase?.timeout_ms ?? 120000),
    orderIndex: String(initialCase?.order_index ?? 0),
    testDataText: JSON.stringify(initialCase?.test_data ?? {}, null, 2),
    linkedSpecificationIds: initialCase?.linked_specification_ids ?? [],
    steps: normalizeSteps(initialCase?.steps),
  };
}

function buildPayload(formState: TestCaseFormState): TestCaseWritePayload {
  const testDataCandidate = formState.testDataText.trim();
  let parsedTestData: Record<string, unknown> = {};

  if (testDataCandidate) {
    let parsedValue: unknown;
    try {
      parsedValue = JSON.parse(testDataCandidate) as unknown;
    } catch {
      throw new Error("Test data must be valid JSON.");
    }
    if (
      typeof parsedValue !== "object" ||
      parsedValue === null ||
      Array.isArray(parsedValue)
    ) {
      throw new Error("Test data must be a JSON object.");
    }
    parsedTestData = parsedValue as Record<string, unknown>;
  }

  const steps = formState.steps
    .map((step, index) => ({
      index: index + 1,
      step: step.step.trim(),
      outcome: step.outcome.trim(),
    }))
    .filter((step) => step.step || step.outcome);

  return {
    title: formState.title.trim(),
    preconditions: formState.preconditions.trim(),
    steps,
    expected_result: formState.expectedResult.trim(),
    test_data: parsedTestData,
    status: formState.status,
    automation_status: formState.automationStatus,
    jira_issue_key: formState.jiraIssueKey.trim() || null,
    on_failure: formState.onFailure,
    timeout_ms: Number(formState.timeoutMs) || 120000,
    order_index: Number(formState.orderIndex) || 0,
    linked_specification_ids: formState.linkedSpecificationIds,
  };
}

export function TestCaseEditorModal({
  isOpen,
  onClose,
  onSubmit,
  isSaving = false,
  scenarioTitle,
  initialCase = null,
  specificationOptions = [],
}: Readonly<TestCaseEditorModalProps>) {
  const [activeTab, setActiveTab] = useState<EditorTab>("details");
  const [jsonError, setJsonError] = useState("");
  const [formState, setFormState] = useState<TestCaseFormState>(
    buildInitialState(initialCase)
  );

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    setActiveTab("details");
    setJsonError("");
    setFormState(buildInitialState(initialCase));
  }, [initialCase, isOpen]);

  const modalTitle = useMemo(() => {
    if (initialCase) {
      return "Edit Test Case";
    }
    return "Create Test Case";
  }, [initialCase]);

  const handleStepChange = (
    stepId: string,
    field: keyof Pick<EditableStep, "step" | "outcome">,
    event: ChangeEvent<HTMLTextAreaElement>
  ) => {
    setFormState((previousState) => ({
      ...previousState,
      steps: previousState.steps.map((step) =>
        step.id === stepId ? { ...step, [field]: event.target.value } : step
      ),
    }));
  };

  const handleAddStep = () => {
    setFormState((previousState) => ({
      ...previousState,
      steps: [...previousState.steps, createEmptyEditableStep(previousState.steps.length + 1)],
    }));
  };

  const handleRemoveStep = (stepId: string) => {
    setFormState((previousState) => {
      const nextSteps = previousState.steps.filter((step) => step.id !== stepId);
      return {
        ...previousState,
        steps: nextSteps.length > 0 ? nextSteps : [createEmptyEditableStep(1)],
      };
    });
  };

  const toggleSpecification = (specificationId: string) => {
    setFormState((previousState) => {
      const alreadySelected = previousState.linkedSpecificationIds.includes(
        specificationId
      );
      return {
        ...previousState,
        linkedSpecificationIds: alreadySelected
          ? previousState.linkedSpecificationIds.filter((id) => id !== specificationId)
          : [...previousState.linkedSpecificationIds, specificationId],
      };
    });
  };

  const handleSubmit = async () => {
    try {
      setJsonError("");
      await onSubmit(buildPayload(formState));
    } catch (error: unknown) {
      if (error instanceof Error) {
        setJsonError(error.message);
      }
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={modalTitle}
      size="xl"
      footer={
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Badge variant={initialCase ? "verified" : "tag"}>
              {initialCase ? `Version ${initialCase.version}` : "Draft design"}
            </Badge>
            {scenarioTitle ? (
              <span className="text-sm text-muted">
                Scenario: <span className="font-medium text-text">{scenarioTitle}</span>
              </span>
            ) : null}
          </div>
          <div className="flex gap-3">
            <Button variant="secondary" onClick={onClose}>
              Cancel
            </Button>
            <Button onClick={() => void handleSubmit()} isLoading={isSaving} loadingText="Saving...">
              {initialCase ? "Save Changes" : "Create Test Case"}
            </Button>
          </div>
        </div>
      }
    >
      <div className="space-y-6">
        <div className="flex flex-wrap gap-3 border-b border-border pb-4">
          <button
            type="button"
            onClick={() => setActiveTab("details")}
            className={`rounded-2xl px-4 py-2 text-sm font-semibold transition ${
              activeTab === "details"
                ? "bg-primary text-white"
                : "bg-bg text-muted hover:text-text"
            }`}
          >
            Test details
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("steps")}
            className={`rounded-2xl px-4 py-2 text-sm font-semibold transition ${
              activeTab === "steps"
                ? "bg-primary text-white"
                : "bg-bg text-muted hover:text-text"
            }`}
          >
            Test steps
          </button>
        </div>

        {activeTab === "details" ? (
          <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_320px]">
            <div className="space-y-5">
              <FormInput
                id="test-case-title"
                label="Title"
                value={formState.title}
                onChange={(event) =>
                  setFormState((previousState) => ({
                    ...previousState,
                    title: event.target.value,
                  }))
                }
                required
              />

              <div>
                <label
                  htmlFor="test-case-preconditions"
                  className="mb-2 block text-xs font-semibold uppercase tracking-[0.18em] text-muted"
                >
                  Preconditions
                </label>
                <textarea
                  id="test-case-preconditions"
                  rows={5}
                  value={formState.preconditions}
                  onChange={(event) =>
                    setFormState((previousState) => ({
                      ...previousState,
                      preconditions: event.target.value,
                    }))
                  }
                  className="w-full rounded-2xl border border-border bg-surface px-4 py-3 text-sm leading-6 text-text outline-none transition placeholder:text-muted focus-visible:ring-4 focus-visible:ring-primary-light/20"
                />
              </div>

              <div>
                <label
                  htmlFor="test-case-expected-result"
                  className="mb-2 block text-xs font-semibold uppercase tracking-[0.18em] text-muted"
                >
                  Expected Result
                </label>
                <textarea
                  id="test-case-expected-result"
                  rows={5}
                  value={formState.expectedResult}
                  onChange={(event) =>
                    setFormState((previousState) => ({
                      ...previousState,
                      expectedResult: event.target.value,
                    }))
                  }
                  className="w-full rounded-2xl border border-border bg-surface px-4 py-3 text-sm leading-6 text-text outline-none transition placeholder:text-muted focus-visible:ring-4 focus-visible:ring-primary-light/20"
                />
              </div>

              <div>
                <label
                  htmlFor="test-case-data"
                  className="mb-2 block text-xs font-semibold uppercase tracking-[0.18em] text-muted"
                >
                  Test Data JSON
                </label>
                <textarea
                  id="test-case-data"
                  rows={8}
                  value={formState.testDataText}
                  onChange={(event) =>
                    setFormState((previousState) => ({
                      ...previousState,
                      testDataText: event.target.value,
                    }))
                  }
                  className="w-full rounded-2xl border border-border bg-surface px-4 py-3 font-mono text-xs leading-6 text-text outline-none transition placeholder:text-muted focus-visible:ring-4 focus-visible:ring-primary-light/20"
                />
                {jsonError ? (
                  <p className="mt-2 text-sm text-red-500">{jsonError}</p>
                ) : null}
              </div>
            </div>

            <div className="space-y-5 rounded-[28px] border border-border bg-bg p-5">
              <FormSelect
                id="test-case-status"
                label="Status"
                value={formState.status}
                onChange={(event) =>
                  setFormState((previousState) => ({
                    ...previousState,
                    status: event.target.value as TestCaseStatus,
                  }))
                }
                options={STATUS_OPTIONS.map((option) => ({
                  value: option.value,
                  label: option.label,
                }))}
              />

              <FormSelect
                id="test-case-automation-status"
                label="Automation status"
                value={formState.automationStatus}
                onChange={(event) =>
                  setFormState((previousState) => ({
                    ...previousState,
                    automationStatus: event.target.value as TestCaseAutomationStatus,
                  }))
                }
                options={AUTOMATION_OPTIONS.map((option) => ({
                  value: option.value,
                  label: option.label,
                }))}
              />

              <FormSelect
                id="test-case-on-failure"
                label="On failure"
                value={formState.onFailure}
                onChange={(event) =>
                  setFormState((previousState) => ({
                    ...previousState,
                    onFailure: event.target.value as TestCaseOnFailure,
                  }))
                }
                options={ON_FAILURE_OPTIONS.map((option) => ({
                  value: option.value,
                  label: option.label,
                }))}
              />

              <FormInput
                id="test-case-timeout"
                label="Timeout (ms)"
                type="number"
                min="0"
                value={formState.timeoutMs}
                onChange={(event) =>
                  setFormState((previousState) => ({
                    ...previousState,
                    timeoutMs: event.target.value,
                  }))
                }
              />

              <FormInput
                id="test-case-order-index"
                label="Order index"
                type="number"
                min="0"
                value={formState.orderIndex}
                onChange={(event) =>
                  setFormState((previousState) => ({
                    ...previousState,
                    orderIndex: event.target.value,
                  }))
                }
              />

              <FormInput
                id="test-case-jira-issue-key"
                label="Jira issue key"
                value={formState.jiraIssueKey}
                onChange={(event) =>
                  setFormState((previousState) => ({
                    ...previousState,
                    jiraIssueKey: event.target.value,
                  }))
                }
                placeholder="QA-123"
              />

              <div className="rounded-2xl border border-border bg-surface p-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted">
                      Linked requirements
                    </p>
                    <p className="mt-1 text-sm text-muted">
                      Select the BA requirements this case covers.
                    </p>
                  </div>
                  <Badge variant="tag">
                    {formState.linkedSpecificationIds.length} linked
                  </Badge>
                </div>

                {specificationOptions.length === 0 ? (
                  <p className="mt-4 text-sm text-muted">
                    No project requirements are available yet.
                  </p>
                ) : (
                  <div className="mt-4 max-h-64 space-y-2 overflow-y-auto pr-1">
                    {specificationOptions.map((specification) => {
                      const isChecked = formState.linkedSpecificationIds.includes(
                        specification.id
                      );
                      return (
                        <label
                          key={specification.id}
                          className={`flex cursor-pointer items-start gap-3 rounded-2xl border px-3 py-3 transition ${
                            isChecked
                              ? "border-primary-light bg-primary-light/10"
                              : "border-border bg-bg hover:border-primary-light/30"
                          }`}
                        >
                          <input
                            type="checkbox"
                            checked={isChecked}
                            onChange={() => toggleSpecification(specification.id)}
                            className="mt-1 h-4 w-4 rounded border-border text-primary focus:ring-primary-light"
                          />
                          <div className="min-w-0">
                            <p className="text-sm font-semibold text-text">
                              {specification.label}
                            </p>
                            <p className="mt-1 text-xs text-muted">
                              {specification.reference || "No external reference"}
                            </p>
                          </div>
                        </label>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h3 className="text-base font-semibold tracking-tight text-text">
                  Step and outcome flow
                </h3>
                <p className="mt-1 text-sm text-muted">
                  Keep each step paired with the expected outcome for clearer execution.
                </p>
              </div>
              <Button variant="secondary" onClick={handleAddStep}>
                Add Step
              </Button>
            </div>

            {formState.steps.map((step, index) => (
              <StepRow
                key={step.id}
                index={index + 1}
                isEditing
                left={{
                  label: "Step",
                  value: step.step,
                  placeholder: "Describe the action to perform...",
                  onChange: (event) => handleStepChange(step.id, "step", event),
                }}
                right={{
                  label: "Outcome",
                  value: step.outcome,
                  placeholder: "Describe the expected outcome...",
                  onChange: (event) => handleStepChange(step.id, "outcome", event),
                }}
                actions={
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => handleRemoveStep(step.id)}
                  >
                    Remove
                  </Button>
                }
              />
            ))}
          </div>
        )}
      </div>
    </Modal>
  );
}
