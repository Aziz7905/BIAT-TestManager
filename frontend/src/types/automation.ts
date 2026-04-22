// Enums

export type ExecutionStatus =
  | "queued"
  | "running"
  | "paused"
  | "passed"
  | "failed"
  | "error"
  | "cancelled";

export type ExecutionBrowser = "chromium" | "firefox" | "webkit" | "chrome" | "edge";
export type ExecutionPlatform = "desktop" | "mobile";
export type ExecutionTriggerType =
  | "manual"
  | "ci_cd"
  | "scheduled"
  | "webhook"
  | "nightly"
  | "diagnostic";
export type ExecutionStepStatus = "pending" | "running" | "passed" | "failed";
export type CheckpointStatus = "pending" | "resolved" | "cancelled" | "expired";
export type ScriptGeneratedBy = "user" | "ai";

// Automation Script

export interface AutomationScript {
  id: string;
  test_case: string;
  test_case_title: string;
  scenario_id: string;
  suite_id: string;
  project_id: string;
  test_case_revision: string | null;
  framework: string;
  language: string;
  script_content: string;
  script_version: number;
  generated_by: ScriptGeneratedBy;
  is_active: boolean;
  created_at: string;
}

export interface AutomationScriptDetail extends AutomationScript {
  validation: { is_valid: boolean; errors: string[] };
  history_versions: number[];
  diff_with_previous: string | null;
}

export interface CreateScriptPayload {
  test_case: string;
  test_case_revision?: string | null;
  framework: string;
  language: string;
  script_content: string;
  generated_by?: ScriptGeneratedBy;
  is_active?: boolean;
}

export type UpdateScriptPayload = Partial<CreateScriptPayload>;

// Execution Step

export interface ExecutionStep {
  id: string;
  execution: string;
  step_index: number;
  action: string;
  target_element: string | null;
  selector_used: string | null;
  input_value: string | null;
  screenshot_url: string | null;
  status: ExecutionStepStatus;
  error_message: string | null;
  stack_trace: string | null;
  duration_ms: number | null;
  executed_at: string | null;
}

// Execution Checkpoint

export interface ExecutionCheckpoint {
  id: string;
  execution: string;
  step: string | null;
  checkpoint_key: string;
  title: string;
  instructions: string;
  payload_json: Record<string, unknown>;
  status: CheckpointStatus;
  requested_at: string;
  resolved_at: string | null;
  resolved_by: number | null;
}

// Stream Ticket

export interface ExecutionStreamTicket {
  ticket: string;
  expires_in: number;
  websocket_path: string;
  browser_websocket_path: string;
  browser_view_url?: string;
  browser_view_urls?: string[];
}

// Execution Result

export interface ExecutionArtifact {
  id?: string;
  execution?: string;
  artifact_type: string;
  path?: string;
  storage_path?: string;
  metadata?: Record<string, unknown>;
  metadata_json?: Record<string, unknown>;
  created_at?: string;
}

export interface TestResult {
  id: string;
  execution: string;
  status: ExecutionStatus;
  duration_ms: number | null;
  total_steps: number;
  passed_steps: number;
  failed_steps: number;
  error_message: string | null;
  stack_trace: string | null;
  junit_xml: string | null;
  video_url: string | null;
  artifacts_path: string | null;
  artifacts: ExecutionArtifact[];
  issues_count: number;
  created_at: string;
}

// Test Execution

export interface TestExecution {
  id: string;
  test_case: string;
  test_case_title: string;
  scenario_id: string;
  suite_id: string;
  project_id: string;
  run_case: string | null;
  script: string | null;
  environment: string | null;
  attempt_number: number;
  triggered_by: number | null;
  triggered_by_name: string | null;
  trigger_type: ExecutionTriggerType;
  status: ExecutionStatus;
  browser: ExecutionBrowser;
  platform: ExecutionPlatform;
  started_at: string | null;
  ended_at: string | null;
  duration_ms: number | null;
  celery_task_id: string | null;
  pause_requested: boolean;
  has_browser_session: boolean;
  result: TestResult | null;
}

export interface CreateExecutionPayload {
  test_case: string;
  script?: string | null;
  environment?: string | null;
  trigger_type?: ExecutionTriggerType;
  browser?: ExecutionBrowser;
  platform?: ExecutionPlatform;
}

export interface StartManualBrowserPayload {
  test_case: string;
  target_url?: string;
  browser?: ExecutionBrowser;
  platform?: ExecutionPlatform;
}

// Execution Schedule

export interface ExecutionSchedule {
  id: string;
  project: string;
  project_name: string;
  suite: string | null;
  suite_name: string | null;
  name: string;
  cron_expression: string;
  timezone: string;
  browser: ExecutionBrowser;
  platform: ExecutionPlatform;
  is_active: boolean;
  next_run_at: string | null;
  created_by: number | null;
  created_by_name: string | null;
}

// WebSocket live events (execution.snapshot + streaming events)

export interface ExecutionSnapshotEvent {
  type: "execution.snapshot";
  execution_id: string;
  payload: {
    execution: TestExecution;
    steps: ExecutionStep[];
    pending_checkpoints: ExecutionCheckpoint[];
    result: TestResult | null;
    artifacts: ExecutionArtifact[];
  };
}

export interface ExecutionStatusChangedEvent {
  type: "execution.status_changed";
  execution_id: string;
  payload: TestExecution;
}

export interface ExecutionStepUpdatedEvent {
  type: "execution.step_updated";
  execution_id: string;
  payload: ExecutionStep;
}

export interface ExecutionResultReadyEvent {
  type: "execution.result_ready";
  execution_id: string;
  payload: TestResult;
}

export interface ExecutionArtifactCreatedEvent {
  type: "execution.artifact_created";
  execution_id: string;
  payload: ExecutionArtifact;
}

export interface ExecutionCheckpointEvent {
  type:
    | "execution.checkpoint_requested"
    | "execution.checkpoint_resolved"
    | "execution.checkpoint_expired";
  execution_id: string;
  payload: ExecutionCheckpoint;
}

export interface ExecutionControlAckEvent {
  type: "execution.control_ack";
  execution_id: string;
  payload: Record<string, unknown>;
}

export type ExecutionStreamEvent =
  | ExecutionSnapshotEvent
  | ExecutionStatusChangedEvent
  | ExecutionStepUpdatedEvent
  | ExecutionResultReadyEvent
  | ExecutionArtifactCreatedEvent
  | ExecutionCheckpointEvent
  | ExecutionControlAckEvent;
