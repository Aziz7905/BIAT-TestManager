import { Badge } from "../ui";
import type { ExecutionStep, TestExecution } from "../../types/automation";

interface ExecutionDetailPanelProps {
  execution: TestExecution | null;
  steps: ExecutionStep[];
  stdoutLog?: string;
  stderrLog?: string;
  latestScreenshotUrl?: string | null;
  isLoading?: boolean;
  isLive?: boolean;
}

function formatDate(value: string | null | undefined): string {
  if (!value) {
    return "-";
  }

  return new Intl.DateTimeFormat("en-GB", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function getExecutionBadgeVariant(status: TestExecution["status"]) {
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

function getStepBadgeVariant(status: ExecutionStep["status"]) {
  if (status === "passed") {
    return "verified";
  }

  if (status === "failed") {
    return "warm";
  }

  if (status === "running") {
    return "automated";
  }

  return "tag";
}

export function ExecutionDetailPanel({
  execution,
  steps,
  stdoutLog = "",
  stderrLog = "",
  latestScreenshotUrl = null,
  isLoading = false,
  isLive = false,
}: Readonly<ExecutionDetailPanelProps>) {
  // Temporary "live execution" panel for v1. This is intentionally built around
  // polled status/step data so we can later swap it for websocket or true live
  // browser streaming without redesigning the surrounding workspace.
  if (!execution) {
    return (
      <div className="rounded-2xl border border-dashed border-border bg-surface p-4 text-sm text-muted">
        Select an execution from the history to inspect its live progress, result summary, and step timeline.
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-border bg-surface p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant={getExecutionBadgeVariant(execution.status)}>
              {execution.status}
            </Badge>
            <Badge variant="tag">
              {execution.browser} / {execution.platform}
            </Badge>
            <Badge variant="tag">
              {execution.trigger_type.replaceAll("_", " ")}
            </Badge>
            {isLive ? <Badge variant="automated">Live refresh</Badge> : null}
          </div>
          <p className="mt-2 text-sm font-semibold text-text">
            Started {formatDate(execution.started_at)}
          </p>
          <p className="mt-1 text-xs text-muted">
            Finished {formatDate(execution.ended_at)} • {execution.duration_ms ?? 0} ms
          </p>
        </div>
        <div className="text-right">
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted">
            Execution ID
          </p>
          <p className="mt-2 break-all font-mono text-xs text-muted">{execution.id}</p>
        </div>
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
        <div className="mt-4 rounded-2xl border border-warm/20 bg-warm/10 p-3 text-sm leading-6 text-warm">
          {execution.result.error_message}
        </div>
      ) : null}

      {execution.result?.stack_trace ? (
        <div className="mt-4 rounded-2xl border border-border bg-bg p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted">
            Stack trace
          </p>
          <pre className="mt-3 overflow-x-auto whitespace-pre-wrap text-xs leading-6 text-text">
            {execution.result.stack_trace}
          </pre>
        </div>
      ) : null}

      <div className="mt-4 rounded-2xl border border-border bg-bg p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted">
            Step timeline
          </p>
          {isLoading ? (
            <span className="text-xs font-semibold text-muted">Refreshing…</span>
          ) : null}
        </div>

        {steps.length === 0 ? (
          <p className="mt-3 text-sm leading-6 text-muted">
            No execution steps are available for this run yet.
          </p>
        ) : (
          <div className="mt-3 space-y-3">
            {steps.map((step) => (
              <div
                key={step.id}
                className="rounded-2xl border border-border bg-surface p-3"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant={getStepBadgeVariant(step.status)}>
                    {step.status}
                  </Badge>
                  <span className="text-xs font-semibold text-muted">
                    Step {step.step_index + 1}
                  </span>
                </div>
                <p className="mt-2 text-sm font-semibold text-text">{step.action}</p>
                {step.target_element ? (
                  <p className="mt-1 text-xs leading-6 text-muted">{step.target_element}</p>
                ) : null}
                {step.error_message ? (
                  <p className="mt-2 text-sm leading-6 text-warm">{step.error_message}</p>
                ) : null}
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1.15fr)_minmax(280px,360px)]">
        <div className="rounded-2xl border border-border bg-bg p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted">
            Live logs
          </p>
          <div className="mt-3 grid gap-3 lg:grid-cols-2">
            <div className="rounded-2xl border border-border bg-surface p-3">
              <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted">
                stdout
              </p>
              <pre className="mt-3 max-h-64 overflow-auto whitespace-pre-wrap text-xs leading-6 text-text">
                {stdoutLog || "No stdout output yet."}
              </pre>
            </div>
            <div className="rounded-2xl border border-border bg-surface p-3">
              <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted">
                stderr
              </p>
              <pre className="mt-3 max-h-64 overflow-auto whitespace-pre-wrap text-xs leading-6 text-text">
                {stderrLog || "No stderr output yet."}
              </pre>
            </div>
          </div>
        </div>

        <div className="rounded-2xl border border-border bg-bg p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted">
            Latest screenshot
          </p>
          {latestScreenshotUrl ? (
            <img
              src={latestScreenshotUrl}
              alt="Latest execution screenshot"
              className="mt-3 w-full rounded-2xl border border-border bg-surface object-cover"
            />
          ) : (
            <p className="mt-3 text-sm leading-6 text-muted">
              No live screenshot is available for this run yet.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
