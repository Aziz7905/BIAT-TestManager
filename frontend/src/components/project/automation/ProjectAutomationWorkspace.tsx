import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  createExecution,
  deleteExecution,
  getExecutions,
  pauseExecution,
  resumeCheckpoint,
  resumeExecution,
  stopExecution,
} from "../../../api/automation/executions";
import { useExecutionStore } from "../../../store/executionStore";
import type { ExecutionStatus, ExecutionStep, TestExecution } from "../../../types/automation";
import { Badge, Button, EmptyState, ErrorMessage, Spinner } from "../../ui";
import {
  executionStatusTone,
  formatDateTime,
  formatLabel,
  resultTone,
} from "../repository/shared";
import CheckpointModal from "./CheckpointModal";
import ExecutionControlBar from "./ExecutionControlBar";
import NoVncViewer from "./NoVncViewer";

const STATUS_FILTERS: Array<ExecutionStatus | "all"> = [
  "all",
  "queued",
  "running",
  "paused",
  "passed",
  "failed",
  "error",
  "cancelled",
];

type BottomTab = "result" | "checkpoints" | "artifacts";

interface ProjectAutomationWorkspaceProps {
  readonly projectId: string;
  readonly focusExecutionId?: string | null;
}

interface StepStatusDotProps { readonly status: string; }
function StepStatusDot({ status }: StepStatusDotProps) {
  if (status === "passed") return <div className="mt-1 h-2 w-2 shrink-0 rounded-full bg-green-500" />;
  if (status === "failed") return <div className="mt-1 h-2 w-2 shrink-0 rounded-full bg-red-500" />;
  if (status === "running") return <div className="mt-1 h-2 w-2 shrink-0 animate-pulse rounded-full bg-blue-400" />;
  return <div className="mt-1 h-2 w-2 shrink-0 rounded-full border border-slate-400" />;
}

