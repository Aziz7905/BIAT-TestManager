import { useEffect, useMemo, useState } from "react";
import {
  commitAIGeneration,
  getAIGenerationSession,
  startAIGeneration,
  updateAIGenerationReview,
} from "../../../api/ai";
import { getSpecificationsPage } from "../../../api/specs";
import type {
  AIGenerationCaseDraft,
  AIGenerationDraftPayload,
  AIGenerationScenarioDraft,
  AIGenerationSectionDraft,
  AIGenerationSession,
  AIGenerationStepDraft,
} from "../../../types/ai";
import type { SpecificationListItem } from "../../../types/specs";
import type { BusinessPriority, ProjectTree, TreeSection } from "../../../types/testing";
import { Badge, Button, Spinner } from "../../ui";

interface AIGenerationPanelProps {
  open: boolean;
  projectId: string;
  projectName: string;
  tree: ProjectTree;
  initialSuiteId?: string | null;
  initialSectionId?: string | null;
  initialObjective?: string;
  initialSourceRefs?: Record<string, unknown>;
  initialJiraIssueKey?: string;
  onClose: () => void;
  onCommitted: () => Promise<void> | void;
}

interface SectionOption {
  id: string;
  suiteId: string;
  name: string;
  depth: number;
}

const readyStatuses = new Set(["ready_for_review", "reviewing", "saved", "failed", "cancelled"]);
const priorityOrder: BusinessPriority[] = ["must_have", "should_have", "could_have", "wont_have"];

