import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { getProject, getProjectTree } from "../api/projects/projects";
import { getCasesForScenario } from "../api/testing";
import type { Project } from "../types/project";
import type {
  ProjectTree as ProjectTreeData,
  TreeCase,
  TreeScenario,
  TreeSection,
  TreeSuite,
} from "../types/testing";
import type { TreeMutationRequest, TreeSelection } from "../types/tree";
import { selectionExistsInTree } from "../types/tree";
import AppLayout from "../components/layout/AppLayout";
import ProjectTree from "../components/project/ProjectTree";
import RepositoryDetailPane from "../components/project/RepositoryDetailPane";
import ProjectMembersModal from "../components/project/ProjectMembersModal";
import CaseEditorModal from "../components/project/case-editor/CaseEditorModal";
import ProjectAutomationWorkspace from "../components/project/automation/ProjectAutomationWorkspace";
import ProjectSpecificationsWorkspace from "../components/project/specs/ProjectSpecificationsWorkspace";
import ProjectTestRunsWorkspace from "../components/project/test-runs/ProjectTestRunsWorkspace";
import { Spinner } from "../components/ui";

type ProjectWorkspaceTab = "repository" | "specs" | "automation" | "test-runs";
type TestPilotGenerationTarget = { suiteId?: string; sectionId?: string };

interface TestPilotLaunchContext {
  selectionType?: TreeSelection["type"];
  suite?: TreeSuite;
  section?: TreeSection;
  scenario?: TreeScenario;
  caseItem?: TreeCase;
}