interface LiveStepItemProps { readonly step: ExecutionStep; }
function LiveStepItem({ step }: LiveStepItemProps) {
  return (
    <div className="border-b border-slate-100 px-3 py-2.5 last:border-b-0">
      <div className="flex items-start gap-2">
        <StepStatusDot status={step.status} />
        <div className="min-w-0">
          <p className="text-xs font-medium leading-tight text-slate-800">
            {step.step_index + 1}. {step.action}
          </p>
          {step.target_element && (
            <p className="mt-0.5 truncate text-[11px] text-slate-400">{step.target_element}</p>
          )}
          {step.error_message && (
            <p className="mt-1 rounded bg-red-50 px-2 py-1 text-[11px] text-red-600">
              {step.error_message}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

export default function ProjectAutomationWorkspace({
  projectId,
  focusExecutionId,
}: ProjectAutomationWorkspaceProps) {
  const [statusFilter, setStatusFilter] = useState<ExecutionStatus | "all">("all");
  const [executions, setExecutions] = useState<TestExecution[]>([]);
  const [selectedExecutionId, setSelectedExecutionId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isMutating, setIsMutating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [checkpointOpen, setCheckpointOpen] = useState(false);
  const [bottomTab, setBottomTab] = useState<BottomTab>("result");

  const {
    execution,
    steps,
    pendingCheckpoints,
    artifacts,
    result,
    isConnecting,
    streamError,
    connect,
    disconnect,
    setExecution,
  } = useExecutionStore();

  const selectedCheckpoint = pendingCheckpoints[0] ?? null;

  const loadExecutions = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const nextExecutions = await getExecutions({
        project: projectId,
        status: statusFilter === "all" ? undefined : statusFilter,
      });
      setExecutions(nextExecutions);
      setSelectedExecutionId((current) => {
        if (focusExecutionId) return focusExecutionId;
        if (current && nextExecutions.some((item) => item.id === current)) return current;
        return nextExecutions[0]?.id ?? null;
      });
    } catch {
      setError("Could not load automation executions.");
    } finally {
      setIsLoading(false);
    }
  }, [focusExecutionId, projectId, statusFilter]);

  useEffect(() => {
    void loadExecutions();
  }, [loadExecutions]);

  useEffect(() => {
    if (focusExecutionId) {
      setSelectedExecutionId(focusExecutionId);
    }
  }, [focusExecutionId]);

  useEffect(() => {
    if (!selectedExecutionId) {
      disconnect();
      return undefined;
    }
    void connect(selectedExecutionId);
    return () => disconnect();
  }, [connect, disconnect, selectedExecutionId]);

  useEffect(() => {
    if (selectedCheckpoint) {
      setCheckpointOpen(true);
      setBottomTab("checkpoints");
    }
  }, [selectedCheckpoint?.id, selectedCheckpoint]);

  async function runControl(action: () => Promise<TestExecution>) {
    setIsMutating(true);
    setError(null);
    try {
      const updated = await action();
      setExecution(updated);
      setExecutions((current) =>
        current.map((item) => (item.id === updated.id ? updated : item))
      );
    } catch {
      setError("Execution control action failed.");
    } finally {
      setIsMutating(false);
    }
  }

  async function handleDeleteExecution(executionId: string) {
    if (!globalThis.confirm("Delete this execution and its stored results?")) return;
    setIsMutating(true);
    try {
      await deleteExecution(executionId);
      await loadExecutions();
    } catch {
      setError("Failed to delete execution.");
    } finally {
      setIsMutating(false);
    }
  }

  async function handleStartExecution(testCaseId: string) {
    setIsMutating(true);
    setError(null);
    try {
      const created = await createExecution({ test_case: testCaseId });
      setExecutions((current) => [created, ...current]);
      setSelectedExecutionId(created.id);
      setExecution(created);
    } catch {
      setError("Could not start a new execution.");
    } finally {
      setIsMutating(false);
    }
  }

  const selectedFromList = useMemo(
    () => executions.find((item) => item.id === selectedExecutionId) ?? null,
    [executions, selectedExecutionId]
  );

  const visibleExecution = useMemo(() => {
    if (!execution || execution.id !== selectedExecutionId) return selectedFromList;
    if (!selectedFromList) return execution;
    return {
      ...selectedFromList,
      ...execution,
      has_browser_session:
        execution.has_browser_session || selectedFromList.has_browser_session,
    };
  }, [execution, selectedExecutionId, selectedFromList]);
  const isExecutionLive =
    visibleExecution?.status === "running" || visibleExecution?.status === "paused";

  return (
    <div className="flex h-full overflow-hidden bg-white">
      {/* Sidebar: execution list */}
      <aside className="flex w-[250px] shrink-0 flex-col border-r border-slate-200 bg-white">
        <div className="border-b border-slate-100 p-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h3 className="text-sm font-semibold text-slate-900">Executions</h3>
              <p className="text-xs text-slate-500">{executions.length} loaded</p>
            </div>
            <Button size="sm" variant="secondary" onClick={() => void loadExecutions()}>
              Refresh
            </Button>
          </div>
          <select
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value as ExecutionStatus | "all")}
            className="mt-3 w-full rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-700 outline-none focus:border-slate-900 focus:ring-1 focus:ring-slate-900"
          >
            {STATUS_FILTERS.map((status) => (
              <option key={status} value={status}>
                {status === "all" ? "All statuses" : formatLabel(status)}
              </option>
            ))}
          </select>
        </div>

        <div className="flex-1 overflow-y-auto">
          {isLoading && (
            <div className="flex justify-center py-10">
              <Spinner size="md" />
            </div>
          )}
          {!isLoading && executions.length === 0 && (
            <div className="px-4 py-8">
              <EmptyState
                title="No executions"
                description="Run an automated case to populate this list."
              />
            </div>
          )}
          {!isLoading &&
            executions.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => setSelectedExecutionId(item.id)}
                className={[
                  "block w-full border-b border-slate-100 px-4 py-3 text-left transition",
                  selectedExecutionId === item.id ? "bg-slate-100" : "hover:bg-slate-50",
                ].join(" ")}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="min-w-0 truncate text-sm font-medium text-slate-900">
                    {item.test_case_title}
                  </span>
                  <Badge
                    label={formatLabel(item.status)}
                    color={executionStatusTone(item.status)}
                    dot
                  />
                </div>
                <div className="mt-1 flex items-center gap-2 text-xs text-slate-400">
                  <span>{item.browser}</span>
                  <span>{formatDateTime(item.started_at ?? item.ended_at)}</span>
                  <button
                    type="button"
                    className="ml-auto text-slate-400 transition hover:text-red-500"
                    onClick={(e) => {
                      e.stopPropagation();
                      void handleDeleteExecution(item.id);
                    }}
                  >
                    Delete
                  </button>
                </div>
              </button>
            ))}
        </div>
      </aside>

      {/* Main: detail panel */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {error && (
          <div className="shrink-0 p-3">
            <ErrorMessage message={error} onDismiss={() => setError(null)} />
          </div>
        )}

        {!visibleExecution && (
          <div className="flex flex-1 items-center justify-center px-6">
            <EmptyState
              title="Select an execution"
              description="Choose an execution to view live steps, the browser session, and results."
            />
          </div>
        )}

        {visibleExecution && (
          <>
            {/* Compact header */}
            <div className="shrink-0 border-b border-slate-200 bg-white px-4 py-2">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge
                      label={formatLabel(visibleExecution.status)}
                      color={executionStatusTone(visibleExecution.status)}
                      dot
                    />
                    <span className="text-xs text-slate-400">
                      {visibleExecution.browser} / {visibleExecution.platform} / Attempt{" "}
                      {visibleExecution.attempt_number}
                    </span>
                    {isConnecting && (
                      <span className="text-xs text-slate-400">/ Connecting stream...</span>
                    )}
                    {streamError && (
                      <span className="text-xs text-red-500">/ {streamError}</span>
                    )}
                  </div>
                  <h2 className="mt-0.5 truncate text-base font-semibold text-slate-900">
                    {visibleExecution.test_case_title}
                  </h2>
                </div>
                <ExecutionControlBar
                  execution={visibleExecution}
                  isBusy={isMutating}
                  onPause={() => void runControl(() => pauseExecution(visibleExecution.id))}
                  onResume={() => void runControl(() => resumeExecution(visibleExecution.id))}
                  onStop={() => void runControl(() => stopExecution(visibleExecution.id))}
                />
                <Button
                  size="sm"
                  variant="primary"
                  onClick={() => void handleStartExecution(visibleExecution.test_case)}
                  disabled={isMutating || isExecutionLive}
                >
                  Start
                </Button>
                <Link
                  to={`/projects/${projectId}/automation/executions/${visibleExecution.id}/live`}
                  aria-disabled={!isExecutionLive}
                  tabIndex={isExecutionLive ? undefined : -1}
                  className={[
                    "inline-flex shrink-0 items-center justify-center rounded-lg border px-3 py-1.5 text-xs font-semibold shadow-sm transition",
                    isExecutionLive
                      ? "border-slate-300 bg-white text-slate-900 hover:bg-slate-50"
                      : "pointer-events-none border-slate-200 bg-slate-50 text-slate-400",
                  ].join(" ")}
                >
                  Full screen
                </Link>
              </div>
            </div>

            {/* Split: steps | browser */}
            <div className="flex min-h-0 flex-1 overflow-hidden">
              {/* Steps panel */}
              <div
                className={[
                  "flex shrink-0 flex-col overflow-y-auto border-r border-slate-100 bg-slate-50",
                  isExecutionLive ? "w-[240px]" : "w-[220px]",
                ].join(" ")}
              >
                <div className="border-b border-slate-100 px-3 py-2">
                  <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                    Live steps{steps.length > 0 && ` / ${steps.length}`}
                  </p>
                </div>
                {steps.length === 0 ? (
                  <div className="flex flex-1 items-center justify-center p-4">
                    <p className="text-center text-xs text-slate-400">
                      Steps appear when the runner starts.
                    </p>
                  </div>
                ) : (
                  steps.map((step) => <LiveStepItem key={step.id} step={step} />)
                )}
              </div>

              {/* Browser panel */}
              <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
                {isExecutionLive ? (
                  <NoVncViewer
                    key={visibleExecution.id}
                    executionId={visibleExecution.id}
                    enabled={visibleExecution.has_browser_session}
                  />
                ) : visibleExecution.has_browser_session ? (
                  <div className="flex flex-1 flex-col items-center justify-center gap-2 bg-slate-950 text-slate-500">
                    <p className="text-sm">Browser session ended</p>
                    <p className="text-xs text-slate-600">
                      Click Start to re-run, or pick another execution.
                    </p>
                  </div>
                ) : (
                  <div className="flex flex-1 flex-col items-center justify-center gap-2 bg-slate-950 text-slate-500">
                    <p className="text-sm">No browser session</p>
                    <p className="text-xs text-slate-600">
                      This execution did not open a browser.
                    </p>
                  </div>
                )}
              </div>
            </div>

            {/* Bottom tabs: Result | Checkpoints | Artifacts */}
            {!isExecutionLive && (
            <div className="flex h-[120px] shrink-0 flex-col border-t border-slate-200 bg-white">
              <div className="flex shrink-0 border-b border-slate-100">
                {(["result", "checkpoints", "artifacts"] as BottomTab[]).map((tab) => (
                  <button
                    key={tab}
                    type="button"
                    onClick={() => setBottomTab(tab)}
                    className={[
                      "px-4 py-2 text-xs font-medium transition",
                      bottomTab === tab
                        ? "border-b-2 border-slate-900 text-slate-900"
                        : "text-slate-500 hover:text-slate-700",
                    ].join(" ")}
                  >
                    {formatLabel(tab)}
                    {tab === "checkpoints" && pendingCheckpoints.length > 0 && (
                      <span className="ml-1.5 rounded-full bg-yellow-400 px-1.5 py-0.5 text-[10px] font-semibold text-yellow-900">
                        {pendingCheckpoints.length}
                      </span>
                    )}
                  </button>
                ))}
              </div>

              <div className="flex-1 overflow-y-auto px-4 py-3">
                {bottomTab === "result" && (
                  <>
                    {result ? (
                      <div className="flex flex-wrap gap-x-6 gap-y-2 text-sm">
                        <div className="flex items-center gap-2">
                          <span className="text-slate-400">Status</span>
                          <Badge
                            label={formatLabel(result.status)}
                            color={resultTone(result.status)}
                            dot
                          />
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="text-slate-400">Duration</span>
                          <span className="font-medium text-slate-700">
                            {result.duration_ms == null ? "-" : `${result.duration_ms} ms`}
                          </span>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="text-slate-400">Steps</span>
                          <span className="font-medium text-slate-700">
                            {result.passed_steps}/{result.total_steps} passed
                          </span>
                        </div>
                        {result.error_message && (
                          <p className="w-full rounded-md bg-red-50 px-3 py-2 text-xs text-red-700">
                            {result.error_message}
                          </p>
                        )}
                      </div>
                    ) : (
                      <p className="text-sm text-slate-400">
                        Result will appear after the execution completes.
                      </p>
                    )}
                  </>
                )}

                {bottomTab === "checkpoints" && (
                  <>
                    {pendingCheckpoints.length === 0 ? (
                      <p className="text-sm text-slate-400">No pending checkpoints.</p>
                    ) : (
                      <div className="space-y-2">
                        {pendingCheckpoints.map((checkpoint) => (
                          <button
                            key={checkpoint.id}
                            type="button"
                            onClick={() => setCheckpointOpen(true)}
                            className="block w-full rounded-md border border-yellow-200 bg-yellow-50 px-3 py-2 text-left"
                          >
                            <span className="text-sm font-medium text-yellow-900">
                              {checkpoint.title}
                            </span>
                            <span className="mt-0.5 block text-xs text-yellow-700">
                              {checkpoint.instructions}
                            </span>
                          </button>
                        ))}
                      </div>
                    )}
                  </>
                )}

                {bottomTab === "artifacts" && (
                  <>
                    {artifacts.length === 0 ? (
                      <p className="text-sm text-slate-400">No artifacts yet.</p>
                    ) : (
                      <div className="flex flex-wrap gap-2">
                        {artifacts.map((artifact, index) => (
                          <div
                            key={artifact.id ?? `${artifact.artifact_type}-${index}`}
                            className="rounded-md border border-slate-200 px-3 py-1.5 text-xs"
                          >
                            <span className="font-medium text-slate-700">
                              {formatLabel(artifact.artifact_type)}
                            </span>
                            <span className="ml-2 text-slate-400">
                              {artifact.storage_path ?? artifact.path ?? ""}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}
                  </>
                )}
              </div>
            </div>
            )}
          </>
        )}
      </div>

      <CheckpointModal
        checkpoint={selectedCheckpoint}
        open={checkpointOpen && Boolean(selectedCheckpoint)}
        onClose={() => setCheckpointOpen(false)}
        onResume={async (payload) => {
          if (!visibleExecution || !selectedCheckpoint) return;
          await resumeCheckpoint(visibleExecution.id, selectedCheckpoint.id, payload);
        }}
      />
    </div>
  );
}