export default function AIGenerationPanel({
  open,
  projectId,
  projectName,
  tree,
  initialSuiteId,
  initialSectionId,
  initialObjective = "",
  initialSourceRefs,
  initialJiraIssueKey = "",
  onClose,
  onCommitted,
}: AIGenerationPanelProps) {
  const [objective, setObjective] = useState("");
  const [selectedSuiteId, setSelectedSuiteId] = useState<string>("");
  const [selectedSectionId, setSelectedSectionId] = useState<string>("");
  const [selectedSpecificationId, setSelectedSpecificationId] = useState<string>("");
  const [jiraIssueKey, setJiraIssueKey] = useState("");
  const [specifications, setSpecifications] = useState<SpecificationListItem[]>([]);
  const [session, setSession] = useState<AIGenerationSession | null>(null);
  const [draft, setDraft] = useState<AIGenerationDraftPayload | null>(null);
  const [selectedCaseIds, setSelectedCaseIds] = useState<Set<string>>(new Set());
  const [generating, setGenerating] = useState(false);
  const [saving, setSaving] = useState<"draft" | "approved" | null>(null);
  const [error, setError] = useState("");

  const sectionOptions = useMemo(() => flattenSectionOptions(tree), [tree]);
  const selectedSuiteSections = useMemo(
    () => sectionOptions.filter((section) => section.suiteId === selectedSuiteId),
    [sectionOptions, selectedSuiteId]
  );

  useEffect(() => {
    if (!open) return;
    setObjective(initialObjective);
    setSelectedSuiteId(initialSuiteId ?? "");
    setSelectedSectionId(initialSectionId ?? "");
    setSelectedSpecificationId("");
    setJiraIssueKey(initialJiraIssueKey);
    setSession(null);
    setDraft(null);
    setSelectedCaseIds(new Set());
    setGenerating(false);
    setSaving(null);
    setError("");
  }, [initialJiraIssueKey, initialObjective, initialSectionId, initialSuiteId, open]);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    getSpecificationsPage(projectId)
      .then((response) => {
        if (!cancelled) setSpecifications(response.results);
      })
      .catch(() => {
        if (!cancelled) setSpecifications([]);
      });
    return () => {
      cancelled = true;
    };
  }, [open, projectId]);

  useEffect(() => {
    if (!session || readyStatuses.has(session.status)) return;
    const interval = window.setInterval(() => {
      void refreshSession(session.id);
    }, 1800);
    return () => window.clearInterval(interval);
  }, [session]);

  useEffect(() => {
    if (!session || session.status !== "ready_for_review") return;
    const payload = normalizeDraftForUI(session.draft_payload);
    if (!payload) return;
    setDraft(payload);
    setSelectedCaseIds(new Set(collectCaseIds(payload)));
  }, [session]);

  function handleSuiteChange(nextSuiteId: string) {
    setSelectedSuiteId(nextSuiteId);
    setSelectedSectionId("");
  }

  async function refreshSession(sessionId: string) {
    const nextSession = await getAIGenerationSession(sessionId);
    setSession(nextSession);
    if (nextSession.status === "failed") {
      setGenerating(false);
      setError(nextSession.error_message || "AI generation failed.");
    } else if (readyStatuses.has(nextSession.status)) {
      setGenerating(false);
    }
  }

  async function handleGenerate() {
    if (!objective.trim()) {
      setError("Objective is required.");
      return;
    }

    setGenerating(true);
    setError("");
    setDraft(null);
    setSelectedCaseIds(new Set());

    try {
      const nextSession = await startAIGeneration({
        project: projectId,
        objective: objective.trim(),
        source_type:
          selectedSpecificationId || jiraIssueKey.trim() || hasSourceRefs(initialSourceRefs)
            ? "mixed"
            : "prompt",
        target_suite: selectedSuiteId || null,
        target_section: selectedSectionId || null,
        attached_specification: selectedSpecificationId || null,
        source_refs: initialSourceRefs,
        jira_issue_key: jiraIssueKey.trim(),
      });
      setSession(nextSession);
      if (readyStatuses.has(nextSession.status)) {
        await refreshSession(nextSession.id);
      }
    } catch (err) {
      setError(errorMessage(err));
      setGenerating(false);
    }
  }

  async function handleSave(createAsApproved: boolean) {
    if (!session || !draft) return;
    const selectedIds = Array.from(selectedCaseIds);
    if (selectedIds.length === 0) {
      setError("Select at least one test case.");
      return;
    }

    setSaving(createAsApproved ? "approved" : "draft");
    setError("");
    try {
      const reviewedSession = await updateAIGenerationReview(session.id, {
        review_decisions: {
          draft_payload: draft,
          selected_case_ids: selectedIds,
        },
      });
      setSession(reviewedSession);
      const committed = await commitAIGeneration(session.id, createAsApproved);
      setSession(committed.session);
      await onCommitted();
      onClose();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSaving(null);
    }
  }

  function toggleCase(caseId: string) {
    setSelectedCaseIds((current) => {
      const next = new Set(current);
      if (next.has(caseId)) next.delete(caseId);
      else next.add(caseId);
      return next;
    });
  }

  if (!open) return null;

  const groupedCounts = draft ? countByBusinessPriority(draft) : {};
  const selectedCount = selectedCaseIds.size;

  return (
    <div className="fixed inset-0 z-40 flex justify-end">
      <div className="absolute inset-0 bg-slate-900/30" onClick={onClose} />
      <aside className="relative flex h-full w-full max-w-5xl flex-col border-l border-slate-200 bg-white shadow-2xl">
        <header className="flex shrink-0 items-start justify-between gap-4 border-b border-slate-200 px-5 py-4">
          <div className="min-w-0">
            <h2 className="text-base font-semibold text-slate-900">Generate tests with AI</h2>
            <p className="mt-1 text-sm text-slate-500">{projectName}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md p-2 text-slate-400 transition hover:bg-slate-100 hover:text-slate-700"
            title="Close"
          >
            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </header>

        <div className="flex min-h-0 flex-1 overflow-hidden">
          <section className="w-80 shrink-0 overflow-y-auto border-r border-slate-200 p-5">
            <div className="space-y-4">
              <label className="block">
                <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Objective
                </span>
                <textarea
                  value={objective}
                  onChange={(event) => setObjective(event.target.value)}
                  rows={6}
                  placeholder="Create authentication tests for valid login, invalid password, empty credentials, and lockout rules."
                  className="mt-2 w-full resize-none rounded-md border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100"
                />
              </label>

              <label className="block">
                <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Target suite
                </span>
                <select
                  value={selectedSuiteId}
                  onChange={(event) => handleSuiteChange(event.target.value)}
                  className="mt-2 w-full rounded-md border border-slate-200 px-3 py-2 text-sm text-slate-800 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100"
                >
                  <option value="">Create or propose suite</option>
                  {tree.suites.map((suite) => (
                    <option key={suite.id} value={suite.id}>
                      {suite.name}
                    </option>
                  ))}
                </select>
              </label>

              <label className="block">
                <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Target section
                </span>
                <select
                  value={selectedSectionId}
                  onChange={(event) => setSelectedSectionId(event.target.value)}
                  disabled={!selectedSuiteId}
                  className="mt-2 w-full rounded-md border border-slate-200 px-3 py-2 text-sm text-slate-800 disabled:bg-slate-50 disabled:text-slate-400 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100"
                >
                  <option value="">Use generated section tree</option>
                  {selectedSuiteSections.map((section) => (
                    <option key={section.id} value={section.id}>
                      {"  ".repeat(Math.max(section.depth - 1, 0))}
                      {section.name}
                    </option>
                  ))}
                </select>
              </label>

              <label className="block">
                <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Specification
                </span>
                <select
                  value={selectedSpecificationId}
                  onChange={(event) => setSelectedSpecificationId(event.target.value)}
                  className="mt-2 w-full rounded-md border border-slate-200 px-3 py-2 text-sm text-slate-800 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100"
                >
                  <option value="">Prompt only</option>
                  {specifications.map((specification) => (
                    <option key={specification.id} value={specification.id}>
                      {specification.external_reference
                        ? `${specification.external_reference} - ${specification.title}`
                        : specification.title}
                    </option>
                  ))}
                </select>
              </label>

              <label className="block">
                <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Jira key
                </span>
                <input
                  value={jiraIssueKey}
                  onChange={(event) => setJiraIssueKey(event.target.value)}
                  placeholder="BIAT-123"
                  className="mt-2 w-full rounded-md border border-slate-200 px-3 py-2 text-sm text-slate-800 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100"
                />
              </label>

              <Button
                className="w-full"
                isLoading={generating}
                loadingText="Generating"
                onClick={() => void handleGenerate()}
              >
                Generate scenarios
              </Button>

              {error && (
                <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                  {error}
                </div>
              )}

              {session && (
                <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600">
                  <div className="flex items-center justify-between gap-3">
                    <span>Status</span>
                    <span className="font-semibold text-slate-800">{session.status}</span>
                  </div>
                  {session.model_name && (
                    <div className="mt-1 flex items-center justify-between gap-3">
                      <span>Model</span>
                      <span className="truncate font-semibold text-slate-800">
                        {session.model_name}
                      </span>
                    </div>
                  )}
                  <div className="mt-1 flex items-center justify-between gap-3">
                    <span>Tokens</span>
                    <span className="font-semibold text-slate-800">
                      {session.input_tokens + session.output_tokens}
                    </span>
                  </div>
                </div>
              )}
            </div>
          </section>

          <section className="min-w-0 flex-1 overflow-y-auto p-5">
            {!session && (
              <EmptyReviewState title="No draft yet" text="Submit an objective to generate a reviewable draft." />
            )}

            {session && !draft && session.status !== "failed" && (
              <div className="flex h-full items-center justify-center">
                <div className="text-center">
                  <Spinner size="lg" />
                  <p className="mt-3 text-sm font-medium text-slate-700">
                    Preparing generated scenarios
                  </p>
                </div>
              </div>
            )}

            {draft && (
              <div className="space-y-5">
                <div className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-200 pb-4">
                  <div className="min-w-0">
                    <h3 className="text-lg font-semibold text-slate-900">{draft.suite.name}</h3>
                    <p className="mt-1 max-w-3xl text-sm text-slate-500">{draft.summary}</p>
                    {draft.open_questions.length > 0 && (
                      <div className="mt-3 rounded-md border border-yellow-200 bg-yellow-50 px-3 py-2 text-sm text-yellow-800">
                        {draft.open_questions.join(" ")}
                      </div>
                    )}
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    {priorityOrder.map((priority) => (
                      <Badge
                        key={priority}
                        label={`${priorityLabel(priority)} ${groupedCounts[priority] ?? 0}`}
                        color={priorityColor(priority)}
                      />
                    ))}
                    <Badge label={`${selectedCount} selected`} color="blue" />
                  </div>
                </div>

                <div className="space-y-4">
                  {draft.sections.map((section) => (
                    <SectionDraftView
                      key={section.draft_id}
                      section={section}
                      depth={0}
                      selectedCaseIds={selectedCaseIds}
                      onToggleCase={toggleCase}
                      onUpdateCase={(caseId, patch) => updateCaseDraft(caseId, patch, setDraft)}
                      onUpdateStep={(caseId, stepIndex, patch) =>
                        updateStepDraft(caseId, stepIndex, patch, setDraft)
                      }
                    />
                  ))}
                </div>
              </div>
            )}
          </section>
        </div>

        <footer className="flex shrink-0 items-center justify-between gap-3 border-t border-slate-200 px-5 py-4">
          <div className="text-sm text-slate-500">
            {draft ? `${selectedCount} selected cases` : "Drafts stay in the AI session until saved."}
          </div>
          <div className="flex items-center gap-2">
            <Button variant="secondary" onClick={onClose}>
              Close
            </Button>
            <Button
              variant="secondary"
              disabled={!draft || selectedCount === 0}
              isLoading={saving === "draft"}
              loadingText="Saving"
              onClick={() => void handleSave(false)}
            >
              Save selected
            </Button>
            <Button
              disabled={!draft || selectedCount === 0}
              isLoading={saving === "approved"}
              loadingText="Approving"
              onClick={() => void handleSave(true)}
            >
              Save & approve
            </Button>
          </div>
        </footer>
      </aside>
    </div>
  );
}

