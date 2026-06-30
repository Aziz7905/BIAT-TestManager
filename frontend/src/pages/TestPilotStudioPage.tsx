import {
  useEffect,
  useMemo,
  useRef,
  useState,
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
import TestPilotLaunchView from "../components/test-pilot/launch/TestPilotLaunchView";
import type {
  AttachmentMenu,
  ProjectTargetMode,
  SavingState,
} from "../components/test-pilot/testPilot.types";
import {
  buildInitialProjectDescription,
  buildSourceRefs,
  collectCaseIds,
  errorMessage,
  generationEvents,
  normalizeDraftForUI,
  parseLaunchContext,
  POLL_INTERVAL_MS,
  resolveCreatableTeamId,
  TERMINAL_STATUSES,
  titleForGeneratedProject,
  userCanCreateProject,
} from "../components/test-pilot/testPilot.utils";
import GenerationWorkspace from "../components/test-pilot/workspace/GenerationWorkspace";
import { Spinner } from "../components/ui";
import { useAuthStore } from "../store/authStore";
import type {
  AIGenerationDraftPayload,
  AIGenerationSession,
} from "../types/ai";
import type { User } from "../types/auth";
import type { Project } from "../types/project";

interface ResolvedProject {
  projectId: string;
  project: Project | null;
}

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
  const canLaunch = Boolean(objective.trim());

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
            <TestPilotLaunchView
              attachmentMenu={attachmentMenu}
              attachmentMenuRef={attachmentMenuRef}
              availableProjects={availableProjects}
              canCreateProject={canCreateProject}
              canLaunch={canLaunch}
              error={error}
              fileInputRef={fileInputRef}
              initialContext={initialContext}
              jiraIssueKey={jiraIssueKey}
              launching={launching}
              objective={objective}
              project={project}
              selectedFile={selectedFile}
              selectedProjectId={selectedProjectId}
              targetMode={targetMode}
              targetPanelOpen={targetPanelOpen}
              onAttachmentMenuChange={setAttachmentMenu}
              onGenerate={() => void handleLaunch()}
              onJiraIssueKeyChange={setJiraIssueKey}
              onObjectiveChange={setObjective}
              onProjectChange={setSelectedProjectId}
              onSelectedFileChange={setSelectedFile}
              onTargetModeChange={setTargetMode}
              onTargetPanelOpenChange={setTargetPanelOpen}
            />
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

