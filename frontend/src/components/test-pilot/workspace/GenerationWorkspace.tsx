import { useMemo, useState } from "react";
import type {
  AIGenerationDraftPayload,
  AIGenerationScenarioDraft,
  AIGenerationSectionDraft,
  AIGenerationSession,
} from "../../../types/ai";
import type { Project } from "../../../types/project";
import { Button } from "../../ui";
import type {
  CaseSelectionFilter,
  DraftEditableField,
  DraftStepEditableField,
  GenerationEvent,
  LaunchContext,
  ReviewFilterValue,
  SavingState,
} from "../testPilot.types";
import {
  collectCaseIds,
  collectCoverageStats,
  collectDraftReferences,
  collectDraftStats,
  collectDraftStructureStats,
  composerModeForStatus,
  deleteDraftCaseStep,
  emptyCoverageStats,
  emptyDraftStats,
  emptyDraftStructureStats,
  extractOpenQuestions,
  filterDraftForReview,
  insertDraftCaseStep,
  phaseHeadline,
  resolveActiveDraftNode,
  updateDraftCaseStep,
  updateDraftCaseTestData,
  updateDraftNodeField,
} from "../testPilot.utils";
import DraftDetailDrawer from "../review/DraftDetailDrawer";
import DraftHierarchyView from "../review/DraftHierarchyView";
import DraftReviewToolbar from "../review/DraftReviewToolbar";
import ClarificationPanel from "./ClarificationPanel";
import ConversationComposer from "./ConversationComposer";
import {
  ActivityTimeline,
  GeneratingState,
  PromptSnapshot,
  SelectedPlan,
  StatusBlock,
} from "./WorkspacePanels";