function SectionDraftView({
  section,
  depth,
  selectedCaseIds,
  onToggleCase,
  onUpdateCase,
  onUpdateStep,
}: {
  section: AIGenerationSectionDraft;
  depth: number;
  selectedCaseIds: Set<string>;
  onToggleCase: (caseId: string) => void;
  onUpdateCase: (caseId: string, patch: Partial<AIGenerationCaseDraft>) => void;
  onUpdateStep: (
    caseId: string,
    stepIndex: number,
    patch: Partial<AIGenerationStepDraft>
  ) => void;
}) {
  return (
    <div
      className="border-l border-slate-200 pl-4"
      style={{ marginLeft: depth ? `${Math.min(depth * 16, 48)}px` : undefined }}
    >
      <div className="mb-3 flex items-center gap-2">
        <span className="h-2 w-2 rounded-full bg-slate-300" />
        <h4 className="text-sm font-semibold text-slate-900">{section.name}</h4>
      </div>

      <div className="space-y-3">
        {section.scenarios.map((scenario) => (
          <ScenarioDraftView
            key={scenario.draft_id}
            scenario={scenario}
            selectedCaseIds={selectedCaseIds}
            onToggleCase={onToggleCase}
            onUpdateCase={onUpdateCase}
            onUpdateStep={onUpdateStep}
          />
        ))}
        {section.children.map((child) => (
          <SectionDraftView
            key={child.draft_id}
            section={child}
            depth={depth + 1}
            selectedCaseIds={selectedCaseIds}
            onToggleCase={onToggleCase}
            onUpdateCase={onUpdateCase}
            onUpdateStep={onUpdateStep}
          />
        ))}
      </div>
    </div>
  );
}

