import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
} from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  answerAIGenerationClarification,
  cancelAIGeneration,
  commitAIGeneration,
  getAIGenerationSession,
  refineAIGeneration,
  startAIGeneration,
  updateAIGenerationReview,
} from "../api/ai";
import { createProject, getProject, getProjects } from "../api/projects/projects";
import AppLayout from "../components/layout/AppLayout";
import { Button, Spinner } from "../components/ui";
import { useAuthStore } from "../store/authStore";
import type {
  AIGenerationCaseDraft,
  AIGenerationDraftPayload,
  AIGenerationScenarioDraft,
  AIGenerationSectionDraft,
  AIGenerationSession,
} from "../types/ai";
import type { User } from "../types/auth";
import type { Project } from "../types/project";

type AttachmentMenu = "closed" | "open";
type SavingState = "draft" | "approved" | null;
type ProjectTargetMode = "auto" | "existing" | "new";

interface GenerationEvent {
  type: string;
  message?: string;
  payload?: unknown;
  created_at?: string;
}

interface LaunchContext {
  projectId: string | null;
  suiteId: string | null;
  sectionId: string | null;
  scenarioId: string | null;
  caseId: string | null;
  selectionType: string | null;
  labels: {
    project?: string;
    suite?: string;
    section?: string;
    scenario?: string;
    case?: string;
  };
}

interface ResolvedProject {
  projectId: string;
  project: Project | null;
}

interface DraftStats {
  sectionCount: number;
  scenarioCount: number;
  caseCount: number;
}

interface ActiveDraftNode {
  id: string;
  type: "suite" | "section" | "scenario" | "case";
  title: string;
  description: string;
  meta: string[];
  steps?: AIGenerationCaseDraft["steps"];
  preconditions?: string;
  expectedResult?: string;
  testData?: Record<string, unknown>;
}

type DraftEditableField = "title" | "description" | "preconditions" | "expectedResult";
type DraftStepEditableField = "action" | "expected_outcome";
type ComposerMode = "clarify" | "refine" | "disabled" | "hidden";
type CaseSelectionFilter = "all" | "selected" | "unselected";

interface DraftReference {
  draft_id: string;
  label: string;
  type: "scenario" | "case";
}

interface CoverageStats {
  selectedCases: number;
  totalCases: number;
  positiveScenarios: number;
  negativeScenarios: number;
  exploratoryScenarios: number;
  warningCount: number;
  casesWithData: number;
  stepCount: number;
}

const TERMINAL_STATUSES = new Set([
  "clarification_required",
  "ready_for_review",
  "reviewing",
  "saved",
  "failed",
  "cancelled",
]);
const POLL_INTERVAL_MS = 1800;
const ACTIVITY_EVENT_LIMIT = 12;

