import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  closeTestRun,
  executeRunCase,
  getRunCases,
  getTestPlans,
  getTestRuns,
  startTestRun,
  updateRunCaseStatus,
} from "../../../api/runs";
import type {
  RunCaseLatestExecution,
  RunScopeOption,
  TestPlan,
  TestRun,
  TestRunCase,
  TestRunCaseStatus,
} from "../../../types/runs";
import type { ProjectTree, TreeSection } from "../../../types/testing";
import { Badge, Button, EmptyState, ErrorMessage, Spinner } from "../../ui";
import {
  executionStatusTone,
  formatDateTime,
  formatLabel,
  resultTone,
} from "../repository/shared";
import CreateTestPlanModal from "./CreateTestPlanModal";
import CreateTestRunModal from "./CreateTestRunModal";
import ExpandRunScopeModal from "./ExpandRunScopeModal";

const MANUAL_STATUSES: TestRunCaseStatus[] = [
  "pending",
  "passed",
  "failed",
  "skipped",
  "cancelled",
];

interface ProjectTestRunsWorkspaceProps {
  projectId: string;
  projectTree: ProjectTree;
}

interface PlanSummary {
  totalRuns: number;
  totalCases: number;
  pendingRuns: number;
  runningRuns: number;
  passedRuns: number;
  failedRuns: number;
  averagePassRate: number;
}

function isExecutionLive(execution: RunCaseLatestExecution | null): boolean {
  if (!execution) return false;
  return (
    execution.status === "running" ||
    execution.status === "queued" ||
    execution.status === "paused"
  );
}

function formatDuration(ms: number | null | undefined): string {
  if (ms == null) return "-";
  if (ms < 1000) return `${ms} ms`;
  const seconds = ms / 1000;
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  const minutes = Math.floor(seconds / 60);
  const remainder = Math.floor(seconds % 60);
  return `${minutes}m ${remainder}s`;
}

function approvedCaseCount(value: { approved_case_count?: number; case_count?: number }) {
  return value.approved_case_count ?? value.case_count ?? 0;
}

function buildSuiteOptions(projectTree: ProjectTree): RunScopeOption[] {
  return projectTree.suites
    .map((suite) => ({
      id: suite.id,
      label: suite.name,
      caseCount: approvedCaseCount(suite.counts),
    }))
    .filter((option) => option.caseCount > 0);
}

function collectSectionOptions(
  sections: TreeSection[],
  suiteName: string,
  parents: string[] = [],
): RunScopeOption[] {
  const options: RunScopeOption[] = [];

  for (const section of sections) {
    const path = [...parents, section.name];
    const caseCount = approvedCaseCount(section.counts);

    if (caseCount > 0) {
      options.push({
        id: section.id,
        label: `${suiteName} / ${path.join(" / ")}`,
        caseCount,
      });
    }

    if (section.children.length > 0) {
      options.push(...collectSectionOptions(section.children, suiteName, path));
    }
  }

  return options;
}

function buildSectionOptions(projectTree: ProjectTree): RunScopeOption[] {
  return projectTree.suites.flatMap((suite) => collectSectionOptions(suite.sections, suite.name));
}

function computeRunSummary(runCases: TestRunCase[]) {
  const total = runCases.length;
  let passed = 0;
  let failed = 0;
  let running = 0;
  let pending = 0;
  let automated = 0;

  for (const runCase of runCases) {
    if (runCase.test_case_automation_status === "automated") automated += 1;
    if (runCase.status === "passed") passed += 1;
    else if (runCase.status === "failed" || runCase.status === "error") failed += 1;
    else if (runCase.status === "running") running += 1;
    else if (runCase.status === "pending") pending += 1;
  }

  const completed = passed + failed;
  const passRate = completed === 0 ? 0 : Math.round((passed / completed) * 100);

  return { total, passed, failed, running, pending, automated, passRate };
}

