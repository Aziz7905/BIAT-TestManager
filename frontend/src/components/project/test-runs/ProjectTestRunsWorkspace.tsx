import { useCallback, useEffect, useState } from "react";
import {
  closeTestRun,
  getRunCases,
  getTestPlans,
  getTestRuns,
  startTestRun,
  updateRunCaseStatus,
} from "../../../api/runs";
import type { TestPlan, TestRun, TestRunCase, TestRunCaseStatus } from "../../../types/runs";
import { Badge, Button, EmptyState, ErrorMessage, Spinner } from "../../ui";
import {
  executionStatusTone,
  formatDateTime,
  formatLabel,
  resultTone,
} from "../repository/shared";

const RUN_CASE_STATUSES: TestRunCaseStatus[] = [
  "pending",
  "running",
  "passed",
  "failed",
  "skipped",
  "error",
  "cancelled",
];

interface ProjectTestRunsWorkspaceProps {
  projectId: string;
}

export default function ProjectTestRunsWorkspace({ projectId }: ProjectTestRunsWorkspaceProps) {
  const [plans, setPlans] = useState<TestPlan[]>([]);
  const [runs, setRuns] = useState<TestRun[]>([]);
  const [runCases, setRunCases] = useState<TestRunCase[]>([]);
  const [selectedPlanId, setSelectedPlanId] = useState<string | null>(null);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [isLoadingPlans, setIsLoadingPlans] = useState(true);
  const [isLoadingRuns, setIsLoadingRuns] = useState(true);
  const [isLoadingCases, setIsLoadingCases] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadPlans = useCallback(async () => {
    setIsLoadingPlans(true);
    try {
      const page = await getTestPlans(projectId);
      setPlans(page.results);
    } catch {
      setError("Could not load test plans.");
    } finally {
      setIsLoadingPlans(false);
    }
  }, [projectId]);

  const loadRuns = useCallback(async () => {
    setIsLoadingRuns(true);
    setError(null);
    try {
      const page = await getTestRuns({
        project: projectId,
        plan: selectedPlanId ?? undefined,
      });
      setRuns(page.results);
      setSelectedRunId((current) => {
        if (current && page.results.some((run) => run.id === current)) return current;
        return page.results[0]?.id ?? null;
      });
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
  }, [loadRunCases]);

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
      current.map((item) => (item.id === runCase.id ? { ...item, status } : item))
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

  const selectedRun = runs.find((run) => run.id === selectedRunId) ?? null;

  return (
    <div className="flex h-full overflow-hidden bg-white">
      <aside className="flex w-[320px] shrink-0 flex-col border-r border-slate-200 bg-white">
        <div className="border-b border-slate-100 p-4">
          <h3 className="text-sm font-semibold text-slate-900">Test Runs</h3>
          <p className="text-xs text-slate-500">Plans and manual execution results</p>
        </div>
        <div className="flex-1 overflow-y-auto">
          <PlanRow
            active={selectedPlanId === null}
            name="All runs"
            subtitle="Across this project"
            count={runs.length}
            onClick={() => {
              setSelectedPlanId(null);
              setSelectedRunId(null);
            }}
          />
          {isLoadingPlans && (
            <div className="flex justify-center py-8">
              <Spinner size="md" />
            </div>
          )}
          {!isLoadingPlans &&
            plans.map((plan) => (
              <PlanRow
                key={plan.id}
                active={selectedPlanId === plan.id}
                name={plan.name}
                subtitle={formatLabel(plan.status)}
                count={plan.run_count}
                onClick={() => {
                  setSelectedPlanId(plan.id);
                  setSelectedRunId(null);
                }}
              />
            ))}
        </div>
      </aside>

      <section className="flex w-[360px] shrink-0 flex-col border-r border-slate-200">
        <div className="flex items-center justify-between gap-3 border-b border-slate-100 p-4">
          <div>
            <h3 className="text-sm font-semibold text-slate-900">Runs</h3>
            <p className="text-xs text-slate-500">{runs.length} loaded</p>
          </div>
          <Button size="sm" variant="secondary" onClick={() => void loadRuns()}>
            Refresh
          </Button>
        </div>
        <div className="flex-1 overflow-y-auto">
          {isLoadingRuns && (
            <div className="flex justify-center py-8">
              <Spinner size="md" />
            </div>
          )}
          {!isLoadingRuns && runs.length === 0 && (
            <div className="px-4 py-8">
              <EmptyState title="No runs" description="Runs will appear after a plan or ad-hoc execution is created." />
            </div>
          )}
          {!isLoadingRuns &&
            runs.map((run) => (
              <button
                key={run.id}
                type="button"
                onClick={() => setSelectedRunId(run.id)}
                className={[
                  "block w-full border-b border-slate-100 px-4 py-3 text-left transition",
                  selectedRunId === run.id ? "bg-slate-100" : "hover:bg-slate-50",
                ].join(" ")}
              >
                <div className="flex items-center justify-between gap-3">
                  <span className="truncate text-sm font-semibold text-slate-900">{run.name}</span>
                  <Badge label={formatLabel(run.status)} color={executionStatusTone(run.status)} dot />
                </div>
                <div className="mt-1 flex items-center gap-2 text-xs text-slate-500">
                  <span>{run.run_case_count} cases</span>
                  <span>{run.pass_rate}% pass</span>
                </div>
              </button>
            ))}
        </div>
      </section>

      <main className="flex-1 overflow-y-auto">
        {error && (
          <div className="p-4">
            <ErrorMessage message={error} onDismiss={() => setError(null)} />
          </div>
        )}

        {!selectedRun && (
          <div className="flex h-full items-center justify-center px-6">
            <EmptyState title="Select a run" description="Choose a run to review and update its test cases." />
          </div>
        )}

        {selectedRun && (
          <div>
            <div className="border-b border-slate-200 px-6 py-5">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <Badge label={formatLabel(selectedRun.status)} color={executionStatusTone(selectedRun.status)} dot />
                  <h2 className="mt-2 text-xl font-semibold text-slate-900">{selectedRun.name}</h2>
                  <p className="mt-1 text-sm text-slate-500">
                    {selectedRun.plan_name ?? "Ad-hoc run"} · {formatDateTime(selectedRun.created_at)}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => void mutateRun(() => startTestRun(selectedRun.id))}
                    disabled={selectedRun.status !== "pending"}
                  >
                    Start
                  </Button>
                  <Button
                    size="sm"
                    variant="primary"
                    onClick={() => void mutateRun(() => closeTestRun(selectedRun.id))}
                    disabled={selectedRun.status === "passed" || selectedRun.status === "failed"}
                  >
                    Close
                  </Button>
                </div>
              </div>
            </div>

            <div className="p-6">
              <h3 className="mb-3 text-sm font-semibold text-slate-900">Run cases</h3>
              {isLoadingCases && (
                <div className="flex justify-center py-8">
                  <Spinner size="md" />
                </div>
              )}
              {!isLoadingCases && runCases.length === 0 && (
                <EmptyState title="No run cases" description="Expand this run from a suite, section, or case list to add coverage." />
              )}
              {!isLoadingCases && runCases.length > 0 && (
                <div className="overflow-hidden rounded-md border border-slate-200">
                  {runCases.map((runCase) => (
                    <div
                      key={runCase.id}
                      className="grid grid-cols-[minmax(0,1fr)_160px_170px] items-center gap-4 border-b border-slate-100 px-4 py-3 last:border-b-0"
                    >
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium text-slate-900">
                          {runCase.test_case_title}
                        </p>
                        <p className="text-xs text-slate-500">Revision v{runCase.revision_version}</p>
                      </div>
                      <Badge label={formatLabel(runCase.status)} color={resultTone(runCase.status)} dot />
                      <select
                        value={runCase.status}
                        onChange={(event) =>
                          void handleRunCaseStatus(
                            runCase,
                            event.target.value as TestRunCaseStatus
                          )
                        }
                        className="rounded-md border border-slate-300 px-2 py-1.5 text-sm outline-none focus:border-slate-900 focus:ring-1 focus:ring-slate-900"
                      >
                        {RUN_CASE_STATUSES.map((status) => (
                          <option key={status} value={status}>
                            {formatLabel(status)}
                          </option>
                        ))}
                      </select>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

function PlanRow({
  active,
  name,
  subtitle,
  count,
  onClick,
}: {
  active: boolean;
  name: string;
  subtitle: string;
  count: number;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={[
        "block w-full border-b border-slate-100 px-4 py-3 text-left transition",
        active ? "bg-slate-100" : "hover:bg-slate-50",
      ].join(" ")}
    >
      <div className="flex items-center justify-between gap-3">
        <span className="truncate text-sm font-semibold text-slate-900">{name}</span>
        <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">
          {count}
        </span>
      </div>
      <p className="mt-1 text-xs text-slate-500">{subtitle}</p>
    </button>
  );
}
