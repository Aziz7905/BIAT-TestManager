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

export type SpecChunkType =
  | "functional_requirement"
  | "acceptance_criteria"
  | "user_story"
  | "other";

export interface SpecChunk {
  id: string;
  chunk_index: number;
  chunk_type: SpecChunkType;
  component_tag: string;
  content: string;
  embedding_vector: number[];
  token_count: number;
  created_at: string;
}

export interface QTestPreview {
  module: string;
  requirement_id: string;
  summary: string;
  description: string;
  section: string;
  preconditions: string;
  expected_result: string;
}

export interface Specification {
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
  uploaded_by: number | null;
  uploaded_by_name: string | null;
  chunk_count: number;
  can_manage: boolean;
  qtest_preview: QTestPreview;
  chunks: SpecChunk[];
  created_at: string;
  updated_at: string;
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

export interface SpecificationSource {
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

export interface SpecificationSourceDetail extends SpecificationSource {
  raw_text: string;
  records: SpecificationSourceRecord[];
}

export interface SpecificationCreatePayload {
  project: string;
  title: string;
  content: string;
  source_type?: SpecificationSourceType;
  jira_issue_key?: string | null;
  source_url?: string | null;
  version?: string;
}

export interface SpecificationUpdatePayload {
  project?: string;
  title?: string;
  content?: string;
  source_type?: SpecificationSourceType;
  jira_issue_key?: string | null;
  source_url?: string | null;
  version?: string;
}

export interface SpecificationSourceCreatePayload {
  project: string;
  name?: string;
  source_type: SpecificationSourceType;
  file?: File | null;
  raw_text?: string;
  source_url?: string | null;
  jira_issue_key?: string | null;
  auto_parse?: boolean;
}

export interface SpecificationSourceUpdatePayload {
  name?: string;
  raw_text?: string;
  source_url?: string | null;
  jira_issue_key?: string | null;
}

export interface SpecificationSourceRecordUpdatePayload {
  title?: string;
  content?: string;
  is_selected?: boolean;
  external_reference?: string;
  section_label?: string;
}

export interface SpecificationSourceImportResponse {
  imported_count: number;
  specifications: Specification[];
}
