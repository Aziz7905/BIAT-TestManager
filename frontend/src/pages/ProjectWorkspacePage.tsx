/** Project-first QA workspace with overview, specs, members, and test suite hierarchy. */
import { useEffect, useMemo, useState } from "react";
import type { FormEvent, ReactNode } from "react";
import {
  Link,
  NavLink,
  Navigate,
  useLocation,
  useNavigate,
  useParams,
} from "react-router-dom";
import { getAdminUsers } from "../api/accounts/users";
import {
  activateAutomationScript,
  createAutomationScript,
  createTestExecution,
  deactivateAutomationScript,
  deleteAutomationScript,
  deleteTestExecution,
  getExecutionArtifactText,
  getExecutionSteps,
  getAutomationScripts,
  getTestExecutions,
  pauseTestExecution,
  resolveExecutionArtifactUrl,
  resumeTestExecution,
  stopTestExecution,
  updateAutomationScript,
  validateAutomationScript,
} from "../api/automation";
import {
  addProjectMember,
  getProject,
  getProjectMembers,
  removeProjectMember,
  updateProjectMember,
} from "../api/projects";
import {
  getSpecificationSource,
  getSpecificationSources,
  getSpecifications,
} from "../api/specs";
import {
  cloneTestScenario,
  createTestCase,
  createTestScenario,
  createTestSuite,
  deleteTestCase,
  deleteTestScenario,
  deleteTestSuite,
  getTestCases,
  getTestScenarios,
  getTestSuites,
  updateTestCase,
  updateTestScenario,
  updateTestSuite,
} from "../api/testing";
import { Button } from "../components/Button";
import { ErrorMessage } from "../components/ErrorMessage";
import { FormInput } from "../components/FormInput";
import { FormSelect } from "../components/FormSelect";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { Modal } from "../components/Modal";
import {
  AutomationScriptEditorModal,
  ExecutionDetailPanel,
  RunExecutionModal,
} from "../components/automation";
import { RequirementDetailPanel } from "../components/project/RequirementDetailPanel";
import {
  RequirementsTreePanel,
  type RequirementTreeGroup,
} from "../components/project/RequirementsTreePanel";
import { TestDesignTreePanel } from "../components/project/TestDesignTreePanel";
import { TestCaseEditorModal } from "../components/testing";
import { Badge, EmptyState } from "../components/ui";
import { useAuthStore } from "../store/authStore";
import type { AdminUser } from "../types/accounts";
import type {
  AutomationScript,
  ExecutionBrowser,
  ExecutionPlatform,
  ExecutionStep,
  AutomationScriptWritePayload,
  TestExecution,
} from "../types/automation";
import type {
  Specification,
  SpecificationSource,
  SpecificationSourceDetail,
} from "../types/specs";
import type { Project, ProjectMember, ProjectMemberRole } from "../types/projects";
import type {
  BusinessPriority,
  TestCase,
  TestCaseWritePayload,
  TestPriority,
  TestScenario,
  TestScenarioPolarity,
  TestScenarioType,
  TestSuite,
} from "../types/testing";

type WorkspaceTab = "overview" | "specifications" | "members" | "test-suites";

interface SuiteFormState {
  name: string;
  description: string;
  folderPath: string;
  specification: string;
}

interface ScenarioFormState {
  title: string;
  description: string;
  scenarioType: TestScenarioType;
  priority: TestPriority;
  businessPriority: BusinessPriority | "";
  polarity: TestScenarioPolarity;
  orderIndex: string;
}

interface FolderGroup {
  key: string;
  label: string;
  depth: number;
  suiteCount: number;
}

const PROJECT_MEMBER_ROLE_OPTIONS: Array<{
  value: ProjectMemberRole;
  label: string;
}> = [
  { value: "owner", label: "owner" },
  { value: "editor", label: "editor" },
  { value: "viewer", label: "viewer" },
];

const SCENARIO_TYPE_OPTIONS: Array<{
  value: TestScenarioType;
  label: string;
}> = [
  { value: "happy_path", label: "happy path" },
  { value: "alternative_flow", label: "alternative flow" },
  { value: "edge_case", label: "edge case" },
  { value: "security", label: "security" },
  { value: "performance", label: "performance" },
  { value: "accessibility", label: "accessibility" },
];

const PRIORITY_OPTIONS: Array<{ value: TestPriority; label: string }> = [
  { value: "critical", label: "critical" },
  { value: "high", label: "high" },
  { value: "medium", label: "medium" },
  { value: "low", label: "low" },
];

const BUSINESS_PRIORITY_OPTIONS: Array<{
  value: BusinessPriority | "";
  label: string;
}> = [
  { value: "", label: "none" },
  { value: "must_have", label: "must have" },
  { value: "should_have", label: "should have" },
  { value: "could_have", label: "could have" },
  { value: "wont_have", label: "won't have" },
];

const POLARITY_OPTIONS: Array<{
  value: TestScenarioPolarity;
  label: string;
}> = [
  { value: "positive", label: "positive" },
  { value: "negative", label: "negative" },
];

const initialSuiteFormState: SuiteFormState = {
  name: "",
  description: "",
  folderPath: "",
  specification: "",
};

const initialScenarioFormState: ScenarioFormState = {
  title: "",
  description: "",
  scenarioType: "happy_path",
  priority: "high",
  businessPriority: "",
  polarity: "positive",
  orderIndex: "0",
};

function extractErrorMessage(data: unknown): string | null {
  if (typeof data === "string" && data.trim()) {
    return data;
  }

  if (Array.isArray(data)) {
    for (const item of data) {
      const message = extractErrorMessage(item);
      if (message) {
        return message;
      }
    }
  }

  if (typeof data === "object" && data !== null) {
    for (const value of Object.values(data)) {
      const message = extractErrorMessage(value);
      if (message) {
        return message;
      }
    }
  }

  return null;
}

function getErrorMessage(error: unknown, fallback: string): string {
  if (
    typeof error === "object" &&
    error !== null &&
    "response" in error &&
    typeof (error as { response?: unknown }).response === "object"
  ) {
    const response = (error as {
      response?: { data?: unknown };
    }).response;

    return extractErrorMessage(response?.data) || fallback;
  }

  return fallback;
}

function formatDate(value: string | null | undefined): string {
  if (!value) {
    return "-";
  }

  try {
    return new Intl.DateTimeFormat("en-GB", {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(new Date(value));
  } catch {
    return value;
  }
}

function getWorkspaceTab(pathname: string, projectId: string): WorkspaceTab {
  const normalizedPath = pathname.replace(/\/+$/, "");

  if (normalizedPath.endsWith(`/${projectId}/specifications`)) {
    return "specifications";
  }

  if (normalizedPath.endsWith(`/${projectId}/members`)) {
    return "members";
  }

  if (normalizedPath.endsWith(`/${projectId}/test-suites`)) {
    return "test-suites";
  }

  return "overview";
}

function getFolderPathLabel(folderPath: string): string {
  if (!folderPath.trim()) {
    return "Unfiled";
  }

  const segments = folderPath
    .split("/")
    .map((segment) => segment.trim())
    .filter(Boolean);

  return segments[segments.length - 1] ?? "Unfiled";
}

function buildFolderGroups(suites: TestSuite[]): FolderGroup[] {
  const counts = new Map<string, number>();

  suites.forEach((suite) => {
    const key = suite.folder_path.trim() || "Unfiled";
    counts.set(key, (counts.get(key) ?? 0) + 1);
  });

  return [...counts.entries()]
    .map(([key, suiteCount]) => ({
      key,
      label: getFolderPathLabel(key),
      depth:
        key === "Unfiled"
          ? 0
          : key.split("/").map((segment) => segment.trim()).filter(Boolean).length - 1,
      suiteCount,
    }))
    .sort((left, right) => left.key.localeCompare(right.key));
}

function getSpecificationSourceLabel(
  source: SpecificationSource | SpecificationSourceDetail
): string {
  if (source.name.trim()) {
    return source.name.trim();
  }

  if (source.file_name?.trim()) {
    return source.file_name.trim();
  }

  if (source.jira_issue_key?.trim()) {
    return source.jira_issue_key.trim();
  }

  if (source.source_url?.trim()) {
    return source.source_url.trim();
  }

  return "Imported source";
}

function getSpecificationSourceStatusVariant(
  status: SpecificationSource["parser_status"]
): "unverified" | "verified" | "warm" {
  if (status === "imported" || status === "ready") {
    return "verified";
  }

  if (status === "failed") {
    return "warm";
  }

  return "unverified";
}

function buildSpecificationTreeGroups(
  sources: SpecificationSource[],
  specifications: Specification[]
): RequirementTreeGroup[] {
  const specificationsBySourceId = new Map<string, Specification[]>();
  const standaloneSpecifications: Specification[] = [];

  specifications.forEach((specification) => {
    if (!specification.source_id) {
      standaloneSpecifications.push(specification);
      return;
    }

    const currentSpecifications =
      specificationsBySourceId.get(specification.source_id) ?? [];
    currentSpecifications.push(specification);
    specificationsBySourceId.set(specification.source_id, currentSpecifications);
  });

  const sourceGroups = sources.map((source) => ({
    key: `source:${source.id}`,
    label: getSpecificationSourceLabel(source),
    subtitle: source.source_type.replaceAll("_", " "),
    statusLabel: source.parser_status,
    statusVariant: getSpecificationSourceStatusVariant(source.parser_status),
    source,
    specifications: specificationsBySourceId.get(source.id) ?? [],
  }));

  if (standaloneSpecifications.length === 0) {
    return sourceGroups;
  }

  return [
    ...sourceGroups,
    {
      key: "source:standalone",
      label: "Standalone requirements",
      subtitle: "manual specifications",
      statusLabel: "manual",
      statusVariant: "verified" as const,
      source: null,
      specifications: standaloneSpecifications,
    },
  ];
}

function getPriorityVariant(priority: TestPriority) {
  if (priority === "critical" || priority === "high") {
    return "priority-high";
  }

  if (priority === "medium") {
    return "priority-medium";
  }

  return "priority-low";
}

function getSuiteStatusVariant(passRate: number) {
  if (passRate >= 90) {
    return "verified";
  }

  if (passRate <= 0) {
    return "warm";
  }

  return "unverified";
}

function getCaseStatusVariant(status: TestCase["status"]) {
  if (status === "passed" || status === "ready") {
    return "verified";
  }

  if (status === "failed" || status === "skipped") {
    return "warm";
  }

  return "unverified";
}

function getAutomationBadgeVariant(status: TestCase["automation_status"]) {
  return status === "automated" ? "automated" : "tag";
}

function getExecutionStatusVariant(status: TestExecution["status"]) {
  if (status === "passed") {
    return "verified";
  }

  if (status === "failed" || status === "error" || status === "cancelled") {
    return "warm";
  }

  if (status === "running") {
    return "automated";
  }

  return "unverified";
}

function getScriptSummaryLabel(script: AutomationScript) {
  return `${script.framework} · ${script.language} · v${script.script_version}`;
}

function parseCaseStepsPreview(testCase: TestCase): string {
  if (!testCase.steps.length) {
    return "No structured steps yet.";
  }

  const firstStep = testCase.steps[0];
  if (typeof firstStep.step === "string" && firstStep.step.trim()) {
    return firstStep.step;
  }
  if (typeof firstStep.action === "string" && firstStep.action.trim()) {
    return firstStep.action;
  }
  return "Structured steps ready.";
}

function getLinkedSpecificationsForSuite(suite: TestSuite) {
  if (suite.specification && suite.specification_title) {
    const hasPrimarySpecification = suite.linked_specifications.some(
      (specification) => specification.id === suite.specification
    );

    if (!hasPrimarySpecification) {
      return [
        {
          id: suite.specification,
          title: suite.specification_title,
          external_reference: null,
          source_type: "manual",
        },
        ...suite.linked_specifications,
      ];
    }
  }

  return suite.linked_specifications;
}

function OverviewMetric({
  label,
  value,
  helper,
}: Readonly<{
  label: string;
  value: string | number;
  helper: string;
}>) {
  return (
    <div className="rounded-[24px] border border-border bg-surface p-5 shadow-sm">
      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted">
        {label}
      </p>
      <p className="mt-3 text-3xl font-semibold tracking-tight text-text">{value}</p>
      <p className="mt-2 text-sm leading-6 text-muted">{helper}</p>
    </div>
  );
}

function WorkspaceSectionTitle({
  title,
  description,
  actions,
}: Readonly<{
  title: string;
  description: string;
  actions?: ReactNode;
}>) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-4">
      <div>
        <h2 className="text-lg font-semibold tracking-tight text-text">{title}</h2>
        <p className="mt-1 text-sm leading-6 text-muted">{description}</p>
      </div>
      {actions}
    </div>
  );
}

