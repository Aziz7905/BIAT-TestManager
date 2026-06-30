import type {
  AIGenerationCaseDraft,
  AIGenerationDraftPayload,
  AIGenerationScenarioDraft,
  AIGenerationSectionDraft,
  AIGenerationSession,
} from "../../types/ai";
import type { User } from "../../types/auth";
import type { Project } from "../../types/project";
import type {
  ActiveDraftNode,
  CaseSelectionFilter,
  ComposerMode,
  CoverageStats,
  DraftEditableField,
  DraftReference,
  DraftStats,
  DraftStructureStats,
  DraftStepEditableField,
  GenerationEvent,
  LaunchContext,
  ProjectTargetMode,
  ReviewFilterValue,
} from "./testPilot.types";

export const TERMINAL_STATUSES = new Set([
  "clarification_required",
  "ready_for_review",
  "reviewing",
  "saved",
  "failed",
  "cancelled",
]);

export const POLL_INTERVAL_MS = 1800;
export const ACTIVITY_EVENT_LIMIT = 12;

export function parseLaunchContext(params: URLSearchParams): LaunchContext {
  return {
    projectId: params.get("project"),
    suiteId: params.get("suite"),
    sectionId: params.get("section"),
    scenarioId: params.get("scenario"),
    caseId: params.get("case"),
    selectionType: params.get("selection"),
    labels: {
      project: params.get("projectName") ?? undefined,
      suite: params.get("suiteName") ?? undefined,
      section: params.get("sectionName") ?? undefined,
      scenario: params.get("scenarioTitle") ?? undefined,
      case: params.get("caseTitle") ?? undefined,
    },
  };
}

export function buildSourceRefs(context: LaunchContext): Record<string, unknown> | undefined {
  const labels = Object.fromEntries(
    Object.entries(context.labels).filter(([, value]) => Boolean(value))
  );
  const repositoryContext = removeEmptyValues({
    project_id: context.projectId,
    suite_id: context.suiteId,
    section_id: context.sectionId,
    scenario_id: context.scenarioId,
    case_id: context.caseId,
    selection_type: context.selectionType,
    labels: Object.keys(labels).length ? labels : null,
  });
  return Object.keys(repositoryContext).length
    ? { repository_context: repositoryContext }
    : undefined;
}

export function removeEmptyValues(value: Record<string, unknown>): Record<string, unknown> {
  return Object.fromEntries(
    Object.entries(value).filter(([, item]) => {
      if (item === null || item === undefined) return false;
      if (typeof item === "string") return item.trim().length > 0;
      return true;
    })
  );
}

export function userCanCreateProject(user: User | null) {
  const role = user?.profile?.organization_role;
  if (role === "platform_owner" || role === "org_admin") return true;
  return user?.profile?.team_memberships?.some(
    (membership) => membership.is_active && membership.role === "manager"
  ) ?? false;
}

export function resolveCreatableTeamId(user: User | null) {
  if (!userCanCreateProject(user)) return null;
  const activeMemberships = user?.profile?.team_memberships?.filter((membership) => membership.is_active) ?? [];
  const managedPrimary = activeMemberships.find((membership) => membership.is_primary && membership.role === "manager");
  const managed = activeMemberships.find((membership) => membership.role === "manager");
  const primary = activeMemberships.find((membership) => membership.is_primary);
  return managedPrimary?.team ?? managed?.team ?? user?.profile?.team ?? primary?.team ?? activeMemberships[0]?.team ?? null;
}

export function titleForGeneratedProject(objective: string) {
  const cleaned = objective.split(/\s+/).join(" ").slice(0, 46).trim();
  return cleaned ? `TestPilot - ${cleaned}` : "TestPilot Workspace";
}

export function buildInitialProjectDescription(objective: string) {
  return [
    "Created by TestPilot from an AI test generation prompt.",
    "",
    "Initial objective:",
    objective,
  ].join("\n");
}

export function targetLabel(targetMode: ProjectTargetMode, projects: Project[]) {
  if (targetMode === "new") return "Project: New";
  if (targetMode === "existing") return "Project: Choose existing";
  if (projects.length === 1) return `Project: ${projects[0].name}`;
  if (projects.length > 1) return "Project: Auto";
  return "Project: New if allowed";
}

