/** Strongly typed frontend contracts for the BIAT Test Manager testing workspace. */
export type TestPriority =
  | "critical"
  | "high"
  | "medium"
  | "low";

export type BusinessPriority =
  | "must_have"
  | "should_have"
  | "could_have"
  | "wont_have";

export type TestScenarioType =
  | "happy_path"
  | "alternative_flow"
  | "edge_case"
  | "security"
  | "performance"
  | "accessibility";

export type TestScenarioPolarity = "positive" | "negative";

export type TestCaseStatus =
  | "draft"
  | "ready"
  | "running"
  | "passed"
  | "failed"
  | "skipped";

export type TestCaseAutomationStatus =
  | "manual"
  | "automated"
  | "in_progress";

export type TestCaseOnFailure =
  | "fail_and_stop"
  | "fail_but_continue";

export interface LinkedSpecificationSummary {
  id: string;
  title: string;
  external_reference: string | null;
  source_type: string;
}

export interface TestStep {
  index?: number;
  step?: string;
  outcome?: string;
  action?: string;
  expected?: string;
  [key: string]: unknown;
}

export interface TestSuite {
  id: string;
  project: string;
  project_name: string;
  specification: string | null;
  specification_title: string | null;
  name: string;
  description: string;
  folder_path: string;
  ai_generated: boolean;
  created_by: number | null;
  created_by_name: string | null;
  scenario_count: number;
  total_case_count: number;
  pass_rate: number;
  linked_specification_count: number;
  linked_specifications: LinkedSpecificationSummary[];
  created_at: string;
}

export interface TestScenario {
  id: string;
  suite_id: string;
  suite_name: string;
  project_id: string;
  specification_id: string | null;
  title: string;
  description: string;
  scenario_type: TestScenarioType;
  priority: TestPriority;
  business_priority: BusinessPriority | null;
  polarity: TestScenarioPolarity;
  ai_generated: boolean;
  ai_confidence: number | null;
  order_index: number;
  case_count: number;
  pass_rate: number;
  linked_specification_count: number;
  linked_specifications: LinkedSpecificationSummary[];
  created_at: string;
}

export interface TestCase {
  id: string;
  scenario_id: string;
  scenario_title: string;
  suite_id: string;
  suite_name: string;
  project_id: string;
  title: string;
  preconditions: string;
  steps: TestStep[];
  expected_result: string;
  test_data: Record<string, unknown>;
  status: TestCaseStatus;
  automation_status: TestCaseAutomationStatus;
  ai_generated: boolean;
  jira_issue_key: string | null;
  version: number;
  on_failure: TestCaseOnFailure;
  timeout_ms: number;
  order_index: number;
  linked_specifications: LinkedSpecificationSummary[];
  linked_specification_ids: string[];
  latest_result_status: string | null;
  gherkin_preview: string;
  version_history: number[];
  created_at: string;
  updated_at: string;
}

export interface TestSuiteCreatePayload {
  project: string;
  specification?: string | null;
  name: string;
  description?: string;
  folder_path?: string;
  ai_generated?: boolean;
}

export interface TestSuiteUpdatePayload {
  project?: string;
  specification?: string | null;
  name?: string;
  description?: string;
  folder_path?: string;
  ai_generated?: boolean;
}

export interface TestScenarioCreatePayload {
  title: string;
  description: string;
  scenario_type: TestScenarioType;
  priority: TestPriority;
  business_priority?: BusinessPriority | null;
  polarity: TestScenarioPolarity;
  ai_generated?: boolean;
  ai_confidence?: number | null;
  order_index?: number;
}

export interface TestScenarioUpdatePayload {
  title?: string;
  description?: string;
  scenario_type?: TestScenarioType;
  priority?: TestPriority;
  business_priority?: BusinessPriority | null;
  polarity?: TestScenarioPolarity;
  ai_generated?: boolean;
  ai_confidence?: number | null;
  order_index?: number;
}

export interface TestCaseWritePayload {
  title: string;
  preconditions?: string;
  steps: TestStep[];
  expected_result: string;
  test_data?: Record<string, unknown>;
  status?: TestCaseStatus;
  automation_status?: TestCaseAutomationStatus;
  ai_generated?: boolean;
  jira_issue_key?: string | null;
  on_failure?: TestCaseOnFailure;
  timeout_ms?: number;
  order_index?: number;
  linked_specification_ids?: string[];
}