function getWorkspaceTabSummary(tab: WorkspaceTab): {
  label: string;
  description: string;
} {
  switch (tab) {
    case "specifications":
      return {
        label: "Requirements",
        description:
          "Browse BA-owned source artifacts first, then open the normalized requirement records produced from them.",
      };
    case "members":
      return {
        label: "Members",
        description:
          "Project access is managed here separately from team membership so collaboration stays controlled at project level.",
      };
    case "test-suites":
      return {
        label: "Test Design",
        description:
          "Work through the QA-owned hierarchy the way teams expect it: folder, suite, scenario, then case.",
      };
    default:
      return {
        label: "Overview",
        description:
          "This workspace links imported BA sources, normalized requirements, project members, and manual-first QA design.",
      };
  }
}

function ProjectSectionExplorer({
  project,
  tabs,
  currentTab,
  projectMembersCount,
  requirementsCount,
  coveredRequirementCount,
  suiteCount,
  scenarioCount,
  caseCount,
  children,
}: Readonly<{
  project: Project;
  tabs: Array<{ key: WorkspaceTab; label: string; to: string }>;
  currentTab: WorkspaceTab;
  projectMembersCount: number;
  requirementsCount: number;
  coveredRequirementCount: number;
  suiteCount: number;
  scenarioCount: number;
  caseCount: number;
  children?: ReactNode;
}>) {
  const sectionSummary = getWorkspaceTabSummary(currentTab);

  return (
    <aside className="space-y-5 xl:sticky xl:top-24">
      <section className="rounded-[28px] border border-border bg-surface p-5 shadow-sm">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted">
          Project workspace
        </p>
        <div className="mt-4 rounded-[24px] border border-border bg-bg p-4">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant={project.status === "active" ? "verified" : "warm"}>
              {project.status}
            </Badge>
            <Badge variant="tag">{project.team_name}</Badge>
          </div>
          <h2 className="mt-3 text-xl font-semibold tracking-tight text-text">
            {project.name}
          </h2>
          <p className="mt-2 text-sm leading-6 text-muted">
            {project.description ||
              "Manual-first QA workspace for requirements, traceability, and test design."}
          </p>
        </div>

        <nav className="mt-5 space-y-2">
        {tabs.map((tab) => {
          const isActive = currentTab === tab.key;
          return (
            <NavLink
              key={tab.to}
              to={tab.to}
              end={tab.key === "overview"}
              className={`block rounded-2xl border px-4 py-3 text-sm font-semibold transition ${
                isActive
                  ? "border-primary-light bg-primary-light/10 text-primary"
                  : "border-border bg-bg text-text hover:border-primary-light/30 hover:bg-primary-light/10"
              }`}
            >
              <span className="block">{tab.label}</span>
            </NavLink>
          );
        })}
        </nav>

        <div className="mt-5 rounded-[24px] border border-border bg-bg p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted">
            Current section
          </p>
          <p className="mt-2 text-sm font-semibold text-text">{sectionSummary.label}</p>
          <p className="mt-2 text-sm leading-6 text-muted">
            {sectionSummary.description}
          </p>
        </div>

        <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-1">
          <div className="rounded-2xl border border-border bg-bg p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted">
              Requirements
            </p>
            <p className="mt-2 text-2xl font-semibold text-text">{requirementsCount}</p>
            <p className="mt-1 text-sm text-muted">
              {coveredRequirementCount} covered
            </p>
          </div>
          <div className="rounded-2xl border border-border bg-bg p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted">
              Test design
            </p>
            <p className="mt-2 text-2xl font-semibold text-text">{suiteCount}</p>
            <p className="mt-1 text-sm text-muted">
              {scenarioCount} scenarios, {caseCount} cases
            </p>
          </div>
          <div className="rounded-2xl border border-border bg-bg p-4 sm:col-span-2 xl:col-span-1">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted">
              Project members
            </p>
            <p className="mt-2 text-2xl font-semibold text-text">
              {projectMembersCount}
            </p>
            <p className="mt-1 text-sm text-muted">
              Access is managed at project level
            </p>
          </div>
        </div>
      </section>

      {children ? (
        <section className="rounded-[28px] border border-border bg-surface p-5 shadow-sm">
          {children}
        </section>
      ) : null}
    </aside>
  );
}

function ProjectWorkspaceSplitLayout({
  explorer,
  content,
}: Readonly<{
  explorer: ReactNode;
  content: ReactNode;
}>) {
  return (
    <div className="grid gap-6 xl:grid-cols-[360px_minmax(0,1fr)]">
      <div>{explorer}</div>
      <div className="min-w-0">{content}</div>
    </div>
  );
}

function ProjectWorkspaceIcon() {
  return (
    <svg className="h-10 w-10" viewBox="0 0 48 48" fill="none" aria-hidden="true">
      <rect
        x="8"
        y="10"
        width="32"
        height="10"
        rx="5"
        className="stroke-primary"
        strokeWidth="2.5"
      />
      <rect
        x="13"
        y="22"
        width="22"
        height="7"
        rx="3.5"
        className="stroke-primary-light"
        strokeWidth="2.5"
      />
      <path
        d="M18 36h12"
        className="stroke-warm"
        strokeWidth="2.5"
        strokeLinecap="round"
      />
    </svg>
  );
}