function ScenarioDraftView({
  scenario,
  selectedCaseIds,
  onToggleCase,
  onUpdateCase,
  onUpdateStep,
}: {
  scenario: AIGenerationScenarioDraft;
  selectedCaseIds: Set<string>;
  onToggleCase: (caseId: string) => void;
  onUpdateCase: (caseId: string, patch: Partial<AIGenerationCaseDraft>) => void;
  onUpdateStep: (
    caseId: string,
    stepIndex: number,
    patch: Partial<AIGenerationStepDraft>
  ) => void;
}) {
  return (
    <div className="rounded-md border border-slate-200 bg-white">
      <div className="border-b border-slate-100 px-4 py-3">
        <div className="flex flex-wrap items-center gap-2">
          <h5 className="min-w-0 flex-1 text-sm font-semibold text-slate-900">
            {scenario.title}
          </h5>
          <Badge label={priorityLabel(scenario.business_priority)} color={priorityColor(scenario.business_priority)} />
          <Badge label={scenario.scenario_type.replaceAll("_", " ")} color="slate" />
          <Badge label={scenario.polarity} color={scenario.polarity === "positive" ? "green" : "orange"} />
        </div>
        {scenario.description && (
          <p className="mt-2 text-sm text-slate-500">{scenario.description}</p>
        )}
      </div>

      <div className="divide-y divide-slate-100">
        {scenario.cases.map((testCase) => (
          <CaseDraftEditor
            key={testCase.draft_id}
            testCase={testCase}
            selected={selectedCaseIds.has(testCase.draft_id)}
            onToggle={() => onToggleCase(testCase.draft_id)}
            onUpdate={(patch) => onUpdateCase(testCase.draft_id, patch)}
            onUpdateStep={(stepIndex, patch) => onUpdateStep(testCase.draft_id, stepIndex, patch)}
          />
        ))}
      </div>
    </div>
  );
}

