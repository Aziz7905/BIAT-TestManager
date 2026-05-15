import type {
  BusinessPriority,
  Priority,
  ScenarioPolarity,
  ScenarioType,
} from "./testing";
import type { ExecutionBrowser, ExecutionPlatform } from "./automation";

export type AIGenerationStatus =
  | "queued"
  | "generating"
  | "ready_for_review"
  | "reviewing"
  | "saved"
  | "failed"
  | "cancelled";

export type AIGenerationSourceType = "prompt" | "specification" | "jira" | "manual" | "mixed";

export interface AIGenerationStepDraft {
  step_index: number;
  action: string;
  expected_outcome: string;
}

export interface AIGenerationCaseDraft {
  draft_id: string;
  title: string;
  preconditions: string;
  steps: AIGenerationStepDraft[];
  expected_result: string;
  test_data: Record<string, unknown>;
  linked_spec_ids: string[];
  possible_duplicates?: unknown[];
  order_index?: number;
  jira_issue_key?: string;
  selected?: boolean;
}

export interface AIGenerationScenarioDraft {
  draft_id: string;
  title: string;
  description: string;
  scenario_type: ScenarioType;
  priority: Priority;
  business_priority: BusinessPriority | null;
  polarity: ScenarioPolarity;
  confidence: number | null;
  possible_duplicates?: unknown[];
  order_index?: number;
  cases: AIGenerationCaseDraft[];
}

export interface AIGenerationSectionDraft {
  draft_id: string;
  name: string;
  order_index?: number;
  scenarios: AIGenerationScenarioDraft[];
  children: AIGenerationSectionDraft[];
}

export interface AIGenerationDraftPayload {
  schema_version?: string;
  summary: string;
  assumptions: string[];
  open_questions: string[];
  coverage_summary?: Record<string, unknown>;
  possible_duplicates?: unknown[];
  suite: {
    draft_id: string;
    name: string;
    description: string;
  };
  sections: AIGenerationSectionDraft[];
}

export interface AIGenerationRetrievedContext {
  id: string;
  context_type: string;
  object_id: string;
  external_ref: string;
  score: number | null;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface AIGenerationSession {
  id: string;
  team: string;
  project: string;
  created_by: number | null;
  created_by_name: string | null;
  target_suite: string | null;
  target_section: string | null;
  attached_specification: string | null;
  status: AIGenerationStatus;
  source_type: AIGenerationSourceType;
  objective: string;
  source_refs: Record<string, unknown>;
  jira_issue_key: string;
  provider_name: string;
  model_name: string;
  purpose: string;
  prompt_version: string;
  schema_version: string;
  draft_payload: Partial<AIGenerationDraftPayload>;
  critic_report: Record<string, unknown>;
  review_decisions: Record<string, unknown>;
  saved_object_ids: Record<string, unknown>;
  input_tokens: number;
  output_tokens: number;
  duration_ms: number | null;
  error_message: string;
  mlflow_run_id: string;
  trace_id: string;
  retrieved_contexts: AIGenerationRetrievedContext[];
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface StartAIGenerationPayload {
  project: string;
  objective: string;
  source_type?: AIGenerationSourceType;
  target_suite?: string | null;
  target_section?: string | null;
  attached_specification?: string | null;
  source_refs?: Record<string, unknown>;
  jira_issue_key?: string;
}

export interface ReviewAIGenerationPayload {
  review_decisions: {
    draft_payload: AIGenerationDraftPayload;
    selected_case_ids: string[];
    dropped_case_ids?: string[];
  };
}

export interface CommitAIGenerationResponse {
  session: AIGenerationSession;
  created: {
    suite_ids: string[];
    section_ids: string[];
    scenario_ids: string[];
    case_ids: string[];
    revision_ids: string[];
    created_case_count: number;
  };
}

export interface StartAIAuthoringSessionPayload {
  test_case: string;
  target_url: string;
  max_steps?: number;
  temperature?: number;
  max_tokens_per_step?: number;
  browser?: ExecutionBrowser;
  platform?: ExecutionPlatform;
}

export interface SaveAIAuthoringTraceResponse {
  test_case_id: string;
  revision_id: string | null;
  version: number;
  step_count: number;
  steps: Array<{
    step: string;
    outcome: string;
  }>;
}