export default function GenerationWorkspace({
  draft,
  events,
  initialContext,
  project,
  running,
  saving,
  selectedCaseIds,
  selectedScenarios,
  session,
  totalCaseCount,
  onCancel,
  onClarify,
  onCommit,
  onDraftChange,
  onOpenRepository,
  onRefine,
  onToggleCase,
}: Readonly<{
  draft: AIGenerationDraftPayload | null;
  events: GenerationEvent[];
  initialContext: LaunchContext;
  project: Project | null;
  running: boolean;
  saving: SavingState;
  selectedCaseIds: Set<string>;
  selectedScenarios: Array<Record<string, unknown>>;
  session: AIGenerationSession;
  totalCaseCount: number;
  onCancel: () => void;
  onClarify: (answers: string) => Promise<void>;
  onCommit: (createAsApproved: boolean) => Promise<void>;
  onDraftChange: (draft: AIGenerationDraftPayload) => void;
  onOpenRepository: () => void;
  onRefine: (instruction: string, draftIds: string[]) => Promise<void>;
  onToggleCase: (caseId: string) => void;
}>) {
  const [activeDraftId, setActiveDraftId] = useState<string | null>(null);
  const [draftQuery, setDraftQuery] = useState("");
  const [typeFilter, setTypeFilter] = useState<ReviewFilterValue>("all");
  const [priorityFilter, setPriorityFilter] = useState<ReviewFilterValue>("all");
  const caseFilter: CaseSelectionFilter = "all";
  const draftStats = useMemo(() => (draft ? collectDraftStats(draft) : emptyDraftStats()), [draft]);
  const structureStats = useMemo(
    () => (draft ? collectDraftStructureStats(draft) : emptyDraftStructureStats()),
    [draft]
  );
  const coverageStats = useMemo(
    () => (draft ? collectCoverageStats(draft, selectedCaseIds) : emptyCoverageStats()),
    [draft, selectedCaseIds]
  );
  const visibleDraft = useMemo(
    () => (draft ? filterDraftForReview(draft, draftQuery, caseFilter, selectedCaseIds, typeFilter, priorityFilter) : null),
    [caseFilter, draft, draftQuery, priorityFilter, selectedCaseIds, typeFilter]
  );
  const visibleCaseIds = useMemo(() => (visibleDraft ? collectCaseIds(visibleDraft) : []), [visibleDraft]);
  const reviewFilterOptions = useMemo(() => (draft ? collectReviewFilterOptions(draft) : emptyReviewFilterOptions()), [draft]);
  const resolvedActiveDraftId = activeDraftId ?? draft?.suite.draft_id ?? null;
  const activeNode = useMemo(
    () => (draft ? resolveActiveDraftNode(draft, resolvedActiveDraftId) : null),
    [draft, resolvedActiveDraftId]
  );
  const reviewCaseIds = useMemo(() => (draft ? collectCaseIds(draft) : []), [draft]);
  const selectedScenarioTarget = selectedScenarios.length || draftStats.scenarioCount;
  const progressPercent = selectedScenarioTarget
    ? Math.min(100, Math.round((draftStats.scenarioCount / selectedScenarioTarget) * 100))
    : running
      ? 12
      : session.status === "ready_for_review"
        ? 100
        : 0;
  const composerMode = composerModeForStatus(session.status);
  const refineReferences = useMemo(() => (draft ? collectDraftReferences(draft) : []), [draft]);
  const openQuestions = useMemo(() => extractOpenQuestions(session), [session]);
  const isClarifying = session.status === "clarification_required";

  function handleNodeFieldChange(field: DraftEditableField, value: string) {
    if (!draft || !activeNode || running) return;
    onDraftChange(updateDraftNodeField(draft, activeNode.id, field, value));
  }

  function handleStepChange(stepIndex: number, field: DraftStepEditableField, value: string) {
    if (!draft || !activeNode || running) return;
    onDraftChange(updateDraftCaseStep(draft, activeNode.id, stepIndex, field, value));
  }

  function handleAddStep(afterStepIndex: number) {
    if (!draft || !activeNode || running) return;
    onDraftChange(insertDraftCaseStep(draft, activeNode.id, afterStepIndex));
  }

  function handleDeleteStep(stepIndex: number) {
    if (!draft || !activeNode || running) return;
    onDraftChange(deleteDraftCaseStep(draft, activeNode.id, stepIndex));
  }

  function handleTestDataChange(value: Record<string, unknown>) {
    if (!draft || !activeNode || running) return;
    onDraftChange(updateDraftCaseTestData(draft, activeNode.id, value));
  }

  function moveDetail(direction: -1 | 1) {
    if (!reviewCaseIds.length || !activeNode) return;
    const currentIndex = reviewCaseIds.indexOf(activeNode.id);
    const fallbackIndex = direction > 0 ? 0 : reviewCaseIds.length - 1;
    const nextIndex = currentIndex >= 0 ? currentIndex + direction : fallbackIndex;
    if (nextIndex < 0 || nextIndex >= reviewCaseIds.length) return;
    setActiveDraftId(reviewCaseIds[nextIndex]);
  }

  function handleToggleScenario(scenario: AIGenerationScenarioDraft) {
    const caseIds = scenario.cases.map((testCase) => testCase.draft_id);
    const allSelected = caseIds.length > 0 && caseIds.every((caseId) => selectedCaseIds.has(caseId));
    caseIds.forEach((caseId) => {
      if (allSelected || !selectedCaseIds.has(caseId)) onToggleCase(caseId);
    });
  }

  function handleToggleVisibleCases() {
    if (!visibleCaseIds.length) return;
    const allSelected = visibleCaseIds.every((caseId) => selectedCaseIds.has(caseId));
    visibleCaseIds.forEach((caseId) => {
      if (allSelected || !selectedCaseIds.has(caseId)) onToggleCase(caseId);
    });
  }

  function closeDraftDetails() {
    setActiveDraftId(draft?.suite.draft_id ?? null);
  }

  const detailNode = activeNode && activeNode.type !== "suite" ? activeNode : null;
  const detailIndex = detailNode ? reviewCaseIds.indexOf(detailNode.id) : -1;

  return (
    <section className="flex h-full flex-col overflow-hidden bg-[#F4F8FC]">
      <header className="flex shrink-0 items-center justify-between gap-4 border-b border-slate-200 bg-white px-6 py-4 shadow-sm">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
            <span>{project?.name ?? "TestPilot workspace"}</span>
            <span>/</span>
            <span className="rounded-full bg-slate-100 px-2 py-0.5 font-medium capitalize text-slate-700">
              {session.status.replaceAll("_", " ")}
            </span>
            {draft && (
              <>
                <span>{draftStats.scenarioCount} scenarios</span>
                <span>{selectedCaseIds.size}/{totalCaseCount} selected</span>
              </>
            )}
          </div>
          <h1 className="mt-1 truncate text-lg font-semibold text-slate-950">{session.objective}</h1>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {running && (
            <button
              type="button"
              onClick={onCancel}
              className="rounded-md border border-red-200 bg-white px-3 py-2 text-sm font-medium text-red-600 hover:bg-red-50"
            >
              Stop generating
            </button>
          )}
          {session.status === "saved" && <Button onClick={onOpenRepository}>Open repository</Button>}
          {draft && session.status !== "saved" && (
            <>
              <button
                type="button"
                onClick={() => void onCommit(false)}
                disabled={Boolean(saving)}
                className="rounded-md border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-60"
              >
                Save draft
              </button>
              <Button
                isLoading={saving === "approved"}
                loadingText="Saving"
                onClick={() => void onCommit(true)}
              >
                Commit selected {selectedCaseIds.size}
              </Button>
            </>
          )}
        </div>
      </header>

      <div className="grid min-h-0 flex-1 grid-cols-1 overflow-hidden lg:grid-cols-[360px_minmax(0,1fr)]">
        <aside className="flex min-h-0 flex-col border-r border-slate-200 bg-[#F8FBFF]">
          <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-5 py-5">
            <PromptSnapshot session={session} initialContext={initialContext} />
            <StatusBlock
              selectedCount={selectedCaseIds.size}
              session={session}
              structureStats={structureStats}
            />
            {selectedScenarios.length > 0 && <SelectedPlan scenarios={selectedScenarios} />}
            <ActivityTimeline
              events={events}
              running={running}
              headline={phaseHeadline(session, events)}
            />
          </div>
          <ConversationComposer
            mode={composerMode}
            references={refineReferences}
            onClarify={onClarify}
            onRefine={onRefine}
          />
        </aside>

        <main className="min-h-0 overflow-y-auto bg-[radial-gradient(circle_at_top_left,rgba(90,184,255,0.16),transparent_34%),radial-gradient(circle_at_bottom_right,rgba(37,99,235,0.08),transparent_32%),linear-gradient(180deg,#F8FBFF,#F4F8FC)] px-5 py-5">
          {isClarifying ? (
            <ClarificationPanel objective={session.objective} openQuestions={openQuestions} />
          ) : draft && draft.sections.length > 0 ? (
            <div className="mx-auto flex min-h-full max-w-[1480px] flex-col">
              <DraftReviewToolbar
                allVisibleCasesSelected={visibleCaseIds.length > 0 && visibleCaseIds.every((caseId) => selectedCaseIds.has(caseId))}
                coverageStats={coverageStats}
                draft={draft}
                draftStats={draftStats}
                headline={phaseHeadline(session, events)}
                priorityFilter={priorityFilter}
                priorityOptions={reviewFilterOptions.priorities}
                progressPercent={progressPercent}
                query={draftQuery}
                running={running}
                typeFilter={typeFilter}
                typeOptions={reviewFilterOptions.types}
                visibleStats={visibleDraft ? collectDraftStats(visibleDraft) : emptyDraftStats()}
                visibleCaseCount={visibleCaseIds.length}
                onPriorityFilterChange={setPriorityFilter}
                onQueryChange={setDraftQuery}
                onToggleVisibleCases={handleToggleVisibleCases}
                onTypeFilterChange={setTypeFilter}
              />
              <DraftHierarchyView
                activeDraftId={activeNode?.id ?? draft.suite.draft_id}
                draft={visibleDraft ?? { ...draft, sections: [] }}
                emptyLabel={draftQuery || caseFilter !== "all" ? "No draft items match the current review filter." : undefined}
                selectedCaseIds={selectedCaseIds}
                onActivate={setActiveDraftId}
                onToggleCase={onToggleCase}
                onToggleScenario={handleToggleScenario}
              />
              {detailNode && (
                <DraftDetailDrawer
                  node={detailNode}
                  readOnly={running}
                  canGoNext={detailIndex >= 0 && detailIndex < reviewCaseIds.length - 1}
                  canGoPrevious={detailIndex > 0}
                  positionLabel={detailIndex >= 0 ? `Reviewing ${detailIndex + 1} of ${reviewCaseIds.length} test cases` : "Reviewing generated details"}
                  onClose={closeDraftDetails}
                  onFieldChange={handleNodeFieldChange}
                  onNext={() => moveDetail(1)}
                  onPrevious={() => moveDetail(-1)}
                  onAddStep={handleAddStep}
                  onDeleteStep={handleDeleteStep}
                  onStepChange={handleStepChange}
                  onTestDataChange={handleTestDataChange}
                />
              )}
            </div>
          ) : (
            <GeneratingState headline={phaseHeadline(session, events)} />
          )}
        </main>
      </div>
    </section>
  );
}

function emptyReviewFilterOptions(): { types: string[]; priorities: string[] } {
  return { types: [], priorities: [] };
}

function collectReviewFilterOptions(draft: AIGenerationDraftPayload): { types: string[]; priorities: string[] } {
  const types = new Set<string>();
  const priorities = new Set<string>();

  function walk(section: AIGenerationSectionDraft) {
    section.scenarios.forEach((scenario) => {
      if (scenario.scenario_type) types.add(scenario.scenario_type);
      if (scenario.priority) priorities.add(scenario.priority);
      if (scenario.business_priority) priorities.add(scenario.business_priority);
    });
    section.children.forEach(walk);
  }

  draft.sections.forEach(walk);
  return {
    types: Array.from(types).sort(),
    priorities: Array.from(priorities).sort(),
  };
}
