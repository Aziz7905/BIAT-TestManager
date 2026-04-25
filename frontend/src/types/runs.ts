export type TestPlanStatus = "draft" | "active" | "archived";
export type TestRunTriggerType = "manual" | "ci_cd" | "scheduled" | "webhook";
export type TestRunStatus = "pending" | "running" | "passed" | "failed" | "cancelled";
export type TestRunCaseStatus =
  | "pending"
  | "running"
  | "passed"
  | "failed"
  | "skipped"
  | "error"
  | "cancelled";

export interface TestPlan {
  id: string;
  project: string;
  project_name: string;
  name: string;
  description: string;
  status: TestPlanStatus;
  run_count: number;
  created_by: number | null;
  created_by_name: string | null;
  created_at: string;
  updated_at: string;
}

export interface CreateTestPlanPayload {
  project: string;
  name: string;
  description?: string;
}

export interface TestRun {
  id: string;
  project: string;
  project_name: string;
  plan: string | null;
  plan_name: string | null;
  name: string;
  status: TestRunStatus;
  trigger_type: TestRunTriggerType;
  run_case_count: number;
  passed_case_count: number;
  pass_rate: number;
  created_by: number | null;
  created_by_name: string | null;
  created_at: string;
  started_at: string | null;
  ended_at: string | null;
}

export interface CreateTestRunPayload {
  project: string;
  plan?: string | null;
  name: string;
  trigger_type?: TestRunTriggerType;
}

export interface RunScopeOption {
  id: string;
  label: string;
  caseCount: number;
}

export type TestCaseAutomationStatus = "manual" | "automated" | "in_progress";

export type RunCaseExecutionStatus =
  | "queued"
  | "running"
  | "paused"
  | "passed"
  | "failed"
  | "error"
  | "cancelled";

export interface RunCaseExecutionResult {
  status: string;
  duration_ms: number;
  total_steps: number;
  passed_steps: number;
  failed_steps: number;
  error_message: string;
}

export interface RunCaseLatestExecution {
  id: string;
  status: RunCaseExecutionStatus;
  browser: string;
  attempt_number: number;
  started_at: string | null;
  ended_at: string | null;
  duration_ms: number | null;
  triggered_by_name: string | null;
  has_browser_session: boolean;
  result: RunCaseExecutionResult | null;
}

export interface TestRunCase {
  id: string;
  run: string;
  run_name: string;
  test_case: string;
  test_case_title: string;
  test_case_automation_status: TestCaseAutomationStatus | null;
  test_case_revision: string;
  revision_version: number;
  assigned_to: number | null;
  assigned_to_name: string | null;
  status: TestRunCaseStatus;
  order_index: number;
  attempt_count: number;
  latest_execution: RunCaseLatestExecution | null;
  created_at: string;
  updated_at: string;
}

export interface ExpandRunPayload {
  suite_id?: string;
  section_id?: string;
  case_ids?: string[];
}
