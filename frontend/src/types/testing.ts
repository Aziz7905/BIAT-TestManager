export type DesignStatus = "draft" | "in_review" | "approved" | "archived";
export type AutomationStatus = "manual" | "automated" | "in_progress";
export type OnFailureBehavior = "fail_and_stop" | "fail_but_continue";
export type ScenarioType =
  | "happy_path"
  | "alternative_flow"
  | "edge_case"
  | "security"
  | "performance"
  | "accessibility";
export type Priority = "low" | "medium" | "high" | "critical";
export type ScenarioPolarity = "positive" | "negative";
export type BusinessPriority = "must_have" | "should_have" | "could_have" | "wont_have";

export interface LinkedSpec {
  id: string;
  title: string;
  external_reference: string | null;
  source_type: string;
}

export interface RepositoryContext {
  project_id: string;
  project_name: string;
  suite_id?: string | null;
  suite_name?: string | null;
  section_id?: string | null;
  section_name?: string | null;
  scenario_id?: string | null;
  scenario_title?: string | null;
  parent_id?: string | null;
  parent_name?: string | null;
}

export interface RepositoryRecentActivity {
  last_execution_at: string | null;
  recent_execution_count: number;
  recent_pass_rate: number;
}

export interface RepositorySummary {
  suite_count?: number;
  section_count?: number;
  child_section_count?: number;
  scenario_count?: number;
  case_count?: number;
  approved_case_count?: number;
  automated_case_count?: number;
  draft_case_count?: number;
  in_review_case_count?: number;
  archived_case_count?: number;
  manual_case_count?: number;
}

export interface RepositoryNodeCounts {
  section_count?: number;
  child_section_count?: number;
  scenario_count?: number;
  case_count?: number;
  approved_case_count?: number;
  automated_case_count?: number;
}

export interface TreeCase {
  id: string;
  title: string;
  design_status: DesignStatus;
  automation_status: AutomationStatus;
  version: number;
  order_index: number;
  latest_result_status: string | null;
  has_active_script: boolean;
}

export interface TreeScenario {
  id: string;
  title: string;
  scenario_type: ScenarioType;
  priority: Priority;
  order_index: number;
  case_count: number;
  approved_case_count: number;
  automated_case_count: number;
}

export interface TreeSection {
  id: string;
  name: string;
  parent_id: string | null;
  order_index: number;
  counts: RepositoryNodeCounts;
  children: TreeSection[];
  scenarios: TreeScenario[];
}

export interface TreeSuite {
  id: string;
  name: string;
  folder_path: string;
  counts: RepositoryNodeCounts;
  sections: TreeSection[];
}

export interface ProjectTree {
  project_id: string;
  project_name: string;
  summary: RepositorySummary;
  suites: TreeSuite[];
}

export interface RepositorySuiteCard {
  id: string;
  name: string;
  folder_path: string;
  counts: RepositoryNodeCounts;
}

export interface RepositorySectionCard {
  id: string;
  name: string;
  counts: RepositoryNodeCounts;
}

export interface RepositoryScenarioCard {
  id: string;
  title: string;
  priority: Priority;
  scenario_type?: ScenarioType;
  counts: RepositoryNodeCounts;
}

export interface RecentRunCard {
  id: string;
  name: string;
  status: string;
  trigger_type: string;
  plan_name: string | null;
  created_by_name: string | null;
  created_at: string | null;
  started_at: string | null;
  ended_at: string | null;
  run_case_count: number;
  passed_case_count: number;
  failed_case_count: number;
  pass_rate: number;
}

export interface ProjectRepositoryOverview {
  project: {
    id: string;
    name: string;
    team_name: string;
    organization_name: string;
  };
  summary: RepositorySummary;
  recent_activity: RepositoryRecentActivity;
  top_suites: RepositorySuiteCard[];
  recent_runs: RecentRunCard[];
}

export interface SuiteOverview {
  id: string;
  name: string;
  description: string;
  folder_path: string;
  context: RepositoryContext;
  specification: LinkedSpec | null;
  created_by_name: string | null;
  created_at: string;
  counts: RepositorySummary;
  recent_activity: RepositoryRecentActivity;
  linked_specifications: LinkedSpec[];
  sections: RepositorySectionCard[];
}

export interface SectionOverview {
  id: string;
  name: string;
  context: RepositoryContext;
  counts: RepositorySummary;
  recent_activity: RepositoryRecentActivity;
  linked_specifications: LinkedSpec[];
  child_sections: RepositorySectionCard[];
  scenarios: RepositoryScenarioCard[];
}

export interface ScenarioOverview {
  id: string;
  title: string;
  description: string;
  scenario_type: ScenarioType;
  priority: Priority;
  business_priority: BusinessPriority | null;
  polarity: ScenarioPolarity;
  context: RepositoryContext;
  coverage: RepositorySummary;
  execution_snapshot: RepositoryRecentActivity;
  linked_specifications: LinkedSpec[];
  cases: TreeCase[];
}

export interface VersionHistoryItem {
  id: string;
  version_number: number;
  created_by: number | null;
  created_by_name: string | null;
  created_at: string;
}

export interface RecentResultItem {
  execution_id: string;
  status: string;
  created_at: string;
  duration_ms: number;
}

export interface TestCaseStep {
  step: string;
  outcome: string;
}

export interface LatestExecutionSnapshot {
  id: string;
  status: string;
  started_at: string | null;
  ended_at: string | null;
  duration_ms: number | null;
  browser: string;
  platform: string;
  framework: string | null;
  artifact_count: number;
}

export interface CaseWorkspace {
  id: string;
  title: string;
  context: RepositoryContext;
  design: {
    preconditions: string;
    steps: TestCaseStep[];
    expected_result: string;
    test_data: Record<string, unknown>;
    design_status: DesignStatus;
    automation_status: AutomationStatus;
    jira_issue_key: string | null;
    on_failure: OnFailureBehavior;
    timeout_ms: number;
    version: number;
    current_revision_id: string | null;
    linked_specifications: LinkedSpec[];
    created_at: string;
    updated_at: string;
  };
  automation: {
    has_active_script: boolean;
    active_script_count: number;
    runnable_frameworks: string[];
    latest_execution: LatestExecutionSnapshot | null;
    artifact_count: number;
    last_artifact_at: string | null;
  };
  history: {
    version_history: VersionHistoryItem[];
    recent_results: RecentResultItem[];
  };
}

export interface CreateSuitePayload {
  project: string;
  name: string;
  description?: string;
  folder_path?: string;
  specification?: string | null;
  ai_generated?: boolean;
}

export interface CreateSectionPayload {
  name: string;
  parent?: string | null;
  order_index?: number;
}

export interface CreateScenarioPayload {
  title: string;
  description?: string;
  scenario_type: ScenarioType;
  priority: Priority;
  business_priority?: BusinessPriority | null;
  polarity: ScenarioPolarity;
  ai_generated?: boolean;
  ai_confidence?: number | null;
  order_index?: number;
}

export interface CreateCasePayload {
  title: string;
  preconditions?: string;
  steps?: TestCaseStep[];
  expected_result: string;
  test_data?: Record<string, unknown>;
  design_status?: DesignStatus;
  status?: DesignStatus;
  automation_status: AutomationStatus;
  ai_generated?: boolean;
  jira_issue_key?: string | null;
  on_failure: OnFailureBehavior;
  timeout_ms?: number;
  order_index?: number;
  linked_specification_ids?: string[];
}
