import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  getExecution,
  pauseExecution,
  resumeCheckpoint,
  resumeExecution,
  stopExecution,
} from "../api/automation/executions";
import CheckpointModal from "../components/project/automation/CheckpointModal";
import ExecutionControlBar from "../components/project/automation/ExecutionControlBar";
import NoVncViewer from "../components/project/automation/NoVncViewer";
import {
  executionStatusTone,
  formatLabel,
  resultTone,
} from "../components/project/repository/shared";
import { Badge, Button, EmptyState, ErrorMessage, Spinner } from "../components/ui";
import { useExecutionStore } from "../store/executionStore";
import type { ExecutionStep, TestExecution } from "../types/automation";

interface StepStatusDotProps {
  readonly status: string;
}

function StepStatusDot({ status }: StepStatusDotProps) {
  if (status === "passed") return <div className="mt-1 h-2 w-2 shrink-0 rounded-full bg-green-500" />;
  if (status === "failed") return <div className="mt-1 h-2 w-2 shrink-0 rounded-full bg-red-500" />;
  if (status === "running") return <div className="mt-1 h-2 w-2 shrink-0 animate-pulse rounded-full bg-blue-400" />;
  return <div className="mt-1 h-2 w-2 shrink-0 rounded-full border border-slate-400" />;
}

