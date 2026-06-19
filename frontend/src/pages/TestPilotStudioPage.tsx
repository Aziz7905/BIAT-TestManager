import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
  type ReactNode,
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

interface DraftReference {
  draft_id: string;
  label: string;
  type: "scenario" | "case";
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
      <div className="flex h-full overflow-hidden bg-white">
        <aside className="hidden w-[68px] shrink-0 border-r border-slate-200 bg-white lg:flex lg:flex-col lg:items-center lg:py-5">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-slate-950 text-sm font-black text-white">
            TP
          </div>
          <div className="mt-8 flex flex-1 flex-col items-center gap-3">
            <RailButton active label="Plan" />
            <RailButton label="Runs" />
            <RailButton label="Data" />
          </div>
        </aside>

        <main className="min-w-0 flex-1 overflow-hidden">
          {!session ? (
            <section className="flex h-full flex-col items-center justify-center overflow-y-auto px-5 py-10">
              <AgentMark />
              <h1 className="text-center text-4xl font-semibold tracking-tight text-slate-950">
                What is your objective today?
              </h1>

              <div className="mt-12 w-full max-w-5xl rounded-lg border border-slate-200 bg-white p-5 shadow-[0_28px_90px_rgba(15,23,42,0.12)]">
                <div className="mb-4 flex flex-wrap items-center gap-2">
                  <ContextChip label={project ? `Project: ${project.name}` : targetLabel(targetMode, availableProjects)} />
                  {initialContext.labels.suite && <ContextChip label={`Suite: ${initialContext.labels.suite}`} />}
                  {initialContext.labels.section && <ContextChip label={`Section: ${initialContext.labels.section}`} />}
                  {initialContext.labels.scenario && <ContextChip label={`Scenario: ${initialContext.labels.scenario}`} />}
                  {initialContext.labels.case && <ContextChip label={`Case: ${initialContext.labels.case}`} />}
                  {!initialContext.projectId && (
                    <button
                      type="button"
                      onClick={() => setTargetPanelOpen((current) => !current)}
                      className="rounded-full border border-slate-200 px-3 py-1 text-xs font-medium text-slate-600 transition hover:border-slate-300 hover:text-slate-950"
                    >
                      Change target
                    </button>
                  )}
                </div>

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

                <textarea
                  value={objective}
                  onChange={(event) => setObjective(event.target.value)}
                  rows={6}
                  placeholder="Describe the feature, workflow, or requirements you want to turn into test scenarios."
                  className="min-h-[150px] w-full resize-none border-0 bg-transparent px-1 text-lg text-slate-900 outline-none placeholder:text-slate-400"
                />

                {(selectedFile || jiraIssueKey) && (
                  <div className="mt-2 flex flex-wrap gap-2">
                    {selectedFile && (
                      <AttachmentChip label={selectedFile.name} onRemove={() => setSelectedFile(null)} />
                    )}
                    {jiraIssueKey && (
                      <AttachmentChip label={`Jira ${jiraIssueKey}`} onRemove={() => setJiraIssueKey("")} />
                    )}
                  </div>
                )}

                {error && <ErrorBanner message={error} />}

                <div className="mt-6 flex flex-wrap items-center justify-between gap-4">
                  <div className="flex items-center gap-2 rounded-lg border border-slate-200 bg-white p-1 shadow-sm">
                    <span className="rounded-md bg-sky-100 px-4 py-2 text-sm font-semibold text-sky-700">
                      Generate scenarios
                    </span>
                  </div>

                  <div className="relative flex items-center gap-2">
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
                    <IconButton
                      label="Attach requirement context"
                      onClick={() => setAttachmentMenu((current) => (current === "open" ? "closed" : "open"))}
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 12.79V8a5 5 0 00-10 0v8a3 3 0 006 0V8" />
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M7 12v4a7 7 0 0014 0v-3" />
                    </IconButton>
                    <Button isLoading={launching} loadingText="Generating" onClick={() => void handleLaunch()}>
                      Launch
                    </Button>

                    {attachmentMenu === "open" && (
                      <AttachmentMenuPanel
                        jiraIssueKey={jiraIssueKey}
                        onFileClick={() => fileInputRef.current?.click()}
                        onJiraIssueKeyChange={setJiraIssueKey}
                      />
                    )}
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
  const draftStats = useMemo(() => (draft ? collectDraftStats(draft) : emptyDraftStats()), [draft]);
  const activeNode = useMemo(
    () => (draft ? resolveActiveDraftNode(draft, activeDraftId) : null),
    [activeDraftId, draft]
  );
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

  return (
    <section className="flex h-full flex-col overflow-hidden">
      <header className="flex shrink-0 items-center justify-between gap-4 border-b border-slate-200 bg-white px-6 py-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
            <span>{project?.name ?? "TestPilot workspace"}</span>
            <span>/</span>
            <span className="capitalize">{session.status.replaceAll("_", " ")}</span>
          </div>
          <h1 className="mt-1 truncate text-xl font-semibold text-slate-950">{session.objective}</h1>
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

      <div className="grid min-h-0 flex-1 grid-cols-1 overflow-hidden lg:grid-cols-[420px_minmax(0,1fr)]">
        <aside className="flex min-h-0 flex-col border-r border-slate-200 bg-slate-50">
          <div className="min-h-0 flex-1 overflow-y-auto px-5 py-5">
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

        <main className="min-h-0 overflow-y-auto bg-white px-6 py-5">
          {isClarifying ? (
            <ClarificationPanel objective={session.objective} openQuestions={openQuestions} />
          ) : draft && draft.sections.length > 0 ? (
            <div className="mx-auto max-w-6xl">
              <div className="mb-5 flex flex-wrap items-start justify-between gap-4">
                <div>
                  <h2 className="text-lg font-semibold text-slate-950">{draft.suite.name}</h2>
                  {draft.summary && <p className="mt-1 text-sm leading-6 text-slate-500">{draft.summary}</p>}
                </div>
                <div className="flex gap-2 text-sm text-slate-600">
                  <span className="rounded-md border border-slate-200 px-3 py-2">
                    {draftStats.sectionCount} sections
                  </span>
                  <span className="rounded-md border border-slate-200 px-3 py-2">
                    {draftStats.scenarioCount} scenarios
                  </span>
                  <span className="rounded-md border border-slate-200 px-3 py-2">
                    {selectedCaseIds.size}/{totalCaseCount} cases
                  </span>
                </div>
              </div>
              <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_380px]">
                <DraftHierarchyView
                  activeDraftId={activeNode?.id ?? draft.suite.draft_id}
                  draft={draft}
                  selectedCaseIds={selectedCaseIds}
                  onActivate={setActiveDraftId}
                  onToggleCase={onToggleCase}
                />
                <DraftDetailPanel
                  node={activeNode}
                  readOnly={running}
                  onFieldChange={handleNodeFieldChange}
                  onStepChange={handleStepChange}
                />
              </div>
            </div>
          ) : (
            <div className="flex h-full items-center justify-center">
              <div className="text-center">
                <Spinner size="lg" />
                <h2 className="mt-5 text-lg font-semibold text-slate-950">
                  {phaseHeadline(session, events)}
                </h2>
                <p className="mt-2 text-sm text-slate-500">
                  Planning candidate scenarios, selecting the strongest set, then expanding test cases.
                </p>
              </div>
            </div>
          )}
        </main>
      </div>
    </section>
  );
}

function PromptSnapshot({
  session,
  initialContext,
}: Readonly<{ session: AIGenerationSession; initialContext: LaunchContext }>) {
  return (
    <div className="mb-5 rounded-lg border border-slate-200 bg-white p-4">
      <h2 className="text-sm font-semibold text-slate-950">Prompt</h2>
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
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-950">Generation</h2>
        <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium capitalize text-slate-700">
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
        <Metric label="Input tokens" value={String(session.input_tokens || 0)} />
        <Metric label="Output tokens" value={String(session.output_tokens || 0)} />
        <Metric label="Selected" value={String(selectedCount)} />
        <Metric label="Total cases" value={String(totalCount)} />
      </div>
    </div>
  );
}

function SelectedPlan({ scenarios }: Readonly<{ scenarios: Array<Record<string, unknown>> }>) {
  return (
    <div className="mt-5 rounded-lg border border-slate-200 bg-white p-4">
      <h2 className="text-sm font-semibold text-slate-950">Selected plan</h2>
      <div className="mt-3 space-y-2">
        {scenarios.map((scenario) => (
          <div
            key={String(scenario.draft_scenario_id ?? scenario.candidate_id)}
            className="rounded-md bg-slate-50 px-3 py-2"
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
    <div className="mt-5 rounded-lg border border-slate-200 bg-white p-4">
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
    <div className="mx-auto max-w-3xl">
      <div className="rounded-lg border border-amber-200 bg-amber-50 px-5 py-4">
        <h2 className="text-base font-semibold text-amber-900">A few questions before drafting</h2>
        <p className="mt-1 text-sm leading-6 text-amber-800">
          The requirements were too ambiguous to generate strong tests. Answer in the chat on the
          left and TestPilot will continue from where it stopped.
        </p>
      </div>
      <div className="mt-5 rounded-lg border border-slate-200 bg-white p-5">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Objective</h3>
        <p className="mt-2 text-sm leading-6 text-slate-700">{objective}</p>
      </div>
      <div className="mt-5 rounded-lg border border-slate-200 bg-white p-5">
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
    ? "Refine the draft — e.g. add a negative case for expired tokens. Use @ to target a scenario or case."
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
  selectedCaseIds,
  onActivate,
  onToggleCase,
}: Readonly<{
  activeDraftId: string;
  draft: AIGenerationDraftPayload;
  selectedCaseIds: Set<string>;
  onActivate: (draftId: string) => void;
  onToggleCase: (caseId: string) => void;
}>) {
  return (
    <section className="overflow-hidden rounded-lg border border-slate-200">
      <button
        type="button"
        onClick={() => onActivate(draft.suite.draft_id)}
        className={[
          "flex w-full items-center justify-between gap-3 border-b border-slate-200 px-4 py-3 text-left transition",
          activeDraftId === draft.suite.draft_id ? "bg-sky-50" : "bg-slate-50 hover:bg-slate-100",
        ].join(" ")}
      >
        <span>
          <span className="block text-sm font-semibold text-slate-950">{draft.suite.name}</span>
          <span className="mt-0.5 block text-xs text-slate-500">Project draft / suite overview</span>
        </span>
        <span className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-xs font-semibold text-slate-600">
          {collectDraftStats(draft).caseCount} cases
        </span>
      </button>
      <div className="divide-y divide-slate-100">
        {draft.sections.map((section) => (
          <SectionTreeNode
            activeDraftId={activeDraftId}
            key={section.draft_id}
            section={section}
            selectedCaseIds={selectedCaseIds}
            onActivate={onActivate}
            onToggleCase={onToggleCase}
          />
        ))}
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
}: Readonly<{
  activeDraftId: string;
  section: AIGenerationSectionDraft;
  selectedCaseIds: Set<string>;
  onActivate: (draftId: string) => void;
  onToggleCase: (caseId: string) => void;
}>) {
  const stats = collectSectionStats(section);
  return (
    <details open className="group">
      <summary
        onClick={() => onActivate(section.draft_id)}
        className={[
          "flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3 transition marker:hidden",
          activeDraftId === section.draft_id ? "bg-sky-50" : "bg-white hover:bg-slate-50",
        ].join(" ")}
      >
        <span className="min-w-0">
          <span className="block truncate text-sm font-semibold text-slate-900">{section.name}</span>
          <span className="mt-0.5 block text-xs text-slate-500">
            {stats.scenarioCount} scenarios / {stats.caseCount} cases
          </span>
        </span>
        <span className="text-slate-400 transition group-open:rotate-90">&gt;</span>
      </summary>
      <div className="border-t border-slate-100 bg-white">
        {section.scenarios.map((scenario) => (
          <ScenarioTreeNode
            activeDraftId={activeDraftId}
            key={scenario.draft_id}
            scenario={scenario}
            selectedCaseIds={selectedCaseIds}
            onActivate={onActivate}
            onToggleCase={onToggleCase}
          />
        ))}
        {section.children.map((child) => (
          <div key={child.draft_id} className="border-t border-slate-100 pl-4">
            <SectionTreeNode
              activeDraftId={activeDraftId}
              section={child}
              selectedCaseIds={selectedCaseIds}
              onActivate={onActivate}
              onToggleCase={onToggleCase}
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
}: Readonly<{
  activeDraftId: string;
  scenario: AIGenerationScenarioDraft;
  selectedCaseIds: Set<string>;
  onActivate: (draftId: string) => void;
  onToggleCase: (caseId: string) => void;
}>) {
  const selectedCount = scenario.cases.filter((testCase) => selectedCaseIds.has(testCase.draft_id)).length;
  return (
    <details open className="border-t border-slate-100 first:border-t-0">
      <summary
        onClick={() => onActivate(scenario.draft_id)}
        className={[
          "grid cursor-pointer list-none gap-3 px-4 py-3 transition marker:hidden md:grid-cols-[minmax(0,1fr)_auto]",
          activeDraftId === scenario.draft_id ? "bg-sky-50" : "bg-white hover:bg-slate-50",
        ].join(" ")}
      >
        <span className="min-w-0">
          <span className="block truncate text-sm font-semibold text-slate-950">{scenario.title}</span>
          <span className="mt-1 line-clamp-2 block text-xs leading-5 text-slate-500">{scenario.description}</span>
        </span>
        <span className="flex flex-wrap items-start gap-2">
          <DraftPill label={scenario.business_priority ?? scenario.priority} />
          <DraftPill label={scenario.scenario_type.replaceAll("_", " ")} />
          <span className="rounded-full border border-slate-200 px-2.5 py-1 text-xs font-semibold text-slate-600">
            {selectedCount}/{scenario.cases.length}
          </span>
        </span>
      </summary>
      <div className="space-y-2 border-t border-slate-100 bg-slate-50 px-4 py-3">
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
        "grid gap-3 rounded-md border bg-white p-3 transition md:grid-cols-[auto_minmax(0,1fr)_auto]",
        active ? "border-sky-300 shadow-sm" : "border-slate-200 hover:border-slate-300",
      ].join(" ")}
    >
      <input
        type="checkbox"
        checked={selected}
        onChange={() => onToggleCase(testCase.draft_id)}
        className="mt-1 h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
      />
      <button type="button" onClick={() => onActivate(testCase.draft_id)} className="min-w-0 text-left">
        <span className="block truncate text-sm font-semibold text-slate-900">{testCase.title}</span>
        <span className="mt-1 block truncate text-xs text-slate-500">{testCase.expected_result}</span>
      </button>
      <button
        type="button"
        onClick={() => onActivate(testCase.draft_id)}
        className="rounded-md border border-slate-200 px-2 py-1 text-xs font-semibold text-slate-500 hover:bg-slate-50"
      >
        Details
      </button>
    </div>
  );
}

function DraftDetailPanel({
  node,
  readOnly,
  onFieldChange,
  onStepChange,
}: Readonly<{
  node: ActiveDraftNode | null;
  readOnly: boolean;
  onFieldChange: (field: DraftEditableField, value: string) => void;
  onStepChange: (stepIndex: number, field: DraftStepEditableField, value: string) => void;
}>) {
  if (!node) {
    return (
      <aside className="rounded-lg border border-slate-200 bg-slate-50 p-5">
        <h3 className="text-sm font-semibold text-slate-950">Draft details</h3>
        <p className="mt-3 text-sm leading-6 text-slate-500">Generation details will appear as the draft grows.</p>
      </aside>
    );
  }
  return (
    <aside className="self-start rounded-lg border border-slate-200 bg-white p-5">
      <div className="flex flex-wrap gap-2">
        <DraftPill label={node.type} />
        {node.meta.map((item) => (
          <DraftPill key={item} label={item} />
        ))}
      </div>
      <EditableField
        label={node.type === "section" ? "Name" : "Title"}
        value={node.title}
        readOnly={readOnly}
        onChange={(value) => onFieldChange("title", value)}
      />
      {(node.type !== "section" || node.description) && (
        <EditableField
          label={node.type === "case" ? "Summary" : "Description"}
          multiline
          value={node.description}
          readOnly={readOnly || node.type === "case"}
          onChange={(value) => onFieldChange("description", value)}
        />
      )}
      {node.expectedResult && (
        <EditableField
          label="Expected result"
          multiline
          value={node.expectedResult}
          readOnly={readOnly}
          onChange={(value) => onFieldChange("expectedResult", value)}
        />
      )}
      {node.preconditions && (
        <EditableField
          label="Preconditions"
          multiline
          value={node.preconditions}
          readOnly={readOnly}
          onChange={(value) => onFieldChange("preconditions", value)}
        />
      )}
      {node.steps?.length ? (
        <div className="mt-5">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Steps</h4>
          <div className="mt-3 space-y-3">
            {node.steps.map((step) => (
              <div key={step.step_index} className="rounded-md border border-slate-200 p-3">
                <EditableField
                  label={`Step ${step.step_index}`}
                  value={step.action}
                  readOnly={readOnly}
                  onChange={(value) => onStepChange(step.step_index, "action", value)}
                />
                <EditableField
                  label="Outcome"
                  multiline
                  value={step.expected_outcome}
                  readOnly={readOnly}
                  onChange={(value) => onStepChange(step.step_index, "expected_outcome", value)}
                />
              </div>
            ))}
          </div>
        </div>
      ) : null}
      {node.testData && Object.keys(node.testData).length > 0 && (
        <div className="mt-5">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Test data</h4>
          <pre className="mt-3 max-h-56 overflow-auto rounded-md bg-slate-950 p-3 text-xs text-slate-100">
            {JSON.stringify(node.testData, null, 2)}
          </pre>
        </div>
      )}
    </aside>
  );
}

function EditableField({
  label,
  multiline = false,
  readOnly,
  value,
  onChange,
}: Readonly<{
  label: string;
  multiline?: boolean;
  readOnly: boolean;
  value: string;
  onChange: (value: string) => void;
}>) {
  const baseClass =
    "mt-2 w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm leading-6 text-slate-700 outline-none transition focus:border-sky-400 focus:ring-2 focus:ring-sky-100 disabled:bg-slate-50 disabled:text-slate-500";
  return (
    <div className="mt-5">
      <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</h4>
      {multiline ? (
        <textarea
          value={value}
          disabled={readOnly}
          rows={Math.max(3, Math.min(8, value.split("\n").length + 1))}
          onChange={(event) => onChange(event.target.value)}
          className={`${baseClass} resize-y`}
        />
      ) : (
        <input
          value={value}
          disabled={readOnly}
          onChange={(event) => onChange(event.target.value)}
          className={baseClass}
        />
      )}
    </div>
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
    <div className="mb-4 rounded-lg border border-slate-200 bg-slate-50 p-4">
      <div className="grid gap-3 md:grid-cols-3">
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
        <select
          value={selectedProjectId}
          onChange={(event) => onProjectChange(event.target.value)}
          className="mt-3 w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none focus:border-slate-400"
        >
          <option value="">Choose a project</option>
          {availableProjects.map((item) => (
            <option key={item.id} value={item.id}>
              {item.name}
            </option>
          ))}
        </select>
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
        "rounded-md border px-3 py-2 text-left transition disabled:cursor-not-allowed disabled:opacity-50",
        active ? "border-sky-300 bg-white text-slate-950" : "border-slate-200 bg-white text-slate-600 hover:border-slate-300",
      ].join(" ")}
    >
      <span className="block text-sm font-semibold">{label}</span>
      <span className="mt-1 block text-xs leading-5">{text}</span>
    </button>
  );
}

function AttachmentMenuPanel({
  jiraIssueKey,
  onFileClick,
  onJiraIssueKeyChange,
}: Readonly<{
  jiraIssueKey: string;
  onFileClick: () => void;
  onJiraIssueKeyChange: (value: string) => void;
}>) {
  return (
    <div className="absolute right-0 top-12 z-20 w-80 overflow-hidden rounded-lg border border-slate-200 bg-white shadow-2xl">
      <button
        type="button"
        onClick={onFileClick}
        className="flex w-full items-center justify-between px-4 py-3 text-left text-sm text-slate-700 hover:bg-slate-50"
      >
        <span>Upload from device</span>
        <span className="text-xs text-slate-400">PDF/DOCX/XLSX/CSV</span>
      </button>
      <div className="border-t border-slate-100 p-4">
        <label htmlFor="testpilot-jira" className="text-xs font-semibold uppercase tracking-wide text-slate-500">
          Jira issue
        </label>
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

function AgentMark() {
  return (
    <div className="mb-7 flex h-14 w-14 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-400 shadow-sm">
      <svg className="h-8 w-8" viewBox="0 0 48 48" fill="none" aria-hidden="true">
        <path d="M15 23c0-5 4-9 9-9s9 4 9 9v4c0 5-4 9-9 9s-9-4-9-9v-4z" stroke="currentColor" strokeWidth="3" />
        <path d="M10 25h28M17 27h5M26 27h5" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
      </svg>
    </div>
  );
}

function RailButton({ active = false, label }: Readonly<{ active?: boolean; label: string }>) {
  return (
    <button
      type="button"
      title={label}
      className={[
        "flex h-11 w-11 items-center justify-center rounded-lg text-xs font-bold transition",
        active ? "bg-slate-100 text-slate-950" : "text-slate-400 hover:bg-slate-50 hover:text-slate-700",
      ].join(" ")}
    >
      {label.slice(0, 2)}
    </button>
  );
}

function IconButton({
  label,
  onClick,
  children,
}: Readonly<{
  label: string;
  onClick: () => void;
  children: ReactNode;
}>) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      onClick={onClick}
      className="rounded-md p-2 text-slate-500 transition hover:bg-slate-100 hover:text-slate-900"
    >
      <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor">
        {children}
      </svg>
    </button>
  );
}

function ContextChip({ label }: Readonly<{ label: string }>) {
  return (
    <span className="inline-flex items-center rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-medium text-slate-700">
      {label}
    </span>
  );
}

function AttachmentChip({ label, onRemove }: Readonly<{ label: string; onRemove: () => void }>) {
  return (
    <span className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-medium text-slate-700">
      {label}
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
  return value.length > max ? `${value.slice(0, max - 1)}…` : value;
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