export default function ProjectWorkspacePage() {
  const { projectId } = useParams<{ projectId: string }>();
  const location = useLocation();
  const navigate = useNavigate();
  const { user } = useAuthStore();

  if (!projectId) {
    return <Navigate to="/projects" replace />;
  }

  const role = user?.profile?.role;
  const isAdminShell = location.pathname.startsWith("/admin/");
  const canManageProject =
    role === "platform_owner" || role === "org_admin" || role === "team_manager";
  const baseProjectsPath = isAdminShell ? "/admin/projects" : "/projects";
  const currentTab = getWorkspaceTab(location.pathname, projectId);

  const [project, setProject] = useState<Project | null>(null);
  const [specifications, setSpecifications] = useState<Specification[]>([]);
  const [specificationSources, setSpecificationSources] = useState<
    SpecificationSource[]
  >([]);
  const [selectedSpecificationSourceDetail, setSelectedSpecificationSourceDetail] =
    useState<SpecificationSourceDetail | null>(null);
  const [projectMembers, setProjectMembers] = useState<ProjectMember[]>([]);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [suites, setSuites] = useState<TestSuite[]>([]);
  const [scenarios, setScenarios] = useState<TestScenario[]>([]);
  const [cases, setCases] = useState<TestCase[]>([]);
  const [automationScripts, setAutomationScripts] = useState<AutomationScript[]>([]);
  const [testExecutions, setTestExecutions] = useState<TestExecution[]>([]);
  const [executionSteps, setExecutionSteps] = useState<ExecutionStep[]>([]);
  const [stdoutLog, setStdoutLog] = useState("");
  const [stderrLog, setStderrLog] = useState("");

  const [selectedFolder, setSelectedFolder] = useState<string>("");
  const [selectedSpecificationTreeGroupKey, setSelectedSpecificationTreeGroupKey] =
    useState<string>("");
  const [selectedSpecificationId, setSelectedSpecificationId] = useState<string>("");
  const [selectedSuiteId, setSelectedSuiteId] = useState<string>("");
  const [selectedScenarioId, setSelectedScenarioId] = useState<string>("");
  const [selectedCaseId, setSelectedCaseId] = useState<string>("");
  const [selectedExecutionId, setSelectedExecutionId] = useState<string>("");

  const [isLoading, setIsLoading] = useState(true);
  const [isSpecificationSourceLoading, setIsSpecificationSourceLoading] =
    useState(false);
  const [isScenarioLoading, setIsScenarioLoading] = useState(false);
  const [isCaseLoading, setIsCaseLoading] = useState(false);
  const [isAutomationLoading, setIsAutomationLoading] = useState(false);
  const [isExecutionDetailLoading, setIsExecutionDetailLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [successMessage, setSuccessMessage] = useState("");

  const [isSuiteModalOpen, setIsSuiteModalOpen] = useState(false);
  const [isScenarioModalOpen, setIsScenarioModalOpen] = useState(false);
  const [isCaseModalOpen, setIsCaseModalOpen] = useState(false);
  const [isScriptModalOpen, setIsScriptModalOpen] = useState(false);
  const [isRunExecutionModalOpen, setIsRunExecutionModalOpen] = useState(false);
  const [editingSuite, setEditingSuite] = useState<TestSuite | null>(null);
  const [editingScenario, setEditingScenario] = useState<TestScenario | null>(null);
  const [editingCase, setEditingCase] = useState<TestCase | null>(null);
  const [editingScript, setEditingScript] = useState<AutomationScript | null>(null);
  const [suiteForm, setSuiteForm] = useState<SuiteFormState>(initialSuiteFormState);
  const [scenarioForm, setScenarioForm] = useState<ScenarioFormState>(
    initialScenarioFormState
  );

  const [memberForm, setMemberForm] = useState<{
    userId: string;
    role: ProjectMemberRole;
  }>({
    userId: "",
    role: "viewer",
  });

  const [updatingMemberId, setUpdatingMemberId] = useState<string | null>(null);
  const [deletingMemberId, setDeletingMemberId] = useState<string | null>(null);
  const [deletingSuiteId, setDeletingSuiteId] = useState<string | null>(null);
  const [cloningScenarioId, setCloningScenarioId] = useState<string | null>(null);
  const [deletingScenarioId, setDeletingScenarioId] = useState<string | null>(null);
  const [deletingCaseId, setDeletingCaseId] = useState<string | null>(null);
  const [deletingScriptId, setDeletingScriptId] = useState<string | null>(null);
  const [switchingScriptId, setSwitchingScriptId] = useState<string | null>(null);
  const [validatingScriptId, setValidatingScriptId] = useState<string | null>(null);
  const [runningExecutionId, setRunningExecutionId] = useState<string | null>(null);
  const [deletingExecutionId, setDeletingExecutionId] = useState<string | null>(null);
  const [runExecutionForm, setRunExecutionForm] = useState<{
    browser: ExecutionBrowser;
    platform: ExecutionPlatform;
  }>({
    browser: "chromium",
    platform: "desktop",
  });

  const folderGroups = useMemo(() => buildFolderGroups(suites), [suites]);
  const specificationTreeGroups = useMemo(
    () => buildSpecificationTreeGroups(specificationSources, specifications),
    [specificationSources, specifications]
  );
  const selectedSpecificationTreeGroup =
    specificationTreeGroups.find(
      (group) => group.key === selectedSpecificationTreeGroupKey
    ) ?? specificationTreeGroups[0] ?? null;
  const selectedProjectSpecification =
    selectedSpecificationTreeGroup?.specifications.find(
      (specification) => specification.id === selectedSpecificationId
    ) ?? null;
  const linkedSuitesForSelectedSpecification = selectedProjectSpecification
    ? suites.filter((suite) =>
        suite.specification === selectedProjectSpecification.id ||
        getLinkedSpecificationsForSuite(suite).some(
          (specification) => specification.id === selectedProjectSpecification.id
        )
      )
    : [];
  const coveredRequirementCount = specifications.filter(
    (specification) => specification.coverage_status === "covered"
  ).length;
  const uncoveredRequirementCount = Math.max(
    specifications.length - coveredRequirementCount,
    0
  );
  const totalScenarioCount = suites.reduce(
    (sum, suite) => sum + suite.scenario_count,
    0
  );
  const totalCaseCount = suites.reduce(
    (sum, suite) => sum + suite.total_case_count,
    0
  );

  const specificationOptions = useMemo(
    () => [
      { value: "", label: "No linked specification" },
      ...specifications.map((specification) => ({
        value: specification.id,
        label: specification.title,
      })),
    ],
    [specifications]
  );
  const caseRequirementOptions = useMemo(
    () =>
      specifications.map((specification) => ({
        id: specification.id,
        label: specification.title,
        reference: specification.external_reference,
      })),
    [specifications]
  );

  const activeSuiteCandidates = useMemo(() => {
    const targetFolder = selectedFolder.trim() || folderGroups[0]?.key || "";
    return suites.filter(
      (suite) => (suite.folder_path.trim() || "Unfiled") === targetFolder
    );
  }, [folderGroups, selectedFolder, suites]);

  const selectedSuite =
    suites.find((suite) => suite.id === selectedSuiteId) ??
    activeSuiteCandidates[0] ??
    null;

  const selectedScenario =
    scenarios.find((scenario) => scenario.id === selectedScenarioId) ??
    scenarios[0] ??
    null;

  const selectedCase =
    cases.find((testCase) => testCase.id === selectedCaseId) ?? cases[0] ?? null;
  const activeAutomationScript =
    automationScripts.find((script) => script.is_active) ?? automationScripts[0] ?? null;
  const selectedExecution =
    testExecutions.find((execution) => execution.id === selectedExecutionId) ??
    testExecutions[0] ??
    null;
  const isSelectedExecutionLive =
    selectedExecution?.status === "queued" || selectedExecution?.status === "running";
  const latestExecutionScreenshotUrl =
    resolveExecutionArtifactUrl(
      selectedExecution?.result?.artifacts.latest_screenshot_url
    ) ??
    executionSteps
      .map((step) => resolveExecutionArtifactUrl(step.screenshot_url))
      .filter((value): value is string => Boolean(value))
      .at(-1) ??
    null;

  const availableProjectMembers = useMemo(() => {
    if (!project) {
      return [];
    }

    const existingUserIds = new Set(projectMembers.map((member) => member.user_id));

    return users.filter((appUser) => {
      const userRole = appUser.profile?.role;
      const belongsToTeam =
        appUser.profile?.team_memberships?.some(
          (membership) => membership.team === project.team && membership.is_active
        ) ?? false;

      return (
        !existingUserIds.has(appUser.id) &&
        belongsToTeam &&
        (userRole === "team_manager" ||
          userRole === "tester" ||
          userRole === "viewer")
      );
    });
  }, [project, projectMembers, users]);

  const projectMemberOptions = useMemo(
    () =>
      availableProjectMembers.map((appUser) => ({
        value: String(appUser.id),
        label: `${appUser.first_name} ${appUser.last_name} - ${appUser.email}`,
      })),
    [availableProjectMembers]
  );

  const workspaceTabs = useMemo(
    () => [
      { key: "overview" as const, label: "Overview", to: `${baseProjectsPath}/${projectId}` },
      {
        key: "specifications" as const,
        label: "Specifications",
        to: `${baseProjectsPath}/${projectId}/specifications`,
      },
      {
        key: "members" as const,
        label: "Members",
        to: `${baseProjectsPath}/${projectId}/members`,
      },
      {
        key: "test-suites" as const,
        label: "Test Suites",
        to: `${baseProjectsPath}/${projectId}/test-suites`,
      },
    ],
    [baseProjectsPath, projectId]
  );

  const loadWorkspace = async (): Promise<void> => {
    try {
      setIsLoading(true);
      setErrorMessage("");

      const requests: [
        Promise<Project>,
        Promise<Specification[]>,
        Promise<SpecificationSource[]>,
        Promise<ProjectMember[]>,
        Promise<TestSuite[]>,
        Promise<AdminUser[]>
      ] = [
        getProject(projectId),
        getSpecifications(projectId),
        getSpecificationSources(projectId),
        getProjectMembers(projectId),
        getTestSuites({ project: projectId }),
        canManageProject ? getAdminUsers() : Promise.resolve([]),
      ];

      const [
        projectData,
        specificationData,
        sourceData,
        memberData,
        suiteData,
        userData,
      ] =
        await Promise.all(requests);

      setProject(projectData);
      setSpecifications(specificationData);
      setSpecificationSources(sourceData);
      setProjectMembers(memberData);
      setSuites(suiteData);
      setUsers(userData);
    } catch (error: unknown) {
      setErrorMessage(getErrorMessage(error, "Failed to load the project workspace."));
    } finally {
      setIsLoading(false);
    }
  };

  const loadSpecificationSourceDetail = async (sourceId: string): Promise<void> => {
    try {
      setIsSpecificationSourceLoading(true);
      const sourceDetail = await getSpecificationSource(sourceId);
      setSelectedSpecificationSourceDetail(sourceDetail);
    } catch (error: unknown) {
      setErrorMessage(
        getErrorMessage(error, "Failed to load the selected requirement source.")
      );
    } finally {
      setIsSpecificationSourceLoading(false);
    }
  };

  const loadScenarios = async (suiteId: string): Promise<void> => {
    try {
      setIsScenarioLoading(true);
      const scenarioData = await getTestScenarios(suiteId);
      const orderedScenarios = [...scenarioData].sort(
        (left, right) => left.order_index - right.order_index
      );
      setScenarios(orderedScenarios);
    } catch (error: unknown) {
      setErrorMessage(getErrorMessage(error, "Failed to load test scenarios."));
    } finally {
      setIsScenarioLoading(false);
    }
  };

  const loadCases = async (scenarioId: string): Promise<void> => {
    try {
      setIsCaseLoading(true);
      const caseData = await getTestCases(scenarioId);
      const orderedCases = [...caseData].sort(
        (left, right) => left.order_index - right.order_index
      );
      setCases(orderedCases);
    } catch (error: unknown) {
      setErrorMessage(getErrorMessage(error, "Failed to load test cases."));
    } finally {
      setIsCaseLoading(false);
    }
  };

  const loadAutomationData = async (testCaseId: string): Promise<void> => {
    try {
      setIsAutomationLoading(true);
      const [scriptData, executionData] = await Promise.all([
        getAutomationScripts({ test_case: testCaseId }),
        getTestExecutions({ test_case: testCaseId }),
      ]);
      setAutomationScripts(scriptData);
      setTestExecutions(executionData);
    } catch (error: unknown) {
      setErrorMessage(getErrorMessage(error, "Failed to load automation data."));
    } finally {
      setIsAutomationLoading(false);
    }
  };

  const loadExecutionSteps = async (executionId: string): Promise<void> => {
    try {
      setIsExecutionDetailLoading(true);
      const stepData = await getExecutionSteps(executionId);
      const orderedStepData = [...stepData].sort(
        (left, right) => left.step_index - right.step_index
      );
      setExecutionSteps(orderedStepData);
    } catch (error: unknown) {
      setErrorMessage(
        getErrorMessage(error, "Failed to load execution details.")
      );
    } finally {
      setIsExecutionDetailLoading(false);
    }
  };

  const loadExecutionLogs = async (executionId: string): Promise<void> => {
    const [nextStdout, nextStderr] = await Promise.all([
      getExecutionArtifactText(executionId, "stdout.log"),
      getExecutionArtifactText(executionId, "stderr.log"),
    ]);
    setStdoutLog(nextStdout);
    setStderrLog(nextStderr);
  };

  useEffect(() => {
    void loadWorkspace();
  }, [projectId, canManageProject]);

  useEffect(() => {
    if (specificationTreeGroups.length === 0) {
      setSelectedSpecificationTreeGroupKey("");
      setSelectedSpecificationId("");
      setSelectedSpecificationSourceDetail(null);
      return;
    }

    const activeGroup = specificationTreeGroups.find(
      (group) => group.key === selectedSpecificationTreeGroupKey
    );

    if (!activeGroup) {
      setSelectedSpecificationTreeGroupKey(specificationTreeGroups[0].key);
      setSelectedSpecificationId(
        specificationTreeGroups[0].specifications[0]?.id ?? ""
      );
      return;
    }

    if (
      selectedSpecificationId &&
      !activeGroup.specifications.some(
        (specification) => specification.id === selectedSpecificationId
      )
    ) {
      setSelectedSpecificationId(activeGroup.specifications[0]?.id ?? "");
    }
  }, [
    selectedSpecificationId,
    selectedSpecificationTreeGroupKey,
    specificationTreeGroups,
  ]);

  useEffect(() => {
    if (!selectedSpecificationTreeGroup?.source?.id) {
      setSelectedSpecificationSourceDetail(null);
      return;
    }

    void loadSpecificationSourceDetail(selectedSpecificationTreeGroup.source.id);
  }, [selectedSpecificationTreeGroup?.source?.id]);

  useEffect(() => {
    if (!folderGroups.length) {
      setSelectedFolder("");
      return;
    }

    const targetFolder = selectedFolder.trim() || folderGroups[0].key;
    const stillExists = folderGroups.some((folderGroup) => folderGroup.key === targetFolder);

    if (!stillExists) {
      setSelectedFolder(folderGroups[0].key);
      return;
    }

    setSelectedFolder(targetFolder);
  }, [folderGroups, selectedFolder]);

  useEffect(() => {
    if (!activeSuiteCandidates.length) {
      setSelectedSuiteId("");
      setScenarios([]);
      setCases([]);
      return;
    }

    const nextSuite =
      activeSuiteCandidates.find((suite) => suite.id === selectedSuiteId) ??
      activeSuiteCandidates[0];
    setSelectedSuiteId(nextSuite.id);
  }, [activeSuiteCandidates, selectedSuiteId]);

  useEffect(() => {
    if (!selectedSuite?.id) {
      setScenarios([]);
      setCases([]);
      return;
    }

    void loadScenarios(selectedSuite.id);
  }, [selectedSuite?.id]);

  useEffect(() => {
    if (!scenarios.length) {
      setSelectedScenarioId("");
      setCases([]);
      return;
    }

    const nextScenario =
      scenarios.find((scenario) => scenario.id === selectedScenarioId) ?? scenarios[0];
    setSelectedScenarioId(nextScenario.id);
  }, [scenarios, selectedScenarioId]);

  useEffect(() => {
    if (!selectedScenario?.id) {
      setCases([]);
      return;
    }

    void loadCases(selectedScenario.id);
  }, [selectedScenario?.id]);

  useEffect(() => {
    if (!cases.length) {
      setSelectedCaseId("");
      setAutomationScripts([]);
      setTestExecutions([]);
      return;
    }

    const nextCase = cases.find((testCase) => testCase.id === selectedCaseId) ?? cases[0];
    setSelectedCaseId(nextCase.id);
  }, [cases, selectedCaseId]);

  useEffect(() => {
    if (!selectedCase?.id) {
      setAutomationScripts([]);
      setTestExecutions([]);
      setExecutionSteps([]);
      setStdoutLog("");
      setStderrLog("");
      setSelectedExecutionId("");
      return;
    }

    void loadAutomationData(selectedCase.id);
  }, [selectedCase?.id]);

  useEffect(() => {
    if (!selectedScenario?.id || !selectedCase?.id) {
      return;
    }

    const hasInFlightExecution = testExecutions.some(
      (execution) =>
        execution.status === "queued" || execution.status === "running"
    );

    if (!hasInFlightExecution) {
      return;
    }

    // Temporary polling loop for near-live execution monitoring. This should be
    // replaced by websocket/server-push updates when real live execution arrives.
    const timeoutId = window.setTimeout(() => {
      const refreshOperations: Array<Promise<void>> = [
        loadCases(selectedScenario.id),
        loadAutomationData(selectedCase.id),
      ];

      if (selectedExecutionId) {
        refreshOperations.push(loadExecutionSteps(selectedExecutionId));
        refreshOperations.push(loadExecutionLogs(selectedExecutionId));
      }

      void Promise.all(refreshOperations);
    }, 2500);

    return () => {
      window.clearTimeout(timeoutId);
    };
  }, [selectedCase?.id, selectedExecutionId, selectedScenario?.id, testExecutions]);

  useEffect(() => {
    if (!testExecutions.length) {
      setSelectedExecutionId("");
      return;
    }

    const activeExecution = testExecutions.find(
      (execution) => execution.id === selectedExecutionId
    );
    if (activeExecution) {
      return;
    }

    setSelectedExecutionId(testExecutions[0].id);
  }, [selectedExecutionId, testExecutions]);

  useEffect(() => {
    if (!selectedExecutionId) {
      setExecutionSteps([]);
      setStdoutLog("");
      setStderrLog("");
      return;
    }

    void Promise.all([
      loadExecutionSteps(selectedExecutionId),
      loadExecutionLogs(selectedExecutionId),
    ]);
  }, [selectedExecutionId]);

  const openSuiteCreateModal = () => {
    setEditingSuite(null);
    setSuiteForm({
      ...initialSuiteFormState,
      folderPath: selectedFolder === "Unfiled" ? "" : selectedFolder,
    });
    setIsSuiteModalOpen(true);
  };

  const openSuiteEditModal = (suite: TestSuite) => {
    setEditingSuite(suite);
    setSuiteForm({
      name: suite.name,
      description: suite.description ?? "",
      folderPath: suite.folder_path ?? "",
      specification: suite.specification ?? "",
    });
    setIsSuiteModalOpen(true);
  };

  const closeSuiteModal = () => {
    setEditingSuite(null);
    setSuiteForm(initialSuiteFormState);
    setIsSuiteModalOpen(false);
  };

  const openScenarioCreateModal = () => {
    setEditingScenario(null);
    setScenarioForm({
      ...initialScenarioFormState,
      orderIndex: String(scenarios.length),
    });
    setIsScenarioModalOpen(true);
  };

  const openScenarioEditModal = (scenario: TestScenario) => {
    setEditingScenario(scenario);
    setScenarioForm({
      title: scenario.title,
      description: scenario.description,
      scenarioType: scenario.scenario_type,
      priority: scenario.priority,
      businessPriority: scenario.business_priority ?? "",
      polarity: scenario.polarity,
      orderIndex: String(scenario.order_index),
    });
    setIsScenarioModalOpen(true);
  };

  const closeScenarioModal = () => {
    setEditingScenario(null);
    setScenarioForm(initialScenarioFormState);
    setIsScenarioModalOpen(false);
  };

  const openCaseCreateModal = () => {
    setEditingCase(null);
    setIsCaseModalOpen(true);
  };

  const openCaseEditModal = (testCase: TestCase) => {
    setEditingCase(testCase);
    setIsCaseModalOpen(true);
  };

  const closeCaseModal = () => {
    setEditingCase(null);
    setIsCaseModalOpen(false);
  };

  const openScriptCreateModal = () => {
    setEditingScript(null);
    setIsScriptModalOpen(true);
  };

  const openScriptEditModal = (script: AutomationScript) => {
    setEditingScript(script);
    setIsScriptModalOpen(true);
  };

  const closeScriptModal = () => {
    setEditingScript(null);
    setIsScriptModalOpen(false);
  };

  const handleSuiteSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!project) {
      return;
    }

    try {
      setIsSaving(true);
      setErrorMessage("");
      setSuccessMessage("");

      const payload = {
        project: project.id,
        specification: suiteForm.specification || null,
        name: suiteForm.name.trim(),
        description: suiteForm.description.trim(),
        folder_path: suiteForm.folderPath.trim(),
      };

      if (editingSuite) {
        await updateTestSuite(editingSuite.id, payload);
        setSuccessMessage("Test suite updated successfully.");
      } else {
        await createTestSuite(payload);
        setSuccessMessage("Test suite created successfully.");
      }

      closeSuiteModal();
      await loadWorkspace();
    } catch (error: unknown) {
      setErrorMessage(getErrorMessage(error, "Failed to save the test suite."));
    } finally {
      setIsSaving(false);
    }
  };

  const handleDeleteSuite = async (suite: TestSuite) => {
    const confirmed = globalThis.confirm(`Delete the suite ${suite.name}?`);
    if (!confirmed) {
      return;
    }

    try {
      setDeletingSuiteId(suite.id);
      await deleteTestSuite(suite.id);
      setSuccessMessage("Test suite deleted successfully.");
      await loadWorkspace();
    } catch (error: unknown) {
      setErrorMessage(getErrorMessage(error, "Failed to delete the test suite."));
    } finally {
      setDeletingSuiteId(null);
    }
  };

  const handleScenarioSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedSuite) {
      return;
    }

    try {
      setIsSaving(true);
      setErrorMessage("");
      setSuccessMessage("");

      const payload = {
        title: scenarioForm.title.trim(),
        description: scenarioForm.description.trim(),
        scenario_type: scenarioForm.scenarioType,
        priority: scenarioForm.priority,
        business_priority: scenarioForm.businessPriority || null,
        polarity: scenarioForm.polarity,
        order_index: Number(scenarioForm.orderIndex) || 0,
      };

      if (editingScenario) {
        await updateTestScenario(selectedSuite.id, editingScenario.id, payload);
        setSuccessMessage("Scenario updated successfully.");
      } else {
        await createTestScenario(selectedSuite.id, payload);
        setSuccessMessage("Scenario created successfully.");
      }

      closeScenarioModal();
      await loadScenarios(selectedSuite.id);
    } catch (error: unknown) {
      setErrorMessage(getErrorMessage(error, "Failed to save the scenario."));
    } finally {
      setIsSaving(false);
    }
  };

  const handleCloneScenario = async (scenario: TestScenario) => {
    try {
      setCloningScenarioId(scenario.id);
      await cloneTestScenario(scenario.id);
      setSuccessMessage("Scenario cloned successfully.");
      if (selectedSuite?.id) {
        await loadScenarios(selectedSuite.id);
      }
    } catch (error: unknown) {
      setErrorMessage(getErrorMessage(error, "Failed to clone the scenario."));
    } finally {
      setCloningScenarioId(null);
    }
  };

  const handleDeleteScenario = async (scenario: TestScenario) => {
    if (!selectedSuite) {
      return;
    }

    const confirmed = globalThis.confirm(`Delete the scenario ${scenario.title}?`);
    if (!confirmed) {
      return;
    }

    try {
      setDeletingScenarioId(scenario.id);
      await deleteTestScenario(selectedSuite.id, scenario.id);
      setSuccessMessage("Scenario deleted successfully.");
      await loadScenarios(selectedSuite.id);
    } catch (error: unknown) {
      setErrorMessage(getErrorMessage(error, "Failed to delete the scenario."));
    } finally {
      setDeletingScenarioId(null);
    }
  };

  const handleCaseSubmit = async (payload: TestCaseWritePayload) => {
    if (!selectedScenario) {
      return;
    }

    try {
      setIsSaving(true);
      setErrorMessage("");
      setSuccessMessage("");

      if (editingCase) {
        await updateTestCase(selectedScenario.id, editingCase.id, payload);
        setSuccessMessage("Test case updated successfully.");
      } else {
        await createTestCase(selectedScenario.id, payload);
        setSuccessMessage("Test case created successfully.");
      }

      closeCaseModal();
      await loadCases(selectedScenario.id);
    } catch (error: unknown) {
      setErrorMessage(getErrorMessage(error, "Failed to save the test case."));
    } finally {
      setIsSaving(false);
    }
  };

  const handleDeleteCase = async (testCase: TestCase) => {
    if (!selectedScenario) {
      return;
    }

    const confirmed = globalThis.confirm(`Delete the test case ${testCase.title}?`);
    if (!confirmed) {
      return;
    }

    try {
      setDeletingCaseId(testCase.id);
      await deleteTestCase(selectedScenario.id, testCase.id);
      setSuccessMessage("Test case deleted successfully.");
      await loadCases(selectedScenario.id);
    } catch (error: unknown) {
      setErrorMessage(getErrorMessage(error, "Failed to delete the test case."));
    } finally {
      setDeletingCaseId(null);
    }
  };

  const refreshSelectedCaseData = async () => {
    if (!selectedScenario?.id || !selectedCase?.id) {
      return;
    }

    const refreshOperations: Array<Promise<void>> = [
      loadCases(selectedScenario.id),
      loadAutomationData(selectedCase.id),
    ];

    if (selectedExecutionId) {
      refreshOperations.push(loadExecutionSteps(selectedExecutionId));
      refreshOperations.push(loadExecutionLogs(selectedExecutionId));
    }

    await Promise.all(refreshOperations);
  };

  const handleScriptSubmit = async (payload: AutomationScriptWritePayload) => {
    if (!selectedCase) {
      return;
    }

    try {
      setIsSaving(true);
      setErrorMessage("");
      setSuccessMessage("");

      if (editingScript) {
        await updateAutomationScript(editingScript.id, payload);
        setSuccessMessage("Automation script updated successfully.");
      } else {
        await createAutomationScript(payload);
        setSuccessMessage("Automation script created successfully.");
      }

      closeScriptModal();
      await refreshSelectedCaseData();
    } catch (error: unknown) {
      setErrorMessage(getErrorMessage(error, "Failed to save the automation script."));
    } finally {
      setIsSaving(false);
    }
  };

  const handleDeleteScript = async (script: AutomationScript) => {
    const confirmed = globalThis.confirm(
      `Delete automation script v${script.script_version}?`
    );
    if (!confirmed || !selectedCase) {
      return;
    }

    try {
      setDeletingScriptId(script.id);
      await deleteAutomationScript(script.id);
      setSuccessMessage("Automation script deleted successfully.");
      await refreshSelectedCaseData();
    } catch (error: unknown) {
      setErrorMessage(
        getErrorMessage(error, "Failed to delete the automation script.")
      );
    } finally {
      setDeletingScriptId(null);
    }
  };

  const handleToggleScriptActive = async (script: AutomationScript) => {
    try {
      setSwitchingScriptId(script.id);
      if (script.is_active) {
        await deactivateAutomationScript(script.id);
        setSuccessMessage("Automation script deactivated successfully.");
      } else {
        await activateAutomationScript(script.id);
        setSuccessMessage("Automation script activated successfully.");
      }
      await refreshSelectedCaseData();
    } catch (error: unknown) {
      setErrorMessage(
        getErrorMessage(error, "Failed to update the script status.")
      );
    } finally {
      setSwitchingScriptId(null);
    }
  };

  const handleValidateScript = async (script: AutomationScript) => {
    try {
      setValidatingScriptId(script.id);
      const validation = await validateAutomationScript(script.id);
      if (validation.is_valid) {
        setSuccessMessage(
          validation.warnings.length
            ? `Script is valid. ${validation.warnings.join(" ")}`
            : "Script validation succeeded."
        );
      } else {
        setErrorMessage(validation.errors.join(" "));
      }
      await loadAutomationData(script.test_case);
    } catch (error: unknown) {
      setErrorMessage(
        getErrorMessage(error, "Failed to validate the automation script.")
      );
    } finally {
      setValidatingScriptId(null);
    }
  };

  const handleRunExecution = async (payload?: {
    browser: ExecutionBrowser;
    platform: ExecutionPlatform;
  }) => {
    if (!selectedCase) {
      return;
    }

    const targetExecutionConfig = payload ?? runExecutionForm;

    try {
      setRunningExecutionId(selectedCase.id);
      setErrorMessage("");
      setSuccessMessage("");
      const execution = await createTestExecution({
        test_case: selectedCase.id,
        script: activeAutomationScript?.id ?? null,
        browser: targetExecutionConfig.browser,
        platform: targetExecutionConfig.platform,
      });
      setSelectedExecutionId(execution.id);
      setIsRunExecutionModalOpen(false);
      setSuccessMessage("Execution queued successfully.");
      await refreshSelectedCaseData();
    } catch (error: unknown) {
      setErrorMessage(
        getErrorMessage(error, "Failed to queue the test execution.")
      );
    } finally {
      setRunningExecutionId(null);
    }
  };

  const handleExecutionControl = async (
    execution: TestExecution,
    action: "pause" | "resume" | "stop"
  ) => {
    try {
      setRunningExecutionId(execution.id);
      if (action === "pause") {
        await pauseTestExecution(execution.id);
        setSuccessMessage("Execution paused successfully.");
      } else if (action === "resume") {
        await resumeTestExecution(execution.id);
        setSuccessMessage("Execution resumed successfully.");
      } else {
        await stopTestExecution(execution.id);
        setSuccessMessage("Execution stopped successfully.");
      }
      await refreshSelectedCaseData();
    } catch (error: unknown) {
      setErrorMessage(getErrorMessage(error, "Failed to update the execution."));
    } finally {
      setRunningExecutionId(null);
    }
  };

  const handleDeleteExecution = async (execution: TestExecution) => {
    if (!selectedCase) {
      return;
    }

    try {
      setDeletingExecutionId(execution.id);
      setErrorMessage("");
      setSuccessMessage("");
      await deleteTestExecution(execution.id);
      setSuccessMessage("Execution deleted successfully.");
      await refreshSelectedCaseData();
    } catch (error: unknown) {
      setErrorMessage(getErrorMessage(error, "Failed to delete the execution."));
    } finally {
      setDeletingExecutionId(null);
    }
  };

  const handleAddProjectMember = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!project || !memberForm.userId) {
      return;
    }

    try {
      setIsSaving(true);
      setErrorMessage("");
      setSuccessMessage("");

      await addProjectMember(project.id, {
        user: Number(memberForm.userId),
        role: memberForm.role,
      });

      setMemberForm({
        userId: "",
        role: "viewer",
      });
      setSuccessMessage("Project member added successfully.");
      await loadWorkspace();
    } catch (error: unknown) {
      setErrorMessage(getErrorMessage(error, "Failed to add the project member."));
    } finally {
      setIsSaving(false);
    }
  };

  const handleProjectMemberRoleChange = async (
    member: ProjectMember,
    nextRole: ProjectMemberRole
  ) => {
    if (!project || member.role === nextRole) {
      return;
    }

    try {
      setUpdatingMemberId(member.id);
      await updateProjectMember(project.id, member.id, { role: nextRole });
      setSuccessMessage("Project member updated successfully.");
      await loadWorkspace();
    } catch (error: unknown) {
      setErrorMessage(getErrorMessage(error, "Failed to update the project member."));
    } finally {
      setUpdatingMemberId(null);
    }
  };

  const handleRemoveProjectMember = async (member: ProjectMember) => {
    if (!project) {
      return;
    }

    const confirmed = globalThis.confirm(
      `Remove ${member.full_name} from ${project.name}?`
    );
    if (!confirmed) {
      return;
    }

    try {
      setDeletingMemberId(member.id);
      await removeProjectMember(project.id, member.id);
      setSuccessMessage("Project member removed successfully.");
      await loadWorkspace();
    } catch (error: unknown) {
      setErrorMessage(getErrorMessage(error, "Failed to remove the project member."));
    } finally {
      setDeletingMemberId(null);
    }
  };

  if (isLoading) {
    return (
      <div className="flex min-h-[420px] items-center justify-center">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  if (!project) {
    return (
      <EmptyState
        icon={<ProjectWorkspaceIcon />}
        title="Project not available"
        description="The selected project could not be loaded or is no longer accessible."
        primaryAction={
          <Button onClick={() => navigate(baseProjectsPath)}>Back to Projects</Button>
        }
      />
    );
  }

  const renderOverview = () => (
    <div className="space-y-6">
      <div className="grid gap-4 xl:grid-cols-3 2xl:grid-cols-6">
        <OverviewMetric
          label="Requirements"
          value={specifications.length}
          helper="Normalized BA requirements currently available in this project."
        />
        <OverviewMetric
          label="Covered"
          value={coveredRequirementCount}
          helper="Requirements linked to at least one test case."
        />
        <OverviewMetric
          label="Uncovered"
          value={uncoveredRequirementCount}
          helper="Requirements that still need case-level traceability."
        />
        <OverviewMetric
          label="Suites"
          value={suites.length}
          helper="Manual suites ready for scenario and case design."
        />
        <OverviewMetric
          label="Scenarios"
          value={totalScenarioCount}
          helper="Scenario volume across the current suite hierarchy."
        />
        <OverviewMetric
          label="Cases"
          value={totalCaseCount}
          helper="Current case volume across all suites in the project."
        />
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.3fr)_minmax(320px,0.7fr)]">
        <div className="rounded-[28px] border border-border bg-surface p-6 shadow-sm">
          <WorkspaceSectionTitle
            title="Project summary"
            description="This project workspace brings together BA sources, requirement records, team members, and the manual qTest-like test design structure."
          />
          <dl className="mt-6 grid gap-4 md:grid-cols-2">
            <div className="rounded-2xl border border-border bg-bg p-4"><dt className="text-xs font-semibold uppercase tracking-[0.18em] text-muted">Team</dt><dd className="mt-2 text-sm font-semibold text-text">{project.team_name}</dd></div>
            <div className="rounded-2xl border border-border bg-bg p-4"><dt className="text-xs font-semibold uppercase tracking-[0.18em] text-muted">Organisation</dt><dd className="mt-2 text-sm font-semibold text-text">{project.organization_name}</dd></div>
            <div className="rounded-2xl border border-border bg-bg p-4"><dt className="text-xs font-semibold uppercase tracking-[0.18em] text-muted">Created by</dt><dd className="mt-2 text-sm font-semibold text-text">{project.created_by_name ?? "-"}</dd></div>
            <div className="rounded-2xl border border-border bg-bg p-4"><dt className="text-xs font-semibold uppercase tracking-[0.18em] text-muted">Last updated</dt><dd className="mt-2 text-sm font-semibold text-text">{formatDate(project.updated_at)}</dd></div>
          </dl>
        </div>

        <div className="rounded-[28px] border border-border bg-surface p-6 shadow-sm">
          <WorkspaceSectionTitle
            title="How To Work Here"
            description="The product keeps raw business artifacts separate from QA-owned design and execution."
          />
          <div className="mt-6 space-y-3">
            <div className="rounded-2xl border border-border bg-bg p-4">
              <p className="text-sm font-semibold text-text">1. Requirements</p>
              <p className="mt-2 text-sm leading-6 text-muted">
                Review BA sources as read-only artifacts, then inspect the normalized
                requirements created from them.
              </p>
            </div>
            <div className="rounded-2xl border border-border bg-bg p-4">
              <p className="text-sm font-semibold text-text">2. Test design</p>
              <p className="mt-2 text-sm leading-6 text-muted">
                Build the editable QA hierarchy through folders, suites, scenarios, and
                test cases with requirement-level traceability.
              </p>
            </div>
            <div className="rounded-2xl border border-border bg-bg p-4">
              <p className="text-sm font-semibold text-text">3. Execution</p>
              <p className="mt-2 text-sm leading-6 text-muted">
                Attach automation scripts only where needed and inspect execution history
                from the selected test case.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );

  const renderSpecifications = () => (
    <div className="space-y-4">
      <WorkspaceSectionTitle
        title="Requirements"
        description="Open each BA source, review the requirement records created from it, and inspect the suites and cases linked to each requirement."
        actions={<Button variant="secondary" onClick={() => navigate(isAdminShell ? "/admin/specifications" : "/specifications")}>Open Import Hub</Button>}
      />

      {specificationTreeGroups.length === 0 ? (
        <EmptyState
          icon={<ProjectWorkspaceIcon />}
          title="No requirement sources in this project yet"
          description="Import a BA specification file in the global hub, then the original source and its requirement records will appear in this project tree."
          primaryAction={<Button onClick={() => navigate(isAdminShell ? "/admin/specifications" : "/specifications")}>Open Specifications</Button>}
        />
      ) : (
        <RequirementDetailPanel
          selectedGroup={selectedSpecificationTreeGroup}
          selectedSpecification={selectedProjectSpecification}
          selectedSourceDetail={selectedSpecificationSourceDetail}
          isSourceLoading={isSpecificationSourceLoading}
          linkedSuites={linkedSuitesForSelectedSpecification}
          onOpenSuites={() => navigate(`${baseProjectsPath}/${projectId}/test-suites`)}
          onOpenRequirement={(specificationId) => {
            setSelectedSpecificationId(specificationId);
          }}
        />
      )}
    </div>
  );

  const renderMembers = () => (
    <div className="space-y-6">
      <WorkspaceSectionTitle title="Project members" description="These are the people assigned directly to this project on top of their team membership." />

      {canManageProject ? (
        <form onSubmit={(event) => void handleAddProjectMember(event)} className="rounded-[28px] border border-border bg-surface p-5 shadow-sm">
          <div className="grid gap-4 md:grid-cols-[2fr_1fr_auto]">
            <FormSelect id="project-workspace-member-user" label="User" value={memberForm.userId} onChange={(event) => setMemberForm((previous) => ({ ...previous, userId: event.target.value }))} options={projectMemberOptions} placeholder="Select a team member" disabled={projectMemberOptions.length === 0} />
            <FormSelect id="project-workspace-member-role" label="Project role" value={memberForm.role} onChange={(event) => setMemberForm((previous) => ({ ...previous, role: event.target.value as ProjectMemberRole }))} options={PROJECT_MEMBER_ROLE_OPTIONS} />
            <div className="self-end"><Button type="submit" isLoading={isSaving} loadingText="Adding..." disabled={projectMemberOptions.length === 0}>Add Member</Button></div>
          </div>
          {projectMemberOptions.length === 0 ? <p className="mt-3 text-sm text-muted">All available team members are already assigned to this project.</p> : null}
        </form>
      ) : null}

      <div className="overflow-hidden rounded-[28px] border border-border bg-surface shadow-sm">
        {projectMembers.length === 0 ? (
          <div className="p-6 text-sm text-muted">No project members found.</div>
        ) : (
          <table className="min-w-full divide-y divide-border">
            <thead className="bg-bg">
              <tr>
                <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-[0.18em] text-muted">Name</th>
                <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-[0.18em] text-muted">Email</th>
                <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-[0.18em] text-muted">User role</th>
                <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-[0.18em] text-muted">Project role</th>
                <th className="px-6 py-4 text-right text-xs font-semibold uppercase tracking-[0.18em] text-muted">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {projectMembers.map((member) => {
                const isBusy = updatingMemberId === member.id || deletingMemberId === member.id;

                return (
                  <tr key={member.id} className="transition hover:bg-bg">
                    <td className="px-6 py-4 text-sm font-semibold text-text">{member.full_name}</td>
                    <td className="px-6 py-4 text-sm text-muted">{member.email}</td>
                    <td className="px-6 py-4 text-sm text-muted">{member.user_role}</td>
                    <td className="px-6 py-4 text-sm text-muted">
                      {canManageProject ? (
                        <select value={member.role} onChange={(event) => void handleProjectMemberRoleChange(member, event.target.value as ProjectMemberRole)} disabled={isBusy} className="w-full rounded-2xl border border-border bg-surface px-3 py-2 text-sm text-text outline-none transition focus-visible:ring-4 focus-visible:ring-primary-light/20">
                          {PROJECT_MEMBER_ROLE_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
                        </select>
                      ) : member.role}
                    </td>
                    <td className="px-6 py-4 text-right text-sm">{canManageProject ? <Button variant="danger" size="sm" onClick={() => void handleRemoveProjectMember(member)} isLoading={deletingMemberId === member.id} loadingText="Removing...">Remove</Button> : <span className="text-muted">View only</span>}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );

  const renderTestSuites = () => (
    <div className="space-y-6">
          <WorkspaceSectionTitle
            title="Test design"
            description="Use the left explorer to move through folders, suites, scenarios, and cases without losing project context."
            actions={canManageProject ? <Button onClick={openSuiteCreateModal}>New Suite</Button> : null}
          />

          {suites.length === 0 ? (
            <EmptyState
              icon={<ProjectWorkspaceIcon />}
              title="No suites in this project yet"
              description="Create the first suite to start organizing scenarios and test cases around this project's requirements."
              primaryAction={canManageProject ? <Button onClick={openSuiteCreateModal}>Create Suite</Button> : undefined}
            />
          ) : (
            <div className="grid gap-6 2xl:grid-cols-[minmax(0,1.1fr)_360px]">
              <section className="space-y-6">
                {selectedSuite ? (
                  <article className="rounded-[28px] border border-border bg-surface p-6 shadow-sm">
                    <div className="flex flex-wrap items-start justify-between gap-4">
                      <div>
                        <div className="flex flex-wrap items-center gap-2">
                          <Badge variant={getSuiteStatusVariant(selectedSuite.pass_rate)}>{selectedSuite.pass_rate}% pass rate</Badge>
                          <Badge variant="tag">{selectedSuite.folder_path || "Unfiled"}</Badge>
                          {selectedSuite.linked_specification_count > 0 ? <Badge variant="tag">{selectedSuite.linked_specification_count} linked requirement{selectedSuite.linked_specification_count === 1 ? "" : "s"}</Badge> : null}
                        </div>
                        <h3 className="mt-4 text-2xl font-semibold tracking-tight text-text">{selectedSuite.name}</h3>
                        <p className="mt-2 text-sm leading-6 text-muted">{selectedSuite.description || "No suite description provided yet."}</p>
                      </div>
                      {canManageProject ? (
                        <div className="flex flex-wrap gap-3">
                          <Button variant="secondary" onClick={() => openSuiteEditModal(selectedSuite)}>Edit Suite</Button>
                          <Button variant="secondary" onClick={openScenarioCreateModal}>Add Scenario</Button>
                          <Button variant="danger" onClick={() => void handleDeleteSuite(selectedSuite)} isLoading={deletingSuiteId === selectedSuite.id} loadingText="Deleting...">Delete Suite</Button>
                        </div>
                      ) : null}
                    </div>

                    <div className="mt-6 grid gap-4 md:grid-cols-3">
                      <div className="rounded-2xl border border-border bg-bg p-4"><p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted">Scenarios</p><p className="mt-2 text-2xl font-semibold text-text">{selectedSuite.scenario_count}</p></div>
                      <div className="rounded-2xl border border-border bg-bg p-4"><p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted">Cases</p><p className="mt-2 text-2xl font-semibold text-text">{selectedSuite.total_case_count}</p></div>
                      <div className="rounded-2xl border border-border bg-bg p-4"><p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted">Primary requirement</p><p className="mt-2 text-sm font-semibold text-text">{selectedSuite.specification_title || "Not set"}</p></div>
                    </div>

                    {getLinkedSpecificationsForSuite(selectedSuite).length > 0 ? (
                      <div className="mt-5 flex flex-wrap gap-2">
                        {getLinkedSpecificationsForSuite(selectedSuite).map((specification) => (
                          <span key={specification.id} className="rounded-full border border-border bg-bg px-2.5 py-1 text-[11px] font-semibold text-primary">{specification.external_reference || specification.title}</span>
                        ))}
                      </div>
                    ) : null}
                  </article>
                ) : (
                  <div className="rounded-[28px] border border-dashed border-border bg-surface p-6 text-sm text-muted shadow-sm">Select a suite from the project tree to inspect its design structure.</div>
                )}

                <article className="rounded-[28px] border border-border bg-surface p-6 shadow-sm">
                  <div className="flex flex-wrap items-start justify-between gap-4">
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted">Scenario</p>
                      <h3 className="mt-2 text-xl font-semibold tracking-tight text-text">{selectedScenario?.title || "Select a scenario"}</h3>
                    </div>
                    {selectedScenario && canManageProject ? (
                      <div className="flex flex-wrap gap-2">
                        <Button variant="secondary" size="sm" onClick={() => openScenarioEditModal(selectedScenario)}>Edit</Button>
                        <Button variant="secondary" size="sm" onClick={() => void handleCloneScenario(selectedScenario)} isLoading={cloningScenarioId === selectedScenario.id} loadingText="Cloning...">Clone</Button>
                        <Button variant="danger" size="sm" onClick={() => void handleDeleteScenario(selectedScenario)} isLoading={deletingScenarioId === selectedScenario.id} loadingText="Deleting...">Delete</Button>
                      </div>
                    ) : null}
                  </div>

                  {!selectedSuite ? (
                    <div className="mt-5 rounded-2xl border border-dashed border-border bg-bg p-5 text-sm text-muted">Select a suite from the left tree to focus its scenarios.</div>
                  ) : isScenarioLoading ? (
                    <div className="flex min-h-[180px] items-center justify-center"><LoadingSpinner size="lg" /></div>
                  ) : !selectedScenario ? (
                    <div className="mt-5 rounded-2xl border border-dashed border-border bg-bg p-5 text-sm text-muted">No scenarios are available in the selected suite yet.</div>
                  ) : (
                    <>
                      <p className="mt-2 text-sm leading-6 text-muted">{selectedScenario.description || "No scenario description provided yet."}</p>
                      <div className="mt-5 flex flex-wrap items-center gap-2">
                        <Badge variant={getPriorityVariant(selectedScenario.priority)}>{selectedScenario.priority.replaceAll("_", " ")}</Badge>
                        {selectedScenario.business_priority ? <Badge variant="tag">{selectedScenario.business_priority.replaceAll("_", " ")}</Badge> : null}
                        <Badge variant="tag">{selectedScenario.scenario_type.replaceAll("_", " ")}</Badge>
                        <Badge variant={selectedScenario.polarity === "positive" ? "verified" : "warm"}>{selectedScenario.polarity}</Badge>
                        <Badge variant="tag">{selectedScenario.case_count} cases, {selectedScenario.pass_rate}% pass rate</Badge>
                      </div>

                      {selectedScenario.linked_specifications.length > 0 ? (
                        <div className="mt-4 flex flex-wrap gap-2">
                          {selectedScenario.linked_specifications.map((specification) => (
                            <span key={specification.id} className="rounded-full border border-border bg-bg px-2.5 py-1 text-[11px] font-semibold text-primary">{specification.external_reference || specification.title}</span>
                          ))}
                        </div>
                      ) : null}
                    </>
                  )}
                </article>

                <article className="rounded-[28px] border border-border bg-surface p-6 shadow-sm">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted">Test cases</p>
                      <p className="mt-1 text-sm text-muted">Focus on the currently selected scenario instead of expanding the full tree.</p>
                    </div>
                    {selectedScenario && canManageProject ? <Button size="sm" onClick={openCaseCreateModal}>Add Test Case</Button> : null}
                  </div>

                  {!selectedScenario ? (
                    <div className="mt-5 rounded-2xl border border-dashed border-border bg-bg p-5 text-sm text-muted">Select a scenario from the left tree to manage its test cases.</div>
                  ) : isCaseLoading ? (
                    <div className="flex min-h-[180px] items-center justify-center"><LoadingSpinner size="lg" /></div>
                  ) : cases.length === 0 ? (
                    <div className="mt-5 rounded-2xl border border-dashed border-border bg-bg p-5 text-sm text-muted">No cases in this scenario yet.</div>
                  ) : (
                    <div className="mt-5 space-y-3">
                      {cases.map((testCase) => {
                        const isSelectedCase = selectedCase?.id === testCase.id;

                        return (
                          <button key={testCase.id} type="button" onClick={() => setSelectedCaseId(testCase.id)} className={`w-full rounded-2xl border px-4 py-4 text-left transition ${isSelectedCase ? "border-primary bg-primary text-white" : "border-border bg-bg text-text hover:border-primary-light/30 hover:bg-primary-light/10"}`}>
                            <div className="flex flex-wrap items-center gap-2">
                              <Badge variant={isSelectedCase ? "automated" : getCaseStatusVariant(testCase.status)}>{testCase.status}</Badge>
                              <Badge variant={isSelectedCase ? "automated" : getAutomationBadgeVariant(testCase.automation_status)}>{testCase.automation_status.replaceAll("_", " ")}</Badge>
                              <span className={`text-xs font-semibold ${isSelectedCase ? "text-white/80" : "text-muted"}`}>v{testCase.version}</span>
                            </div>
                            <div className="mt-3">
                              <p className="truncate text-sm font-semibold tracking-tight">{testCase.title}</p>
                              <p className={`mt-1 truncate text-xs ${isSelectedCase ? "text-white/80" : "text-muted"}`}>{parseCaseStepsPreview(testCase)}</p>
                              {testCase.linked_specifications.length > 0 ? (
                                <div className="mt-2 flex flex-wrap gap-2">
                                  {testCase.linked_specifications.map((specification) => (
                                    <span key={specification.id} className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${isSelectedCase ? "bg-white/15 text-white" : "border border-border bg-surface text-primary"}`}>{specification.external_reference || specification.title}</span>
                                  ))}
                                </div>
                              ) : null}
                            </div>
                          </button>
                        );
                      })}
                    </div>
                  )}
                </article>
              </section>

              <aside className="rounded-[28px] border border-border bg-surface p-5 shadow-sm">
                <WorkspaceSectionTitle title="Test case detail" description="Inspect the selected case without leaving the suite browser." actions={selectedCase && canManageProject ? <Button variant="secondary" size="sm" onClick={() => openCaseEditModal(selectedCase)}>Edit Case</Button> : null} />

                {selectedCase ? (
                  <div className="mt-6 space-y-5">
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge variant={getCaseStatusVariant(selectedCase.status)}>{selectedCase.status}</Badge>
                        <Badge variant={getAutomationBadgeVariant(selectedCase.automation_status)}>{selectedCase.automation_status.replaceAll("_", " ")}</Badge>
                        <span className="rounded-full border border-border bg-bg px-2.5 py-1 text-xs font-semibold text-muted">v{selectedCase.version}</span>
                      </div>
                      <h3 className="mt-3 text-lg font-semibold tracking-tight text-text">{selectedCase.title}</h3>
                      <p className="mt-2 text-sm text-muted">Updated {formatDate(selectedCase.updated_at)}</p>
                    </div>

                    <div className="space-y-4">
                      <div className="rounded-2xl border border-border bg-bg p-4">
                        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted">Linked requirements</p>
                        {selectedCase.linked_specifications.length === 0 ? (
                          <p className="mt-2 text-sm leading-6 text-muted">No requirement is linked to this case yet.</p>
                        ) : (
                          <div className="mt-3 flex flex-wrap gap-2">{selectedCase.linked_specifications.map((specification) => <span key={specification.id} className="rounded-full border border-border bg-surface px-3 py-1 text-xs font-semibold text-primary">{specification.external_reference || specification.title}</span>)}</div>
                        )}
                      </div>
                      <div className="rounded-2xl border border-border bg-bg p-4"><p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted">Preconditions</p><p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-text">{selectedCase.preconditions || "No preconditions documented."}</p></div>
                      <div className="rounded-2xl border border-border bg-bg p-4"><p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted">Expected result</p><p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-text">{selectedCase.expected_result || "No expected result documented."}</p></div>
                      <div className="rounded-2xl border border-border bg-bg p-4"><p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted">Gherkin preview</p><pre className="mt-2 overflow-x-auto whitespace-pre-wrap text-xs leading-6 text-text">{selectedCase.gherkin_preview}</pre></div>
                      <div className="rounded-2xl border border-border bg-bg p-4">
                        <div className="flex flex-wrap items-start justify-between gap-3">
                          <div>
                            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted">Automation</p>
                            <p className="mt-2 text-sm leading-6 text-muted">
                              Store one or more scripts for this case and trigger local executions through the worker.
                            </p>
                          </div>
                          {canManageProject ? (
                            <div className="flex flex-wrap gap-2">
                              <Button variant="secondary" size="sm" onClick={openScriptCreateModal}>
                                Add Script
                              </Button>
                              <Button
                                size="sm"
                                onClick={() => setIsRunExecutionModalOpen(true)}
                                isLoading={runningExecutionId === selectedCase.id}
                                disabled={automationScripts.length === 0}
                              >
                                Run Test Case
                              </Button>
                            </div>
                          ) : null}
                        </div>

                        {isAutomationLoading ? (
                          <div className="mt-5 flex min-h-[140px] items-center justify-center">
                            <LoadingSpinner size="lg" />
                          </div>
                        ) : (
                          <div className="mt-5 space-y-4">
                            <div>
                              <div className="flex flex-wrap items-center justify-between gap-2">
                                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted">
                                  Scripts
                                </p>
                                {activeAutomationScript ? (
                                  <Badge variant="automated">
                                    Active {getScriptSummaryLabel(activeAutomationScript)}
                                  </Badge>
                                ) : (
                                  <Badge variant="unverified">No active script</Badge>
                                )}
                              </div>

                              {automationScripts.length === 0 ? (
                                <div className="mt-3 rounded-2xl border border-dashed border-border bg-surface p-4 text-sm text-muted">
                                  No automation script is linked to this test case yet.
                                </div>
                              ) : (
                                <div className="mt-3 space-y-3">
                                  {automationScripts.map((script) => (
                                    <div
                                      key={script.id}
                                      className="rounded-2xl border border-border bg-surface p-4"
                                    >
                                      <div className="flex flex-wrap items-center justify-between gap-3">
                                        <div>
                                          <div className="flex flex-wrap items-center gap-2">
                                            <Badge variant={script.is_active ? "automated" : "tag"}>
                                              {script.is_active ? "active" : "inactive"}
                                            </Badge>
                                            <Badge variant="tag">{getScriptSummaryLabel(script)}</Badge>
                                          </div>
                                          <p className="mt-2 text-sm font-semibold text-text">
                                            Stored {formatDate(script.created_at)}
                                          </p>
                                        </div>

                                        <div className="flex flex-wrap gap-2">
                                          <Button
                                            variant="secondary"
                                            size="sm"
                                            onClick={() => void handleValidateScript(script)}
                                            isLoading={validatingScriptId === script.id}
                                            loadingText="Checking..."
                                          >
                                            Validate
                                          </Button>
                                          {canManageProject ? (
                                            <>
                                              <Button
                                                variant="secondary"
                                                size="sm"
                                                onClick={() => openScriptEditModal(script)}
                                              >
                                                Edit
                                              </Button>
                                              <Button
                                                variant="secondary"
                                                size="sm"
                                                onClick={() => void handleToggleScriptActive(script)}
                                                isLoading={switchingScriptId === script.id}
                                                loadingText="Updating..."
                                              >
                                                {script.is_active ? "Deactivate" : "Activate"}
                                              </Button>
                                              <Button
                                                variant="danger"
                                                size="sm"
                                                onClick={() => void handleDeleteScript(script)}
                                                isLoading={deletingScriptId === script.id}
                                                loadingText="Deleting..."
                                              >
                                                Delete
                                              </Button>
                                            </>
                                          ) : null}
                                        </div>
                                      </div>
                                      {script.validation?.warnings?.length ? (
                                        <p className="mt-3 text-xs leading-6 text-muted">
                                          {script.validation.warnings.join(" ")}
                                        </p>
                                      ) : null}
                                    </div>
                                  ))}
                                </div>
                              )}
                            </div>

                            <div>
                              <div className="flex flex-wrap items-center justify-between gap-2">
                                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted">
                                  Execution history
                                </p>
                                {selectedCase.latest_result_status ? (
                                  <Badge variant={getExecutionStatusVariant(selectedCase.latest_result_status as TestExecution["status"])}>
                                    latest result {selectedCase.latest_result_status}
                                  </Badge>
                                ) : null}
                              </div>

                              {testExecutions.length === 0 ? (
                                <div className="mt-3 rounded-2xl border border-dashed border-border bg-surface p-4 text-sm text-muted">
                                  No execution has been recorded for this test case yet.
                                </div>
                              ) : (
                                <div className="mt-3 space-y-3">
                                  {testExecutions.map((execution) => (
                                    <div
                                      key={execution.id}
                                      className={`rounded-2xl border bg-surface p-4 transition ${
                                        selectedExecution?.id === execution.id
                                          ? "border-primary shadow-sm"
                                          : "border-border"
                                      }`}
                                    >
                                      <div className="flex flex-wrap items-start justify-between gap-3">
                                        <button
                                          type="button"
                                          className="min-w-0 flex-1 text-left"
                                          onClick={() => setSelectedExecutionId(execution.id)}
                                        >
                                          <div className="flex flex-wrap items-center gap-2">
                                            <Badge variant={getExecutionStatusVariant(execution.status)}>
                                              {execution.status}
                                            </Badge>
                                            <Badge variant="tag">
                                              {execution.browser} / {execution.platform}
                                            </Badge>
                                            <Badge variant="tag">
                                              {execution.trigger_type.replaceAll("_", " ")}
                                            </Badge>
                                            {selectedExecution?.id === execution.id ? (
                                              <Badge variant="automated">Viewing details</Badge>
                                            ) : null}
                                          </div>
                                          <p className="mt-2 text-sm font-semibold text-text">
                                            Started {formatDate(execution.started_at)}
                                          </p>
                                          <p className="mt-1 text-xs text-muted">
                                            Finished {formatDate(execution.ended_at)} • {execution.duration_ms ?? 0} ms
                                          </p>
                                        </button>

                                        {canManageProject ? (
                                          <div className="flex flex-wrap gap-2">
                                            {execution.status === "running" ? (
                                              <Button
                                                variant="secondary"
                                                size="sm"
                                                onClick={() => void handleExecutionControl(execution, "pause")}
                                                isLoading={runningExecutionId === execution.id}
                                                loadingText="Updating..."
                                              >
                                                Pause
                                              </Button>
                                            ) : null}
                                            {execution.status === "paused" ? (
                                              <Button
                                                variant="secondary"
                                                size="sm"
                                                onClick={() => void handleExecutionControl(execution, "resume")}
                                                isLoading={runningExecutionId === execution.id}
                                                loadingText="Updating..."
                                              >
                                                Resume
                                              </Button>
                                            ) : null}
                                            {execution.status === "queued" ||
                                            execution.status === "running" ||
                                            execution.status === "paused" ? (
                                              <Button
                                                variant="danger"
                                                size="sm"
                                                onClick={() => void handleExecutionControl(execution, "stop")}
                                                isLoading={runningExecutionId === execution.id}
                                                loadingText="Stopping..."
                                              >
                                                Stop
                                              </Button>
                                            ) : null}
                                            {execution.status === "failed" ||
                                            execution.status === "error" ||
                                            execution.status === "cancelled" ? (
                                              <Button
                                                variant="danger"
                                                size="sm"
                                                onClick={() => void handleDeleteExecution(execution)}
                                                isLoading={deletingExecutionId === execution.id}
                                                loadingText="Deleting..."
                                              >
                                                Delete
                                              </Button>
                                            ) : null}
                                            {selectedExecution?.id !== execution.id ? (
                                              <Button
                                                variant="secondary"
                                                size="sm"
                                                onClick={() => setSelectedExecutionId(execution.id)}
                                              >
                                                Details
                                              </Button>
                                            ) : null}
                                          </div>
                                        ) : null}
                                      </div>

                                      {execution.result ? (
                                        <div className="mt-4 grid gap-3 md:grid-cols-3">
                                          <div className="rounded-2xl border border-border bg-bg p-3">
                                            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted">
                                              Result
                                            </p>
                                            <p className="mt-2 text-sm font-semibold text-text">
                                              {execution.result.status}
                                            </p>
                                          </div>
                                          <div className="rounded-2xl border border-border bg-bg p-3">
                                            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted">
                                              Step summary
                                            </p>
                                            <p className="mt-2 text-sm font-semibold text-text">
                                              {execution.result.passed_steps}/{execution.result.total_steps} passed
                                            </p>
                                          </div>
                                          <div className="rounded-2xl border border-border bg-bg p-3">
                                            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted">
                                              Issues
                                            </p>
                                            <p className="mt-2 text-sm font-semibold text-text">
                                              {execution.result.issues_count}
                                            </p>
                                          </div>
                                        </div>
                                      ) : null}

                                      {execution.result?.error_message ? (
                                        <div className="mt-3 rounded-2xl border border-warm/20 bg-warm/10 p-3 text-sm leading-6 text-warm">
                                          {execution.result.error_message}
                                        </div>
                                      ) : null}
                                    </div>
                                  ))}
                                </div>
                              )}

                              <div className="mt-4">
                                <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted">
                                    Execution details
                                  </p>
                                  {/* Temporary live-monitoring indicator. It reflects the
                                      polling-based detail refresh, not true browser streaming. */}
                                  {isSelectedExecutionLive ? (
                                    <span className="text-xs font-semibold text-muted">
                                      Auto-refreshing every 2.5s
                                    </span>
                                  ) : null}
                                </div>
                                <ExecutionDetailPanel
                                  execution={selectedExecution}
                                  steps={executionSteps}
                                  stdoutLog={stdoutLog}
                                  stderrLog={stderrLog}
                                  latestScreenshotUrl={latestExecutionScreenshotUrl}
                                  isLoading={isExecutionDetailLoading}
                                  isLive={isSelectedExecutionLive}
                                />
                              </div>
                            </div>
                          </div>
                        )}
                      </div>
                    </div>

                    {canManageProject ? <div className="flex gap-3"><Button variant="secondary" onClick={() => openCaseEditModal(selectedCase)}>Edit</Button><Button variant="danger" onClick={() => void handleDeleteCase(selectedCase)} isLoading={deletingCaseId === selectedCase.id} loadingText="Deleting...">Delete</Button></div> : null}
                  </div>
                ) : (
                  <div className="mt-6 rounded-[24px] border border-dashed border-border bg-bg p-6 text-sm text-muted">Select a scenario and test case to inspect its details here.</div>
                )}
              </aside>
            </div>
          )}
        </div>
  );

  const renderSidebarContent = () => {
    if (currentTab === "specifications") {
      return specificationTreeGroups.length > 0 ? (
        <RequirementsTreePanel
          groups={specificationTreeGroups}
          selectedGroupKey={selectedSpecificationTreeGroupKey}
          selectedSpecificationId={selectedSpecificationId}
          onSelectGroup={(groupKey) => {
            setSelectedSpecificationTreeGroupKey(groupKey);
            setSelectedSpecificationId("");
          }}
          onSelectSpecification={(groupKey, specificationId) => {
            setSelectedSpecificationTreeGroupKey(groupKey);
            setSelectedSpecificationId(specificationId);
          }}
          embedded
        />
      ) : (
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted">
            Requirements tree
          </p>
          <p className="mt-2 text-sm leading-6 text-muted">
            Imported BA sources and normalized requirements will appear here.
          </p>
          <p className="mt-5 rounded-2xl border border-dashed border-border bg-bg px-4 py-4 text-sm text-muted">
            No requirement sources are available in this project yet.
          </p>
        </div>
      );
    }

    if (currentTab === "test-suites") {
      return (
        <TestDesignTreePanel
          folderGroups={folderGroups}
          suites={suites}
          scenarios={scenarios}
          cases={cases}
          selectedFolder={selectedFolder}
          selectedSuiteId={selectedSuite?.id ?? ""}
          selectedScenarioId={selectedScenario?.id ?? ""}
          selectedCaseId={selectedCase?.id ?? ""}
          onSelectFolder={setSelectedFolder}
          onSelectSuite={setSelectedSuiteId}
          onSelectScenario={setSelectedScenarioId}
          onSelectCase={setSelectedCaseId}
          embedded
        />
      );
    }

    if (currentTab === "members") {
      return (
        <div className="space-y-3">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted">
            Membership guide
          </p>
          <div className="rounded-2xl border border-border bg-bg p-4">
            <p className="text-sm font-semibold text-text">Project assignment</p>
            <p className="mt-2 text-sm leading-6 text-muted">
              Team membership answers who belongs to the team. Project membership
              answers who can work in this project.
            </p>
          </div>
          <div className="rounded-2xl border border-border bg-bg p-4">
            <p className="text-sm font-semibold text-text">Current access</p>
            <p className="mt-2 text-sm leading-6 text-muted">
              {projectMembers.length} member{projectMembers.length === 1 ? "" : "s"}{" "}
              currently assigned at project level.
            </p>
          </div>
        </div>
      );
    }

    return (
      <div className="space-y-3">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted">
          Workspace flow
        </p>
        <div className="rounded-2xl border border-border bg-bg p-4">
          <p className="text-sm font-semibold text-text">Requirements first</p>
          <p className="mt-2 text-sm leading-6 text-muted">
            Keep BA source artifacts authoritative and read-only for QA.
          </p>
        </div>
        <div className="rounded-2xl border border-border bg-bg p-4">
          <p className="text-sm font-semibold text-text">Traceability at case level</p>
          <p className="mt-2 text-sm leading-6 text-muted">
            Coverage is driven by linked test cases, not only suite-level context.
          </p>
        </div>
        <div className="rounded-2xl border border-border bg-bg p-4">
          <p className="text-sm font-semibold text-text">Automation later</p>
          <p className="mt-2 text-sm leading-6 text-muted">
            Execution augments the manual-first foundation instead of replacing it.
          </p>
        </div>
      </div>
    );
  };

  const renderActiveContent = () => {
    if (currentTab === "specifications") {
      return renderSpecifications();
    }

    if (currentTab === "members") {
      return renderMembers();
    }

    if (currentTab === "test-suites") {
      return renderTestSuites();
    }

    return renderOverview();
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-2 text-sm text-muted">
        <Link to={baseProjectsPath} className="hover:text-primary">
          Projects
        </Link>
        <span>/</span>
        <span className="font-medium text-text">{project.name}</span>
      </div>

      <section className="rounded-[32px] border border-border bg-surface p-7 shadow-panel xl:p-8">
        <div className="flex flex-wrap items-start justify-between gap-6">
          <div className="max-w-4xl">
            <div className="flex flex-wrap items-center gap-3">
              <Badge variant={project.status === "active" ? "verified" : "warm"}>
                {project.status}
              </Badge>
              <Badge variant="tag">{project.organization_name}</Badge>
              <Badge variant="tag">{project.team_name}</Badge>
            </div>
            <h1 className="mt-4 text-4xl font-semibold tracking-tight text-text">
              {project.name}
            </h1>
            <p className="mt-4 text-sm leading-7 text-muted">
              {project.description ||
                "This project workspace connects imported BA sources, normalized requirements, project members, and manual-first QA design in one place."}
            </p>
          </div>

          <div className="grid w-full gap-3 sm:grid-cols-3 xl:w-auto xl:min-w-[360px]">
            <div className="rounded-2xl border border-border bg-bg p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted">
                Requirements
              </p>
              <p className="mt-2 text-2xl font-semibold text-text">
                {specifications.length}
              </p>
              <p className="mt-1 text-sm text-muted">{coveredRequirementCount} covered</p>
            </div>
            <div className="rounded-2xl border border-border bg-bg p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted">
                Test cases
              </p>
              <p className="mt-2 text-2xl font-semibold text-text">{totalCaseCount}</p>
              <p className="mt-1 text-sm text-muted">{suites.length} suites</p>
            </div>
            <div className="rounded-2xl border border-border bg-bg p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted">
                Members
              </p>
              <p className="mt-2 text-2xl font-semibold text-text">
                {projectMembers.length}
              </p>
              <p className="mt-1 text-sm text-muted">project-level access</p>
            </div>
          </div>
        </div>
      </section>

      {successMessage ? (
        <div className="rounded-2xl border border-status-verified-text/15 bg-status-verified-bg px-4 py-3 text-sm text-status-verified-text shadow-sm">
          {successMessage}
        </div>
      ) : null}

      {errorMessage ? (
        <ErrorMessage
          message={errorMessage}
          onDismiss={() => setErrorMessage("")}
        />
      ) : null}

      <ProjectWorkspaceSplitLayout
        explorer={
          <ProjectSectionExplorer
            project={project}
            tabs={workspaceTabs}
            currentTab={currentTab}
            projectMembersCount={projectMembers.length}
            requirementsCount={specifications.length}
            coveredRequirementCount={coveredRequirementCount}
            suiteCount={suites.length}
            scenarioCount={totalScenarioCount}
            caseCount={totalCaseCount}
          >
            {renderSidebarContent()}
          </ProjectSectionExplorer>
        }
        content={renderActiveContent()}
      />

      <Modal
        isOpen={isSuiteModalOpen}
        onClose={closeSuiteModal}
        title={editingSuite ? "Edit Test Suite" : "Create Test Suite"}
        size="lg"
      >
        <form onSubmit={(event) => void handleSuiteSubmit(event)} className="space-y-4">
          <FormInput
            id="workspace-suite-name"
            label="Suite name"
            value={suiteForm.name}
            onChange={(event) =>
              setSuiteForm((previous) => ({
                ...previous,
                name: event.target.value,
              }))
            }
            required
          />
          <FormInput
            id="workspace-suite-folder-path"
            label="Folder path"
            value={suiteForm.folderPath}
            onChange={(event) =>
              setSuiteForm((previous) => ({
                ...previous,
                folderPath: event.target.value,
              }))
            }
            helperText="Use slash-separated folders such as Core/Login."
            placeholder="Core/Login"
          />
          <FormSelect
            id="workspace-suite-specification"
            label="Linked specification"
            value={suiteForm.specification}
            onChange={(event) =>
              setSuiteForm((previous) => ({
                ...previous,
                specification: event.target.value,
              }))
            }
            options={specificationOptions}
          />
          <div>
            <label
              htmlFor="workspace-suite-description"
              className="mb-2 block text-xs font-semibold uppercase tracking-[0.18em] text-muted"
            >
              Description
            </label>
            <textarea
              id="workspace-suite-description"
              value={suiteForm.description}
              onChange={(event) =>
                setSuiteForm((previous) => ({
                  ...previous,
                  description: event.target.value,
                }))
              }
              rows={5}
              className="w-full rounded-2xl border border-border bg-surface px-4 py-3 text-sm leading-6 text-text outline-none transition placeholder:text-muted focus-visible:ring-4 focus-visible:ring-primary-light/20"
            />
          </div>
          <div className="flex justify-end gap-3">
            <Button variant="secondary" onClick={closeSuiteModal}>
              Cancel
            </Button>
            <Button type="submit" isLoading={isSaving} loadingText="Saving...">
              {editingSuite ? "Save Suite" : "Create Suite"}
            </Button>
          </div>
        </form>
      </Modal>

      <Modal
        isOpen={isScenarioModalOpen}
        onClose={closeScenarioModal}
        title={editingScenario ? "Edit Scenario" : "Create Scenario"}
        size="lg"
      >
        <form onSubmit={(event) => void handleScenarioSubmit(event)} className="space-y-4">
          <FormInput
            id="workspace-scenario-title"
            label="Title"
            value={scenarioForm.title}
            onChange={(event) =>
              setScenarioForm((previous) => ({
                ...previous,
                title: event.target.value,
              }))
            }
            required
          />
          <div>
            <label
              htmlFor="workspace-scenario-description"
              className="mb-2 block text-xs font-semibold uppercase tracking-[0.18em] text-muted"
            >
              Description
            </label>
            <textarea
              id="workspace-scenario-description"
              value={scenarioForm.description}
              onChange={(event) =>
                setScenarioForm((previous) => ({
                  ...previous,
                  description: event.target.value,
                }))
              }
              rows={5}
              className="w-full rounded-2xl border border-border bg-surface px-4 py-3 text-sm leading-6 text-text outline-none transition placeholder:text-muted focus-visible:ring-4 focus-visible:ring-primary-light/20"
            />
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            <FormSelect
              id="workspace-scenario-type"
              label="Scenario type"
              value={scenarioForm.scenarioType}
              onChange={(event) =>
                setScenarioForm((previous) => ({
                  ...previous,
                  scenarioType: event.target.value as TestScenarioType,
                }))
              }
              options={SCENARIO_TYPE_OPTIONS}
            />
            <FormSelect
              id="workspace-scenario-priority"
              label="Priority"
              value={scenarioForm.priority}
              onChange={(event) =>
                setScenarioForm((previous) => ({
                  ...previous,
                  priority: event.target.value as TestPriority,
                }))
              }
              options={PRIORITY_OPTIONS}
            />
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            <FormSelect
              id="workspace-scenario-business-priority"
              label="Business priority"
              value={scenarioForm.businessPriority}
              onChange={(event) =>
                setScenarioForm((previous) => ({
                  ...previous,
                  businessPriority: event.target.value as BusinessPriority | "",
                }))
              }
              options={BUSINESS_PRIORITY_OPTIONS}
              helperText="Optional MoSCoW classification from the business perspective."
            />
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            <FormSelect
              id="workspace-scenario-polarity"
              label="Polarity"
              value={scenarioForm.polarity}
              onChange={(event) =>
                setScenarioForm((previous) => ({
                  ...previous,
                  polarity: event.target.value as TestScenarioPolarity,
                }))
              }
              options={POLARITY_OPTIONS}
            />
            <FormInput
              id="workspace-scenario-order-index"
              label="Order index"
              type="number"
              min="0"
              value={scenarioForm.orderIndex}
              onChange={(event) =>
                setScenarioForm((previous) => ({
                  ...previous,
                  orderIndex: event.target.value,
                }))
              }
            />
          </div>
          <div className="flex justify-end gap-3">
            <Button variant="secondary" onClick={closeScenarioModal}>
              Cancel
            </Button>
            <Button type="submit" isLoading={isSaving} loadingText="Saving...">
              {editingScenario ? "Save Scenario" : "Create Scenario"}
            </Button>
          </div>
        </form>
      </Modal>

      <AutomationScriptEditorModal
        isOpen={isScriptModalOpen}
        onClose={closeScriptModal}
        onSubmit={handleScriptSubmit}
        testCaseId={selectedCase?.id ?? null}
        initialScript={editingScript}
        isSaving={isSaving}
      />

      <RunExecutionModal
        isOpen={isRunExecutionModalOpen}
        onClose={() => setIsRunExecutionModalOpen(false)}
        onSubmit={async (payload) => {
          setRunExecutionForm(payload);
          await handleRunExecution(payload);
        }}
        isSubmitting={runningExecutionId === selectedCase?.id}
        defaultBrowser={runExecutionForm.browser}
        defaultPlatform={runExecutionForm.platform}
      />

      <TestCaseEditorModal
        isOpen={isCaseModalOpen}
        onClose={closeCaseModal}
        onSubmit={handleCaseSubmit}
        isSaving={isSaving}
        initialCase={editingCase}
        scenarioTitle={selectedScenario?.title}
        specificationOptions={caseRequirementOptions}
      />
    </div>
  );
}





