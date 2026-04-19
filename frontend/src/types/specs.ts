import type { AutomationStatus, DesignStatus } from "./testing";

export type SpecificationSourceType =
  | "manual"
  | "plain_text"
  | "csv"
  | "xlsx"
  | "pdf"
  | "docx"
  | "jira_issue"
  | "file_upload"
  | "url";

export type SpecificationSourceParserStatus =
  | "uploaded"
  | "parsing"
  | "ready"
  | "failed"
  | "imported";

export type SpecificationSourceRecordStatus =
  | "pending"
  | "imported"
  | "skipped"
  | "failed";

export type SpecificationIndexStatus = "pending" | "indexed" | "failed" | "stale";
export type CoverageStatus = "covered" | "uncovered";

export interface QTestPreview {
  module: string;
  requirement_id: string;
  summary: string;
  description: string;
  section: string;
  preconditions: string;
  expected_result: string;
}

export interface SpecChunk {
  id: string;
  chunk_index: number;
  chunk_type: string;
  component_tag: string | null;
  content: string;
  embedding_model_config_id: string | null;
  embedding_model: string | null;
  embedded_at: string | null;
  token_count: number;
  created_at: string;
}

export interface LinkedTestCaseCompact {
  id: string;
  title: string;
  status: DesignStatus;
  automation_status: AutomationStatus;
  version: number;
  scenario_id: string;
  scenario_title: string;
  suite_id: string;
  suite_name: string;
}

export interface SpecificationSourceRecord {
  id: string;
  record_index: number;
  external_reference: string;
  section_label: string;
  row_number: number | null;
  title: string;
  content: string;
  record_metadata: Record<string, unknown>;
  is_selected: boolean;
  import_status: SpecificationSourceRecordStatus;
  error_message: string;
  linked_specification_id: string | null;
  linked_specification_title: string | null;
  created_at: string;
  updated_at: string;
}

export interface SpecificationSourceListItem {
  id: string;
  project: string;
  project_name: string;
  team_name: string;
  organization_name: string;
  name: string;
  source_type: SpecificationSourceType;
  file_name: string | null;
  source_url: string | null;
  jira_issue_key: string | null;
  parser_status: SpecificationSourceParserStatus;
  parser_error: string;
  source_metadata: Record<string, unknown>;
  column_mapping: Record<string, unknown>;
  record_count: number;
  selected_record_count: number;
  imported_record_count: number;
  uploaded_by_name: string | null;
  can_manage: boolean;
  created_at: string;
  updated_at: string;
}

export interface SpecificationSourceDetail extends SpecificationSourceListItem {
  raw_text: string;
  records: SpecificationSourceRecord[];
}

export interface SpecificationListItem {
  id: string;
  project: string;
  project_name: string;
  team: string;
  team_name: string;
  organization: string;
  organization_name: string;
  source_id: string | null;
  source_name: string | null;
  source_record_id: string | null;
  title: string;
  content: string;
  source_type: SpecificationSourceType;
  jira_issue_key: string | null;
  source_url: string | null;
  external_reference: string | null;
  source_metadata: Record<string, unknown>;
  version: string;
  index_status: SpecificationIndexStatus;
  index_error: string;
  indexed_at: string | null;
  uploaded_by: number | null;
  uploaded_by_name: string | null;
  chunk_count: number;
  can_manage: boolean;
  qtest_preview: QTestPreview;
  chunks: SpecChunk[];
  linked_test_case_count: number;
  linked_scenario_count: number;
  linked_suite_count: number;
  linked_test_cases: LinkedTestCaseCompact[];
  coverage_status: CoverageStatus;
  created_at: string;
  updated_at: string;
}

export type SpecificationDetail = SpecificationListItem;

export interface CreateSpecificationSourcePayload {
  project: string;
  name?: string;
  source_type: SpecificationSourceType;
  file?: File | null;
  raw_text?: string;
  source_url?: string;
  jira_issue_key?: string;
  auto_parse?: boolean;
  auto_import?: boolean;
}

export interface UpdateSpecificationSourcePayload {
  name?: string;
  raw_text?: string;
  source_url?: string;
  jira_issue_key?: string;
}

export interface UpdateSpecificationSourceRecordPayload {
  title?: string;
  content?: string;
  is_selected?: boolean;
  external_reference?: string;
  section_label?: string;
}

export interface ImportSpecificationSourceResponse {
  imported_count: number;
  specifications: SpecificationListItem[];
}