function computePlanSummary(runs: TestRun[]): PlanSummary {
  const totalRuns = runs.length;
  const totalCases = runs.reduce((sum, run) => sum + run.run_case_count, 0);
  const pendingRuns = runs.filter((run) => run.status === "pending").length;
  const runningRuns = runs.filter((run) => run.status === "running").length;
  const passedRuns = runs.filter((run) => run.status === "passed").length;
  const failedRuns = runs.filter((run) => run.status === "failed").length;
  const averagePassRate =
    totalRuns === 0 ? 0 : Math.round(runs.reduce((sum, run) => sum + run.pass_rate, 0) / totalRuns);

  return {
    totalRuns,
    totalCases,
    pendingRuns,
    runningRuns,
    passedRuns,
    failedRuns,
    averagePassRate,
  };
}

function planTone(status: TestPlan["status"]) {
  switch (status) {
    case "active":
      return "green";
    case "archived":
      return "slate";
    default:
      return "blue";
  }
}

export default function ProjectTestRunsWorkspace({
  projectId,
  projectTree,
}: ProjectTestRunsWorkspaceProps) {
  const [plans, setPlans] = useState<TestPlan[]>([]);
  const [runs, setRuns] = useState<TestRun[]>([]);
  const [runCases, setRunCases] = useState<TestRunCase[]>([]);
  const [selectedPlanId, setSelectedPlanId] = useState<string | null>(null);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [isLoadingPlans, setIsLoadingPlans] = useState(true);
  const [isLoadingRuns, setIsLoadingRuns] = useState(true);
  const [isLoadingCases, setIsLoadingCases] = useState(false);
  const [mutatingRunCaseId, setMutatingRunCaseId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [autoRefreshToken, setAutoRefreshToken] = useState(0);
  const [showCreatePlan, setShowCreatePlan] = useState(false);
  const [showCreateRun, setShowCreateRun] = useState(false);
  const [showExpandRun, setShowExpandRun] = useState(false);

  const suiteOptions = useMemo(() => buildSuiteOptions(projectTree), [projectTree]);
  const sectionOptions = useMemo(() => buildSectionOptions(projectTree), [projectTree]);

  const loadPlans = useCallback(async () => {
    setIsLoadingPlans(true);
    try {
      const page = await getTestPlans(projectId);
      setPlans(page.results);
      setSelectedPlanId((current) => {
        if (current && page.results.some((plan) => plan.id === current)) return current;
        return page.results[0]?.id ?? null;
      });
    } catch {
      setError("Could not load test plans.");
    } finally {
      setIsLoadingPlans(false);
    }
  }, [projectId]);

  const loadRuns = useCallback(async () => {
    if (!selectedPlanId) {
      setRuns([]);
      setSelectedRunId(null);
      setIsLoadingRuns(false);
      return;
    }

    setIsLoadingRuns(true);
    setError(null);

    try {
      const page = await getTestRuns({
        project: projectId,
        plan: selectedPlanId,
      });
      setRuns(page.results);
      setSelectedRunId((current) =>
        current && page.results.some((run) => run.id === current) ? current : null,
      );
    } catch {
      setError("Could not load test runs.");
    } finally {
      setIsLoadingRuns(false);
    }
  }, [projectId, selectedPlanId]);

  const loadRunCases = useCallback(async () => {
    if (!selectedRunId) {
      setRunCases([]);
      return;
    }

    setIsLoadingCases(true);
    try {
      setRunCases(await getRunCases(selectedRunId));
    } catch {
      setError("Could not load run cases.");
    } finally {
      setIsLoadingCases(false);
    }
  }, [selectedRunId]);

  useEffect(() => {
    void loadPlans();
  }, [loadPlans]);

  useEffect(() => {
    void loadRuns();
  }, [loadRuns]);

  useEffect(() => {
    void loadRunCases();
  }, [autoRefreshToken, loadRunCases]);

  const hasLiveCase = useMemo(
    () => runCases.some((runCase) => isExecutionLive(runCase.latest_execution)),
    [runCases],
  );

  useEffect(() => {
    if (!hasLiveCase) return undefined;
    const interval = globalThis.setInterval(() => {
      setAutoRefreshToken((token) => token + 1);
    }, 4000);
    return () => globalThis.clearInterval(interval);
  }, [hasLiveCase]);

  async function mutateRun(action: () => Promise<TestRun>) {
    setError(null);
    try {
      const updated = await action();
      setRuns((current) => current.map((run) => (run.id === updated.id ? updated : run)));
    } catch {
      setError("Could not update this run.");
    }
  }

  async function handleRunCaseStatus(runCase: TestRunCase, status: TestRunCaseStatus) {
    setRunCases((current) =>
      current.map((item) => (item.id === runCase.id ? { ...item, status } : item)),
    );
    try {
      const updated = await updateRunCaseStatus(runCase.id, status);
      setRunCases((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      void loadRuns();
    } catch {
      setError("Could not update this run case.");
      void loadRunCases();
    }
  }

  async function handleExecute(runCase: TestRunCase) {
    setMutatingRunCaseId(runCase.id);
    setError(null);
    try {
      const updated = await executeRunCase(runCase.id);
      setRunCases((current) =>
        current.map((item) => (item.id === updated.id ? updated : item)),
      );
      void loadRuns();
    } catch {
      setError("Could not queue this execution.");
    } finally {
      setMutatingRunCaseId(null);
    }
  }

  const selectedPlan = plans.find((plan) => plan.id === selectedPlanId) ?? null;
  const selectedRun = runs.find((run) => run.id === selectedRunId) ?? null;
  const runSummary = useMemo(() => computeRunSummary(runCases), [runCases]);
  const planSummary = useMemo(() => computePlanSummary(runs), [runs]);
  const canCreateRun = suiteOptions.length > 0 || sectionOptions.length > 0;

  return (
    <>
      <div className="flex h-full overflow-hidden bg-slate-50">
        <aside className="flex w-[300px] shrink-0 flex-col border-r border-slate-200 bg-white">
          <div className="flex items-start justify-between gap-3 border-b border-slate-100 p-4">
            <div>
              <h3 className="text-sm font-semibold text-slate-900">Test plans</h3>
              <p className="text-xs text-slate-500">Group runs by release, area, or cycle</p>
            </div>
            <Button size="sm" onClick={() => setShowCreatePlan(true)}>
              New plan
            </Button>
          </div>

          <div className="flex-1 overflow-y-auto">
            {isLoadingPlans && (
              <div className="flex justify-center py-8">
                <Spinner size="md" />
              </div>
            )}

            {!isLoadingPlans && plans.length === 0 && (
              <div className="px-4 py-8">
                <EmptyState
                  title="No test plans yet"
                  description="Create a plan to group meaningful runs instead of mixing them with ad-hoc automation history."
                />
                <div className="mt-4">
                  <Button size="sm" onClick={() => setShowCreatePlan(true)}>
                    Create first plan
                  </Button>
                </div>
              </div>
            )}

            {!isLoadingPlans &&
              plans.map((plan) => (
                <button
                  key={plan.id}
                  type="button"
                  onClick={() => {
                    setSelectedPlanId(plan.id);
                    setSelectedRunId(null);
                  }}
                  className={[
                    "block w-full border-b border-slate-100 px-4 py-4 text-left transition",
                    selectedPlanId === plan.id ? "bg-slate-100" : "hover:bg-slate-50",
                  ].join(" ")}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-semibold text-slate-900">{plan.name}</p>
                      <p className="mt-1 line-clamp-2 text-xs text-slate-500">
                        {plan.description || "No description yet."}
                      </p>
                    </div>
                    <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">
                      {plan.run_count}
                    </span>
                  </div>
                  <div className="mt-2 flex items-center gap-2">
                    <Badge label={formatLabel(plan.status)} color={planTone(plan.status)} />
                    <span className="text-xs text-slate-400">{formatDateTime(plan.created_at)}</span>
                  </div>
                </button>
              ))}
          </div>
        </aside>

        <section className="flex w-[380px] shrink-0 flex-col border-r border-slate-200 bg-white">
          <div className="flex items-start justify-between gap-3 border-b border-slate-100 p-4">
            <div>
              <h3 className="text-sm font-semibold text-slate-900">
                {selectedPlan ? selectedPlan.name : "Runs"}
              </h3>
              <p className="text-xs text-slate-500">
                {selectedPlan
                  ? `${runs.length} run${runs.length === 1 ? "" : "s"} in this plan`
                  : "Select a plan to review its runs"}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Button size="sm" variant="secondary" onClick={() => void loadRuns()}>
                Refresh
              </Button>
              <Button
                size="sm"
                onClick={() => setShowCreateRun(true)}
                disabled={!selectedPlan || !canCreateRun}
              >
                Add run
              </Button>
            </div>
          </div>

          <div className="flex-1 overflow-y-auto">
            {!selectedPlan && (
              <div className="px-4 py-8">
                <EmptyState
                  title="Select a plan"
                  description="Plans keep run scope clean and make progress easier to read than a flat execution log."
                />
              </div>
            )}

            {selectedPlan && isLoadingRuns && (
              <div className="flex justify-center py-8">
                <Spinner size="md" />
              </div>
            )}

            {selectedPlan && !isLoadingRuns && runs.length === 0 && (
              <div className="px-4 py-8">
                <EmptyState
                  title="No runs in this plan"
                  description="Add a run and scope it to a suite or section to start executing approved cases."
                />
                <div className="mt-4">
                  <Button onClick={() => setShowCreateRun(true)} disabled={!canCreateRun}>
                    Add first run
                  </Button>
                </div>
              </div>
            )}

            {selectedPlan &&
              !isLoadingRuns &&
              runs.map((run) => (
                <button
                  key={run.id}
                  type="button"
                  onClick={() => setSelectedRunId(run.id)}
                  className={[
                    "block w-full border-b border-slate-100 px-4 py-4 text-left transition",
                    selectedRunId === run.id ? "bg-slate-100" : "hover:bg-slate-50",
                  ].join(" ")}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-semibold text-slate-900">{run.name}</p>
                      <p className="mt-1 text-xs text-slate-500">
                        {run.run_case_count} cases / {run.pass_rate}% pass /{" "}
                        {formatDateTime(run.started_at || run.created_at)}
                      </p>
                    </div>
                    <Badge
                      label={formatLabel(run.status)}
                      color={executionStatusTone(run.status)}
                      dot
                    />
                  </div>
                </button>
              ))}
          </div>
        </section>

        <main className="flex min-w-0 flex-1 flex-col overflow-hidden bg-slate-50">
          {error && (
            <div className="shrink-0 p-4">
              <ErrorMessage message={error} onDismiss={() => setError(null)} />
            </div>
          )}

          {!selectedPlan && (
            <div className="flex flex-1 items-center justify-center px-6">
              <div className="max-w-xl text-center">
                <h2 className="text-xl font-semibold text-slate-900">Plans first</h2>
                <p className="mt-2 text-sm text-slate-500">
                  Use test plans to group runs around a release or validation cycle. One-off
                  automation history stays more useful in the Automation tab.
                </p>
                <div className="mt-5 flex justify-center">
                  <Button onClick={() => setShowCreatePlan(true)}>Create test plan</Button>
                </div>
              </div>
            </div>
          )}

          {selectedPlan && !selectedRun && (
            <PlanOverviewPanel
              plan={selectedPlan}
              summary={planSummary}
              runs={runs}
              canCreateRun={canCreateRun}
              onCreateRun={() => setShowCreateRun(true)}
            />
          )}

          {selectedPlan && selectedRun && (
            <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
              <div className="shrink-0 border-b border-slate-200 bg-white px-6 py-4">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge
                        label={formatLabel(selectedRun.status)}
                        color={executionStatusTone(selectedRun.status)}
                        dot
                      />
                      <span className="text-xs text-slate-500">
                        {selectedPlan.name} / {formatLabel(selectedRun.trigger_type)}
                      </span>
                    </div>
                    <h2 className="mt-1 truncate text-lg font-semibold text-slate-900">
                      {selectedRun.name}
                    </h2>
                    <p className="mt-0.5 text-xs text-slate-500">
                      Created {formatDateTime(selectedRun.created_at)}
                      {selectedRun.created_by_name ? ` by ${selectedRun.created_by_name}` : ""}
                    </p>
                  </div>

                  <div className="flex flex-wrap items-center gap-2">
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={() => setShowExpandRun(true)}
                      disabled={!canCreateRun}
                    >
                      Add approved cases
                    </Button>
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={() => void mutateRun(() => startTestRun(selectedRun.id))}
                      disabled={selectedRun.status !== "pending" || runCases.length === 0}
                    >
                      Start run
                    </Button>
                    <Button
                      size="sm"
                      onClick={() => void mutateRun(() => closeTestRun(selectedRun.id))}
                      disabled={
                        runCases.length === 0 ||
                        selectedRun.status === "passed" ||
                        selectedRun.status === "failed" ||
                        selectedRun.status === "cancelled"
                      }
                    >
                      Close run
                    </Button>
                  </div>
                </div>

                <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-6">
                  <StatCard label="Cases" value={runSummary.total.toString()} />
                  <StatCard label="Automated" value={`${runSummary.automated}/${runSummary.total}`} />
                  <StatCard label="Passed" value={runSummary.passed.toString()} tone="passed" />
                  <StatCard
                    label="Failed"
                    value={runSummary.failed.toString()}
                    tone={runSummary.failed > 0 ? "failed" : undefined}
                  />
                  <StatCard label="Pending" value={runSummary.pending.toString()} />
                  <StatCard label="Pass rate" value={`${runSummary.passRate}%`} />
                </div>
              </div>

              <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
                <div className="flex shrink-0 items-center justify-between border-b border-slate-200 bg-white px-6 py-3">
                  <div>
                    <h3 className="text-sm font-semibold text-slate-900">Run cases</h3>
                    <p className="text-xs text-slate-500">
                      Update manual cases here and trigger automated ones only when needed.
                    </p>
                  </div>
                  <Button size="sm" variant="secondary" onClick={() => void loadRunCases()}>
                    Refresh
                  </Button>
                </div>

                <div className="flex-1 overflow-y-auto">
                  {isLoadingCases && runCases.length === 0 && (
                    <div className="flex justify-center py-10">
                      <Spinner size="md" />
                    </div>
                  )}

                  {!isLoadingCases && runCases.length === 0 && (
                    <div className="px-6 py-10">
                      <EmptyState
                        title="No run cases yet"
                        description="Add approved cases from a suite or section to make this run ready for execution."
                      />
                      <div className="mt-4">
                        <Button onClick={() => setShowExpandRun(true)} disabled={!canCreateRun}>
                          Add approved cases
                        </Button>
                      </div>
                    </div>
                  )}

                  {runCases.length > 0 && (
                    <ul className="divide-y divide-slate-200">
                      {runCases.map((runCase) => (
                        <RunCaseRow
                          key={runCase.id}
                          runCase={runCase}
                          projectId={projectId}
                          isMutating={mutatingRunCaseId === runCase.id}
                          onManualStatusChange={(status) => void handleRunCaseStatus(runCase, status)}
                          onExecute={() => void handleExecute(runCase)}
                        />
                      ))}
                    </ul>
                  )}
                </div>
              </div>
            </div>
          )}
        </main>
      </div>

      <CreateTestPlanModal
        open={showCreatePlan}
        projectId={projectId}
        onClose={() => setShowCreatePlan(false)}
        onCreated={(plan) => {
          setPlans((current) => [plan, ...current]);
          setSelectedPlanId(plan.id);
          setSelectedRunId(null);
          setShowCreatePlan(false);
        }}
      />

      {selectedPlan && (
        <CreateTestRunModal
          open={showCreateRun}
          projectId={projectId}
          planId={selectedPlan.id}
          planName={selectedPlan.name}
          suiteOptions={suiteOptions}
          sectionOptions={sectionOptions}
          onClose={() => setShowCreateRun(false)}
          onCreated={(run) => {
            setShowCreateRun(false);
            void loadRuns().then(() => {
              setSelectedRunId(run.id);
              void loadPlans();
            });
          }}
        />
      )}

      <ExpandRunScopeModal
        open={showExpandRun}
        runId={selectedRun?.id ?? null}
        runName={selectedRun?.name ?? ""}
        suiteOptions={suiteOptions}
        sectionOptions={sectionOptions}
        onClose={() => setShowExpandRun(false)}
        onExpanded={() => {
          setShowExpandRun(false);
          void loadRuns();
          void loadRunCases();
        }}
      />
    </>
  );
}

function PlanOverviewPanel({
  plan,
  summary,
  runs,
  canCreateRun,
  onCreateRun,
}: {
  plan: TestPlan;
  summary: PlanSummary;
  runs: TestRun[];
  canCreateRun: boolean;
  onCreateRun: () => void;
}) {
  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
      <div className="shrink-0 border-b border-slate-200 bg-white px-6 py-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <Badge label={formatLabel(plan.status)} color={planTone(plan.status)} />
              <span className="text-xs text-slate-500">
                Created {formatDateTime(plan.created_at)}
                {plan.created_by_name ? ` by ${plan.created_by_name}` : ""}
              </span>
            </div>
            <h2 className="mt-1 truncate text-lg font-semibold text-slate-900">{plan.name}</h2>
            <p className="mt-2 max-w-3xl text-sm text-slate-600">
              {plan.description || "No description yet. Use this plan to organize a focused execution cycle."}
            </p>
          </div>

          <Button onClick={onCreateRun} disabled={!canCreateRun}>
            Add run
          </Button>
        </div>

        <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-6">
          <StatCard label="Runs" value={summary.totalRuns.toString()} />
          <StatCard label="Cases in plan" value={summary.totalCases.toString()} />
          <StatCard label="Pending" value={summary.pendingRuns.toString()} />
          <StatCard label="Running" value={summary.runningRuns.toString()} />
          <StatCard label="Passed" value={summary.passedRuns.toString()} tone="passed" />
          <StatCard
            label="Failed"
            value={summary.failedRuns.toString()}
            tone={summary.failedRuns > 0 ? "failed" : undefined}
          />
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-6">
        {runs.length === 0 ? (
          <div className="max-w-xl">
            <EmptyState
              title="Start this plan with a scoped run"
              description="Create a run and seed it from a suite or section. Approved cases only are added, so the run starts with executable coverage."
            />
          </div>
        ) : (
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-slate-900">Recent runs</h3>
              <p className="text-xs text-slate-500">Average pass rate {summary.averagePassRate}%</p>
            </div>
            <div className="grid gap-3">
              {runs.slice(0, 5).map((run) => (
                <div
                  key={run.id}
                  className="rounded-lg border border-slate-200 bg-white px-4 py-3"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-semibold text-slate-900">{run.name}</p>
                      <p className="mt-1 text-xs text-slate-500">
                        {run.run_case_count} cases / {run.pass_rate}% pass /{" "}
                        {formatDateTime(run.started_at || run.created_at)}
                      </p>
                    </div>
                    <Badge
                      label={formatLabel(run.status)}
                      color={executionStatusTone(run.status)}
                      dot
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function StatCard({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: "passed" | "failed";
}) {
  let valueClass = "text-slate-900";
  if (tone === "passed") valueClass = "text-green-600";
  else if (tone === "failed") valueClass = "text-red-600";

  return (
    <div className="rounded-md border border-slate-200 bg-white px-4 py-3">
      <p className="text-[11px] font-medium uppercase tracking-wide text-slate-500">{label}</p>
      <p className={`mt-1 text-2xl font-semibold ${valueClass}`}>{value}</p>
    </div>
  );
}

interface RunCaseRowProps {
  runCase: TestRunCase;
  projectId: string;
  isMutating: boolean;
  onManualStatusChange: (status: TestRunCaseStatus) => void;
  onExecute: () => void;
}

function RunCaseRow({
  runCase,
  projectId,
  isMutating,
  onManualStatusChange,
  onExecute,
}: RunCaseRowProps) {
  const execution = runCase.latest_execution;
  const isAutomated = runCase.test_case_automation_status === "automated";
  const isLive = isExecutionLive(execution);
  const result = execution?.result ?? null;
  const canOpenLive = Boolean(isLive && execution?.has_browser_session);

  return (
    <li className="flex flex-wrap items-start gap-4 bg-white px-6 py-4">
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-medium text-slate-400">#{runCase.order_index + 1}</span>
          <Badge label={formatLabel(runCase.status)} color={resultTone(runCase.status)} dot />
          {isAutomated ? (
            <span className="rounded-full bg-blue-50 px-2 py-0.5 text-[11px] font-medium text-blue-700">
              Automated
            </span>
          ) : (
            <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-600">
              Manual
            </span>
          )}
          {runCase.attempt_count > 0 && (
            <span className="text-[11px] text-slate-400">
              {runCase.attempt_count} attempt{runCase.attempt_count === 1 ? "" : "s"}
            </span>
          )}
        </div>

        <p className="mt-2 truncate text-sm font-semibold text-slate-900">{runCase.test_case_title}</p>
        <p className="text-xs text-slate-500">
          Revision v{runCase.revision_version}
          {runCase.assigned_to_name ? ` / Assigned to ${runCase.assigned_to_name}` : ""}
        </p>

        {execution && (
          <div className="mt-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs">
              <div className="flex items-center gap-1.5">
                <span className="text-slate-500">Latest</span>
                <Badge
                  label={formatLabel(execution.status)}
                  color={executionStatusTone(execution.status)}
                  dot
                />
              </div>
              <span className="text-slate-500">
                {formatDateTime(execution.started_at ?? execution.ended_at)}
              </span>
              <span className="text-slate-500">
                Attempt {execution.attempt_number} / {execution.browser}
              </span>
              {result && (
                <>
                  <span className="text-slate-500">
                    Steps{" "}
                    <span className="font-semibold text-slate-800">
                      {result.passed_steps}/{result.total_steps}
                    </span>
                  </span>
                  <span className="text-slate-500">
                    Duration{" "}
                    <span className="font-semibold text-slate-800">
                      {formatDuration(result.duration_ms)}
                    </span>
                  </span>
                </>
              )}
              {execution.triggered_by_name && (
                <span className="text-slate-500">By {execution.triggered_by_name}</span>
              )}
            </div>

            {result?.error_message && (
              <p className="mt-2 rounded-md bg-red-50 px-2 py-1 text-xs text-red-700">
                {result.error_message}
              </p>
            )}
          </div>
        )}
      </div>

      <div className="flex shrink-0 flex-col items-stretch gap-2">
        {isAutomated && (
          <Button size="sm" onClick={onExecute} disabled={isMutating || isLive}>
            {isLive ? "Running..." : execution ? "Run again" : "Run"}
          </Button>
        )}

        {canOpenLive && execution && (
          <Link
            to={`/projects/${projectId}/automation/executions/${execution.id}/live`}
            className="inline-flex items-center justify-center rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-900 transition hover:bg-slate-50"
          >
            Live view
          </Link>
        )}

        {!isAutomated && (
          <select
            value={runCase.status}
            onChange={(event) => onManualStatusChange(event.target.value as TestRunCaseStatus)}
            className="w-[160px] rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-sm outline-none focus:border-slate-900 focus:ring-1 focus:ring-slate-900"
            disabled={isMutating}
          >
            {MANUAL_STATUSES.map((status) => (
              <option key={status} value={status}>
                {formatLabel(status)}
              </option>
            ))}
          </select>
        )}
      </div>
    </li>
  );
}