export function normalizeDraftForUI(payload: Partial<AIGenerationDraftPayload>): AIGenerationDraftPayload | null {
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

export function normalizeSection(section: AIGenerationSectionDraft): AIGenerationSectionDraft {
  return {
    ...section,
    scenarios: section.scenarios ?? [],
    children: (section.children ?? []).map(normalizeSection),
  };
}

export function emptyDraftStats(): DraftStats {
  return { sectionCount: 0, scenarioCount: 0, caseCount: 0 };
}

export function emptyDraftStructureStats(): DraftStructureStats {
  return {
    suiteCount: 0,
    sectionCount: 0,
    childSectionCount: 0,
    scenarioCount: 0,
    caseCount: 0,
  };
}

export function collectDraftStats(draft: AIGenerationDraftPayload): DraftStats {
  return draft.sections.reduce(
    (total, section) => mergeDraftStats(total, collectSectionStats(section)),
    emptyDraftStats()
  );
}

export function collectDraftStructureStats(draft: AIGenerationDraftPayload): DraftStructureStats {
  return draft.sections.reduce(
    (total, section) => mergeDraftStructureStats(total, collectSectionStructureStats(section, false)),
    { ...emptyDraftStructureStats(), suiteCount: 1 }
  );
}

function collectSectionStructureStats(
  section: AIGenerationSectionDraft,
  childSection: boolean
): DraftStructureStats {
  const ownStats: DraftStructureStats = {
    suiteCount: 0,
    sectionCount: childSection ? 0 : 1,
    childSectionCount: childSection ? 1 : 0,
    scenarioCount: section.scenarios.length,
    caseCount: section.scenarios.reduce((total, scenario) => total + scenario.cases.length, 0),
  };
  return section.children.reduce(
    (total, child) => mergeDraftStructureStats(total, collectSectionStructureStats(child, true)),
    ownStats
  );
}

function mergeDraftStructureStats(
  left: DraftStructureStats,
  right: DraftStructureStats
): DraftStructureStats {
  return {
    suiteCount: left.suiteCount + right.suiteCount,
    sectionCount: left.sectionCount + right.sectionCount,
    childSectionCount: left.childSectionCount + right.childSectionCount,
    scenarioCount: left.scenarioCount + right.scenarioCount,
    caseCount: left.caseCount + right.caseCount,
  };
}

export function collectSectionStats(section: AIGenerationSectionDraft): DraftStats {
  const ownStats = {
    sectionCount: 1,
    scenarioCount: section.scenarios.length,
    caseCount: section.scenarios.reduce((total, scenario) => total + scenario.cases.length, 0),
  };
  return section.children.reduce(
    (total, child) => mergeDraftStats(total, collectSectionStats(child)),
    ownStats
  );
}

export function mergeDraftStats(left: DraftStats, right: DraftStats): DraftStats {
  return {
    sectionCount: left.sectionCount + right.sectionCount,
    scenarioCount: left.scenarioCount + right.scenarioCount,
    caseCount: left.caseCount + right.caseCount,
  };
}

export function emptyCoverageStats(): CoverageStats {
  return {
    selectedCases: 0,
    totalCases: 0,
    positiveScenarios: 0,
    negativeScenarios: 0,
    exploratoryScenarios: 0,
    warningCount: 0,
    casesWithData: 0,
    stepCount: 0,
  };
}

export function collectCoverageStats(draft: AIGenerationDraftPayload, selectedCaseIds: Set<string>): CoverageStats {
  return draft.sections.reduce(
    (total, section) => mergeCoverageStats(total, collectSectionCoverageStats(section)),
    { ...emptyCoverageStats(), selectedCases: selectedCaseIds.size }
  );
}

export function collectSectionCoverageStats(section: AIGenerationSectionDraft): CoverageStats {
  const ownStats = section.scenarios.reduce((total, scenario) => {
    const next = { ...total };
    if (scenario.polarity === "negative") next.negativeScenarios += 1;
    else next.positiveScenarios += 1;

    scenario.cases.forEach((testCase) => {
      next.totalCases += 1;
      next.warningCount += testCase.warnings?.length ?? 0;
      next.stepCount += testCase.steps.length;
      if (Object.keys(testCase.test_data ?? {}).length > 0) next.casesWithData += 1;
    });
    return next;
  }, emptyCoverageStats());

  return section.children.reduce(
    (total, child) => mergeCoverageStats(total, collectSectionCoverageStats(child)),
    ownStats
  );
}

export function mergeCoverageStats(left: CoverageStats, right: CoverageStats): CoverageStats {
  return {
    selectedCases: left.selectedCases + right.selectedCases,
    totalCases: left.totalCases + right.totalCases,
    positiveScenarios: left.positiveScenarios + right.positiveScenarios,
    negativeScenarios: left.negativeScenarios + right.negativeScenarios,
    exploratoryScenarios: left.exploratoryScenarios + right.exploratoryScenarios,
    warningCount: left.warningCount + right.warningCount,
    casesWithData: left.casesWithData + right.casesWithData,
    stepCount: left.stepCount + right.stepCount,
  };
}

export function filterDraftForReview(
  draft: AIGenerationDraftPayload,
  query: string,
  caseFilter: CaseSelectionFilter,
  selectedCaseIds: Set<string>,
  typeFilter: ReviewFilterValue = "all",
  priorityFilter: ReviewFilterValue = "all"
): AIGenerationDraftPayload {
  const normalizedQuery = normalizeSearchText(query);
  return {
    ...draft,
    sections: draft.sections
      .map((section) =>
        filterSectionForReview(section, normalizedQuery, caseFilter, selectedCaseIds, typeFilter, priorityFilter)
      )
      .filter((section): section is AIGenerationSectionDraft => Boolean(section)),
  };
}

export function filterSectionForReview(
  section: AIGenerationSectionDraft,
  query: string,
  caseFilter: CaseSelectionFilter,
  selectedCaseIds: Set<string>,
  typeFilter: ReviewFilterValue,
  priorityFilter: ReviewFilterValue
): AIGenerationSectionDraft | null {
  const sectionMatches = Boolean(query) && normalizeSearchText(section.name).includes(query);
  const scenarios = section.scenarios
    .map((scenario) =>
      filterScenarioForReview(
        scenario,
        query,
        caseFilter,
        selectedCaseIds,
        sectionMatches,
        typeFilter,
        priorityFilter
      )
    )
    .filter((scenario): scenario is AIGenerationScenarioDraft => Boolean(scenario));
  const children = section.children
    .map((child) => filterSectionForReview(child, query, caseFilter, selectedCaseIds, typeFilter, priorityFilter))
    .filter((child): child is AIGenerationSectionDraft => Boolean(child));

  if (!scenarios.length && !children.length) return null;
  return { ...section, scenarios, children };
}

export function filterScenarioForReview(
  scenario: AIGenerationScenarioDraft,
  query: string,
  caseFilter: CaseSelectionFilter,
  selectedCaseIds: Set<string>,
  ancestorMatches: boolean,
  typeFilter: ReviewFilterValue,
  priorityFilter: ReviewFilterValue
): AIGenerationScenarioDraft | null {
  if (!scenarioMatchesType(scenario, typeFilter)) return null;
  if (!scenarioMatchesPriority(scenario, priorityFilter)) return null;

  const scenarioText = normalizeSearchText(
    [
      scenario.title,
      scenario.description,
      scenario.scenario_type,
      scenario.priority,
      scenario.business_priority,
      scenario.polarity,
    ]
      .filter(Boolean)
      .join(" ")
  );
  const scenarioMatches = ancestorMatches || !query || scenarioText.includes(query);
  const cases = scenario.cases.filter((testCase) => {
    if (!caseSelectionMatches(testCase.draft_id, caseFilter, selectedCaseIds)) return false;
    if (scenarioMatches) return true;
    return caseMatchesQuery(testCase, query);
  });
  if (!cases.length) return null;
  return { ...scenario, cases };
}

function scenarioMatchesType(scenario: AIGenerationScenarioDraft, typeFilter: ReviewFilterValue): boolean {
  return typeFilter === "all" || scenario.scenario_type === typeFilter;
}

function scenarioMatchesPriority(
  scenario: AIGenerationScenarioDraft,
  priorityFilter: ReviewFilterValue
): boolean {
  return (
    priorityFilter === "all" ||
    scenario.priority === priorityFilter ||
    scenario.business_priority === priorityFilter
  );
}

export function caseSelectionMatches(
  caseId: string,
  caseFilter: CaseSelectionFilter,
  selectedCaseIds: Set<string>
): boolean {
  if (caseFilter === "selected") return selectedCaseIds.has(caseId);
  if (caseFilter === "unselected") return !selectedCaseIds.has(caseId);
  return true;
}

export function caseMatchesQuery(testCase: AIGenerationCaseDraft, query: string): boolean {
  if (!query) return true;
  return normalizeSearchText(
    [
      testCase.title,
      testCase.expected_result,
      testCase.preconditions,
      JSON.stringify(testCase.test_data ?? {}),
      ...testCase.steps.flatMap((step) => [step.action, step.expected_outcome]),
    ].join(" ")
  ).includes(query);
}

export function normalizeSearchText(value: string): string {
  return value.trim().toLowerCase();
}

export function resolveActiveDraftNode(
  draft: AIGenerationDraftPayload,
  activeDraftId: string | null
): ActiveDraftNode {
  if (!activeDraftId || activeDraftId === draft.suite.draft_id) {
    const stats = collectDraftStats(draft);
    return {
      id: draft.suite.draft_id,
      type: "suite",
      title: draft.suite.name,
      description: draft.suite.description || draft.summary,
      meta: [`${stats.sectionCount} sections`, `${stats.scenarioCount} scenarios`, `${stats.caseCount} cases`],
    };
  }
  for (const section of draft.sections) {
    const node = resolveSectionNode(section, activeDraftId);
    if (node) return node;
  }
  return resolveActiveDraftNode(draft, draft.suite.draft_id);
}

export function resolveSectionNode(
  section: AIGenerationSectionDraft,
  activeDraftId: string
): ActiveDraftNode | null {
  if (section.draft_id === activeDraftId) {
    const stats = collectSectionStats(section);
    return {
      id: section.draft_id,
      type: "section",
      title: section.name,
      description: "",
      meta: [`${stats.scenarioCount} scenarios`, `${stats.caseCount} cases`],
    };
  }
  for (const scenario of section.scenarios) {
    if (scenario.draft_id === activeDraftId) {
      return {
        id: scenario.draft_id,
        type: "scenario",
        title: scenario.title,
        description: scenario.description,
        meta: [
          scenario.scenario_type,
          scenario.priority,
          scenario.business_priority ?? scenario.polarity,
          `${scenario.cases.length} cases`,
        ],
      };
    }
    const testCase = scenario.cases.find((item) => item.draft_id === activeDraftId);
    if (testCase) {
      return {
        id: testCase.draft_id,
        type: "case",
        title: testCase.title,
        description: testCase.expected_result,
        meta: [`${testCase.steps.length} steps`],
        preconditions: testCase.preconditions,
        expectedResult: testCase.expected_result,
        steps: testCase.steps,
        testData: testCase.test_data,
      };
    }
  }
  for (const child of section.children) {
    const node = resolveSectionNode(child, activeDraftId);
    if (node) return node;
  }
  return null;
}

export function updateDraftNodeField(
  draft: AIGenerationDraftPayload,
  draftId: string,
  field: DraftEditableField,
  value: string
): AIGenerationDraftPayload {
  const next = cloneDraft(draft);
  if (next.suite.draft_id === draftId) {
    if (field === "title") next.suite.name = value;
    if (field === "description") next.suite.description = value;
    return next;
  }
  next.sections = next.sections.map((section) =>
    updateSectionNodeField(section, draftId, field, value)
  );
  return next;
}

export function updateSectionNodeField(
  section: AIGenerationSectionDraft,
  draftId: string,
  field: DraftEditableField,
  value: string
): AIGenerationSectionDraft {
  const next = { ...section };
  if (next.draft_id === draftId && field === "title") {
    next.name = value;
    return next;
  }
  next.scenarios = next.scenarios.map((scenario) => {
    if (scenario.draft_id === draftId) {
      return {
        ...scenario,
        title: field === "title" ? value : scenario.title,
        description: field === "description" ? value : scenario.description,
      };
    }
    return {
      ...scenario,
      cases: scenario.cases.map((testCase) => {
        if (testCase.draft_id !== draftId) return testCase;
        return {
          ...testCase,
          title: field === "title" ? value : testCase.title,
          preconditions: field === "preconditions" ? value : testCase.preconditions,
          expected_result: field === "expectedResult" ? value : testCase.expected_result,
        };
      }),
    };
  });
  next.children = next.children.map((child) => updateSectionNodeField(child, draftId, field, value));
  return next;
}

export function updateDraftCaseStep(
  draft: AIGenerationDraftPayload,
  caseDraftId: string,
  stepIndex: number,
  field: DraftStepEditableField,
  value: string
): AIGenerationDraftPayload {
  const next = cloneDraft(draft);
  next.sections = next.sections.map((section) =>
    updateSectionCaseStep(section, caseDraftId, stepIndex, field, value)
  );
  return next;
}

export function updateSectionCaseStep(
  section: AIGenerationSectionDraft,
  caseDraftId: string,
  stepIndex: number,
  field: DraftStepEditableField,
  value: string
): AIGenerationSectionDraft {
  return {
    ...section,
    scenarios: section.scenarios.map((scenario) => ({
      ...scenario,
      cases: scenario.cases.map((testCase) => {
        if (testCase.draft_id !== caseDraftId) return testCase;
        return {
          ...testCase,
          steps: testCase.steps.map((step) =>
            step.step_index === stepIndex ? { ...step, [field]: value } : step
          ),
        };
      }),
    })),
    children: section.children.map((child) =>
      updateSectionCaseStep(child, caseDraftId, stepIndex, field, value)
    ),
  };
}

export function insertDraftCaseStep(
  draft: AIGenerationDraftPayload,
  caseDraftId: string,
  afterStepIndex: number
): AIGenerationDraftPayload {
  const next = cloneDraft(draft);
  next.sections = next.sections.map((section) => insertSectionCaseStep(section, caseDraftId, afterStepIndex));
  return next;
}

export function insertSectionCaseStep(
  section: AIGenerationSectionDraft,
  caseDraftId: string,
  afterStepIndex: number
): AIGenerationSectionDraft {
  return {
    ...section,
    scenarios: section.scenarios.map((scenario) => ({
      ...scenario,
      cases: scenario.cases.map((testCase) => {
        if (testCase.draft_id !== caseDraftId) return testCase;
        const insertAt = Math.max(
          0,
          testCase.steps.findIndex((step) => step.step_index === afterStepIndex) + 1
        );
        const steps = [...testCase.steps];
        steps.splice(insertAt, 0, {
          step_index: afterStepIndex + 1,
          action: "",
          expected_outcome: "",
        });
        return { ...testCase, steps: reindexSteps(steps) };
      }),
    })),
    children: section.children.map((child) => insertSectionCaseStep(child, caseDraftId, afterStepIndex)),
  };
}

export function deleteDraftCaseStep(
  draft: AIGenerationDraftPayload,
  caseDraftId: string,
  stepIndex: number
): AIGenerationDraftPayload {
  const next = cloneDraft(draft);
  next.sections = next.sections.map((section) => deleteSectionCaseStep(section, caseDraftId, stepIndex));
  return next;
}

export function deleteSectionCaseStep(
  section: AIGenerationSectionDraft,
  caseDraftId: string,
  stepIndex: number
): AIGenerationSectionDraft {
  return {
    ...section,
    scenarios: section.scenarios.map((scenario) => ({
      ...scenario,
      cases: scenario.cases.map((testCase) => {
        if (testCase.draft_id !== caseDraftId) return testCase;
        return {
          ...testCase,
          steps: reindexSteps(testCase.steps.filter((step) => step.step_index !== stepIndex)),
        };
      }),
    })),
    children: section.children.map((child) => deleteSectionCaseStep(child, caseDraftId, stepIndex)),
  };
}

export function reindexSteps(steps: AIGenerationCaseDraft["steps"]): AIGenerationCaseDraft["steps"] {
  return steps.map((step, index) => ({ ...step, step_index: index + 1 }));
}

export function updateDraftCaseTestData(
  draft: AIGenerationDraftPayload,
  caseDraftId: string,
  testData: Record<string, unknown>
): AIGenerationDraftPayload {
  const next = cloneDraft(draft);
  next.sections = next.sections.map((section) => updateSectionCaseTestData(section, caseDraftId, testData));
  return next;
}

export function updateSectionCaseTestData(
  section: AIGenerationSectionDraft,
  caseDraftId: string,
  testData: Record<string, unknown>
): AIGenerationSectionDraft {
  return {
    ...section,
    scenarios: section.scenarios.map((scenario) => ({
      ...scenario,
      cases: scenario.cases.map((testCase) =>
        testCase.draft_id === caseDraftId ? { ...testCase, test_data: testData } : testCase
      ),
    })),
    children: section.children.map((child) => updateSectionCaseTestData(child, caseDraftId, testData)),
  };
}

export function cloneDraft(draft: AIGenerationDraftPayload): AIGenerationDraftPayload {
  return structuredClone(draft);
}

export function collectCaseIds(draft: AIGenerationDraftPayload): string[] {
  return draft.sections.flatMap(collectSectionCaseIds);
}

export function collectSectionCaseIds(section: AIGenerationSectionDraft): string[] {
  return [
    ...section.scenarios.flatMap((scenario) => scenario.cases.map((testCase) => testCase.draft_id)),
    ...section.children.flatMap(collectSectionCaseIds),
  ];
}

export function generationEvents(session: AIGenerationSession | null): GenerationEvent[] {
  const events = session?.critic_report?.events;
  if (!Array.isArray(events)) return [];
  return events.filter((event): event is GenerationEvent => {
    return Boolean(event && typeof event === "object" && "type" in event);
  });
}

export function hasTemporaryAttachmentContext(session: AIGenerationSession): boolean {
  const attachments = session.source_refs.temporary_attachments;
  return Array.isArray(attachments) && attachments.length > 0;
}

export function eventLabel(type: string) {
  return type
    .split("_")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

const EVENT_LABELS: Record<string, string> = {
  session_started: "Session queued",
  candidate_pool_started: "Building candidate pool",
  generation_plan_created: "Generation plan ready",
  clarification_required: "Clarification needed",
  refine_requested: "Refinement requested",
  draft_refined: "Refinements applied",
  generation_cancelled: "Generation stopped",
};

const PHASE_BY_EVENT: Record<string, string> = {
  session_started: "Queuing the generation session",
  candidate_pool_started: "Building the candidate scenario pool",
  generation_plan_created: "Selecting the strongest plan",
  clarification_required: "A few questions before drafting",
  refine_requested: "Applying your requested changes",
  draft_refined: "Refinements applied",
};

export function friendlyEventLabel(type: string): string {
  return EVENT_LABELS[type] ?? eventLabel(type);
}

export function phaseHeadline(session: AIGenerationSession, events: GenerationEvent[]): string {
  switch (session.status) {
    case "clarification_required":
      return "A few questions before drafting";
    case "ready_for_review":
    case "reviewing":
      return "Draft ready for review";
    case "saved":
      return "Saved to the repository";
    case "failed":
      return "Generation failed";
    case "cancelled":
      return "Generation stopped";
    default:
      break;
  }
  const last = events[events.length - 1];
  return (last && PHASE_BY_EVENT[last.type]) || "Structuring tests for clarity and coverage";
}

export function formatEventTime(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "";
  return parsed.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export function composerModeForStatus(status: string): ComposerMode {
  if (status === "clarification_required") return "clarify";
  if (status === "ready_for_review" || status === "reviewing") return "refine";
  if (status === "queued" || status === "generating") return "disabled";
  return "hidden";
}

export function extractOpenQuestions(session: AIGenerationSession): string[] {
  const payload = session.draft_payload as { open_questions?: unknown } | null;
  const questions = payload?.open_questions;
  if (!Array.isArray(questions)) return [];
  return questions.map((question) => String(question)).filter(Boolean);
}

export function collectDraftReferences(draft: AIGenerationDraftPayload): DraftReference[] {
  const refs: DraftReference[] = [];
  const walk = (section: AIGenerationSectionDraft) => {
    section.scenarios.forEach((scenario) => {
      refs.push({ draft_id: scenario.draft_id, label: scenario.title, type: "scenario" });
      scenario.cases.forEach((testCase) => {
        refs.push({ draft_id: testCase.draft_id, label: testCase.title, type: "case" });
      });
    });
    section.children.forEach(walk);
  };
  draft.sections.forEach(walk);
  return refs;
}

export function truncate(value: string, max: number): string {
  return value.length > max ? `${value.slice(0, max - 1)}...` : value;
}

export function errorMessage(error: unknown): string {
  if (typeof error === "object" && error !== null && "response" in error) {
    const data = (error as { response?: { data?: unknown } }).response?.data;
    if (data && typeof data === "object" && "detail" in data) {
      const detail = (data as Record<string, unknown>).detail;
      if (typeof detail === "string") return detail;
    }
    if (data) return JSON.stringify(data);
  }
  if (error instanceof Error) return error.message;
  return "Something went wrong.";
}