export default function TestPilotStudioPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const user = useAuthStore((state) => state.user);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const attachmentMenuRef = useRef<HTMLDivElement | null>(null);
  const knownCaseIdsRef = useRef<Set<string>>(new Set());

  const initialContext = useMemo(() => parseLaunchContext(searchParams), [searchParams]);
  const [availableProjects, setAvailableProjects] = useState<Project[]>([]);
  const [project, setProject] = useState<Project | null>(null);
  const [targetMode, setTargetMode] = useState<ProjectTargetMode>(
    initialContext.projectId ? "existing" : "auto"
  );
  const [selectedProjectId, setSelectedProjectId] = useState(initialContext.projectId ?? "");
  const [targetPanelOpen, setTargetPanelOpen] = useState(false);
  const [objective, setObjective] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [jiraIssueKey, setJiraIssueKey] = useState("");
  const [attachmentMenu, setAttachmentMenu] = useState<AttachmentMenu>("closed");
  const [session, setSession] = useState<AIGenerationSession | null>(null);
  const [draft, setDraft] = useState<AIGenerationDraftPayload | null>(null);
  const [selectedCaseIds, setSelectedCaseIds] = useState<Set<string>>(new Set());
  const [loadingContext, setLoadingContext] = useState(Boolean(initialContext.projectId));
  const [launching, setLaunching] = useState(false);
  const [saving, setSaving] = useState<SavingState>(null);
  const [error, setError] = useState("");

  const events = useMemo(() => generationEvents(session), [session]);
  const plan = session?.critic_report?.generation_plan as Record<string, unknown> | undefined;
  const selectedScenarios = Array.isArray(plan?.selected_scenarios)
    ? (plan.selected_scenarios as Array<Record<string, unknown>>)
    : [];
  const running = Boolean(session && !TERMINAL_STATUSES.has(session.status));
  const totalCaseCount = draft ? collectCaseIds(draft).length : 0;
  const canCreateProject = userCanCreateProject(user);

  useEffect(() => {
    let cancelled = false;
    getProjects("active")
      .then((projects) => {
        if (!cancelled) setAvailableProjects(projects);
      })
      .catch(() => {
        if (!cancelled) setError("Could not load project context.");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!initialContext.projectId) {
      setLoadingContext(false);
      return;
    }

    let cancelled = false;
    setLoadingContext(true);
    getProject(initialContext.projectId)
      .then((nextProject) => {
        if (cancelled) return;
        setProject(nextProject);
        setSelectedProjectId(nextProject.id);
      })
      .catch(() => {
        if (!cancelled) setError("Could not load the project context attached to this TestPilot session.");
      })
      .finally(() => {
        if (!cancelled) setLoadingContext(false);
      });

    return () => {
      cancelled = true;
    };
  }, [initialContext.projectId]);

  useEffect(() => {
    if (attachmentMenu !== "open") return;

    function handlePointerDown(event: MouseEvent) {
      if (!attachmentMenuRef.current?.contains(event.target as Node)) {
        setAttachmentMenu("closed");
      }
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setAttachmentMenu("closed");
    }

    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [attachmentMenu]);

  useEffect(() => {
    if (!session || TERMINAL_STATUSES.has(session.status)) return;
    const interval = window.setInterval(() => {
      void refreshSession(session.id);
    }, POLL_INTERVAL_MS);
    return () => window.clearInterval(interval);
  }, [session]);

  useEffect(() => {
    if (!session) return;
    const nextDraft = normalizeDraftForUI(session.draft_payload);
    if (!nextDraft) return;
    const nextCaseIds = collectCaseIds(nextDraft);
    const visibleCaseIds = new Set(nextCaseIds);
    setDraft(nextDraft);
    setSelectedCaseIds((current) => {
      const next = new Set(Array.from(current).filter((caseId) => visibleCaseIds.has(caseId)));
      nextCaseIds.forEach((caseId) => {
        if (!knownCaseIdsRef.current.has(caseId)) next.add(caseId);
      });
      knownCaseIdsRef.current = visibleCaseIds;
      return next;
    });
  }, [session]);

  async function handleLaunch() {
    const trimmedObjective = objective.trim();
    if (!trimmedObjective) {
      setError("Describe the workflow or requirement first.");
      return;
    }

    setLaunching(true);
    setError("");
    setDraft(null);
    setSelectedCaseIds(new Set());
    knownCaseIdsRef.current = new Set();

    try {
      const resolvedProject = await resolveProjectForGeneration({
        targetMode,
        selectedProjectId,
        availableProjects,
        contextProjectId: initialContext.projectId,
        objective: trimmedObjective,
        user,
      });
      if (resolvedProject.project) setProject(resolvedProject.project);

      const nextSession = await startAIGeneration({
        project: resolvedProject.projectId,
        objective: trimmedObjective,
        source_type: selectedFile || jiraIssueKey.trim() ? "mixed" : "prompt",
        target_suite: initialContext.suiteId,
        target_section: initialContext.sectionId,
        temporary_attachments: selectedFile ? [selectedFile] : undefined,
        source_refs: buildSourceRefs(initialContext),
        jira_issue_key: jiraIssueKey.trim(),
      });
      setSession(nextSession);
      if (TERMINAL_STATUSES.has(nextSession.status)) {
        await refreshSession(nextSession.id);
      }
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLaunching(false);
    }
  }

  async function refreshSession(sessionId: string) {
    const nextSession = await getAIGenerationSession(sessionId);
    setSession(nextSession);
    if (nextSession.status === "failed") {
      setError(nextSession.error_message || "Test generation failed.");
    }
  }

  async function handleCancel() {
    if (!session) return;
    try {
      const cancelled = await cancelAIGeneration(session.id);
      setSession(cancelled);
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  async function handleCommit(createAsApproved: boolean) {
    if (!session || !draft) return;
    const selectedIds = Array.from(selectedCaseIds);
    if (!selectedIds.length) {
      setError("Select at least one test case.");
      return;
    }

    setSaving(createAsApproved ? "approved" : "draft");
    setError("");
    try {
      await updateAIGenerationReview(session.id, {
        review_decisions: {
          draft_payload: draft,
          selected_case_ids: selectedIds,
        },
      });
      const committed = await commitAIGeneration(session.id, createAsApproved);
      setSession(committed.session);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSaving(null);
    }
  }

  async function handleClarify(answers: string) {
    if (!session) return;
    setError("");
    try {
      const next = await answerAIGenerationClarification(session.id, answers);
      setSession(next);
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  async function handleRefine(instruction: string, draftIds: string[]) {
    if (!session) return;
    setError("");
    try {
      const next = await refineAIGeneration(session.id, instruction, draftIds);
      setSession(next);
    } catch (err) {
      setError(errorMessage(err));
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

  const canLaunch = Boolean(objective.trim() || selectedFile || jiraIssueKey.trim());

  if (loadingContext) {
    return (
      <AppLayout>
        <div className="flex h-full items-center justify-center">
          <Spinner size="lg" />
        </div>
      </AppLayout>
    );
  }

  return (
    <AppLayout projectName={project?.name}>
      <div className="h-full overflow-hidden bg-white">
        <main className="h-full min-w-0 overflow-hidden">
          {!session ? (
            <section
              className="relative flex h-full flex-col items-center justify-center overflow-y-auto bg-slate-50 px-4 py-6 sm:px-6"
              style={{
                backgroundImage:
                  [
                    "linear-gradient(180deg, rgba(255,255,255,0.46) 0%, rgba(255,255,255,0.30) 48%, rgba(255,255,255,0.16) 100%)",
                    "linear-gradient(90deg, rgba(255,255,255,0.56) 0%, rgba(255,255,255,0.26) 50%, rgba(255,255,255,0.52) 100%)",
                    "url('/testpilot-prompt-bg.png')",
                  ].join(", "),
                backgroundPosition: "center",
                backgroundSize: "cover",
              }}
            >
              <div className="w-full max-w-[900px]">
                <div className="mb-5 text-center">
                  <div className="mx-auto flex h-20 w-20 items-center justify-center overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-[0_18px_48px_rgba(15,23,42,0.14)]">
                    <img src="/biat_logo.png" alt="BIAT logo" className="h-full w-full object-cover" />
                  </div>
                  <h1 className="mt-4 text-3xl font-semibold tracking-tight text-[#17233C] sm:text-[34px]">
                    What is your objective today?
                  </h1>
                  <p className="mt-2 text-sm font-medium text-[#334155] sm:text-base">
                    Describe a feature, workflow, or requirement to generate structured test coverage.
                  </p>
                </div>

                <div className="rounded-2xl border border-white/70 bg-white/94 p-4 shadow-[0_18px_45px_rgba(11,23,51,0.18)] sm:p-5">
                  <div className="mb-3 flex items-center justify-between gap-4">
                    <div className="min-w-0">
                      <span className="block truncate text-sm font-semibold text-[#17233C]">
                        Project: {project ? project.name : targetLabel(targetMode, availableProjects).replace("Project: ", "")}
                      </span>
                    </div>
                    {!initialContext.projectId && (
                      <button
                        type="button"
                        onClick={() => setTargetPanelOpen((current) => !current)}
                        className="shrink-0 rounded-md px-2 py-1.5 text-sm font-semibold text-[#2563EB] transition hover:bg-[#EAF4FF] focus:outline-none focus:ring-2 focus:ring-[#5AB8FF]"
                      >
                        Change project
                      </button>
                    )}
                  </div>

                  {(initialContext.labels.suite ||
                    initialContext.labels.section ||
                    initialContext.labels.scenario ||
                    initialContext.labels.case) && (
                    <div className="mb-4 flex flex-wrap gap-2">
                      {initialContext.labels.suite && <ContextChip label={`Suite: ${initialContext.labels.suite}`} />}
                      {initialContext.labels.section && <ContextChip label={`Section: ${initialContext.labels.section}`} />}
                      {initialContext.labels.scenario && <ContextChip label={`Scenario: ${initialContext.labels.scenario}`} />}
                      {initialContext.labels.case && <ContextChip label={`Case: ${initialContext.labels.case}`} />}
                    </div>
                  )}

                  {targetPanelOpen && (
                    <ProjectTargetPanel
                      availableProjects={availableProjects}
                      canCreateProject={canCreateProject}
                      selectedProjectId={selectedProjectId}
                      targetMode={targetMode}
                      onTargetModeChange={setTargetMode}
                      onProjectChange={setSelectedProjectId}
                    />
                  )}

                  {(selectedFile || jiraIssueKey) && (
                    <div className="mb-3 flex flex-wrap gap-2">
                      {selectedFile && (
                        <AttachmentChip label={selectedFile.name} onRemove={() => setSelectedFile(null)} />
                      )}
                      {jiraIssueKey && (
                        <AttachmentChip kind="jira" label={`Jira ${jiraIssueKey}`} onRemove={() => setJiraIssueKey("")} />
                      )}
                    </div>
                  )}

                  <div>
                    <label htmlFor="testpilot-objective" className="text-sm font-semibold text-[#17233C]">
                      Objective or requirements
                    </label>
                    <textarea
                      id="testpilot-objective"
                      value={objective}
                      onChange={(event) => setObjective(event.target.value)}
                      rows={7}
                      placeholder="Describe the workflow, rule, user story, or file context to test."
                      className="mt-2 h-[clamp(118px,18vh,165px)] w-full resize-none rounded-xl border border-[#D9E8F7] bg-white px-4 py-3 text-base leading-6 text-[#17233C] outline-none placeholder:text-slate-400 transition focus:border-[#5AB8FF] focus:ring-2 focus:ring-[#EAF4FF]"
                    />
                    {error && <ErrorBanner message={error} />}
                    <div className="mt-3 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                      <div ref={attachmentMenuRef} className="relative flex flex-wrap items-center gap-2">
                        <input
                          ref={fileInputRef}
                          type="file"
                          accept=".pdf,.docx,.xlsx,.csv,.txt"
                          className="hidden"
                          onChange={(event) => {
                            setSelectedFile(event.target.files?.[0] ?? null);
                            setAttachmentMenu("closed");
                          }}
                        />
                        <button
                          type="button"
                          onClick={() => fileInputRef.current?.click()}
                          className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 bg-white text-[#17233C] transition hover:bg-[#EAF4FF] focus:outline-none focus:ring-2 focus:ring-[#5AB8FF]"
                          aria-label="Upload files"
                        >
                          <DocumentStackIcon />
                        </button>
                        <button
                          type="button"
                          onClick={() => setAttachmentMenu((current) => (current === "open" ? "closed" : "open"))}
                          className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 bg-white text-[#17233C] transition hover:bg-[#EAF4FF] focus:outline-none focus:ring-2 focus:ring-[#5AB8FF]"
                          aria-label="Import from Jira"
                        >
                          <JiraLogo />
                        </button>
                        {attachmentMenu === "open" && (
                          <AttachmentMenuPanel
                            jiraIssueKey={jiraIssueKey}
                            onClose={() => setAttachmentMenu("closed")}
                            onJiraIssueKeyChange={setJiraIssueKey}
                          />
                        )}
                      </div>
                      <div className="flex items-center justify-end gap-2">
                        <button
                          type="button"
                          disabled={!canLaunch || launching}
                          onClick={() => void handleLaunch()}
                          className="inline-flex h-10 items-center justify-center rounded-lg border border-[#5AB8FF] bg-[#5AB8FF] px-4 text-sm font-semibold text-[#0B1733] shadow-sm transition hover:bg-[#7AC7FF] focus:outline-none focus:ring-2 focus:ring-[#2563EB] focus:ring-offset-2 disabled:cursor-not-allowed disabled:border-slate-200 disabled:bg-slate-100 disabled:text-slate-400 disabled:shadow-none"
                        >
                          {launching ? "Generating" : "Generate test plan"}
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </section>
          ) : (
            <GenerationWorkspace
              draft={draft}
              events={events}
              initialContext={initialContext}
              project={project}
              running={running}
              saving={saving}
              selectedCaseIds={selectedCaseIds}
              selectedScenarios={selectedScenarios}
              session={session}
              totalCaseCount={totalCaseCount}
              onCancel={() => void handleCancel()}
              onClarify={handleClarify}
              onCommit={handleCommit}
              onDraftChange={setDraft}
              onOpenRepository={() => navigate(`/projects/${session.project}`)}
              onRefine={handleRefine}
              onToggleCase={toggleCase}
            />
          )}
        </main>
      </div>
    </AppLayout>
  );
}

function GenerationWorkspace({
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
  const caseFilter: CaseSelectionFilter = "all";
  const draftStats = useMemo(() => (draft ? collectDraftStats(draft) : emptyDraftStats()), [draft]);
  const coverageStats = useMemo(
    () => (draft ? collectCoverageStats(draft, selectedCaseIds) : emptyCoverageStats()),
    [draft, selectedCaseIds]
  );
  const visibleDraft = useMemo(
    () => (draft ? filterDraftForReview(draft, draftQuery, caseFilter, selectedCaseIds) : null),
    [caseFilter, draft, draftQuery, selectedCaseIds]
  );
  const activeNode = useMemo(
    () => (draft ? resolveActiveDraftNode(draft, activeDraftId) : null),
    [activeDraftId, draft]
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

  useEffect(() => {
    if (!draft) return;
    setActiveDraftId((current) => current ?? draft.suite.draft_id);
  }, [draft]);

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
              progressPercent={progressPercent}
              scenarioCount={draftStats.scenarioCount}
              scenarioTarget={selectedScenarioTarget}
              selectedCount={selectedCaseIds.size}
              session={session}
              totalCount={totalCaseCount}
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
                coverageStats={coverageStats}
                draft={draft}
                draftStats={draftStats}
                headline={phaseHeadline(session, events)}
                progressPercent={progressPercent}
                query={draftQuery}
                running={running}
                visibleStats={visibleDraft ? collectDraftStats(visibleDraft) : emptyDraftStats()}
                onQueryChange={setDraftQuery}
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
            <div className="flex h-full items-center justify-center px-4">
              <div className="w-full max-w-2xl rounded-2xl border border-[#D9E8F7] bg-white/92 p-7 text-center shadow-[0_18px_45px_rgba(11,23,51,0.08)]">
                <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-[#EAF4FF]">
                  <Spinner size="lg" />
                </div>
                <h2 className="mt-5 text-xl font-semibold text-[#17233C]">
                  {phaseHeadline(session, events)}
                </h2>
                <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-[#64748B]">
                  Planning candidate scenarios, selecting the strongest set, then expanding test cases.
                </p>
                <div className="mt-6 grid gap-3 text-left sm:grid-cols-3">
                  {["Understanding context", "Selecting coverage", "Drafting cases"].map((item) => (
                    <div key={item} className="rounded-lg border border-[#D9E8F7] bg-[#F8FBFF] px-3 py-2 text-xs font-semibold text-[#64748B]">
                      {item}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </main>
      </div>
    </section>
  );
}

function DraftReviewToolbar({
  coverageStats,
  draft,
  draftStats,
  headline,
  progressPercent,
  query,
  running,
  visibleStats,
  onQueryChange,
}: Readonly<{
  coverageStats: CoverageStats;
  draft: AIGenerationDraftPayload;
  draftStats: DraftStats;
  headline: string;
  progressPercent: number;
  query: string;
  running: boolean;
  visibleStats: DraftStats;
  onQueryChange: (query: string) => void;
}>) {
  return (
    <div className="mb-5 rounded-2xl border border-[#D9E8F7] bg-white/95 p-4 shadow-sm">
      <div className="mb-4 border-b border-[#E4EEF8] pb-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="text-sm text-slate-600">
            Progress: <span className="font-semibold text-slate-950">{progressPercent}%</span>
          </div>
          <div className="text-sm font-semibold text-slate-500">{headline}</div>
        </div>
        <div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-200">
          <div
            className={[
              "h-full rounded-full transition-all duration-500",
              running ? "bg-emerald-500" : "bg-blue-600",
            ].join(" ")}
            style={{ width: `${progressPercent}%` }}
          />
        </div>
      </div>
      <div className="mb-3 flex flex-wrap items-center gap-3 rounded-xl bg-[#F8FBFF] px-3 py-2 text-sm text-slate-600">
        <span className="font-medium text-slate-950">{draft.suite.name}</span>
        <span className="text-slate-300">/</span>
        <span>{draftStats.scenarioCount} scenarios</span>
        <span>{draftStats.caseCount} cases</span>
        <span className="text-emerald-700">{coverageStats.positiveScenarios}P</span>
        <span className="text-red-600">{coverageStats.negativeScenarios}N</span>
        {coverageStats.warningCount > 0 && <span className="text-amber-700">{coverageStats.warningCount} warnings</span>}
      </div>
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex shrink-0 items-center gap-3">
          <input
            type="checkbox"
            checked={coverageStats.totalCases > 0 && coverageStats.selectedCases === coverageStats.totalCases}
            readOnly
            className="h-5 w-5 rounded border-slate-300 text-blue-600"
            aria-label="All cases selected status"
          />
          <span className="text-sm font-semibold text-slate-600">{coverageStats.selectedCases}</span>
          <span className="text-sm text-slate-400">{visibleStats.scenarioCount} visible</span>
        </div>
        <label className="relative min-w-0 flex-1">
          <span className="sr-only">Search draft</span>
          <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-xs font-semibold text-slate-400" aria-hidden>
            Search
          </span>
          <input
            value={query}
            onChange={(event) => onQueryChange(event.target.value)}
            placeholder="Search by test cases"
            className="h-10 w-full rounded-md border border-slate-300 bg-white pl-16 pr-3 text-sm text-slate-900 outline-none transition placeholder:text-slate-500 focus:border-blue-400 focus:ring-2 focus:ring-blue-100"
          />
        </label>
        <div className="flex flex-wrap items-center gap-2">
          <ToolbarDropdownButton label="Type" />
          <ToolbarDropdownButton label="Priority" />
        </div>
      </div>
    </div>
  );
}

function ToolbarDropdownButton({ label }: Readonly<{ label: string }>) {
  return (
    <button
      type="button"
      className="inline-flex h-10 items-center gap-3 rounded-md border border-slate-300 bg-white px-4 text-sm font-semibold text-slate-600 transition hover:border-slate-400 hover:text-slate-950"
    >
      {label}
      <span className="text-slate-400" aria-hidden>v</span>
    </button>
  );
}

function PromptSnapshot({
  session,
  initialContext,
}: Readonly<{ session: AIGenerationSession; initialContext: LaunchContext }>) {
  return (
    <div className="rounded-xl border border-[#D9E8F7] bg-white p-4 shadow-sm">
      <h2 className="text-xs font-semibold uppercase tracking-wide text-[#64748B]">Prompt</h2>
      <p className="mt-3 text-sm leading-6 text-slate-700">{session.objective}</p>
      <div className="mt-3 flex flex-wrap gap-2">
        {hasTemporaryAttachmentContext(session) ? <ContextChip label="Document attached" /> : null}
        {initialContext.selectionType && <ContextChip label={`Context: ${initialContext.selectionType}`} />}
      </div>
    </div>
  );
}

function StatusBlock({
  progressPercent,
  scenarioCount,
  scenarioTarget,
  session,
  selectedCount,
  totalCount,
}: Readonly<{
  progressPercent: number;
  scenarioCount: number;
  scenarioTarget: number;
  session: AIGenerationSession;
  selectedCount: number;
  totalCount: number;
}>) {
  return (
    <div className="rounded-xl border border-[#D9E8F7] bg-white p-4 shadow-sm">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-950">Generation</h2>
        <span className="rounded-full bg-[#EAF4FF] px-2.5 py-1 text-xs font-medium capitalize text-[#17233C]">
          {session.status.replaceAll("_", " ")}
        </span>
      </div>
      <div className="mt-4">
        <div className="flex items-center justify-between text-xs text-slate-500">
          <span>Plan to draft</span>
          <span>{scenarioCount}/{scenarioTarget || "?"} scenarios</span>
        </div>
        <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-100">
          <div
            className="h-full rounded-full bg-emerald-500 transition-all duration-500"
            style={{ width: `${progressPercent}%` }}
          />
        </div>
      </div>
      <div className="mt-4 grid grid-cols-2 gap-3">
        <Metric label="Input" value={String(session.input_tokens || 0)} />
        <Metric label="Output" value={String(session.output_tokens || 0)} />
        <Metric label="Selected" value={String(selectedCount)} />
        <Metric label="Cases" value={String(totalCount)} />
      </div>
    </div>
  );
}

function SelectedPlan({ scenarios }: Readonly<{ scenarios: Array<Record<string, unknown>> }>) {
  return (
    <div className="rounded-xl border border-[#D9E8F7] bg-white p-4 shadow-sm">
      <h2 className="text-sm font-semibold text-slate-950">Selected plan</h2>
      <div className="mt-3 space-y-2">
        {scenarios.map((scenario) => (
          <div
            key={String(scenario.draft_scenario_id ?? scenario.candidate_id)}
            className="rounded-lg bg-[#F8FBFF] px-3 py-2"
          >
            <div className="text-sm font-medium text-slate-800">{String(scenario.title ?? "Scenario")}</div>
            <div className="mt-1 text-xs text-slate-500">
              {String(scenario.category ?? "functional")} / {String(scenario.priority ?? "should_have")} /{" "}
              {String(scenario.intended_case_count ?? "?")} cases
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function ActivityTimeline({
  events,
  running,
  headline,
}: Readonly<{ events: GenerationEvent[]; running: boolean; headline: string }>) {
  const visible = events.slice(-ACTIVITY_EVENT_LIMIT);
  return (
    <div className="rounded-xl border border-[#D9E8F7] bg-white p-4 shadow-sm">
      <div className="flex items-center gap-2">
        {running ? (
          <span className="relative flex h-2.5 w-2.5" aria-hidden>
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-sky-400 opacity-75" />
            <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-sky-500" />
          </span>
        ) : (
          <span className="h-2.5 w-2.5 rounded-full bg-emerald-500" aria-hidden />
        )}
        <h2 className="text-sm font-semibold text-slate-950">{running ? "Thinking" : "Thought process"}</h2>
      </div>
      <p className="mt-1 text-sm font-medium text-slate-600">{headline}</p>
      <ol className="mt-4">
        {visible.length ? (
          visible.map((event, index) => {
            const isLast = index === visible.length - 1;
            return (
              <li key={`${event.type}-${index}`} className="relative flex gap-3 pb-4 last:pb-0">
                {!isLast && <span className="absolute left-[5px] top-3 h-full w-px bg-slate-200" aria-hidden />}
                <span
                  className={[
                    "relative mt-1 h-2.5 w-2.5 shrink-0 rounded-full",
                    isLast && running ? "bg-sky-500" : "bg-slate-300",
                  ].join(" ")}
                  aria-hidden
                />
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-medium text-slate-800">{friendlyEventLabel(event.type)}</span>
                    {event.created_at && (
                      <span className="text-[11px] text-slate-400">{formatEventTime(event.created_at)}</span>
                    )}
                  </div>
                  {event.message && <p className="mt-0.5 text-sm leading-6 text-slate-500">{event.message}</p>}
                </div>
              </li>
            );
          })
        ) : (
          <li className="text-sm text-slate-500">Starting the generation session.</li>
        )}
      </ol>
    </div>
  );
}

function ClarificationPanel({
  objective,
  openQuestions,
}: Readonly<{ objective: string; openQuestions: string[] }>) {
  return (
    <div className="mx-auto max-w-4xl">
      <div className="rounded-2xl border border-amber-200 bg-gradient-to-br from-amber-50 to-white px-6 py-5 shadow-sm">
        <h2 className="text-lg font-semibold text-amber-950">A few questions before drafting</h2>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-amber-800">
          The requirements were too ambiguous to generate strong tests. Answer in the chat on the
          left and TestPilot will continue from where it stopped.
        </p>
      </div>
      <div className="mt-5 grid gap-5 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
      <div className="rounded-2xl border border-[#D9E8F7] bg-white p-5 shadow-sm">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Objective</h3>
        <p className="mt-2 text-sm leading-6 text-slate-700">{objective}</p>
      </div>
      <div className="rounded-2xl border border-[#D9E8F7] bg-white p-5 shadow-sm">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Open questions</h3>
        {openQuestions.length ? (
          <ol className="mt-3 space-y-3">
            {openQuestions.map((question, index) => (
              <li key={`${index}-${question.slice(0, 12)}`} className="flex gap-3">
                <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-amber-100 text-xs font-semibold text-amber-700">
                  {index + 1}
                </span>
                <span className="text-sm leading-6 text-slate-700">{question}</span>
              </li>
            ))}
          </ol>
        ) : (
          <p className="mt-3 text-sm text-slate-500">Add more concrete requirements to continue.</p>
        )}
      </div>
      </div>
    </div>
  );
}

function ConversationComposer({
  mode,
  references,
  onClarify,
  onRefine,
}: Readonly<{
  mode: ComposerMode;
  references: DraftReference[];
  onClarify: (answers: string) => Promise<void>;
  onRefine: (instruction: string, draftIds: string[]) => Promise<void>;
}>) {
  const [text, setText] = useState("");
  const [selectedRefs, setSelectedRefs] = useState<DraftReference[]>([]);
  const [mentionOpen, setMentionOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  if (mode === "hidden") return null;

  if (mode === "disabled") {
    return (
      <div className="border-t border-slate-200 bg-white px-5 py-4">
        <div className="flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-3 text-sm text-slate-500">
          <span className="relative flex h-2.5 w-2.5" aria-hidden>
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-sky-400 opacity-75" />
            <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-sky-500" />
          </span>
          <span>TestPilot is working&hellip;</span>
        </div>
      </div>
    );
  }

  const isRefine = mode === "refine";
  const placeholder = isRefine
    ? "Refine the draft - e.g. add a negative case for expired tokens. Use @ to target a scenario or case."
    : "Answer the questions so TestPilot can continue.";

  function toggleRef(ref: DraftReference) {
    setSelectedRefs((current) =>
      current.some((item) => item.draft_id === ref.draft_id)
        ? current.filter((item) => item.draft_id !== ref.draft_id)
        : [...current, ref]
    );
    setMentionOpen(false);
  }

  async function submit() {
    const trimmed = text.trim();
    if (!trimmed || submitting) return;
    setSubmitting(true);
    try {
      if (isRefine) {
        await onRefine(trimmed, selectedRefs.map((ref) => ref.draft_id));
      } else {
        await onClarify(trimmed);
      }
      setText("");
      setSelectedRefs([]);
    } finally {
      setSubmitting(false);
    }
  }

  function handleKeyDown(event: ReactKeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void submit();
    }
  }

  return (
    <div className="relative border-t border-slate-200 bg-white px-5 py-4">
      {isRefine && selectedRefs.length > 0 && (
        <div className="mb-2 flex flex-wrap gap-2">
          {selectedRefs.map((ref) => (
            <span
              key={ref.draft_id}
              className="inline-flex items-center gap-1 rounded-full border border-sky-200 bg-sky-50 px-2.5 py-1 text-xs font-medium text-sky-700"
            >
              {ref.type === "scenario" ? "Scenario" : "Case"}: {truncate(ref.label, 26)}
              <button
                type="button"
                onClick={() => toggleRef(ref)}
                className="text-sky-400 hover:text-sky-700"
                aria-label={`Remove ${ref.label}`}
              >
                x
              </button>
            </span>
          ))}
        </div>
      )}
      {mentionOpen && isRefine && (
        <div className="absolute inset-x-5 bottom-[96px] z-20 max-h-60 overflow-y-auto rounded-lg border border-slate-200 bg-white shadow-xl">
          {references.length ? (
            references.map((ref) => (
              <button
                key={ref.draft_id}
                type="button"
                onClick={() => toggleRef(ref)}
                className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-sm hover:bg-slate-50"
              >
                <span className="truncate text-slate-700">{ref.label}</span>
                <span className="shrink-0 text-xs uppercase text-slate-400">{ref.type}</span>
              </button>
            ))
          ) : (
            <p className="px-3 py-2 text-sm text-slate-500">No scenarios or cases yet.</p>
          )}
        </div>
      )}
      <div className="rounded-lg border border-slate-200 bg-white focus-within:border-sky-400 focus-within:ring-2 focus-within:ring-sky-100">
        <textarea
          value={text}
          onChange={(event) => setText(event.target.value)}
          onKeyDown={handleKeyDown}
          rows={3}
          placeholder={placeholder}
          className="w-full resize-none border-0 bg-transparent px-3 py-2 text-sm text-slate-800 outline-none placeholder:text-slate-400"
        />
        <div className="flex items-center justify-between px-2 py-2">
          {isRefine ? (
            <button
              type="button"
              onClick={() => setMentionOpen((open) => !open)}
              className="rounded-md px-2 py-1 text-sm font-semibold text-slate-500 hover:bg-slate-100"
              title="Reference a scenario or case"
            >
              @
            </button>
          ) : (
            <span />
          )}
          <Button size="sm" isLoading={submitting} loadingText="Sending" onClick={() => void submit()}>
            {isRefine ? "Send" : "Answer"}
          </Button>
        </div>
      </div>
    </div>
  );
}

function DraftHierarchyView({
  activeDraftId,
  draft,
  emptyLabel,
  selectedCaseIds,
  onActivate,
  onToggleCase,
  onToggleScenario,
}: Readonly<{
  activeDraftId: string;
  draft: AIGenerationDraftPayload;
  emptyLabel?: string;
  selectedCaseIds: Set<string>;
  onActivate: (draftId: string) => void;
  onToggleCase: (caseId: string) => void;
  onToggleScenario: (scenario: AIGenerationScenarioDraft) => void;
}>) {
  return (
    <section className="min-h-0">
      <div className="space-y-4">
        {draft.sections.length ? draft.sections.map((section) => (
          <SectionTreeNode
            activeDraftId={activeDraftId}
            key={section.draft_id}
            section={section}
            selectedCaseIds={selectedCaseIds}
            onActivate={onActivate}
            onToggleCase={onToggleCase}
            onToggleScenario={onToggleScenario}
          />
        )) : (
          <div className="rounded-lg border border-slate-200 bg-white px-4 py-12 text-center">
            <p className="text-sm font-medium text-slate-700">{emptyLabel ?? "No generated items yet."}</p>
    ? "Refine the draft - e.g. add a negative case for expired tokens. Use @ to target a scenario or case."
          </div>
        )}
      </div>
    </section>
  );
}

function SectionTreeNode({
  activeDraftId,
  section,
  selectedCaseIds,
  onActivate,
  onToggleCase,
  onToggleScenario,
}: Readonly<{
  activeDraftId: string;
  section: AIGenerationSectionDraft;
  selectedCaseIds: Set<string>;
  onActivate: (draftId: string) => void;
  onToggleCase: (caseId: string) => void;
  onToggleScenario: (scenario: AIGenerationScenarioDraft) => void;
}>) {
  const stats = collectSectionStats(section);
  return (
    <details open className="group rounded-xl border border-[#D9E8F7] bg-white shadow-sm">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3.5 marker:hidden">
        <button type="button" onClick={() => onActivate(section.draft_id)} className="min-w-0 text-left">
          <span className="block truncate text-sm font-semibold text-slate-900">{section.name}</span>
          <span className="mt-0.5 block text-xs text-slate-500">
            {stats.scenarioCount} scenarios / {stats.caseCount} cases
          </span>
        </button>
        <span className="text-slate-400 transition group-open:rotate-90">&gt;</span>
      </summary>
      <div className="border-t border-[#E4EEF8] bg-white">
        {section.scenarios.map((scenario) => (
          <ScenarioTreeNode
            activeDraftId={activeDraftId}
            key={scenario.draft_id}
            scenario={scenario}
            selectedCaseIds={selectedCaseIds}
            onActivate={onActivate}
            onToggleCase={onToggleCase}
            onToggleScenario={onToggleScenario}
          />
        ))}
        {section.children.map((child) => (
          <div key={child.draft_id} className="border-t border-[#E4EEF8] bg-[#F8FBFF] p-3">
            <SectionTreeNode
              activeDraftId={activeDraftId}
              section={child}
              selectedCaseIds={selectedCaseIds}
              onActivate={onActivate}
              onToggleCase={onToggleCase}
              onToggleScenario={onToggleScenario}
            />
          </div>
        ))}
      </div>
    </details>
  );
}

function ScenarioTreeNode({
  activeDraftId,
  scenario,
  selectedCaseIds,
  onActivate,
  onToggleCase,
  onToggleScenario,
}: Readonly<{
  activeDraftId: string;
  scenario: AIGenerationScenarioDraft;
  selectedCaseIds: Set<string>;
  onActivate: (draftId: string) => void;
  onToggleCase: (caseId: string) => void;
  onToggleScenario: (scenario: AIGenerationScenarioDraft) => void;
}>) {
  const selectedCount = scenario.cases.filter((testCase) => selectedCaseIds.has(testCase.draft_id)).length;
  const selected = scenario.cases.length > 0 && selectedCount === scenario.cases.length;
  const polarityCounts = collectScenarioPolarityCounts(scenario);
  return (
    <details className="group border-t border-[#E4EEF8] first:border-t-0">
      <summary
        className={[
          "grid cursor-pointer list-none items-center gap-3 px-4 py-3.5 transition marker:hidden md:grid-cols-[auto_auto_minmax(0,1fr)_auto_auto]",
          activeDraftId === scenario.draft_id ? "bg-[#EAF4FF]" : "bg-white hover:bg-[#F8FBFF]",
        ].join(" ")}
      >
        <input
          type="checkbox"
          checked={selected}
          onChange={(event) => {
            event.preventDefault();
            event.stopPropagation();
            onToggleScenario(scenario);
          }}
          onClick={(event) => event.stopPropagation()}
          className="h-5 w-5 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
          aria-label={`Select all cases in ${scenario.title}`}
        />
        <span className="text-slate-500" aria-hidden>
          list
        </span>
        <button type="button" onClick={(event) => {
          event.preventDefault();
          event.stopPropagation();
          onActivate(scenario.draft_id);
        }} className="min-w-0 text-left">
          <span className="block truncate text-sm font-semibold text-slate-950">{scenario.title}</span>
          <span className="mt-1 line-clamp-2 block text-xs leading-5 text-slate-500">{scenario.description}</span>
        </button>
        <span className="flex flex-wrap items-center gap-2">
          <DraftPill label={scenario.business_priority ?? scenario.priority} />
          <ScenarioCaseCounters counts={polarityCounts} />
        </span>
        <span className="text-xl leading-none text-slate-400 transition group-open:rotate-90">&gt;</span>
      </summary>
      <div className="divide-y divide-[#E4EEF8] border-t border-[#E4EEF8] bg-white">
        {scenario.cases.map((testCase) => (
          <CaseTreeRow
            active={activeDraftId === testCase.draft_id}
            key={testCase.draft_id}
            selected={selectedCaseIds.has(testCase.draft_id)}
            testCase={testCase}
            onActivate={onActivate}
            onToggleCase={onToggleCase}
          />
        ))}
      </div>
    </details>
  );
}

function ScenarioCaseCounters({ counts }: Readonly<{ counts: { positive: number; negative: number; edge: number } }>) {
  return (
    <span className="inline-flex items-center gap-1 text-xs font-semibold">
      <span className="text-emerald-600">{counts.positive}P</span>
      <span className="text-red-500">{counts.negative}N</span>
      <span className="text-slate-500">{counts.edge}E</span>
    </span>
  );
}

function collectScenarioPolarityCounts(scenario: AIGenerationScenarioDraft): { positive: number; negative: number; edge: number } {
  if (scenario.polarity === "negative") {
    return { positive: 0, negative: scenario.cases.length, edge: 0 };
  }
  const edgeCount = scenario.cases.filter((testCase) => testCase.warnings?.length).length;
  return { positive: Math.max(0, scenario.cases.length - edgeCount), negative: 0, edge: edgeCount };
}

function CaseTreeRow({
  active,
  selected,
  testCase,
  onActivate,
  onToggleCase,
}: Readonly<{
  active: boolean;
  selected: boolean;
  testCase: AIGenerationCaseDraft;
  onActivate: (draftId: string) => void;
  onToggleCase: (caseId: string) => void;
}>) {
  return (
    <div
      className={[
        "grid items-start gap-3 bg-white px-4 py-3.5 transition md:grid-cols-[auto_auto_minmax(0,1fr)_auto]",
        active ? "bg-[#EAF4FF]" : "hover:bg-[#F8FBFF]",
      ].join(" ")}
    >
      <input
        type="checkbox"
        checked={selected}
        onChange={() => onToggleCase(testCase.draft_id)}
        className="mt-1 h-5 w-5 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
      />
      <span className="mt-0.5 text-slate-500" aria-hidden>
        !
      </span>
      <button type="button" onClick={() => onActivate(testCase.draft_id)} className="min-w-0 text-left">
        <span className="block truncate text-sm font-semibold text-slate-900">{testCase.title}</span>
        <span className="mt-1 line-clamp-2 block text-xs leading-5 text-slate-500">{testCase.expected_result}</span>
        <span className="mt-2 flex flex-wrap items-center gap-2 text-[11px] font-medium text-slate-500">
          <span className="text-slate-400">^</span>
          <span>Functional</span>
          <PolarityPill polarity={testCase.warnings?.length ? "edge" : "positive"} />
        </span>
      </button>
      <button
        type="button"
        onClick={() => onActivate(testCase.draft_id)}
        className="self-center text-2xl leading-none text-slate-400 hover:text-slate-700"
        aria-label={`Open ${testCase.title}`}
      >
        &gt;
      </button>
    </div>
  );
}

function PolarityPill({ polarity }: Readonly<{ polarity: string }>) {
  const normalized = polarity.toLowerCase();
  const className = normalized.includes("negative")
    ? "border-red-200 bg-red-50 text-red-700"
    : normalized.includes("edge") || normalized.includes("explor")
      ? "border-amber-200 bg-amber-50 text-amber-700"
      : "border-emerald-200 bg-emerald-50 text-emerald-700";
  return (
    <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-semibold capitalize ${className}`}>
      {polarity.replaceAll("_", " ")}
    </span>
  );
}

function DraftDetailDrawer({
  node,
  readOnly,
  canGoNext,
  canGoPrevious,
  positionLabel,
  onClose,
  onFieldChange,
  onNext,
  onPrevious,
  onAddStep,
  onDeleteStep,
  onStepChange,
  onTestDataChange,
}: Readonly<{
  node: ActiveDraftNode | null;
  readOnly: boolean;
  canGoNext: boolean;
  canGoPrevious: boolean;
  positionLabel: string;
  onClose: () => void;
  onFieldChange: (field: DraftEditableField, value: string) => void;
  onNext: () => void;
  onPrevious: () => void;
  onAddStep: (afterStepIndex: number) => void;
  onDeleteStep: (stepIndex: number) => void;
  onStepChange: (stepIndex: number, field: DraftStepEditableField, value: string) => void;
  onTestDataChange: (value: Record<string, unknown>) => void;
}>) {
  if (!node) return null;

  return (
    <div className="fixed inset-0 z-50 bg-slate-950/45">
      <aside className="ml-auto flex h-full w-full max-w-[calc(100vw-520px)] min-w-[720px] flex-col bg-white shadow-2xl">
        <header className="shrink-0 border-b border-slate-200 px-6 py-5">
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              <h2 className="truncate text-2xl font-semibold text-slate-950">{node.title}</h2>
              <div className="mt-4 flex flex-wrap items-center gap-3 text-sm text-slate-600">
                <button type="button" className="font-semibold text-slate-800">High</button>
                <span className="text-slate-300">|</span>
                <span>Functional</span>
                <span className="rounded-full border border-slate-300 bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-700">
                  AI Generated
                </span>
              </div>
            </div>
            <div className="flex shrink-0 items-center gap-5">
              <button type="button" onClick={onClose} className="text-sm font-semibold text-slate-900">Save</button>
              <button
                type="button"
                onClick={onClose}
                className="text-2xl leading-none text-slate-400 hover:text-slate-700"
                aria-label="Close details"
              >
              x
              </button>
            </div>
          </div>
          <div className="mt-6 flex gap-6 border-b border-slate-200 text-sm font-semibold text-slate-600">
            <button type="button" className="-mb-px border-b-2 border-slate-900 px-1 pb-3 text-slate-950">
              Test details
            </button>
          </div>
        </header>

        <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">
          {node.type !== "case" && (
            <EditableDetailBlock
              label="Description"
              readOnly={readOnly}
              value={node.description}
              onChange={(value) => onFieldChange("description", value)}
            />
          )}
          {node.preconditions !== undefined && (
            <EditableDetailBlock
              label="Pre-conditions"
              readOnly={readOnly}
              value={node.preconditions}
              onChange={(value) => onFieldChange("preconditions", value)}
            />
          )}
          {node.expectedResult !== undefined && (
            <EditableDetailBlock
              label="Expected result"
              readOnly={readOnly}
              value={node.expectedResult}
              onChange={(value) => onFieldChange("expectedResult", value)}
            />
          )}

          {node.steps?.length ? (
            <div className="mt-7 border-t border-slate-200 pt-5">
              <h3 className="text-sm font-semibold text-slate-800">Test Steps</h3>
              <div className="mt-4 space-y-4">
                {node.steps.map((step) => (
                  <div key={step.step_index} className="grid gap-4 md:grid-cols-[40px_minmax(0,1fr)_minmax(0,1fr)_52px]">
                    <div className="flex flex-col items-center gap-2 text-xs text-slate-500">
                      <span>{step.step_index}</span>
                      <span className="h-4 w-4 rounded-full border-4 border-slate-700 bg-white" />
                      <span className="h-full w-px bg-slate-200" />
                    </div>
                    <EditableStepCard
                      label="Step"
                      value={step.action}
                      readOnly={readOnly}
                      onChange={(value) => onStepChange(step.step_index, "action", value)}
                    />
                    <EditableStepCard
                      label="Outcome"
                      value={step.expected_outcome}
                      readOnly={readOnly}
                      onChange={(value) => onStepChange(step.step_index, "expected_outcome", value)}
                    />
                    <div className="flex flex-col overflow-hidden rounded-md border border-slate-200">
                      <button
                        type="button"
                        disabled={readOnly}
                        onClick={() => onAddStep(step.step_index)}
                        className="flex h-1/2 items-center justify-center text-2xl text-slate-500 hover:bg-slate-50 disabled:opacity-40"
                        aria-label={`Add a step after step ${step.step_index}`}
                      >
                        +
                      </button>
                      <button
                        type="button"
                        disabled={readOnly}
                        onClick={() => onDeleteStep(step.step_index)}
                        className="flex h-1/2 items-center justify-center border-t border-slate-200 text-xl text-slate-400 hover:bg-slate-50 disabled:opacity-40"
                        aria-label={`Delete step ${step.step_index}`}
                      >
                        x
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          {node.type === "case" && (
            <div className="mt-7 border-t border-slate-200 pt-5">
              <h3 className="text-sm font-semibold text-slate-800">Test data</h3>
              <EditableJsonBlock
                readOnly={readOnly}
                value={node.testData ?? {}}
                onChange={onTestDataChange}
              />
            </div>
          )}
        </div>

        <footer className="flex shrink-0 items-center justify-between border-t border-slate-200 bg-white px-6 py-4">
          <span className="text-sm text-slate-600">{positionLabel}</span>
          <div className="flex gap-2">
            <button
              type="button"
              disabled={!canGoPrevious}
              onClick={onPrevious}
              className="rounded-md border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-600 disabled:text-slate-300"
            >
              Previous
            </button>
            <button
              type="button"
              disabled={!canGoNext}
              onClick={onNext}
              className="rounded-md bg-slate-950 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-800 disabled:bg-slate-200 disabled:text-slate-400"
            >
              Next
            </button>
          </div>
        </footer>
      </aside>
    </div>
  );
}

function EditableDetailBlock({
  label,
  readOnly,
  value,
  onChange,
}: Readonly<{ label: string; readOnly: boolean; value: string; onChange: (value: string) => void }>) {
  return (
    <section className="mb-7">
      <h3 className="text-sm font-semibold text-slate-800">{label}</h3>
      <textarea
        value={value}
        disabled={readOnly}
        rows={Math.max(3, Math.min(8, value.split("\n").length + 1))}
        onChange={(event) => onChange(event.target.value)}
        className="mt-3 w-full resize-y rounded-md border border-slate-200 bg-white px-3 py-2 text-sm leading-6 text-slate-800 outline-none focus:border-slate-500 focus:ring-2 focus:ring-slate-100 disabled:bg-slate-50"
      />
    </section>
  );
}

function EditableJsonBlock({
  readOnly,
  value,
  onChange,
}: Readonly<{ readOnly: boolean; value: Record<string, unknown>; onChange: (value: Record<string, unknown>) => void }>) {
  const [text, setText] = useState(() => JSON.stringify(value, null, 2));
  const [error, setError] = useState("");

  useEffect(() => {
    setText(JSON.stringify(value, null, 2));
    setError("");
  }, [value]);

  function commitJson() {
    try {
      const parsed = JSON.parse(text || "{}");
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
        setError("Test data must be a JSON object.");
        return;
      }
      setError("");
      onChange(parsed as Record<string, unknown>);
    } catch {
      setError("Invalid JSON. Fix it before saving this draft.");
    }
  }

  return (
    <div className="mt-3">
      <textarea
        value={text}
        disabled={readOnly}
        rows={8}
        onBlur={commitJson}
        onChange={(event) => setText(event.target.value)}
        className="w-full resize-y rounded-md border border-slate-200 bg-slate-950 p-3 font-mono text-xs leading-5 text-slate-100 outline-none focus:border-slate-500 focus:ring-2 focus:ring-slate-200 disabled:opacity-70"
      />
      {error && <p className="mt-2 text-xs font-medium text-red-600">{error}</p>}
    </div>
  );
}

function EditableStepCard({
  label,
  readOnly,
  value,
  onChange,
}: Readonly<{ label: string; readOnly: boolean; value: string; onChange: (value: string) => void }>) {
  return (
    <label className="block rounded-md border border-slate-300 bg-white px-4 py-3">
      <span className="text-sm font-semibold text-slate-500">{label}</span>
      <textarea
        value={value}
        disabled={readOnly}
        rows={3}
        onChange={(event) => onChange(event.target.value)}
        className="mt-2 w-full resize-y border-0 p-0 text-sm leading-6 text-slate-800 outline-none disabled:bg-white"
      />
    </label>
  );
}

function DraftPill({ label }: Readonly<{ label: string }>) {
  return (
    <span className="inline-flex items-center rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs font-semibold capitalize text-slate-600">
      {label.replaceAll("_", " ")}
    </span>
  );
}

function ProjectTargetPanel({
  availableProjects,
  canCreateProject,
  selectedProjectId,
  targetMode,
  onProjectChange,
  onTargetModeChange,
}: Readonly<{
  availableProjects: Project[];
  canCreateProject: boolean;
  selectedProjectId: string;
  targetMode: ProjectTargetMode;
  onProjectChange: (projectId: string) => void;
  onTargetModeChange: (mode: ProjectTargetMode) => void;
}>) {
  return (
    <div className="mb-4 rounded-xl border border-[#D9E8F7] bg-[#F8FBFF] p-3">
      <div className="grid gap-2 md:grid-cols-3">
        <TargetOption
          active={targetMode === "auto"}
          label="Auto"
          text="Use project context, one existing project, or create a new one when allowed."
          onClick={() => onTargetModeChange("auto")}
        />
        <TargetOption
          active={targetMode === "existing"}
          label="Existing"
          text="Generate into a project you choose."
          onClick={() => onTargetModeChange("existing")}
        />
        <TargetOption
          active={targetMode === "new"}
          disabled={!canCreateProject}
          label="New project"
          text={canCreateProject ? "Create a new project from this prompt." : "Only managers can create projects."}
          onClick={() => onTargetModeChange("new")}
        />
      </div>
      {targetMode === "existing" && (
        <div className="mt-3 rounded-lg border border-[#D9E8F7] bg-white p-3 shadow-sm">
          <div className="mb-2 flex items-center justify-between gap-3">
            <span className="text-xs font-semibold uppercase tracking-wide text-[#64748B]">Choose a project</span>
            <span className="text-xs text-[#64748B]">{availableProjects.length} available</span>
          </div>
          <div className="max-h-40 space-y-1 overflow-y-auto pr-1">
            {availableProjects.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => onProjectChange(item.id)}
                className={[
                  "flex w-full items-center justify-between gap-3 rounded-md px-3 py-2 text-left text-sm transition focus:outline-none focus:ring-2 focus:ring-[#5AB8FF]",
                  selectedProjectId === item.id
                    ? "bg-[#EAF4FF] font-semibold text-[#17233C]"
                    : "text-[#17233C] hover:bg-slate-50",
                ].join(" ")}
              >
                <span className="truncate">{item.name}</span>
                {selectedProjectId === item.id && <span className="text-xs font-semibold text-[#2563EB]">Selected</span>}
              </button>
            ))}
            {!availableProjects.length && (
              <div className="px-3 py-2 text-sm text-[#64748B]">No active projects available.</div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function TargetOption({
  active,
  disabled = false,
  label,
  text,
  onClick,
}: Readonly<{
  active: boolean;
  disabled?: boolean;
  label: string;
  text: string;
  onClick: () => void;
}>) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className={[
        "rounded-lg border px-3 py-2 text-left transition disabled:cursor-not-allowed disabled:opacity-50",
        active
          ? "border-[#5AB8FF] bg-white text-[#17233C] shadow-sm"
          : "border-[#D9E8F7] bg-white/80 text-[#64748B] hover:border-[#CFE7FF] hover:bg-white",
      ].join(" ")}
    >
      <span className="block text-sm font-semibold">{label}</span>
      <span className="mt-1 block text-xs leading-5">{text}</span>
    </button>
  );
}

function AttachmentMenuPanel({
  jiraIssueKey,
  onClose,
  onJiraIssueKeyChange,
}: Readonly<{
  jiraIssueKey: string;
  onClose: () => void;
  onJiraIssueKeyChange: (value: string) => void;
}>) {
  return (
    <div className="absolute bottom-11 left-0 z-20 w-72 overflow-hidden rounded-lg border border-blue-100 bg-white shadow-2xl">
      <div className="p-4">
        <div className="flex items-center justify-between gap-3">
          <label htmlFor="testpilot-jira" className="inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
            <JiraLogo />
            Jira issue
          </label>
          <button
            type="button"
            onClick={onClose}
            className="rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700 focus:outline-none focus:ring-2 focus:ring-[#5AB8FF]"
            aria-label="Close Jira import"
          >
            x
          </button>
        </div>
        <input
          id="testpilot-jira"
          value={jiraIssueKey}
          onChange={(event) => onJiraIssueKeyChange(event.target.value)}
          placeholder="BIAT-123"
          className="mt-2 w-full rounded-md border border-slate-200 px-3 py-2 text-sm text-slate-900 outline-none focus:border-slate-400"
        />
      </div>
    </div>
  );
}

function DocumentStackIcon() {
  return (
    <span className="inline-flex h-5 w-5 items-center justify-center rounded bg-blue-50 text-blue-700" aria-hidden>
      <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M7 3h7l5 5v13H7z" />
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M14 3v5h5M5 7H3v13h10" />
      </svg>
    </span>
  );
}

function SpreadsheetIcon() {
  return (
    <span className="inline-flex h-5 w-5 items-center justify-center rounded bg-emerald-50 text-emerald-700" aria-hidden>
      <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 3h9l3 3v15H6z" />
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 10h6M9 14h6M12 10v8" />
      </svg>
    </span>
  );
}

function JiraLogo() {
  return (
    <span className="inline-flex h-5 w-5 items-center justify-center text-blue-600" aria-hidden>
      <svg className="h-4 w-4" viewBox="0 0 24 24" fill="currentColor">
        <path d="M12.2 3.4 20.6 12l-8.4 8.6-2.9-2.9 5.5-5.7-5.5-5.7 2.9-2.9Z" opacity=".85" />
        <path d="M5.8 3.4 14.2 12l-8.4 8.6L3 17.7 8.5 12 3 6.3l2.8-2.9Z" opacity=".55" />
      </svg>
    </span>
  );
}

function ContextChip({ label }: Readonly<{ label: string }>) {
  return (
    <span className="inline-flex items-center rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-medium text-slate-700">
      {label}
    </span>
  );
}

function AttachmentChip({
  kind,
  label,
  onRemove,
}: Readonly<{ kind?: "jira"; label: string; onRemove: () => void }>) {
  const lowerLabel = label.toLowerCase();
  const icon = kind === "jira" ? <JiraLogo /> : lowerLabel.endsWith(".xlsx") || lowerLabel.endsWith(".csv") ? <SpreadsheetIcon /> : <DocumentStackIcon />;
  return (
    <span className="inline-flex max-w-full items-center gap-2 rounded-md border border-slate-200 bg-white/90 px-2.5 py-1.5 text-xs font-medium text-slate-700 shadow-sm">
      {icon}
      <span className="max-w-[260px] truncate">{label}</span>
      <button type="button" onClick={onRemove} aria-label={`Remove ${label}`} className="text-slate-400 hover:text-slate-700">
        x
      </button>
    </span>
  );
}

function ErrorBanner({ message }: Readonly<{ message: string }>) {
  return (
    <div className="mt-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
      {message}
    </div>
  );
}

function Metric({ label, value }: Readonly<{ label: string; value: string }>) {
  return (
    <div className="rounded-md bg-slate-50 px-3 py-2">
      <div className="text-xs text-slate-500">{label}</div>
      <div className="mt-1 text-lg font-semibold text-slate-950">{value}</div>
    </div>
  );
}

async function resolveProjectForGeneration({
  availableProjects,
  contextProjectId,
  objective,
  selectedProjectId,
  targetMode,
  user,
}: Readonly<{
  availableProjects: Project[];
  contextProjectId: string | null;
  objective: string;
  selectedProjectId: string;
  targetMode: ProjectTargetMode;
  user: User | null;
}>): Promise<ResolvedProject> {
  if (contextProjectId) return { projectId: contextProjectId, project: null };
  if (targetMode === "existing") {
    if (!selectedProjectId) throw new Error("Choose the project where TestPilot should generate tests.");
    return {
      projectId: selectedProjectId,
      project: availableProjects.find((item) => item.id === selectedProjectId) ?? null,
    };
  }
  if (targetMode === "auto" && availableProjects.length === 1) {
    return { projectId: availableProjects[0].id, project: availableProjects[0] };
  }
  if (targetMode === "auto" && availableProjects.length > 1 && !userCanCreateProject(user)) {
    throw new Error("Choose an existing project. Your account cannot create a new one automatically.");
  }
  return createProjectFromObjective({ objective, user });
}

async function createProjectFromObjective({
  objective,
  user,
}: Readonly<{ objective: string; user: User | null }>): Promise<ResolvedProject> {
  const teamId = resolveCreatableTeamId(user);
  if (!teamId) {
    throw new Error("Only a team manager or organization admin with an active team can create a new project.");
  }
  const project = await createProject({
    team: teamId,
    name: titleForGeneratedProject(objective),
    description: buildInitialProjectDescription(objective),
  });
  return { projectId: project.id, project };
}

function parseLaunchContext(params: URLSearchParams): LaunchContext {
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

function buildSourceRefs(context: LaunchContext): Record<string, unknown> | undefined {
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

function removeEmptyValues(value: Record<string, unknown>): Record<string, unknown> {
  return Object.fromEntries(
    Object.entries(value).filter(([, item]) => {
      if (item === null || item === undefined) return false;
      if (typeof item === "string") return item.trim().length > 0;
      return true;
    })
  );
}

function userCanCreateProject(user: User | null) {
  const role = user?.profile?.organization_role;
  if (role === "platform_owner" || role === "org_admin") return true;
  return user?.profile?.team_memberships?.some(
    (membership) => membership.is_active && membership.role === "manager"
  ) ?? false;
}

function resolveCreatableTeamId(user: User | null) {
  if (!userCanCreateProject(user)) return null;
  const activeMemberships = user?.profile?.team_memberships?.filter((membership) => membership.is_active) ?? [];
  const managedPrimary = activeMemberships.find((membership) => membership.is_primary && membership.role === "manager");
  const managed = activeMemberships.find((membership) => membership.role === "manager");
  const primary = activeMemberships.find((membership) => membership.is_primary);
  return managedPrimary?.team ?? managed?.team ?? user?.profile?.team ?? primary?.team ?? activeMemberships[0]?.team ?? null;
}

function titleForGeneratedProject(objective: string) {
  const cleaned = objective.split(/\s+/).join(" ").slice(0, 46).trim();
  return cleaned ? `TestPilot - ${cleaned}` : "TestPilot Workspace";
}

function buildInitialProjectDescription(objective: string) {
  return [
    "Created by TestPilot from an AI test generation prompt.",
    "",
    "Initial objective:",
    objective,
  ].join("\n");
}

function targetLabel(targetMode: ProjectTargetMode, projects: Project[]) {
  if (targetMode === "new") return "Project: New";
  if (targetMode === "existing") return "Project: Choose existing";
  if (projects.length === 1) return `Project: ${projects[0].name}`;
  if (projects.length > 1) return "Project: Auto";
  return "Project: New if allowed";
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

function emptyDraftStats(): DraftStats {
  return { sectionCount: 0, scenarioCount: 0, caseCount: 0 };
}

function collectDraftStats(draft: AIGenerationDraftPayload): DraftStats {
  return draft.sections.reduce(
    (total, section) => mergeDraftStats(total, collectSectionStats(section)),
    emptyDraftStats()
  );
}

function collectSectionStats(section: AIGenerationSectionDraft): DraftStats {
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

function mergeDraftStats(left: DraftStats, right: DraftStats): DraftStats {
  return {
    sectionCount: left.sectionCount + right.sectionCount,
    scenarioCount: left.scenarioCount + right.scenarioCount,
    caseCount: left.caseCount + right.caseCount,
  };
}

function emptyCoverageStats(): CoverageStats {
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

function collectCoverageStats(draft: AIGenerationDraftPayload, selectedCaseIds: Set<string>): CoverageStats {
  return draft.sections.reduce(
    (total, section) => mergeCoverageStats(total, collectSectionCoverageStats(section)),
    { ...emptyCoverageStats(), selectedCases: selectedCaseIds.size }
  );
}

function collectSectionCoverageStats(section: AIGenerationSectionDraft): CoverageStats {
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

function mergeCoverageStats(left: CoverageStats, right: CoverageStats): CoverageStats {
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

function filterDraftForReview(
  draft: AIGenerationDraftPayload,
  query: string,
  caseFilter: CaseSelectionFilter,
  selectedCaseIds: Set<string>
): AIGenerationDraftPayload {
  const normalizedQuery = normalizeSearchText(query);
  return {
    ...draft,
    sections: draft.sections
      .map((section) => filterSectionForReview(section, normalizedQuery, caseFilter, selectedCaseIds))
      .filter((section): section is AIGenerationSectionDraft => Boolean(section)),
  };
}

function filterSectionForReview(
  section: AIGenerationSectionDraft,
  query: string,
  caseFilter: CaseSelectionFilter,
  selectedCaseIds: Set<string>
): AIGenerationSectionDraft | null {
  const sectionMatches = Boolean(query) && normalizeSearchText(section.name).includes(query);
  const scenarios = section.scenarios
    .map((scenario) => filterScenarioForReview(scenario, query, caseFilter, selectedCaseIds, sectionMatches))
    .filter((scenario): scenario is AIGenerationScenarioDraft => Boolean(scenario));
  const children = section.children
    .map((child) => filterSectionForReview(child, query, caseFilter, selectedCaseIds))
    .filter((child): child is AIGenerationSectionDraft => Boolean(child));

  if (!scenarios.length && !children.length) return null;
  return { ...section, scenarios, children };
}

function filterScenarioForReview(
  scenario: AIGenerationScenarioDraft,
  query: string,
  caseFilter: CaseSelectionFilter,
  selectedCaseIds: Set<string>,
  ancestorMatches: boolean
): AIGenerationScenarioDraft | null {
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

function caseSelectionMatches(
  caseId: string,
  caseFilter: CaseSelectionFilter,
  selectedCaseIds: Set<string>
): boolean {
  if (caseFilter === "selected") return selectedCaseIds.has(caseId);
  if (caseFilter === "unselected") return !selectedCaseIds.has(caseId);
  return true;
}

function caseMatchesQuery(testCase: AIGenerationCaseDraft, query: string): boolean {
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

function normalizeSearchText(value: string): string {
  return value.trim().toLowerCase();
}

function resolveActiveDraftNode(
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

function resolveSectionNode(
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

function updateDraftNodeField(
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

function updateSectionNodeField(
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

function updateDraftCaseStep(
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

function updateSectionCaseStep(
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

function insertDraftCaseStep(
  draft: AIGenerationDraftPayload,
  caseDraftId: string,
  afterStepIndex: number
): AIGenerationDraftPayload {
  const next = cloneDraft(draft);
  next.sections = next.sections.map((section) => insertSectionCaseStep(section, caseDraftId, afterStepIndex));
  return next;
}

function insertSectionCaseStep(
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

function deleteDraftCaseStep(
  draft: AIGenerationDraftPayload,
  caseDraftId: string,
  stepIndex: number
): AIGenerationDraftPayload {
  const next = cloneDraft(draft);
  next.sections = next.sections.map((section) => deleteSectionCaseStep(section, caseDraftId, stepIndex));
  return next;
}

function deleteSectionCaseStep(
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

function reindexSteps(steps: AIGenerationCaseDraft["steps"]): AIGenerationCaseDraft["steps"] {
  return steps.map((step, index) => ({ ...step, step_index: index + 1 }));
}

function updateDraftCaseTestData(
  draft: AIGenerationDraftPayload,
  caseDraftId: string,
  testData: Record<string, unknown>
): AIGenerationDraftPayload {
  const next = cloneDraft(draft);
  next.sections = next.sections.map((section) => updateSectionCaseTestData(section, caseDraftId, testData));
  return next;
}

function updateSectionCaseTestData(
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

function cloneDraft(draft: AIGenerationDraftPayload): AIGenerationDraftPayload {
  return structuredClone(draft);
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

function generationEvents(session: AIGenerationSession | null): GenerationEvent[] {
  const events = session?.critic_report?.events;
  if (!Array.isArray(events)) return [];
  return events.filter((event): event is GenerationEvent => {
    return Boolean(event && typeof event === "object" && "type" in event);
  });
}

function hasTemporaryAttachmentContext(session: AIGenerationSession): boolean {
  const attachments = session.source_refs.temporary_attachments;
  return Array.isArray(attachments) && attachments.length > 0;
}

function eventLabel(type: string) {
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

function friendlyEventLabel(type: string): string {
  return EVENT_LABELS[type] ?? eventLabel(type);
}

function phaseHeadline(session: AIGenerationSession, events: GenerationEvent[]): string {
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

function formatEventTime(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "";
  return parsed.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function composerModeForStatus(status: string): ComposerMode {
  if (status === "clarification_required") return "clarify";
  if (status === "ready_for_review" || status === "reviewing") return "refine";
  if (status === "queued" || status === "generating") return "disabled";
  return "hidden";
}

function extractOpenQuestions(session: AIGenerationSession): string[] {
  const payload = session.draft_payload as { open_questions?: unknown } | null;
  const questions = payload?.open_questions;
  if (!Array.isArray(questions)) return [];
  return questions.map((question) => String(question)).filter(Boolean);
}

function collectDraftReferences(draft: AIGenerationDraftPayload): DraftReference[] {
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

function truncate(value: string, max: number): string {
  return value.length > max ? `${value.slice(0, max - 1)}...` : value;
}

function errorMessage(error: unknown): string {
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

