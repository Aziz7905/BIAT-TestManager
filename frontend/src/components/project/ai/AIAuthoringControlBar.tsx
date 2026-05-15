import Button from "../../ui/Button";
import type { TestExecution } from "../../../types/automation";

interface AIAuthoringControlBarProps {
  readonly execution: TestExecution | null;
  readonly isBusy: boolean;
  readonly isSavingScript?: boolean;
  readonly onPause: () => void;
  readonly onResume: () => void;
  readonly onStop: () => void;
  readonly onSaveScript?: () => void;
}

/**
 * AI-authoring-only control bar.
 *
 * Replaces the regression `ExecutionControlBar` when the execution's
 * `trigger_type === "ai_authoring"`. Same Pause/Resume/Stop backend endpoints
 * (the agent loop honors `pause_requested` and keeps the Selenoid browser
 * alive), but the labels and semantics are AI-specific: "Pause AI", "Take
 * Control", "Resume AI". When the AI is paused the user already has full
 * keyboard/mouse routed to the same browser through the noVNC frame — Take
 * Control is the same wire action as Pause; the label makes the affordance
 * legible.
 */
export default function AIAuthoringControlBar({
  execution,
  isBusy,
  isSavingScript = false,
  onPause,
  onResume,
  onStop,
  onSaveScript,
}: AIAuthoringControlBarProps) {
  const status = execution?.status;
  const isRunning = status === "running";
  const isPaused = status === "paused";
  const isPassed = status === "passed";
  const canStop =
    status === "queued" || status === "running" || status === "paused";

  return (
    <div className="flex flex-wrap items-center gap-2">
      {!isPaused && !isPassed && (
        <Button
          size="sm"
          variant="secondary"
          onClick={onPause}
          disabled={!isRunning || isBusy}
          title="Pause the AI agent. The browser stays alive so you can take control."
        >
          Pause AI
        </Button>
      )}
      {isPaused && (
        <>
          <Button
            size="sm"
            variant="secondary"
            disabled
            title="You are driving the Selenoid browser through the noVNC frame above."
          >
            You are driving
          </Button>
          <Button
            size="sm"
            variant="primary"
            onClick={onResume}
            disabled={isBusy}
            title="Resume AI. The agent will observe the current page state and continue."
          >
            Resume AI
          </Button>
        </>
      )}
      {!isPassed && (
        <Button
          size="sm"
          variant="danger"
          onClick={onStop}
          disabled={!canStop || isBusy}
        >
          Stop
        </Button>
      )}
      {isPassed && onSaveScript && (
        <Button
          size="sm"
          variant="primary"
          onClick={onSaveScript}
          isLoading={isSavingScript}
          loadingText="Saving script"
          title="Translate the trace into a Selenium Python script and save it under this test case."
        >
          Save as Selenium script
        </Button>
      )}
    </div>
  );
}
