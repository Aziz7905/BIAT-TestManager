/** Strongly typed frontend contracts for the BIAT Test Manager automation layer. */
export type AutomationFramework = "playwright" | "selenium";

export type AutomationLanguage =
  | "python"
  | "javascript"
  | "typescript"
  | "java";

export type AutomationScriptGeneratedBy = "ai" | "user";

export type ExecutionTriggerType =
  | "manual"
  | "ci_cd"
  | "scheduled"
  | "webhook"
  | "nightly";

export type ExecutionStatus =
  | "queued"
  | "running"
  | "paused"
  | "passed"
  | "failed"
  | "error"
  | "cancelled";

export type ExecutionBrowser =
  | "chromium"
  | "firefox"
  | "webkit"
  | "chrome"
  | "edge";

export type ExecutionPlatform = "desktop" | "mobile";

export type ExecutionStepStatus = "pending" | "running" | "passed" | "failed";

export type TestResultStatus = "passed" | "failed" | "skipped" | "error";

export interface ScriptValidationResult {
  is_valid: boolean;
  errors: string[];
  warnings: string[];
}

export interface AutomationScript {
  id: string;
  test_case: string;
  test_case_title: string;
  scenario_id: string;
  suite_id: string;
  project_id: string;
  framework: AutomationFramework;
  language: AutomationLanguage;
  script_content: string;
  script_version: number;
  generated_by: AutomationScriptGeneratedBy;
  is_active: boolean;
  validation?: ScriptValidationResult;
  history_versions?: number[];
  diff_with_previous?: string;
  created_at: string;
}

export interface ExecutionStep {
  id: string;
  execution: string;
  step_index: number;
  action: string;
  target_element: string;
  selector_used: string | null;
  input_value: string | null;
  screenshot_url: string | null;
  status: ExecutionStepStatus;
  error_message: string | null;
  stack_trace: string | null;
  duration_ms: number | null;
  executed_at: string | null;
}

export interface TestResult {
  id: string;
  execution: string;
  status: TestResultStatus;
  duration_ms: number;
  total_steps: number;
  passed_steps: number;
  failed_steps: number;
  error_message: string | null;
  stack_trace: string | null;
  junit_xml: string | null;
  video_url: string | null;
  artifacts_path: string | null;
  artifacts: {
    video_url: string | null;
    artifacts_path: string | null;
    stdout_log_url: string | null;
    stderr_log_url: string | null;
    latest_screenshot_url: string | null;
  };
  ai_failure_analysis: string | null;
  issues_count: number;
  created_at: string;
}

export interface TestExecution {
  id: string;
  test_case: string;
  test_case_title: string;
  scenario_id: string;
  suite_id: string;
  project_id: string;
  script: string | null;
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
  agent_run: string | null;
  result: TestResult | null;
}

export interface AutomationScriptWritePayload {
  test_case: string;
  framework: AutomationFramework;
  language: AutomationLanguage;
  script_content: string;
  generated_by?: AutomationScriptGeneratedBy;
  is_active?: boolean;
}

export interface TestExecutionCreatePayload {
  test_case: string;
  script?: string | null;
  trigger_type?: ExecutionTriggerType;
  browser?: ExecutionBrowser;
  platform?: ExecutionPlatform;
}
