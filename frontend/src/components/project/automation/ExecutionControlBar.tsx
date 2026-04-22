import Button from "../../ui/Button";
import type { TestExecution } from "../../../types/automation";

interface ExecutionControlBarProps {
  execution: TestExecution | null;
  isBusy: boolean;
  onPause: () => void;
  onResume: () => void;
  onStop: () => void;
}

export default function ExecutionControlBar({
  execution,
  isBusy,
  onPause,
  onResume,
  onStop,
}: ExecutionControlBarProps) {
  const status = execution?.status;
  const canPause = status === "running";
  const canResume = status === "paused";
  const canStop = status === "queued" || status === "running" || status === "paused";

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Button size="sm" variant="secondary" onClick={onPause} disabled={!canPause || isBusy}>
        Pause
      </Button>
      <Button size="sm" variant="secondary" onClick={onResume} disabled={!canResume || isBusy}>
        Resume
      </Button>
      <Button size="sm" variant="danger" onClick={onStop} disabled={!canStop || isBusy}>
        Stop
      </Button>
    </div>
  );
}
