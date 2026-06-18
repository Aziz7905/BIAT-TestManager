import type { AutomationStatus, DesignStatus } from "./testing";

export type SpecificationSourceType =
  | "manual"
  | "plain_text"
  | "csv"
  | "xlsx"
  | "pdf"
  | "docx"
  | "jira_issue"
  | "file_upload";

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

export type StructuralType = "table" | "key_value_block" | "list" | "text_block" | "unknown";
export type RegionRecordType = "requirement" | "test_case" | "test_data" | "context" | "ignore";

export interface SpecRecordReview {
  needs_mapping: boolean;
  confirmed: boolean;
  record_type: RegionRecordType | null;
  column_mapping: Record<string, string>;
}

export interface SpecRecordCellRef {
  coordinate: string;
  column: number;
  column_letter: string;
  header_candidate: string;
  raw_value: string;
  displayed_value: string;
}

export interface SpecGridCell {
  coordinate?: string;
  row?: number | null;
  column: number;
  column_letter: string;
  raw_value: string;
  displayed_value: string;
}

export interface SpecRecordStructure {
  region_id: string;
  container: string;
  structural_type: StructuralType;
  source_range: string;
  header_candidates: { row: number; values: string[] }[];
  row?: {
    row_number: number;
    source_range: string;
    cells: SpecRecordCellRef[];
  };
  grid?: SpecGridCell[][];
}

export interface SpecRecordMetadata {
  source_mode?: string;
  structure?: SpecRecordStructure;
  review?: SpecRecordReview;
  validation?: { fatal_errors?: string[]; warnings?: string[] };
  [key: string]: unknown;
}

export interface SpecificationSourceRecord {
  id: string;
  record_index: number;
  external_reference: string;
  section_label: string;
  row_number: number | null;
  title: string;
  content: string;
  record_metadata: SpecRecordMetadata;
  is_selected: boolean;
  import_status: SpecificationSourceRecordStatus;
  error_message: string;
  linked_specification_id: string | null;
  linked_specification_title: string | null;
  created_at: string;
  updated_at: string;
}

export interface ApplyRegionMappingPayload {
  region_id: string;
  record_type: RegionRecordType;
  column_mapping: Record<string, string>;
}

// A structural region grouped from a source's records, used by the mapping UI.
export interface SpecRegionMappingTarget {
  region_id: string;
  container: string;
  source_range: string;
  structural_type: StructuralType;
  columns: string[];
  record_type: RegionRecordType | null;
  column_mapping: Record<string, string>;
}

// Canonical mapping targets the user chooses from (fixed target schema).
export const BIAT_MAPPING_FIELDS: { value: string; label: string }[] = [
  { value: "", label: "Keep as extra field" },
  { value: "external_id", label: "External ID" },
  { value: "title", label: "Title" },
  { value: "description", label: "Description" },
  { value: "acceptance_criteria", label: "Acceptance criteria" },
  { value: "preconditions", label: "Preconditions" },
  { value: "steps", label: "Steps" },
  { value: "expected_result", label: "Expected result" },
  { value: "priority", label: "Priority" },
  { value: "module", label: "Module" },
  { value: "section", label: "Section" },
];

export const REGION_RECORD_TYPE_OPTIONS: { value: RegionRecordType; label: string }[] = [
  { value: "requirement", label: "Requirements" },
  { value: "test_case", label: "Test cases" },
  { value: "context", label: "Generic context" },
  { value: "test_data", label: "Test data" },
  { value: "ignore", label: "Ignore" },
];

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
  source_type?: SpecificationSourceType;
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