function CaseDraftEditor({
  testCase,
  selected,
  onToggle,
  onUpdate,
  onUpdateStep,
}: {
  testCase: AIGenerationCaseDraft;
  selected: boolean;
  onToggle: () => void;
  onUpdate: (patch: Partial<AIGenerationCaseDraft>) => void;
  onUpdateStep: (stepIndex: number, patch: Partial<AIGenerationStepDraft>) => void;
}) {
  return (
    <div className={selected ? "bg-blue-50/40 px-4 py-3" : "px-4 py-3"}>
      <div className="flex items-start gap-3">
        <input
          type="checkbox"
          checked={selected}
          onChange={onToggle}
          className="mt-2 h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
        />
        <div className="min-w-0 flex-1 space-y-3">
          <input
            value={testCase.title}
            onChange={(event) => onUpdate({ title: event.target.value })}
            className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm font-semibold text-slate-900 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100"
          />
          <textarea
            value={testCase.preconditions}
            onChange={(event) => onUpdate({ preconditions: event.target.value })}
            rows={2}
            placeholder="Preconditions"
            className="w-full resize-none rounded-md border border-slate-200 px-3 py-2 text-sm text-slate-700 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100"
          />
          <div className="space-y-2">
            {testCase.steps.map((step, index) => (
              <div key={`${testCase.draft_id}-${index}`} className="grid gap-2 md:grid-cols-2">
                <input
                  value={step.action}
                  onChange={(event) => onUpdateStep(index, { action: event.target.value })}
                  placeholder="Action"
                  className="rounded-md border border-slate-200 px-3 py-2 text-sm text-slate-700 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100"
                />
                <input
                  value={step.expected_outcome}
                  onChange={(event) =>
                    onUpdateStep(index, { expected_outcome: event.target.value })
                  }
                  placeholder="Expected outcome"
                  className="rounded-md border border-slate-200 px-3 py-2 text-sm text-slate-700 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100"
                />
              </div>
            ))}
          </div>
          <textarea
            value={testCase.expected_result}
            onChange={(event) => onUpdate({ expected_result: event.target.value })}
            rows={2}
            placeholder="Expected result"
            className="w-full resize-none rounded-md border border-slate-200 px-3 py-2 text-sm text-slate-700 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100"
          />
          {Boolean(testCase.possible_duplicates?.length) && (
            <div className="rounded-md border border-yellow-200 bg-yellow-50 px-3 py-2 text-xs text-yellow-800">
              Possible duplicate detected from repository memory.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function EmptyReviewState({ title, text }: { title: string; text: string }) {
  return (
    <div className="flex h-full items-center justify-center">
      <div className="text-center">
        <div className="mx-auto flex h-10 w-10 items-center justify-center rounded-md bg-slate-100 text-slate-400">
          <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6l4 2" />
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 22a10 10 0 100-20 10 10 0 000 20z" />
          </svg>
        </div>
        <h3 className="mt-3 text-sm font-semibold text-slate-900">{title}</h3>
        <p className="mt-1 text-sm text-slate-500">{text}</p>
      </div>
    </div>
  );
}

function normalizeDraftForUI(payload: Partial<AIGenerationDraftPayload>): AIGenerationDraftPayload | null {
  if (!payload.suite || !Array.isArray(payload.sections)) return null;
  return {
    schema_version: payload.schema_version,
    summary: payload.summary ?? "",
    assumptions: payload.assumptions ?? [],
    open_questions: payload.open_questions ?? [],
    coverage_summary: payload.coverage_summary ?? {},
    possible_duplicates: payload.possible_duplicates ?? [],
    suite: payload.suite,
    sections: payload.sections.map(normalizeSection),
  };
}

function normalizeSection(section: AIGenerationSectionDraft): AIGenerationSectionDraft {
  return {
    ...section,
    scenarios: section.scenarios ?? [],
    children: (section.children ?? []).map(normalizeSection),
  };
}

function collectCaseIds(draft: AIGenerationDraftPayload): string[] {
  return draft.sections.flatMap(collectSectionCaseIds);
}

function collectSectionCaseIds(section: AIGenerationSectionDraft): string[] {
  return [
    ...section.scenarios.flatMap((scenario) => scenario.cases.map((testCase) => testCase.draft_id)),
    ...section.children.flatMap(collectSectionCaseIds),
  ];
}

function flattenSectionOptions(tree: ProjectTree): SectionOption[] {
  return tree.suites.flatMap((suite) =>
    suite.sections.flatMap((section) => flattenSectionOption(section, suite.id, 1))
  );
}

function flattenSectionOption(section: TreeSection, suiteId: string, depth: number): SectionOption[] {
  return [
    { id: section.id, suiteId, name: section.name, depth },
    ...section.children.flatMap((child) => flattenSectionOption(child, suiteId, depth + 1)),
  ];
}

function updateCaseDraft(
  caseId: string,
  patch: Partial<AIGenerationCaseDraft>,
  setDraft: (updater: (draft: AIGenerationDraftPayload | null) => AIGenerationDraftPayload | null) => void
) {
  setDraft((current) => {
    if (!current) return current;
    return {
      ...current,
      sections: current.sections.map((section) => updateCaseInSection(section, caseId, patch)),
    };
  });
}

function updateCaseInSection(
  section: AIGenerationSectionDraft,
  caseId: string,
  patch: Partial<AIGenerationCaseDraft>
): AIGenerationSectionDraft {
  return {
    ...section,
    scenarios: section.scenarios.map((scenario) => ({
      ...scenario,
      cases: scenario.cases.map((testCase) =>
        testCase.draft_id === caseId ? { ...testCase, ...patch } : testCase
      ),
    })),
    children: section.children.map((child) => updateCaseInSection(child, caseId, patch)),
  };
}

function updateStepDraft(
  caseId: string,
  stepIndex: number,
  patch: Partial<AIGenerationStepDraft>,
  setDraft: (updater: (draft: AIGenerationDraftPayload | null) => AIGenerationDraftPayload | null) => void
) {
  setDraft((current) => {
    if (!current) return current;
    return {
      ...current,
      sections: current.sections.map((section) =>
        updateStepInSection(section, caseId, stepIndex, patch)
      ),
    };
  });
}

function updateStepInSection(
  section: AIGenerationSectionDraft,
  caseId: string,
  stepIndex: number,
  patch: Partial<AIGenerationStepDraft>
): AIGenerationSectionDraft {
  return {
    ...section,
    scenarios: section.scenarios.map((scenario) => ({
      ...scenario,
      cases: scenario.cases.map((testCase) =>
        testCase.draft_id === caseId
          ? {
              ...testCase,
              steps: testCase.steps.map((step, index) =>
                index === stepIndex ? { ...step, ...patch } : step
              ),
            }
          : testCase
      ),
    })),
    children: section.children.map((child) => updateStepInSection(child, caseId, stepIndex, patch)),
  };
}

function countByBusinessPriority(draft: AIGenerationDraftPayload): Partial<Record<BusinessPriority, number>> {
  const counts: Partial<Record<BusinessPriority, number>> = {};
  for (const scenario of draft.sections.flatMap(flattenScenarios)) {
    const priority = scenario.business_priority;
    if (!priority) continue;
    counts[priority] = (counts[priority] ?? 0) + scenario.cases.length;
  }
  return counts;
}

function flattenScenarios(section: AIGenerationSectionDraft): AIGenerationScenarioDraft[] {
  return [
    ...section.scenarios,
    ...section.children.flatMap(flattenScenarios),
  ];
}

function priorityLabel(priority: BusinessPriority | null) {
  if (!priority) return "not set";
  return priority.replaceAll("_", " ");
}

function priorityColor(priority: BusinessPriority | null): "blue" | "green" | "yellow" | "orange" | "slate" {
  if (priority === "must_have") return "green";
  if (priority === "should_have") return "blue";
  if (priority === "could_have") return "yellow";
  if (priority === "wont_have") return "orange";
  return "slate";
}

function errorMessage(error: unknown) {
  if (typeof error === "object" && error && "response" in error) {
    const data = (error as { response?: { data?: unknown } }).response?.data;
    if (typeof data === "object" && data && "detail" in data) {
      return String((data as { detail: unknown }).detail);
    }
    return JSON.stringify(data);
  }
  return "Something went wrong.";
}

function hasSourceRefs(sourceRefs: Record<string, unknown> | undefined) {
  return Boolean(sourceRefs && Object.keys(sourceRefs).length > 0);
}