function LiveStepItem({ step }: { readonly step: ExecutionStep }) {
  return (
    <div className="border-b border-slate-100 px-5 py-4 last:border-b-0">
      <div className="flex items-start gap-3">
        <StepStatusDot status={step.status} />
        <div className="min-w-0">
          <p className="text-sm font-semibold leading-snug text-slate-900">
            {step.step_index + 1}. {step.action}
          </p>
          {step.target_element && (
            <p className="mt-1 truncate text-xs text-slate-400">{step.target_element}</p>
          )}
          {step.error_message && (
            <p className="mt-2 rounded-md bg-red-50 px-2.5 py-2 text-xs text-red-700">
              {step.error_message}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

function BrowserEndedView() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-2 bg-slate-950 text-slate-500">
      <p className="text-sm">Browser session ended</p>
      <p className="text-xs text-slate-600">Live stream is only available while the execution is running.</p>
    </div>
  );
}

export default function AutomationLivePage() {
  const { id: projectId, executionId } = useParams<{ id: string; executionId: string }>();
  const navigate = useNavigate();
  const [loadedExecution, setLoadedExecution] = useState<TestExecution | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isMutating, setIsMutating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [checkpointOpen, setCheckpointOpen] = useState(false);

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

  useEffect(() => {
    if (!executionId) return undefined;

    let cancelled = false;
    setIsLoading(true);
    setError(null);

    getExecution(executionId)
      .then((nextExecution) => {
        if (cancelled) return;
        setLoadedExecution(nextExecution);
      })
      .catch(() => {
        if (!cancelled) setError("Could not load this execution.");
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });

    void connect(executionId);
    return () => {
      cancelled = true;
      disconnect();
    };
  }, [connect, disconnect, executionId]);

  useEffect(() => {
    if (selectedCheckpoint) {
      setCheckpointOpen(true);
    }
  }, [selectedCheckpoint]);

  const visibleExecution = useMemo(() => {
    if (!execution || execution.id !== executionId) return loadedExecution;
    if (!loadedExecution) return execution;
    return {
      ...loadedExecution,
      ...execution,
      has_browser_session: execution.has_browser_session || loadedExecution.has_browser_session,
    };
  }, [execution, executionId, loadedExecution]);

  const isLive =
    visibleExecution?.status === "running" || visibleExecution?.status === "paused";
  const showBrowser =
    Boolean(visibleExecution?.has_browser_session) && Boolean(isLive);

  const runControl = useCallback(
    async (action: () => Promise<TestExecution>) => {
      setIsMutating(true);
      setError(null);
      try {
        const updated = await action();
        setLoadedExecution(updated);
        setExecution(updated);
      } catch {
        setError("Execution control action failed.");
      } finally {
        setIsMutating(false);
      }
    },
    [setExecution],
  );

  if (isLoading && !visibleExecution) {
    return (
      <div className="flex h-screen items-center justify-center bg-slate-950">
        <Spinner size="lg" />
      </div>
    );
  }

  if (!visibleExecution) {
    return (
      <div className="flex h-screen items-center justify-center bg-slate-50 px-6">
        <EmptyState title="Execution not found" description="This live session is no longer available." />
      </div>
    );
  }

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-white">
      <header className="flex shrink-0 items-center justify-between gap-4 border-b border-slate-200 bg-white px-5 py-3">
        <div className="flex min-w-0 items-center gap-4">
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={() => navigate(`/projects/${projectId}?tab=automation`)}
          >
            Back
          </Button>
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
              {isConnecting && <span className="text-xs text-slate-400">/ Connecting stream...</span>}
              {streamError && <span className="text-xs text-red-500">/ {streamError}</span>}
            </div>
            <h1 className="mt-0.5 truncate text-base font-semibold text-slate-950">
              {visibleExecution.test_case_title}
            </h1>
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-2">
          <Link
            to={`/projects/${projectId}?tab=automation`}
            className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-900 transition hover:bg-slate-50"
          >
            Automation
          </Link>
          <ExecutionControlBar
            execution={visibleExecution}
            isBusy={isMutating}
            onPause={() => void runControl(() => pauseExecution(visibleExecution.id))}
            onResume={() => void runControl(() => resumeExecution(visibleExecution.id))}
            onStop={() => void runControl(() => stopExecution(visibleExecution.id))}
          />
        </div>
      </header>

      {error && (
        <div className="shrink-0 border-b border-slate-200 bg-white px-5 py-2">
          <ErrorMessage message={error} onDismiss={() => setError(null)} />
        </div>
      )}

      <main className="flex min-h-0 flex-1 overflow-hidden">
        <aside className="flex w-[360px] shrink-0 flex-col border-r border-slate-200 bg-slate-50">
          <div className="shrink-0 border-b border-slate-200 px-5 py-3">
            <p className="text-[11px] font-semibold uppercase text-slate-400">
              Live steps / {steps.length}
            </p>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto">
            {steps.length === 0 ? (
              <div className="flex h-full items-center justify-center px-6">
                <p className="text-center text-sm text-slate-400">Steps appear when the runner starts.</p>
              </div>
            ) : (
              steps.map((step) => <LiveStepItem key={step.id} step={step} />)
            )}
          </div>
          <div className="shrink-0 border-t border-slate-200 bg-white px-5 py-3">
            {result ? (
              <div className="grid grid-cols-3 gap-3 text-xs">
                <div>
                  <div className="text-slate-400">Status</div>
                  <Badge label={formatLabel(result.status)} color={resultTone(result.status)} dot />
                </div>
                <div>
                  <div className="text-slate-400">Steps</div>
                  <div className="font-semibold text-slate-900">
                    {result.passed_steps}/{result.total_steps}
                  </div>
                </div>
                <div>
                  <div className="text-slate-400">Artifacts</div>
                  <div className="font-semibold text-slate-900">{artifacts.length}</div>
                </div>
              </div>
            ) : (
              <p className="text-xs text-slate-400">Result appears after completion.</p>
            )}
          </div>
        </aside>

        <section className="min-w-0 flex-1 overflow-hidden bg-slate-950">
          {showBrowser ? (
            <NoVncViewer executionId={visibleExecution.id} enabled />
          ) : visibleExecution.has_browser_session ? (
            <BrowserEndedView />
          ) : (
            <NoVncViewer executionId={visibleExecution.id} enabled={false} />
          )}
        </section>
      </main>

      <CheckpointModal
        checkpoint={selectedCheckpoint}
        open={checkpointOpen && Boolean(selectedCheckpoint)}
        onClose={() => setCheckpointOpen(false)}
        onResume={async (payload) => {
          if (!selectedCheckpoint) return;
          await resumeCheckpoint(visibleExecution.id, selectedCheckpoint.id, payload);
        }}
      />
    </div>
  );
}