export default function ProjectWorkspacePage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const [project, setProject] = useState<Project | null>(null);
  const [tree, setTree] = useState<ProjectTreeData | null>(null);
  const [loading, setLoading] = useState(true);
  const [selection, setSelection] = useState<TreeSelection | null>(null);
  const [showMembers, setShowMembers] = useState(false);
  const [detailRefreshKey, setDetailRefreshKey] = useState(0);
  const [editingCaseId, setEditingCaseId] = useState<string | null>(null);
  const [scenarioCasesById, setScenarioCasesById] = useState<Record<string, TreeCase[]>>({});
  const [loadingScenarioIds, setLoadingScenarioIds] = useState<Record<string, boolean>>({});
  const [focusedExecutionId, setFocusedExecutionId] = useState<string | null>(null);
  const [treeWidth, setTreeWidth] = useState(320);
  const [resizing, setResizing] = useState(false);

  const requestedTab = searchParams.get("tab");
  const activeTab: ProjectWorkspaceTab =
    requestedTab === "specs" ||
    requestedTab === "automation" ||
    requestedTab === "test-runs"
      ? requestedTab
      : "repository";

  const setActiveTab = useCallback(
    (tab: ProjectWorkspaceTab) => {
      const nextParams = new URLSearchParams(searchParams);
      nextParams.set("tab", tab);
      setSearchParams(nextParams, { replace: true });
    },
    [searchParams, setSearchParams]
  );

  const loadScenarioCases = useCallback(async (scenarioId: string) => {
    if (!scenarioId) return;
    setLoadingScenarioIds((s) => ({ ...s, [scenarioId]: true }));
    try {
      const cases = await getCasesForScenario(scenarioId);
      setScenarioCasesById((s) => ({ ...s, [scenarioId]: cases }));
    } finally {
      setLoadingScenarioIds((s) => {
        const next = { ...s };
        delete next[scenarioId];
        return next;
      });
    }
  }, []);

  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    setLoading(true);

    Promise.all([getProject(id), getProjectTree(id)])
      .then(([nextProject, nextTree]) => {
        if (cancelled) return;
        setProject(nextProject);
        setTree(nextTree);
        setSelection(null);
        setScenarioCasesById({});
        setLoadingScenarioIds({});
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [id]);

  useEffect(() => {
    if (!tree || !selection) return;
    let scenarioId: string | undefined;
    if (selection.type === "scenario") scenarioId = selection.id;
    else if (selection.type === "case") scenarioId = selection.parentId;
    if (scenarioId && !scenarioCasesById[scenarioId]) {
      void loadScenarioCases(scenarioId);
    }
  }, [loadScenarioCases, scenarioCasesById, selection, tree]);

  useEffect(() => {
    if (!resizing) return;

    function handleMouseMove(event: MouseEvent) {
      const nextWidth = Math.min(Math.max(event.clientX, 240), 640);
      setTreeWidth(nextWidth);
    }

    function handleMouseUp() {
      setResizing(false);
    }

    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", handleMouseUp);
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";

    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };
  }, [resizing]);

  const refreshTree = useCallback(
    async (request?: TreeMutationRequest) => {
      if (!id) return;
      const nextTree = await getProjectTree(id);

      if (request?.resetCaseCache) {
        setScenarioCasesById({});
      } else if (request?.invalidateScenarioIds?.length) {
        setScenarioCasesById((current) => {
          const next = { ...current };
          for (const sid of request.invalidateScenarioIds!) delete next[sid];
          return next;
        });
      }

      setTree(nextTree);
      setSelection((current) => {
        if (request && "nextSelection" in request) return request.nextSelection ?? null;
        return selectionExistsInTree(nextTree, current) ? current : null;
      });
      setDetailRefreshKey((v) => v + 1);
    },
    [id]
  );

  const refreshProject = useCallback(async () => {
    if (!id) return;
    const nextProject = await getProject(id);
    setProject(nextProject);
  }, [id]);

  const openTestPilot = useCallback(
    (target?: TestPilotGenerationTarget) => {
      if (!id || !tree) return;
      const launchContext = buildTestPilotLaunchContext({
        tree,
        selection,
        scenarioCasesById,
        target,
      });
      const params = new URLSearchParams();
      params.set("project", id);
      params.set("projectName", project?.name ?? tree.project_name);
      if (launchContext.selectionType) params.set("selection", launchContext.selectionType);
      if (launchContext.suite) {
        params.set("suite", launchContext.suite.id);
        params.set("suiteName", launchContext.suite.name);
      }
      if (launchContext.section) {
        params.set("section", launchContext.section.id);
        params.set("sectionName", launchContext.section.name);
      }
      if (launchContext.scenario) {
        params.set("scenario", launchContext.scenario.id);
        params.set("scenarioTitle", launchContext.scenario.title);
      }
      if (launchContext.caseItem) {
        params.set("case", launchContext.caseItem.id);
        params.set("caseTitle", launchContext.caseItem.title);
      }
      navigate(`/testpilot?${params.toString()}`);
    },
    [id, navigate, project?.name, scenarioCasesById, selection, tree]
  );

  if (loading) {
    return (
      <AppLayout>
        <div className="flex h-full items-center justify-center">
          <Spinner size="lg" />
        </div>
      </AppLayout>
    );
  }

  if (!project || !tree) {
    return (
      <AppLayout>
        <div className="flex h-full items-center justify-center text-sm text-slate-500">
          Project not found.
        </div>
      </AppLayout>
    );
  }

  return (
    <AppLayout projectName={project.name}>
      <div className="flex h-full flex-col overflow-hidden bg-slate-50">
        <div className="border-b border-slate-200 bg-white px-4 py-3">
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              <h2 className="truncate text-sm font-semibold text-slate-900">{project.name}</h2>
              <p className="mt-0.5 text-xs text-slate-500">{project.team_name}</p>
            </div>
            <div className="flex shrink-0 items-center gap-2">
              <button
                onClick={() => openTestPilot()}
                className="inline-flex items-center gap-1.5 rounded-md bg-slate-900 px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-slate-800"
                title="Generate with TestPilot"
              >
                <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M12 3l1.7 5.1L19 10l-5.3 1.9L12 17l-1.7-5.1L5 10l5.3-1.9L12 3z"
                  />
                </svg>
                Generate tests
              </button>
              <button
                onClick={() => setShowMembers(true)}
                className="inline-flex items-center gap-1 rounded-md border border-slate-200 px-2.5 py-1.5 text-xs text-slate-600 transition hover:bg-slate-50 hover:text-slate-900"
                title="Manage project members"
              >
                <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M17 20h5v-2a4 4 0 00-3-3.87M9 20H4v-2a4 4 0 013-3.87m6-5.13a4 4 0 11-8 0 4 4 0 018 0zm6 0a4 4 0 11-8 0 4 4 0 018 0z"
                  />
                </svg>
                {project.member_count}
              </button>
            </div>
          </div>

          <div className="mt-3 flex items-center gap-2">
            {([
              { key: "repository", label: "Repository" },
              { key: "specs", label: "Specifications" },
              { key: "automation", label: "Automation" },
              { key: "test-runs", label: "Test Runs" },
            ] as const).map((tab) => (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                className={[
                  "rounded-md px-3 py-1.5 text-sm font-medium transition",
                  activeTab === tab.key
                    ? "bg-slate-900 text-white"
                    : "text-slate-600 hover:bg-slate-100 hover:text-slate-900",
                ].join(" ")}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        {activeTab === "repository" ? (
          <div className="flex flex-1 overflow-hidden">
            <aside
              className="flex shrink-0 flex-col overflow-hidden border-r border-slate-200 bg-white"
              style={{ width: `${treeWidth}px` }}
            >
              <div className="flex-1 overflow-hidden">
                <ProjectTree
                  tree={tree}
                  selection={selection}
                  onSelect={setSelection}
                  projectId={id ?? ""}
                  scenarioCasesById={scenarioCasesById}
                  loadingScenarioIds={loadingScenarioIds}
                  onLoadScenarioCases={loadScenarioCases}
                  onOpenCaseEditor={setEditingCaseId}
                  onGenerateWithAI={(target) => openTestPilot(target)}
                  onMutate={refreshTree}
                />
              </div>
            </aside>

            <div
              role="separator"
              aria-orientation="vertical"
              aria-label="Resize repository panels"
              onMouseDown={() => setResizing(true)}
              className={`relative w-1 shrink-0 cursor-col-resize bg-slate-200 transition hover:bg-blue-400 ${
                resizing ? "bg-blue-500" : ""
              }`}
            >
              <div className="absolute inset-y-0 left-1/2 w-3 -translate-x-1/2" />
            </div>

            <main className="flex-1 overflow-hidden bg-white">
              <RepositoryDetailPane
                projectId={id ?? ""}
                selection={selection}
                refreshKey={detailRefreshKey}
                onSelect={setSelection}
                onClearSelection={() => setSelection(null)}
                onEditCase={setEditingCaseId}
                onViewExecution={(executionId) => {
                  setFocusedExecutionId(executionId);
                  setActiveTab("automation");
                }}
                onScenarioSaved={() => void refreshTree({ resetCaseCache: true })}
              />
            </main>
          </div>
        ) : activeTab === "specs" ? (
          <div className="flex-1 overflow-hidden">
            <ProjectSpecificationsWorkspace
              projectId={id ?? ""}
              onOpenCase={(caseId, scenarioId) => {
                setSelection({ type: "case", id: caseId, parentId: scenarioId });
                setActiveTab("repository");
              }}
            />
          </div>
        ) : activeTab === "automation" ? (
          <div className="flex-1 overflow-hidden">
            <ProjectAutomationWorkspace
              projectId={id ?? ""}
              focusExecutionId={focusedExecutionId}
            />
          </div>
        ) : (
          <div className="flex-1 overflow-hidden">
            <ProjectTestRunsWorkspace projectId={id ?? ""} projectTree={tree} />
          </div>
        )}
      </div>

      <ProjectMembersModal
        open={showMembers}
        project={project}
        onClose={() => setShowMembers(false)}
        onChanged={refreshProject}
      />

      <CaseEditorModal
        open={Boolean(editingCaseId)}
        caseId={editingCaseId}
        onClose={() => setEditingCaseId(null)}
        onSaved={({ caseId, scenarioId }) =>
          refreshTree({
            nextSelection: { type: "case", id: caseId, parentId: scenarioId },
            invalidateScenarioIds: [scenarioId],
          })
        }
      />

    </AppLayout>
  );
}

function buildTestPilotLaunchContext({
  tree,
  selection,
  scenarioCasesById,
  target,
}: {
  tree: ProjectTreeData;
  selection: TreeSelection | null;
  scenarioCasesById: Record<string, TreeCase[]>;
  target?: TestPilotGenerationTarget;
}): TestPilotLaunchContext {
  if (target?.sectionId) {
    const sectionContext = findSectionContext(tree, target.sectionId);
    if (sectionContext) {
      return {
        selectionType: "section",
        suite: sectionContext.suite,
        section: sectionContext.section,
      };
    }
  }

  if (target?.suiteId) {
    const suite = tree.suites.find((item) => item.id === target.suiteId);
    if (suite) return { selectionType: "suite", suite };
  }

  if (!selection) return {};

  if (selection.type === "suite") {
    const suite = tree.suites.find((item) => item.id === selection.id);
    return suite ? { selectionType: "suite", suite } : {};
  }

  if (selection.type === "section") {
    const sectionContext = findSectionContext(tree, selection.id);
    if (!sectionContext) return {};
    return {
      selectionType: "section",
      suite: sectionContext.suite,
      section: sectionContext.section,
    };
  }

  const scenarioId = selection.type === "scenario" ? selection.id : selection.parentId;
  if (!scenarioId) return {};
  const scenarioContext = findScenarioContext(tree, scenarioId);
  if (!scenarioContext) return {};

  const caseItem =
    selection.type === "case"
      ? (scenarioCasesById[scenarioId] ?? []).find((item) => item.id === selection.id)
      : undefined;

  return {
    selectionType: selection.type,
    suite: scenarioContext.suite,
    section: scenarioContext.section,
    scenario: scenarioContext.scenario,
    caseItem,
  };
}

function findSectionContext(
  tree: ProjectTreeData,
  sectionId: string
): { suite: TreeSuite; section: TreeSection } | null {
  for (const suite of tree.suites) {
    const section = findSection(suite.sections, sectionId);
    if (section) return { suite, section };
  }
  return null;
}

function findScenarioContext(
  tree: ProjectTreeData,
  scenarioId: string
): { suite: TreeSuite; section: TreeSection; scenario: TreeScenario } | null {
  for (const suite of tree.suites) {
    const result = findScenarioInSections(suite.sections, scenarioId);
    if (result) return { suite, ...result };
  }
  return null;
}

function findSection(sections: TreeSection[], sectionId: string): TreeSection | null {
  for (const section of sections) {
    if (section.id === sectionId) return section;
    const child = findSection(section.children, sectionId);
    if (child) return child;
  }
  return null;
}

function findScenarioInSections(
  sections: TreeSection[],
  scenarioId: string
): { section: TreeSection; scenario: TreeScenario } | null {
  for (const section of sections) {
    const scenario = section.scenarios.find((item) => item.id === scenarioId);
    if (scenario) return { section, scenario };
    const child = findScenarioInSections(section.children, scenarioId);
    if (child) return child;
  }
  return null;
}
